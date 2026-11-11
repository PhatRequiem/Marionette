"""Message boundaries, correlation across handoff, and failure cleanup."""
import asyncio
import io
from pathlib import Path
import re
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
import connection
import diagnostics
import log_router
from conversation import Conversation
import terminal
from log_view import DiagnosticView


class FakeAPI:
    def __init__(self):
        self.closing = threading.Event()
        self.fail = False
    def count(self, messages):
        return 10
    def reply(self, messages, reserve, **kwargs):
        diagnostics.log('Runtime usage: {"prompt_tokens":10}')
        if self.fail:
            raise RuntimeError('synthetic failure')
        return 'synthetic answer', 'stop'


class MessageLogTests(unittest.TestCase):
    def test_unique_turns_failure_end_and_separate_preparation(self):
        api = FakeAPI()
        chat = Conversation(api, 512)
        records = []
        with patch('diagnostics.write', side_effect=records.append):
            chat.turn('first synthetic message')
            chat.finish_preparation()
            api.fail = True
            with self.assertRaisesRegex(RuntimeError, 'synthetic failure'):
                chat.turn('second synthetic message')
            diagnostics.log('unrelated session event')
        text = b''.join(records).decode()
        ids = re.findall(r'\[message ([^\]]+)\] =+ MESSAGE START \| processing', text)
        self.assertEqual(len(ids), 2)
        self.assertNotEqual(*ids)
        for identifier in ids:
            diagnostics.message_id(identifier)
        self.assertIn(f'[message {ids[1]}] Message failed: RuntimeError: synthetic failure', text)
        self.assertIn('MESSAGE END | processing | failed', text)
        self.assertLess(text.index('MESSAGE END | processing | completed'),
                        text.index('MESSAGE START | cache preparation'))
        self.assertLess(text.index('MESSAGE END | cache preparation'),
                        text.rindex('MESSAGE START | processing'))
        self.assertTrue(text.endswith('Client: unrelated session event\n'))
        self.assertEqual(len(chat.history), 2)
        server, model = io.BytesIO(), io.BytesIO()
        log_router.route(io.BytesIO(b''.join(records)), server, model)
        self.assertEqual(server.getvalue(), model.getvalue())
        self.assertIn(ids[1].encode(), server.getvalue())

    def test_discord_id_survives_socket_queue_and_worker(self):
        chat = Conversation(FakeAPI(), 512)
        records, results, errors = [], [], []
        identifier = 'discord:987654321'
        with tempfile.TemporaryDirectory() as directory, \
             patch('diagnostics.write', side_effect=records.append), patch('sys.stdout', io.StringIO()):
            address = Path(directory) / 'chat.sock'
            with connection.LocalConnection(address, chat.submit_discord, diagnostics.log):
                def send():
                    try:
                        results.append(asyncio.run(connection.request(address, 'synthetic DM', '123',
                                                                      message_id=identifier)))
                    except Exception as error:
                        errors.append(error)
                sender = threading.Thread(target=send)
                sender.start()
                item = chat.incoming.get(timeout=3)
                chat.incoming.put(item)
                terminal.display_discord(chat)
                sender.join(3)
                self.assertFalse(sender.is_alive())
                chat.finish_preparation()
        self.assertEqual(errors, [])
        self.assertEqual(results[0]['answer'], 'synthetic answer')
        text = b''.join(records).decode()
        for event in ('Discord input', 'Runtime usage:', 'Discord answer:', 'MESSAGE START', 'MESSAGE END'):
            self.assertTrue(any(f'[message {identifier}]' in line and event in line
                                for line in text.splitlines()), event)
        self.assertNotIn('[message local:', text)

    def test_invalid_ids_and_viewer_colors(self):
        for value in ('discord:12\ninjected', 'local:not-a-uuid', 123):
            with self.assertRaises(ValueError):
                diagnostics.message_id(value)
        viewer = DiagnosticView()
        prefix = '    | Client: [message discord:123] '
        self.assertEqual(viewer.row(prefix + '========== MESSAGE START | processing =========='), 'meta')
        self.assertEqual(viewer.row(prefix + 'Runtime usage: {}'), 'tokens')
        self.assertEqual(viewer.row(prefix + 'Message failed: RuntimeError: test'), 'error')
