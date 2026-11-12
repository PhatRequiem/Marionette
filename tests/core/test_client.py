"""Conversation policy: idle preparation, exact budgets, and failed turns."""
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
import context
import inference
import terminal
from style import COLORS


class ClientTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        datasheet = Path(directory.name) / 'observations.md'
        datasheet.write_text('<!-- startup-observations:start -->\n<!-- startup-observations:end -->\n')
        environment = patch.dict(os.environ, {'MARIONETTE_DATA_DIR': directory.name,
            'MARIONETTE_SETUP_DATASHEET_PATH': str(datasheet)})
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
        self.assertEqual([call.args[0] for call in logged.call_args_list
                          if call.args[0].startswith('Reasoning:')], ['Reasoning: "Check the sum."'])

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
                with patch('inference.OpenAI', return_value=sdk), patch('diagnostics.log') as logged:
                    if finish:
                        self.assertEqual(api.reply([{'role': 'user', 'content': 'hello'}], 100), ('PUBLIC', finish))
                        self.assertIn('Reasoning: "PRIVATE"', [call.args[0] for call in logged.call_args_list])
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'completion status'):
                            api.reply([{'role': 'user', 'content': 'hello'}], 100)
                    self.assertTrue(any('"total_tokens": 15' in call.args[0] for call in logged.call_args_list))

    def test_agent_uses_exact_messages_without_trimming_or_tools(self):
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
        with patch('inference.OpenAI', return_value=sdk):
            self.assertEqual(inference.API('http://localhost').reply(messages, 32768), ('Hi', 'stop'))
        self.assertEqual(captured[0]['messages'], messages)
        self.assertEqual(captured[0]['seed'], -1)
        self.assertNotIn('tools', captured[0])
        self.assertNotIn('temperature', captured[0])  # Keep configured server sampling.

    def test_generation_allowance_uses_half_context_up_to_32k(self):
        for capacity, expected in ((65536, 32768), (8192, 4096)):
            class FakeAPI:
                closing = threading.Event()
                def prepare(self, messages):
                    self.prepared = messages
                def count(self, messages):
                    return 10
                def reply(self, messages, reserve, *, on_delta=None):
                    self.reserve = reserve
                    return 'answer', 'stop'
            api = FakeAPI()
            with patch('builtins.input', side_effect=['1', 'hello', '/exit']), patch('diagnostics.log'), patch('sys.stdout', io.StringIO()):
                client.chat(api, capacity)
                api.worker.join()
            self.assertEqual(api.reserve, expected)

    def test_rollover_removes_whole_exchanges(self):
        history = []
        for i in range(8):
            history += [{'role': 'user', 'content': str(i)}, {'role': 'assistant', 'content': str(i)}]
        original = history.copy()
        fitted, removed, tokens = context.fit_history(history, 'new', lambda messages: len(messages)*10, 85, 20)
        self.assertEqual(history, original)
        self.assertEqual(removed, 6)
        self.assertEqual([m['role'] for m in fitted], ['user', 'assistant', 'user', 'assistant', 'user'])
        self.assertEqual(fitted[0]['content'], '6')
        self.assertLess(tokens + 20, 85)

    def test_oversized_message_does_not_mutate_history(self):
        history = [{'role': 'user', 'content': 'old'}, {'role': 'assistant', 'content': 'answer'}]
        original = history.copy()
        with self.assertRaisesRegex(ValueError, 'Shorten'):
            context.fit_history(history, 'huge', lambda _: 100, 100, 20)
        self.assertEqual(history, original)

    def test_exact_boundary_reserves_spare_token(self):
        with self.assertRaises(ValueError):
            context.fit_history([], 'new', lambda _: 80, 100, 20)

    def test_failed_stream_not_kept_and_clear_starts_empty(self):
        class FakeAPI:
            closing = threading.Event()
            def __init__(self):
                self.sent = []
            def prepare(self, messages):
                self.prepared = messages
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
                        report = Path(os.environ['MARIONETTE_SETUP_DATASHEET_PATH']).read_text()
                        self.assertIn('Startup status: **ready**', report)
                        self.assertIn('8192 tokens', report)
                        self.assertIn('| Model name | Unverified |', report)
                        self.assertIn('| Discord interface | Offline |', report)
                        self.assertIn('| Registered tools at capture | update_soul |', report)
                        self.assertIn('| Tool: update_contact_notes | Available |', report)
                        with self.assertRaises(ProcessLookupError):
                            os.kill(pid, 0)
                    finally:
                        if process.poll() is None:
                            process.terminate()
                            process.communicate(timeout=10)



class PreparationTests(unittest.TestCase):
    def history(self):
        return [{'role': role, 'content': str(i)} for i in range(8)
                for role in ('user', 'assistant')]

    def test_idle_rollover_prepares_before_committing_and_waits_for_early_input(self):
        started, release = threading.Event(), threading.Event()
        history = self.history()
        class FakeAPI:
            closing = threading.Event()
            def count(self, messages):
                return len(messages) * 10
            def prepare(self, messages):
                self.prepared = messages.copy()
                started.set()
                release.wait(3)
        api = FakeAPI()
        with patch('diagnostics.log'):
            pending = context.Preparation(api, history, 200, 50)
            self.assertTrue(started.wait(2))
            self.assertIs(pending.history, history)
            self.assertTrue(pending.thread.is_alive())
            release.set()
            result = pending.result()
        self.assertEqual(len(history), 16)
        self.assertEqual(len(result), 10)
        self.assertEqual(result, api.prepared)
        self.assertEqual(result[0]['role'], 'user')
        self.assertEqual(result[-1]['role'], 'assistant')

    def test_preparation_failure_retains_original_history(self):
        class FakeAPI:
            closing = threading.Event()
            def count(self, messages):
                return len(messages) * 10
            def prepare(self, messages):
                raise RuntimeError('synthetic cache failure')
        history = self.history()
        with patch('diagnostics.log') as logged:
            pending = context.Preparation(FakeAPI(), history, 200, 50)
            self.assertIs(pending.result(), history)
            self.assertTrue(any('synthetic cache failure' in call.args[0] for call in logged.call_args_list))

    def test_no_prefill_when_next_turn_has_room(self):
        class FakeAPI:
            closing = threading.Event()
            def count(self, messages):
                return 20
            def prepare(self, messages):
                raise AssertionError('unnecessary prefill')
        history = self.history()
        with patch('diagnostics.log'):
            pending = context.Preparation(FakeAPI(), history, 8192, 512)
            self.assertIs(pending.result(), history)

    def test_prepare_excludes_marker_and_leaves_token_boundary(self):
        api = inference.API('http://127.0.0.1:1')
        with patch.object(inference.secrets, 'token_hex', return_value='test'), patch.object(api, 'json', side_effect=[{'prompt': 'historyMARIONETTE_NEXT_INPUT_testend'}, {'tokens': [1, 2, 3]}, {'timings': {}}]) as request, patch('diagnostics.log'):
            api.prepare(self.history())
        self.assertEqual(request.call_args_list[1].args[1]['content'], 'history')
        self.assertEqual(request.call_args_list[2].args,
                         ('/completion', {'prompt': [1, 2], 'n_predict': 0, 'cache_prompt': True}))
