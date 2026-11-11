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
from contacts import ContactProfiles
from conversation import Conversation


class ContactProfileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'contacts/profiles.json'
        self.profiles = ContactProfiles(self.path)
        self.config = self.root / '.env'
        self.config.write_text('DISCORD_ALLOWED_USER_ID=123\nDISCORD_BOT_TOKEN=never-copy-this\n')
        self.profiles.link_owner(self.config)

    def test_persistence_backup_and_same_person_across_sources(self):
        owner = self.profiles.profiles[0]
        uuid.UUID(owner['uuid'])
        restored = self.root / 'restored/profiles.json'
        restored.parent.mkdir()
        shutil.copy2(self.path, restored)
        profiles = ContactProfiles(restored)
        self.assertEqual(profiles.data, self.profiles.data)
        self.assertEqual(profiles.resolve('terminal', owner['uuid'])['contact_uuid'],
                         profiles.resolve('discord', '123')['contact_uuid'])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('never-copy-this', self.path.read_text())
        with self.assertRaises(ValueError):
            profiles.resolve('discord', '456')

    def test_selector_new_profile_survives_restart_without_owner_link(self):
        with patch('builtins.input', side_effect=['bad', '2', 'Guest']), patch('sys.stdout', io.StringIO()):
            guest = select_profile(self.profiles)
        self.assertNotEqual(guest['uuid'], self.profiles.data['owner_uuid'])
        self.assertEqual(guest['linked_accounts'], [])
        restored = ContactProfiles(self.path)
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
            ContactProfiles(self.path)
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
            self.assertEqual([m['source'] for m in metadata], ['discord'])
            self.assertEqual(metadata[0]['contact_uuid'], owner['uuid'])
            self.assertEqual(len(conversation.histories['terminal:' + owner['uuid']]), 2)
            self.assertEqual(api.counted[0], api.sent[0])
            self.assertTrue(any('Sender identity:' in str(call) for call in logged.call_args_list))
            conversation.turn('/clear')
            self.assertEqual(conversation.history, [])
            conversation.turn('visitor', source='discord', sender_id='456')
            conversation.pending.result()
            self.assertNotEqual(self.profiles.resolve('discord', '456')['contact_uuid'],
                                self.profiles.data['owner_uuid'])

    def test_contacts_overhead_counts_toward_input_limit(self):
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

    def test_v1_migration_preserves_identity_and_backup_and_is_idempotent(self):
        owner = str(uuid.uuid4())
        legacy = {'version': 1, 'owner_uuid': owner, 'profiles': [
            {'uuid': owner, 'name': 'Legacy', 'discord_id': '123'}]}
        self.path.write_text(json.dumps(legacy))
        original = self.path.read_bytes()
        migrated = ContactProfiles(self.path)
        profile = migrated.profiles[0]
        self.assertEqual(migrated.data['schema_version'], 2)
        self.assertEqual(profile['uuid'], owner)
        self.assertEqual(profile['linked_accounts'], [{'service': 'discord', 'account_id': '123'}])
        self.assertIsNone(profile['created_at'])
        self.assertIsNone(profile['timezone'])
        self.assertIsNone(profile['preferred_name'])
        self.assertIsNotNone(profile['updated_at'])
        backup = self.path.with_name('profiles.v1.backup.json')
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        saved = self.path.read_bytes()
        ContactProfiles(self.path)
        self.assertEqual(self.path.read_bytes(), saved)
        restored = self.root / 'old-backup/profiles.json'
        restored.parent.mkdir()
        restored.write_bytes(backup.read_bytes())
        self.assertEqual(ContactProfiles(restored).resolve('discord', '123')['contact_uuid'], owner)

    def test_new_fields_and_timestamp_updates(self):
        profile = self.profiles.add('Test')
        created = profile['created_at']
        updated = profile['updated_at']
        self.profiles.save()
        self.assertEqual(profile['updated_at'], updated)
        profile.update(preferred_name='Tester', timezone='America/New_York')
        profile['linked_accounts'].append({'service': 'future_chat', 'account_id': 'test-account'})
        self.profiles.save()
        self.assertEqual(profile['created_at'], created)
        self.assertNotEqual(profile['updated_at'], updated)
        identity = ContactProfiles(self.path).resolve('terminal', profile['uuid'])
        self.assertEqual(identity['preferred_name'], 'Tester')
        self.assertEqual(identity['timezone'], 'America/New_York')
        with self.assertRaisesRegex(ValueError, 'Unknown message source'):
            self.profiles.resolve('future_chat', 'test-account')

    def test_invalid_metadata_and_duplicate_accounts_rejected_without_writing(self):
        import copy
        original = self.path.read_bytes()
        valid = copy.deepcopy(self.profiles.data)
        for change in ({'timezone': 'Imaginary/Nowhere'}, {'created_at': 'yesterday'},
                       {'updated_at': '2026-01-01T00:00:00'}, {'preferred_name': '\x1b'},
                       {'linked_accounts': [{'service': 'terminal', 'account_id': 'x'}]},
                       {'linked_accounts': [{'service': 'discord', 'account_id': '123'},
                                            {'service': 'discord', 'account_id': '0123'}]}):
            with self.subTest(change=change):
                self.profiles.data = copy.deepcopy(valid)
                self.profiles.profiles[0].update(change)
                with self.assertRaises(ValueError):
                    self.profiles.save()
                self.assertEqual(self.path.read_bytes(), original)
        self.profiles.data = valid
        self.profiles.data['schema_version'] = 999
        with self.assertRaises(ValueError):
            self.profiles.save()

    def test_invalid_legacy_and_failed_migration_keep_original_file(self):
        from unittest.mock import patch
        owner = str(uuid.uuid4())
        legacy = {'version': 1, 'owner_uuid': owner, 'profiles': [
            {'uuid': owner, 'name': 'Legacy', 'discord_id': '123'}]}
        self.path.write_text(json.dumps(legacy))
        original = self.path.read_bytes()
        with patch('contacts.os.replace', side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(OSError):
                ContactProfiles(self.path)
        self.assertEqual(self.path.read_bytes(), original)
        ContactProfiles(self.path)  # Retry may reuse the matching backup.
        legacy['profiles'][0]['discord_id'] = 'invalid'
        self.path.write_text(json.dumps(legacy))
        invalid = self.path.read_bytes()
        with self.assertRaises(ValueError):
            ContactProfiles(self.path)
        self.assertEqual(self.path.read_bytes(), invalid)
