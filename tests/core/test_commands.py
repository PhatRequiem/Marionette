"""Command routing and clearing preserve existing interface behavior."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from commands import execute_clear, recognize


class CommandTests(unittest.TestCase):
    def test_interface_specific_recognition(self):
        for source in ('terminal', 'discord'):
            self.assertEqual(recognize(' /clear \n', source), 'clear')
            self.assertIsNone(recognize('hello', source))
        self.assertEqual(recognize(' /exit ', 'terminal'), 'exit')
        self.assertEqual(recognize('/unknown', 'terminal'), 'help')
        self.assertIsNone(recognize('/exit', 'discord'))
        self.assertIsNone(recognize('/unknown', 'discord'))
        self.assertIsNone(recognize(' /unknown', 'terminal'))

    def test_clear_waits_only_after_authorization_and_does_not_run_model(self):
        history = [{'role': 'user', 'content': 'retain until cleared'}]
        pending = Mock()
        conversation = SimpleNamespace(profiles=SimpleNamespace(data={'owner_uuid': 'owner'}),
                                       history=history, pending=pending)
        with patch('diagnostics.log'):
            self.assertIn('Permission denied', execute_clear(conversation, {'person_uuid': 'guest'}))
            pending.result.assert_not_called()
            self.assertIs(conversation.history, history)
            self.assertIs(conversation.pending, pending)
            self.assertEqual(execute_clear(conversation, {'person_uuid': 'owner'}), 'Chat history cleared.')
        pending.result.assert_called_once_with()
        self.assertEqual(conversation.history, [])
        self.assertIsNone(conversation.pending)
