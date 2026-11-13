"""Synthetic Obsidian export checks; no personal profiles or conversations."""
import json
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from storage import Store
from conversation_vault import sync, atomic_write


class ConversationVaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / 'conversations' / 'marionette.sqlite3'
        self.store = Store(self.database)
        self.addCleanup(self.store.close)
        self.session = self.store.start()
        self.profiles = self.root / 'profiles.json'
        self.profiles.write_text(json.dumps({'profiles': [{'uuid': 'one', 'name': 'Sample User'}]}))

    def message(self, content, kind='input', contact='one'):
        self.store.message(self.session, 'terminal:1', 'terminal:' + contact,
                           {'contact_uuid': contact}, 'terminal', None,
                           'assistant' if kind != 'input' else 'user', kind, content, 'received')

    def test_sync_preserves_text_ids_and_separates_contacts(self):
        self.message('Hello [[not a link]]\n```\n![](https://example.test/image)')
        self.message('Answer', 'answer')
        self.message('Private reasoning', 'reasoning')
        self.message('Other person', contact='two')
        result = sync(self.database, self.profiles)
        self.assertEqual((result['messages'], result['conversations']), (3, 2))
        vault = Path(result['vault'])
        files = list((vault / 'Generated').rglob('conversation-*.md'))
        self.assertEqual(len(files), 2)
        content = ''.join(p.read_text() for p in files)
        self.assertIn('Sample User', content)
        self.assertIn('terminal:1', content)
        self.assertIn('````text\nHello', content)
        self.assertNotIn('Private reasoning', content)
        self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM messages').fetchone()[0], 4)

    def test_resync_updates_same_note_and_preserves_annotations(self):
        self.message('First')
        vault = Path(sync(self.database)['vault'])
        note = vault / 'Annotations' / 'mine.md'
        note.write_text('My annotation')
        original = list((vault / 'Generated').rglob('conversation-*.md'))[0]
        self.message('Second', 'answer')
        sync(self.database)
        self.assertEqual(len(list((vault / 'Generated').rglob('conversation-*.md'))), 1)
        self.assertIn('Second', original.read_text())
        self.assertEqual(note.read_text(), 'My annotation')

    def test_deleted_records_remove_stale_generated_pages(self):
        self.message('Old memory')
        vault = Path(sync(self.database)['vault'])
        with self.store.db:
            self.store.db.execute('DELETE FROM messages')
        result = sync(self.database)
        self.assertEqual(result['messages'], 0)
        self.assertEqual(list((vault / 'Generated').rglob('conversation-*.md')), [])
        self.assertNotIn('Old memory', ''.join(p.read_text() for p in vault.rglob('*.md')))

    def test_rejects_symlink_and_unmanaged_destination(self):
        vault = self.database.parent / 'obsidian-vault'
        vault.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            sync(self.database)
        vault.unlink()
        (vault / 'Generated').mkdir(parents=True)
        with self.assertRaises(ValueError):
            sync(self.database)

    def test_missing_database_is_not_created(self):
        with self.assertRaises(Exception):
            sync(self.root / 'missing.sqlite3')
        self.assertFalse((self.root / 'missing.sqlite3').exists())

    def test_reset_waits_until_old_export_finishes(self):
        self.message('Old message')
        ready, start, finished = threading.Event(), threading.Event(), threading.Event()
        failures = []
        def reset():
            try:
                writer = Store(self.database)
                ready.set()
                start.wait(5)
                writer.reset_memory(self.session, 'new-generation')
                writer.close()
                finished.set()
            except Exception as error:
                failures.append(error)
        worker = threading.Thread(target=reset)
        worker.start()
        self.assertTrue(ready.wait(2))
        def write(path, content):
            start.set()
            self.assertFalse(finished.wait(.02))
            atomic_write(path, content)
        try:
            with patch('conversation_vault.atomic_write', side_effect=write):
                sync(self.database)
        finally:
            start.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertTrue(finished.is_set())

    def test_contact_compartments_and_v1_migration(self):
        self.message('First person')
        self.message('Second person', contact='two')
        vault = self.database.parent / 'obsidian-vault'
        generated = vault / 'Generated'
        generated.mkdir(parents=True)
        (generated / '.marionette-managed').write_text('Marionette conversation mirror v1\n')
        (generated / 'day-old.md').write_text('[[contact-old]]')
        (generated / 'contact-old.md').write_text('old hub')
        (vault / 'Annotations').mkdir()
        (vault / 'Annotations/mine.md').write_text('Keep this')
        sync(self.database, self.profiles)
        self.assertFalse((generated / 'day-old.md').exists())
        self.assertFalse((generated / 'contact-old.md').exists())
        compartments = list((generated / 'Contacts').iterdir())
        self.assertEqual(len(compartments), 2)
        import re
        for compartment in compartments:
            self.assertTrue((compartment / 'Profile.md').exists())
            self.assertTrue((compartment / 'Dates.md').exists())
            self.assertEqual(len(list((compartment / 'Conversations').glob('*.md'))), 1)
            for page in compartment.rglob('*.md'):
                for target in re.findall(r'\[\[([^]|]+)', page.read_text()):
                    self.assertTrue(target.startswith('Generated/Contacts/' + compartment.name + '/'))
                    self.assertTrue((vault / (target + '.md')).exists())
        self.assertNotIn('[[', (generated / 'Conversations.md').read_text())
        self.assertEqual((vault / 'Annotations/mine.md').read_text(), 'Keep this')
        self.assertTrue((generated / 'Groups').is_dir())
