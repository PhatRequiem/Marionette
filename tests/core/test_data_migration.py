"""Synthetic path and conversation-schema migrations; no real memories."""
import sys
import tempfile
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from data_migration import migrate_personal_paths
from storage import Store


class MigrationTests(unittest.TestCase):
    def test_paths_preserve_bytes_permissions_and_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder, file in [('identities', 'profiles.json'), ('characters', 'example.md'), ('self', 'identity.json')]:
                path = root / folder / file
                path.parent.mkdir()
                path.write_bytes(b'synthetic exact bytes')
                path.chmod(0o600)
            migrate_personal_paths(root)
            migrate_personal_paths(root)
            for path in ('contacts/profiles.json', 'contact_notes/example.md', 'soul/profile.json'):
                self.assertEqual((root/path).read_bytes(), b'synthetic exact bytes')
                self.assertEqual((root/path).stat().st_mode & 0o777, 0o600)
            self.assertFalse((root/'self').exists())

    def test_conflict_and_symlink_do_not_move_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'identities').mkdir()
            (root/'contacts').mkdir()
            with self.assertRaises(ValueError): migrate_personal_paths(root)
            self.assertTrue((root/'identities').exists())
            (root/'contacts').rmdir()
            (root/'characters').symlink_to(root/'identities')
            with self.assertRaises(ValueError): migrate_personal_paths(root)
            self.assertTrue((root/'identities').exists())

    def test_legacy_database_keeps_contact_and_message(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'logs.sqlite3'
            store = Store(path)
            session = store.start()
            store.message(session, 'terminal:example', 'terminal:example', {'contact_uuid':'synthetic'},
                          'terminal', 'synthetic', 'user', 'input', 'example message', 'received')
            store.db.execute('ALTER TABLE messages RENAME COLUMN contact_uuid TO person_uuid')
            store.db.execute('DROP INDEX messages_contact')
            store.db.execute('CREATE INDEX messages_person ON messages(person_uuid, recorded_at)')
            store.db.execute('DROP TABLE memory_epoch')
            store.db.execute('PRAGMA user_version=2')
            store.db.commit()
            store.close()
            for _ in range(2):
                store = Store(path)
                row = store.db.execute('SELECT contact_uuid,content FROM messages').fetchone()
                self.assertEqual(tuple(row), ('synthetic','example message'))
                self.assertEqual(store.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                store.close()
