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
        files = list((vault / 'Generated').rglob('*conversation-*.md'))
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
        original = list((vault / 'Generated').rglob('*conversation-*.md'))[0]
        self.message('Second', 'answer')
        sync(self.database)
        self.assertEqual(len(list((vault / 'Generated').rglob('*conversation-*.md'))), 1)
        self.assertIn('Second', original.read_text())
        self.assertEqual(note.read_text(), 'My annotation')

    def test_deleted_records_remove_stale_generated_pages(self):
        self.message('Old memory')
        vault = Path(sync(self.database)['vault'])
        with self.store.db:
            self.store.db.execute('DELETE FROM messages')
        result = sync(self.database)
        self.assertEqual(result['messages'], 0)
        self.assertEqual(list((vault / 'Generated').rglob('*conversation-*.md')), [])
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
        (generated / 'Conversations.md').write_text('old index')
        (vault / 'Welcome.md').write_text('Start at [[Conversations]]')
        (vault / 'Annotations').mkdir()
        (vault / 'Annotations/mine.md').write_text('Keep this')
        sync(self.database, self.profiles)
        self.assertFalse((generated / 'day-old.md').exists())
        self.assertFalse((generated / 'contact-old.md').exists())
        compartments = list((generated / 'Contacts').iterdir())
        self.assertEqual(len(compartments), 2)
        import re
        for compartment in compartments:
            self.assertTrue((compartment / (compartment.name.rsplit('-', 1)[0] + '.md')).exists())
            self.assertTrue((compartment / (compartment.name.rsplit('-', 1)[0] + ' - Dates.md')).exists())
            self.assertEqual(len(list((compartment / 'Conversations').glob('*.md'))), 1)
            for page in compartment.rglob('*.md'):
                for target in re.findall(r'\[\[([^]|]+)', page.read_text()):
                    self.assertTrue(target.startswith('Generated/Contacts/' + compartment.name + '/'))
                    self.assertTrue((vault / (target + '.md')).exists())
        self.assertFalse((generated / 'Conversations.md').exists())
        index = (generated / 'Contacts.md').read_text()
        for compartment in compartments:
            self.assertIn('[[Generated/Contacts/' + compartment.name + '/' + compartment.name.rsplit('-', 1)[0] + '|', index)
        self.assertIn('[[Generated/Contacts|Contacts]]', (vault / 'Welcome.md').read_text())
        self.assertEqual((vault / 'Annotations/mine.md').read_text(), 'Keep this')
        self.assertTrue((generated / 'Groups').is_dir())

    def test_contact_notes_mirror_refresh_and_missing_source(self):
        self.message('Hello')
        notes = self.root / 'contact_notes'
        notes.mkdir()
        source = notes / 'one.md'
        content = '# Sample User\n§\nLikes dogs.\n'
        source.write_text(content)
        vault = Path(sync(self.database, self.profiles, notes)['vault'])
        mirror = next((vault / 'Generated/Contacts').rglob('* - Notes.md'))
        self.assertEqual(mirror.read_bytes(), source.read_bytes())
        self.assertIn(' - Notes|Contact notes]]', (mirror.parent / 'Sample User.md').read_text())
        mirror.write_text('Local edit')
        source.write_text('# Sample User\n§\nUpdated note.\n')
        sync(self.database, self.profiles, notes)
        self.assertEqual(mirror.read_bytes(), source.read_bytes())
        source.unlink()
        sync(self.database, self.profiles, notes)
        self.assertIn('No saved contact-notes file', mirror.read_text())
        self.assertFalse(source.exists())
        source.symlink_to(self.profiles)
        with self.assertRaises(ValueError):
            sync(self.database, self.profiles, notes)

    def test_documentation_mirror_keeps_nested_files_and_removes_stale_copies(self):
        docs_root = self.root / 'docs'
        docs = docs_root / 'active'
        (docs / 'current-operation').mkdir(parents=True)
        (docs_root / 'development/history').mkdir(parents=True)
        (docs_root / 'development/history/old.md').write_text('EXCLUDED_HISTORY')
        (docs / '.obsidian').mkdir()
        (docs / '.obsidian/config.json').write_text('not documentation')
        (docs / 'guide.md').write_text('# Guide\n[Guide](current-operation/plan.md)\n')
        (docs / 'current-operation/plan.md').write_text('# Current operation\n')
        (docs / 'schema.json').write_bytes(b'{"value": 1}\r\n')
        result = sync(self.database, docs=docs_root)
        vault = Path(result['vault'])
        target = vault / 'Generated/Self documentation/active'
        self.assertEqual(result['documentation_files'], 3)
        self.assertFalse(any('EXCLUDED_HISTORY' in p.read_text() for p in vault.rglob('*.md')))
        legacy = vault / 'Generated/Self documentation/docs/development/history'
        legacy.mkdir(parents=True)
        (legacy / 'old.md').write_text('EXCLUDED_HISTORY')
        for relative in ('guide.md', 'current-operation/plan.md', 'schema.json'):
            self.assertEqual((target / relative).read_bytes(), (docs / relative).read_bytes())
        self.assertFalse((target / '.obsidian').exists())
        self.assertIn('[[Generated/Self documentation|Self documentation]]', (vault / 'Welcome.md').read_text())
        self.assertIn('Self%20documentation/active/guide.md', (vault / 'Generated/Self documentation.md').read_text())
        (docs / 'schema.json').unlink()
        (docs / 'guide.md').write_text('# Updated guide')
        sync(self.database, docs=docs_root)
        self.assertFalse((target / 'schema.json').exists())
        self.assertFalse((vault / 'Generated/Self documentation/docs').exists())
        self.assertEqual((target / 'guide.md').read_text(), '# Updated guide')
        (docs / 'unsafe.md').symlink_to(self.profiles)
        with self.assertRaises(ValueError):
            sync(self.database, docs=docs_root)
