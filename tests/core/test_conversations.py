"""Conversation isolation and safe use of the single model worker."""
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from conversation import Conversation
from contacts import ContactProfiles


class FakeAPI:
    def __init__(self):
        self.closing = threading.Event()
        self.sent = []
        self.fail = False
    def count(self, messages): return len(messages) * 60
    def prepare(self, messages): pass
    def reply(self, messages, reserve, **kwargs):
        if self.fail:
            raise RuntimeError('synthetic failure')
        self.sent.append(messages.copy())
        return 'answer', 'stop'


class ConversationsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        profiles = ContactProfiles(Path(temp.name) / 'profiles.json')
        self.api = FakeAPI()
        self.chat = Conversation(self.api, 512, profiles, profiles.profiles[0])
        self.log = patch('diagnostics.log').start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self.chat.finish_preparation)

    def test_rollover_failure_and_clear_affect_only_originating_history(self):
        chat = self.chat
        chat.turn('terminal fact')
        chat.finish_preparation()
        terminal_key = chat.key
        original = chat.history.copy()
        for n in range(5):
            chat.turn(f'DM fact {n}', source='discord', sender_id='123')
            chat.finish_preparation()
        self.assertLess(len(chat.history), 10)
        self.assertEqual(chat.histories[terminal_key], original)
        self.assertNotIn('terminal fact', str(self.api.sent[-1]))
        previous = chat.history.copy()
        self.api.fail = True
        with self.assertRaises(RuntimeError):
            chat.turn('failed DM', source='discord', sender_id='456')
        self.assertEqual(chat.history, [])
        self.assertEqual(chat.histories['discord:123'], previous)
        self.api.fail = False
        chat.turn('/clear', source='discord', sender_id='123')
        self.assertEqual(chat.history, [])
        chat.turn('terminal continuation')
        self.assertIn('terminal fact', str(self.api.sent[-1]))
        self.assertNotIn('DM fact', str(self.api.sent[-1]))

    def test_switch_waits_for_preparation_and_commits_to_original_conversation(self):
        started, release = threading.Event(), threading.Event()
        original = [{'role': 'user', 'content': 'prepared terminal history'}]
        class Pending:
            def result(self):
                started.set()
                if not release.wait(5):
                    raise RuntimeError('Test worker was not released')
                return original
        self.chat.pending = Pending()
        self.chat.pending_key = self.chat.key
        terminal_key = self.chat.key
        errors = []
        def switch():
            try:
                self.chat.turn('new DM', source='discord', sender_id='123')
            except Exception as error:
                errors.append(error)
        worker = threading.Thread(target=switch)
        worker.start()
        try:
            self.assertTrue(started.wait(2))
            self.assertEqual(self.api.sent, [])
        finally:
            release.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(self.chat.histories[terminal_key], original)
        self.assertNotIn('prepared terminal history', str(self.api.sent[-1]))
        self.assertEqual(self.chat.pending_key, 'discord:123')
