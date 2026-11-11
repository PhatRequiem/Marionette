"""Permissions use resolved UUIDs, never names or message claims."""
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from identity import Profiles
from permissions import require_command
from conversation import Conversation


class PermissionTests(unittest.TestCase):
    def test_default_deny(self):
        for command, identity, owner in [('/clear', None, 'owner'),
                ('/clear', {'person_uuid': 'guest', 'display_name': 'Phat'}, 'owner'),
                ('/clear', {'person_uuid': None}, None),
                ('/unknown', {'person_uuid': 'owner'}, 'owner')]:
            with self.assertRaises(PermissionError):
                require_command(command, identity, owner)
        require_command('/clear', {'person_uuid': 'owner'}, 'owner')

    def test_guest_denied_owner_allowed_across_sources(self):
        class API:
            closing = threading.Event()
        with tempfile.TemporaryDirectory() as directory, patch('diagnostics.log') as logged:
            profiles = Profiles(Path(directory) / 'profiles.json')
            owner = profiles.profiles[0]
            owner['linked_accounts'] = [{'service': 'discord', 'account_id': '123'}]
            guest = profiles.add('Guest')
            guest['linked_accounts'] = [{'service': 'discord', 'account_id': '456'}]
            conversation = Conversation(API(), 8192, profiles, guest)
            history = [{'role': 'user', 'content': 'keep'}, {'role': 'assistant', 'content': 'kept'}]
            conversation.history = history
            for kwargs in ({}, {'source': 'discord', 'sender_id': '456'}):
                answer, _ = conversation.turn('/clear', **kwargs)
                self.assertIn('Permission denied', answer)
                self.assertIs(conversation.history, history)
            answer, _ = conversation.turn('/clear', source='discord', sender_id='789')
            self.assertIn('Permission denied', answer)
            self.assertIs(conversation.history, history)
            conversation.turn('/clear', source='discord', sender_id='123')
            self.assertEqual(conversation.history, [])
            conversation.history = history
            conversation.terminal_profile = owner
            conversation.turn('/clear')
            self.assertEqual(conversation.history, [])
            self.assertTrue(any('Command denied:' in str(c) for c in logged.call_args_list))
