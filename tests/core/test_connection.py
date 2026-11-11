"""Shared history, serialization, and private local connection lifecycle."""
import asyncio
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import httpx
from openai import OpenAI
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/marionette'))
from identity import Profiles
import connection
from conversation import Conversation
from inference import API
import terminal
from style import COLORS


class ConnectionTests(unittest.TestCase):
    def test_shared_history_clear_and_detach(self):
        class API:
            closing = threading.Event()
            def __init__(self):
                self.sent = []
            def count(self, messages):
                return 10
            def reply(self, messages, reserve, **kwargs):
                self.sent.append(messages.copy())
                return 'answer', 'stop'
        api = API()
        conversation = Conversation(api, 65536)
        with tempfile.TemporaryDirectory() as directory, patch('diagnostics.log'):
            profiles = Profiles(Path(directory) / 'profiles.json')
            profiles.profiles[0]['linked_accounts'] = [{'service': 'discord', 'account_id': '123'}]
            conversation = Conversation(api, 65536, profiles, profiles.profiles[0])
            address = Path(directory) / 'chat.sock'
            with connection.LocalConnection(address, lambda message, sender_id, **_: conversation.turn(message, source='discord', sender_id=sender_id), lambda _: None):
                conversation.turn('terminal first', on_delta=terminal.ReplyDisplay())
                result = asyncio.run(connection.request(address, 'discord second', 123))
                self.assertEqual(result, {'answer': 'answer', 'finish': 'stop', 'timings': {}})
                conversation.turn('terminal third', on_delta=terminal.ReplyDisplay())
                self.assertEqual([m['content'].split('\n\nMessage:\n', 1)[-1] for m in api.sent[-1]],
                    ['terminal first', 'answer', 'discord second', 'answer', 'terminal third'])
                asyncio.run(connection.request(address, '/clear', 123))
                conversation.turn('fresh terminal', on_delta=terminal.ReplyDisplay())
                self.assertEqual(len(api.sent[-1]), 1)
                self.assertTrue(api.sent[-1][0]['content'].endswith('Message:\nfresh terminal'))
                conversation.pending.result()
            self.assertFalse(address.exists())
            self.assertFalse(api.closing.is_set())

    def test_simultaneous_inputs_never_generate_together(self):
        entered, release = threading.Event(), threading.Event()
        class API:
            closing = threading.Event()
            def __init__(self):
                self.sent = []
            def count(self, messages):
                return 10
            def reply(self, messages, reserve, **kwargs):
                self.sent.append(messages.copy())
                if len(self.sent) == 1:
                    entered.set()
                    if not release.wait(3):
                        raise RuntimeError('Test timed out')
                return 'answer', 'stop'
        api = API()
        conversation = Conversation(api, 65536)
        with patch('diagnostics.log'):
            first = threading.Thread(target=conversation.turn, args=('terminal',))
            second = threading.Thread(target=conversation.turn, args=('discord',))
            first.start()
            self.assertTrue(entered.wait(2))
            second.start()
            self.assertEqual(len(api.sent), 1)
            release.set()
            first.join(3); second.join(3)
            self.assertFalse(first.is_alive() or second.is_alive())
            self.assertEqual([m['content'] for m in api.sent[-1]], ['terminal', 'answer', 'discord'])
            conversation.pending.result()

    def test_discord_display_has_sender_colors_and_only_returns_answer(self):
        api = API('http://127.0.0.1:1')
        conversation = Conversation(api, 65536)
        events = [
            {'choices': [{'delta': {'reasoning_content': 'Private thinking.'}}]},
            {'choices': [{'delta': {'content': 'Final answer.'}, 'finish_reason': 'stop'}]},
        ]
        payload = (''.join('data: ' + json.dumps(e) + '\n\n' for e in events)
                   + 'data: [DONE]\n\n').encode()
        sdk = OpenAI(base_url='http://127.0.0.1:1/v1', api_key='EMPTY',
            http_client=httpx.Client(transport=httpx.MockTransport(lambda request:
                httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=payload))))
        output = io.StringIO()
        result = []
        with patch('inference.OpenAI', return_value=sdk), patch.object(api, 'count', return_value=10), \
             patch('diagnostics.log'), patch('sys.stdout', output), \
             patch.object(output, 'isatty', return_value=True), patch.dict(os.environ, {'TERM': 'xterm'}):
            worker = threading.Thread(target=lambda: result.append(
                conversation.submit_discord('Hello from Discord', sender_id='123')))
            worker.start()
            # Wait for the queued request without arbitrary timing assumptions.
            item = conversation.incoming.get(timeout=2)
            conversation.incoming.put(item)
            self.assertTrue(terminal.display_discord(conversation))
            worker.join(2)
            self.assertFalse(worker.is_alive())
            conversation.pending.result()
        self.assertEqual(result, [('Final answer.', 'stop')])
        rendered = output.getvalue()
        self.assertIn(COLORS['meta'] + '[Discord · ' + COLORS['ids'] + '123' + COLORS['meta'] + ']\n', rendered)
        self.assertIn(COLORS['input'] + 'Hello from Discord', rendered)
        self.assertIn(COLORS['reasoning_heading'] + 'Reasoning:\n' + COLORS['data'] + 'Private thinking.', rendered)
        self.assertIn(COLORS['reply'] + 'Final answer.', rendered)
        self.assertEqual(conversation.history[0]['content'], 'Hello from Discord')

    def test_discord_handoff_returns_immediately_and_propagates_failure(self):
        from concurrent.futures import Future
        api = API('http://127.0.0.1:1')
        conversation = Conversation(api, 65536)
        for failure in (None, TimeoutError('generation timed out')):
            future = Future()
            if failure:
                future.set_exception(failure)
            else:
                future.set_result(('answer', 'stop'))
            with patch('conversation.Future', return_value=future), \
                 patch.object(api.closing, 'wait', side_effect=AssertionError('unnecessary polling delay')):
                if failure:
                    with self.assertRaisesRegex(TimeoutError, 'generation timed out'):
                        conversation.submit_discord('test', sender_id='123')
                else:
                    self.assertEqual(conversation.submit_discord('test', sender_id='123'), ('answer', 'stop'))
        api.closing.set()
        with self.assertRaisesRegex(RuntimeError, 'Session is closing'):
            conversation.submit_discord('test', sender_id='123')
