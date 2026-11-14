"""Command routing and clearing preserve existing interface behavior."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from commands import HELP_TEXT, execute_clear, recognize


class CommandTests(unittest.TestCase):
    def test_interface_specific_recognition(self):
        for source in ('terminal', 'discord'):
            self.assertEqual(recognize(' /help \n', source), 'help')
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

    def test_manual_setup_refresh_is_owner_terminal_only_and_never_generates(self):
        import tempfile
        import threading
        from contacts import ContactProfiles
        from conversation import Conversation
        self.assertEqual(recognize('/refreshsetup','terminal'),'refreshsetup')
        self.assertIsNone(recognize('/refreshsetup','discord'))
        with tempfile.TemporaryDirectory() as directory, patch('diagnostics.log'):
            profiles=ContactProfiles(Path(directory)/'profiles.json')
            owner=profiles.profiles[0];guest=profiles.add('Guest')
            for selected in (owner,guest):
                api=Mock(closing=threading.Event())
                convo=Conversation(api,8192,profiles,selected)
                convo.setup_refresh=Mock(return_value='updated')
                answer,_=convo.turn('/refreshsetup')
                forced=[c for c in convo.setup_refresh.call_args_list if c.kwargs.get('force')]
                self.assertEqual(len(forced),1 if selected is owner else 0)
                self.assertEqual(answer,'Setup datasheet: updated' if selected is owner else 'Access Denied')
                api.reply.assert_not_called();self.assertIsNone(convo.pending)

    def test_help_is_available_without_owner_and_preserves_history_without_model(self):
        import threading
        from conversation import Conversation
        for source in ('terminal', 'discord'):
            api = Mock(closing=threading.Event())
            conversation = Conversation(api, 8192)
            conversation.history = [{'role': 'user', 'content': 'retain context'}]
            before = conversation.history.copy()
            answer, finish = conversation.turn(' /help ', source=source, sender_id='123')
            self.assertEqual((answer, finish), (HELP_TEXT, 'stop'))
            self.assertEqual(conversation.history, before)
            self.assertIsNone(conversation.pending)
            api.reply.assert_not_called()
            api.count.assert_not_called()
        commands = ('help', 'ddm [on|off]', 'clear', 'resetmemory', 'shutdown', 'startdiscord',
                    'stopdiscord', 'refreshsetup', 'exit')
        self.assertEqual(len(HELP_TEXT.splitlines()), len(commands) + 1)
        for command in commands:
            self.assertIn('/' + command + ' — ', HELP_TEXT)

    def test_ddm_owner_policy_persists_and_blocks_queued_nonowner_before_registration(self):
        import tempfile
        import threading
        from contacts import ContactProfiles
        from conversation import Conversation
        from discord_access import DiscordAccess
        with tempfile.TemporaryDirectory() as directory, patch('diagnostics.log'):
            profiles = ContactProfiles(Path(directory) / 'profiles.json')
            owner = profiles.profiles[0]
            owner['linked_accounts'] = [{'service': 'discord', 'account_id': '123'}]
            profiles.save()
            guest = profiles.add('Guest')
            api = Mock(closing=threading.Event())
            convo = Conversation(api, 8192, profiles, owner)
            convo.discord_access = DiscordAccess(directory)
            self.assertTrue(convo.discord_access.enabled())
            self.assertIn('OFF', convo.turn('/ddm off')[0])
            self.assertFalse(DiscordAccess(directory).enabled())
            self.assertEqual(convo.discord_access.path.stat().st_mode & 0o777, 0o600)
            before = len(profiles.profiles)
            self.assertIn('limited to the owner', convo.turn('private input', source='discord', sender_id='456')[0])
            self.assertEqual(len(profiles.profiles), before)
            self.assertIn('OFF', convo.turn('/ddm', source='discord', sender_id='123')[0])
            self.assertIn('ON', convo.turn('/ddm on', source='discord', sender_id='123')[0])
            self.assertIn('Usage:', convo.turn('/ddm maybe')[0])
            self.assertTrue(convo.discord_access.enabled())
            convo.terminal_profile = guest
            self.assertEqual(convo.turn('/ddm off')[0], 'Access Denied')
            self.assertEqual(convo.turn('/ddm off', source='discord', sender_id='456')[0], 'Access Denied')
            self.assertTrue(convo.discord_access.enabled())
            convo.discord_access.path.write_text('invalid')
            self.assertFalse(convo.discord_access.enabled())
            self.assertIn('ON', convo.turn('/ddm on', source='discord', sender_id='123')[0])
            api.reply.assert_not_called()
            self.assertIsNone(convo.pending)
