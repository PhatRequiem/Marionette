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
        finish = Mock()
        conversation = SimpleNamespace(key='discord:123', history=history,
                                       finish_preparation=finish)
        with patch('diagnostics.log'):
            self.assertIn('Permission denied', execute_clear(conversation,
                {'contact_uuid': 'guest', 'source': 'discord', 'sender_id': '456'}))
            finish.assert_not_called()
            self.assertIs(conversation.history, history)
            self.assertEqual(execute_clear(conversation,
                {'contact_uuid': 'owner', 'source': 'discord', 'sender_id': '123'}), 'Chat history cleared.')
        finish.assert_called_once_with()
        self.assertEqual(conversation.history, [])
