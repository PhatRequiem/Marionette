"""Synthetic citation metadata, note edits and vault link resolution."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from conversation_refs import conversation_reference
from conversation_vault import sync
from storage import Store
from contacts import ContactProfiles
from contact_notes import ContactNotes, UpdateContactNotes
from conversation import Conversation
from test_conversations import FakeAPI


class ConversationReferenceTests(unittest.TestCase):
    def test_reference_reaches_model_and_note_edits_resolve_after_rename(self):
        with tempfile.TemporaryDirectory() as directory, patch('diagnostics.log'):
            root = Path(directory)
            profiles = ContactProfiles(root / 'contacts/profiles.json')
            owner = profiles.profiles[0]
            notes = ContactNotes(root / 'contact_notes')
            store = Store(root / 'conversations/marionette.sqlite3')
            self.addCleanup(store.close)
            session = store.start()
            api = FakeAPI()
            conversation = Conversation(api, 8192, profiles, owner, notes, store, session)
            conversation.turn('I play banjo.')
            conversation.finish_preparation()
            sent = api.sent[-1][0]['content']
            metadata = json.loads(sent.split('\n', 1)[1].split('\n\nMessage:\n')[0])
            ref = metadata['conversation_reference']
            self.assertEqual(ref, conversation_reference(session, 'terminal:' + owner['uuid'], owner['uuid']))
            self.assertNotEqual(ref, conversation_reference('other-session', 'terminal:' + owner['uuid'], owner['uuid']))
            tool = UpdateContactNotes(notes, metadata, notes.read(owner['uuid']))
            def edit(args):
                result = json.loads(tool.call(json.dumps(args)))
                self.assertTrue(result['success'], result)
            linked = f'[Plays banjo]({ref}).'
            edit({'action': 'add', 'content': linked})
            edit({'action': 'add', 'content': 'My impression: I like the way he talks to me.'})
            edit({'action': 'patch', 'old_text': 'Plays banjo', 'content': 'Enjoys playing banjo'})
            source = notes.read(owner['uuid'])
            for name in ('Phat', 'Renamed Person'):
                owner['name'] = name
                profiles.save()
                vault = Path(sync(root / 'conversations/marionette.sqlite3', profiles.path, notes.directory)['vault'])
                mirrored = next((vault / 'Generated/Contacts').rglob('* - Notes.md'))
                target = re.search(r'\[Enjoys playing banjo\]\(([^)]+)\)', mirrored.read_text())[1]
                self.assertTrue((mirrored.parent / unquote(target)).is_file())
                self.assertNotIn(ref, mirrored.read_text())
                self.assertEqual(notes.read(owner['uuid']), source)
                self.assertIn('My impression:', mirrored.read_text())
            edit({'action': 'remove', 'old_text': f'[Enjoys playing banjo]({ref}).'})
            self.assertNotIn(ref, notes.read(owner['uuid']))
            self.assertIn('My impression:', notes.read(owner['uuid']))
