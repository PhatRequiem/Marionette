"""Permissions use resolved UUIDs, never names or message claims."""
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from contacts import ContactProfiles
from permissions import require_command
from conversation import Conversation


class PermissionTests(unittest.TestCase):
    def test_default_deny_and_only_own_conversation(self):
        identity = {'contact_uuid': 'person', 'source': 'discord', 'sender_id': '123'}
        for command, sender, key in [('/clear', None, 'discord:123'),
                ('/clear', identity, 'discord:456'),
                ('/clear', identity, 'terminal:person'),
                ('/unknown', identity, 'discord:123')]:
            with self.assertRaises(PermissionError):
                require_command(command, sender, key)
        require_command('/clear', identity, 'discord:123')

    def test_each_person_clears_only_their_originating_conversation(self):
        class API:
            closing = threading.Event()
        with tempfile.TemporaryDirectory() as directory, patch('diagnostics.log'):
            profiles = ContactProfiles(Path(directory) / 'profiles.json')
            owner = profiles.profiles[0]
            owner['linked_accounts'] = [{'service': 'discord', 'account_id': '123'}]
            conversation = Conversation(API(), 8192, profiles, owner)
            keys = ['terminal:' + owner['uuid'], 'discord:123', 'discord:456']
            for key in keys:
                conversation.histories[key] = [{'role': 'user', 'content': key}]
            conversation.turn('/clear', source='discord', sender_id='456')
            self.assertEqual(conversation.histories[keys[2]], [])
            self.assertTrue(conversation.histories[keys[0]])
            self.assertTrue(conversation.histories[keys[1]])
            conversation.turn('/clear', source='discord', sender_id='123')
            self.assertTrue(conversation.histories[keys[0]])
            conversation.turn('/clear')
            self.assertTrue(all(not value for value in conversation.histories.values()))
