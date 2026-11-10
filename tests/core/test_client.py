"""Conversation policy: framework trimming, exact budgets, and failed turns."""
import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import time
import threading
from pathlib import Path
import tempfile
import unittest
import httpx
from openai import OpenAI
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/marionette'))
spec = importlib.util.spec_from_file_location('client', ROOT / 'src/marionette/session.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)
import inference
import terminal
from style import COLORS


class ClientTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        environment = patch.dict(os.environ, {'MARIONETTE_DATA_DIR': directory.name})
        environment.start()
        self.addCleanup(environment.stop)

    def test_reasoning_is_white_answer_is_pink_and_only_answer_is_retained(self):
        events = [
            {'choices': [{'delta': {'reasoning_content': 'Check '}}]},
            {'choices': [{'delta': {'reasoning_content': 'the sum.', 'content': 'Four.'}, 'finish_reason': 'stop'}]},
        ]
        payload = (''.join('data: ' + json.dumps(event) + '\n\n' for event in events)
                   + 'data: [DONE]\n\n').encode()
        sent = []
        def handle(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=payload)
        sdk = OpenAI(base_url='http://127.0.0.1:1/v1', api_key='EMPTY',
                     http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        output = io.StringIO()
        api = inference.API('http://127.0.0.1:1')
        api.count = lambda messages: 10
        with patch('inference.OpenAI', return_value=sdk), patch('diagnostics.log') as logged, patch('sys.stdout', output), patch.object(output, 'isatty', return_value=True), patch.dict(os.environ, {'TERM': 'xterm'}):
            answer, finish = api.reply([{'role': 'user', 'content': 'Two plus two?'}], 1024, on_delta=terminal.ReplyDisplay())
        self.assertEqual((answer, finish), ('Four.', 'stop'))
        self.assertTrue(sent[0]['chat_template_kwargs']['enable_thinking'])
        self.assertEqual(output.getvalue(), COLORS['reasoning_heading'] + 'Reasoning:\n' + COLORS['data'] + 'Check '
                         + 'the sum.' + COLORS['answer_heading']
                         + '\n\nAnswer:\n' + COLORS['reply'] + 'Four.')
        self.assertEqual(sent[0]['messages'], [{'role': 'user', 'content': 'Two plus two?'}])
        self.assertEqual(sent[0]['max_tokens'], 1024)
        self.assertNotIn('tools', sent[0])
        logged.assert_any_call('Reasoning: "Check the sum."')

    def test_agent_preserves_usage_finish_and_rejects_partial_streams(self):
        for finish in ('stop', 'length', None):
            with self.subTest(finish=finish):
                events = [
                    {'choices': [{'delta': {'reasoning_content': 'PRIVATE', 'content': 'PUBLIC'},
                                  'finish_reason': finish}]},
                    {'choices': [], 'usage': {'prompt_tokens': 12, 'completion_tokens': 3, 'total_tokens': 15}},
                ]
                payload = ''.join('data: ' + json.dumps(e) + '\n\n' for e in events)
                payload += 'data: [DONE]\n\n'
                sdk = OpenAI(base_url='http://localhost/v1', api_key='EMPTY',
                    http_client=httpx.Client(transport=httpx.MockTransport(lambda request:
                        httpx.Response(200, headers={'content-type': 'text/event-stream'}, text=payload))))
                api = inference.API('http://localhost')
                api.count = lambda messages: 10
                with patch('inference.OpenAI', return_value=sdk), patch('diagnostics.log') as logged:
                    if finish:
                        self.assertEqual(api.reply([{'role': 'user', 'content': 'hello'}], 100), ('PUBLIC', finish))
                        self.assertIn('Reasoning: "PRIVATE"', [call.args[0] for call in logged.call_args_list])
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'completion status'):
                            api.reply([{'role': 'user', 'content': 'hello'}], 100)
                    self.assertTrue(any('"total_tokens": 15' in call.args[0] for call in logged.call_args_list))

    def test_agent_trims_and_commits_exact_sent_history_without_tools(self):
        messages = [{'role': 'user', 'content': 'old ' * 60000},
                    {'role': 'assistant', 'content': 'previous answer'},
                    {'role': 'user', 'content': 'Sender metadata: synthetic discord user. Hello'}]
        captured = []
        def handle(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200, headers={'content-type': 'text/event-stream'},
                text='data: {"choices":[{"delta":{"content":"Hi"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
        sdk = OpenAI(base_url='http://localhost/v1', api_key='EMPTY',
            http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        original = [m.copy() for m in messages]
        api = inference.API('http://localhost')
        api.count = lambda messages: 10
        with patch('inference.OpenAI', return_value=sdk), patch('diagnostics.log'):
            self.assertEqual(api.reply(messages, 32768), ('Hi', 'stop'))
        self.assertNotEqual(messages, original)
        self.assertEqual(messages[-1], original[-1])
        self.assertEqual(captured[0]['messages'], messages)
        self.assertEqual(captured[0]['seed'], -1)
        self.assertNotIn('tools', captured[0])
        self.assertNotIn('temperature', captured[0])  # Keep configured server sampling.

    def test_generation_allowance_uses_half_context_up_to_32k(self):
        for capacity, expected in ((65536, 32768), (8192, 4096)):
            class FakeAPI:
                closing = threading.Event()
                def count(self, messages):
                    return 10
                def reply(self, messages, reserve, *, on_delta=None):
                    self.reserve = reserve
                    return 'answer', 'stop'
            api = FakeAPI()
            with patch('builtins.input', side_effect=['1', 'hello', '/exit']), patch('diagnostics.log'), patch('sys.stdout', io.StringIO()):
                client.chat(api, capacity)
            self.assertEqual(api.reserve, expected)

    def test_failed_stream_not_kept_and_clear_starts_empty(self):
        class FakeAPI:
            closing = threading.Event()
            def __init__(self):
                self.sent = []
            def count(self, _):
                return 30
            def reply(self, messages, reserve, *, on_delta=None):
                self.sent.append(messages.copy())
                if len(self.sent) == 1:
                    raise RuntimeError('stream interrupted')
                return 'answer', 'stop'
        api = FakeAPI()
        with patch('builtins.input', side_effect=['1', 'failed', 'good', '/clear', 'fresh', '/exit']), patch('diagnostics.log'), patch('sys.stdout', io.StringIO()):
            client.chat(api, 8192)
        self.assertEqual([m['content'].split('\n\nMessage:\n', 1)[1] for m in api.sent[1]], ['good'])
        self.assertEqual([m['content'].split('\n\nMessage:\n', 1)[1] for m in api.sent[2]], ['fresh'])

    def test_eof_and_termination_stop_owned_server(self):
        for action in ('eof', 'terminate'):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as directory:
                output_path = Path(directory) / 'terminal.txt'
                with output_path.open('w') as output:
                    process = subprocess.Popen(
                        [sys.executable, str(ROOT / 'src/marionette/session.py'),
                         sys.executable, str(ROOT / 'tests/core/fake_server.py')],
                        stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT,
                        text=True, cwd=directory)
                    try:
                        process.stdin.write('1\n')
                        process.stdin.flush()
                        deadline = time.monotonic() + 10
                        while 'Ready.' not in output_path.read_text():
                            self.assertIsNone(process.poll(), output_path.read_text())
                            self.assertLess(time.monotonic(), deadline, 'Startup timed out')
                            time.sleep(.02)
                        children = Path(f'/proc/{process.pid}/task/{process.pid}/children').read_text().split()
                        self.assertEqual(len(children), 1)
                        pid = int(children[0])
                        if action == 'terminate':
                            process.send_signal(signal.SIGTERM)
                        process.communicate('', timeout=10)
                        self.assertEqual(process.returncode, 0, output_path.read_text())
                        self.assertFalse(list(Path(directory).glob('*setup*')))
                        with self.assertRaises(ProcessLookupError):
                            os.kill(pid, 0)
                    finally:
                        if process.poll() is None:
                            process.terminate()
                            process.communicate(timeout=10)
