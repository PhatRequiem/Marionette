"""Synthetic identities, persistence, source mapping and actual request budgeting."""
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from terminal import select_profile
from identity import Profiles
from conversation import Conversation


class IdentityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'identities/profiles.json'
        self.profiles = Profiles(self.path)
        self.config = self.root / '.env'
        self.config.write_text('DISCORD_ALLOWED_USER_ID=123\nDISCORD_BOT_TOKEN=never-copy-this\n')
        self.profiles.link_owner(self.config)

    def test_persistence_backup_and_same_person_across_sources(self):
        owner = self.profiles.profiles[0]
        uuid.UUID(owner['uuid'])
        restored = self.root / 'restored/profiles.json'
        restored.parent.mkdir()
        shutil.copy2(self.path, restored)
        profiles = Profiles(restored)
        self.assertEqual(profiles.data, self.profiles.data)
        self.assertEqual(profiles.resolve('terminal', owner['uuid'])['person_uuid'],
                         profiles.resolve('discord', '123')['person_uuid'])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('never-copy-this', self.path.read_text())
        with self.assertRaises(ValueError):
            profiles.resolve('discord', '456')

    def test_selector_new_profile_survives_restart_without_owner_link(self):
        with patch('builtins.input', side_effect=['bad', '2', 'Guest']), patch('sys.stdout', io.StringIO()):
            guest = select_profile(self.profiles)
        self.assertNotEqual(guest['uuid'], self.profiles.data['owner_uuid'])
        self.assertIsNone(guest['discord_id'])
        restored = Profiles(self.path)
        with patch('builtins.input', return_value='2'), patch('sys.stdout', io.StringIO()):
            self.assertEqual(select_profile(restored), guest)
        for name in ('Phat', '\x1b[31m', ''):
            with self.assertRaises(ValueError):
                restored.add(name)
        self.assertEqual(restored.resolve('discord', '123')['display_name'], 'Phat')

    def test_corruption_and_changed_account_fail_without_overwriting(self):
        self.config.write_text('DISCORD_ALLOWED_USER_ID=456\n')
        original = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.profiles.link_owner(self.config)
        self.assertEqual(self.path.read_bytes(), original)
        self.path.write_text('{broken')
        with self.assertRaises(ValueError):
            Profiles(self.path)
        self.assertEqual(self.path.read_text(), '{broken')

    def test_metadata_is_counted_retained_and_logs_actual_sender(self):
        class API:
            closing = threading.Event()
            def count(self, messages):
                self.counted = messages.copy()
                return 10
            def reply(self, messages, reserve, **kwargs):
                self.sent = messages.copy()
                return 'answer', 'stop'
        api = API()
        owner = self.profiles.profiles[0]
        conversation = Conversation(api, 8192, self.profiles, owner)
        with patch('diagnostics.log') as logged:
            conversation.turn('terminal hello')
            conversation.pending.result()
            conversation.turn('discord hello', source='discord', sender_id='123')
            conversation.pending.result()
            users = [m['content'] for m in api.sent if m['role'] == 'user']
            metadata = [json.loads(m.split('\n', 1)[1].split('\n\nMessage:\n')[0]) for m in users]
            self.assertEqual([m['source'] for m in metadata], ['terminal', 'discord'])
            self.assertEqual(metadata[0]['person_uuid'], metadata[1]['person_uuid'])
            self.assertEqual(api.counted[0], api.sent[0])
            self.assertTrue(any('Sender identity:' in str(call) for call in logged.call_args_list))
            conversation.turn('/clear')
            self.assertEqual(conversation.history, [])
            with self.assertRaises(ValueError):
                conversation.turn('unknown', source='discord', sender_id='456')

    def test_identity_overhead_counts_toward_input_limit(self):
        class API:
            closing = threading.Event()
            def count(self, messages):
                return sum(len(m['content']) for m in messages)
            def reply(self, *args, **kwargs):
                raise AssertionError('Oversized metadata plus input must not reach generation')
        conversation = Conversation(API(), 256, self.profiles, self.profiles.profiles[0])
        with patch('diagnostics.log'), self.assertRaisesRegex(ValueError, 'Shorten'):
            conversation.turn('short')
        self.assertEqual(conversation.history, [])
