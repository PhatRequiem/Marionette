"""Shared history, serialization, and private local connection lifecycle."""
import asyncio
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/marionette'))
import connection
import session


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
        conversation = session.Conversation(api, 65536)
        with tempfile.TemporaryDirectory() as directory, patch.object(session, 'log'):
            address = Path(directory) / 'chat.sock'
            with connection.LocalConnection(address, conversation.turn, lambda _: None):
                conversation.turn('terminal first', display=True)
                result = asyncio.run(connection.request(address, 'discord second'))
                self.assertEqual(result, ('answer', 'stop'))
                conversation.turn('terminal third', display=True)
                self.assertEqual([m['content'] for m in api.sent[-1]],
                    ['terminal first', 'answer', 'discord second', 'answer', 'terminal third'])
                asyncio.run(connection.request(address, '/clear'))
                conversation.turn('fresh terminal', display=True)
                self.assertEqual(api.sent[-1], [{'role': 'user', 'content': 'fresh terminal'}])
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
        conversation = session.Conversation(api, 65536)
        with patch.object(session, 'log'):
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
