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
            self.assertEqual(recognize(' /shutdown \n', source), 'shutdown')
            self.assertIsNone(recognize('hello', source))
        self.assertEqual(recognize(' /exit ', 'terminal'), 'exit')
        self.assertEqual(recognize('/unknown', 'terminal'), 'help')
        self.assertIsNone(recognize('/exit', 'discord'))
        self.assertIsNone(recognize('/unknown', 'discord'))
        self.assertIsNone(recognize(' /unknown', 'terminal'))

    def test_discord_controls_terminal_owner_only_without_model(self):
        import tempfile
        import threading
        from contacts import ContactProfiles
        from conversation import Conversation
        with tempfile.TemporaryDirectory() as directory, patch('diagnostics.log'):
            profiles=ContactProfiles(Path(directory)/'profiles.json')
            owner=profiles.profiles[0];guest=profiles.add('Guest')
            for command in ('startdiscord','stopdiscord'):
                self.assertEqual(recognize('/'+command,'terminal'),command)
                self.assertIsNone(recognize('/'+command,'discord'))
                for selected in (owner,guest):
                    api=Mock(closing=threading.Event())
                    convo=Conversation(api,8192,profiles,selected)
                    convo.discord_control=Mock()
                    method=convo.discord_control.start if command=='startdiscord' else convo.discord_control.stop
                    method.return_value='synthetic result'
                    answer,finish=convo.turn('/'+command)
                    if selected is owner:
                        method.assert_called_once_with()
                        self.assertEqual(answer,'synthetic result')
                    else:
                        method.assert_not_called()
                        self.assertEqual(answer,'Access Denied')
                    api.reply.assert_not_called()
                    self.assertIsNone(convo.pending)

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

    def test_shutdown_requires_saved_owner_and_never_calls_model(self):
        import tempfile
        import threading
        from contacts import ContactProfiles
        from conversation import Conversation
        with tempfile.TemporaryDirectory() as directory, patch('diagnostics.log'):
            profiles = ContactProfiles(Path(directory) / 'profiles.json')
            owner = profiles.profiles[0]
            owner['linked_accounts'] = [{'service': 'discord', 'account_id': '123'}]
            profiles.save()
            guest = profiles.add('Guest')
            for source, sender, selected, allowed in (
                ('terminal', None, guest, False), ('discord', '456', owner, False),
                ('terminal', None, owner, True), ('discord', '123', guest, True)):
                api = Mock(closing=threading.Event())
                conversation = Conversation(api, 8192, profiles, selected)
                answer, finish = conversation.turn('/shutdown', source=source, sender_id=sender)
                self.assertEqual(conversation.shutdown_requested, allowed)
                self.assertEqual(finish, 'shutdown' if allowed else 'stop')
                if not allowed: self.assertEqual(answer, 'Access Denied')
                api.reply.assert_not_called()
                self.assertIsNone(conversation.pending)
                self.assertFalse(api.closing.is_set())  # UI returns through normal cleanup.
