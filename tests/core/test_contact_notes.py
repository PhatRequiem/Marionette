"""Private, bounded contact notes; synthetic identities and tool calls only."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from contact_notes import ContactNotes, UpdateContactNotes, LIMIT, DELIMITER, split_notes
from contacts import ContactProfiles
from conversation import Conversation


class CharacterTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.profiles = ContactProfiles(self.root / 'contacts/profiles.json')
        self.owner = self.profiles.profiles[0]
        self.owner['linked_accounts'] = [{'service': 'discord', 'account_id': '123'}]
        self.profiles.save()
        self.identity = self.profiles.resolve('terminal', self.owner['uuid'])
        self.store = ContactNotes(self.root / 'contact_notes')
        self.initial = self.store.current(self.identity)
        self.tool = UpdateContactNotes(self.store, self.identity, self.initial)

    def call(self, **kwargs):
        with patch('diagnostics.log'):
            return json.loads(self.tool.call(json.dumps(kwargs)))

    def test_boundary_unicode_persistence_and_same_format_restore(self):
        entry = 'é' * (LIMIT - len('# Phat' + DELIMITER))
        text = '# Phat' + DELIMITER + entry
        self.assertEqual(len(text), LIMIT)
        self.assertTrue(self.call(action='add', content=entry)['success'])
        saved = self.store.path(self.owner['uuid']).read_bytes()
        self.assertFalse(self.call(action='patch', old_text=entry, content=entry + 'é')['success'])
        self.assertEqual(self.store.path(self.owner['uuid']).read_bytes(), saved)
        self.assertEqual(self.store.path(self.owner['uuid']).stat().st_mode & 0o777, 0o600)
        copy = self.root / 'restored'
        shutil.copytree(self.root / 'contact_notes', copy)
        self.assertEqual(ContactNotes(copy).current(self.identity), text)
        self.assertEqual(ContactNotes(self.root / 'contact_notes').current(self.identity), text)

    def test_cannot_choose_other_person_path_or_identity_fields(self):
        other = self.profiles.add('Other')
        other_identity = self.profiles.resolve('terminal', other['uuid'])
        original = self.store.current(other_identity)
        registry = self.profiles.path.read_bytes()
        for key in ('contact_uuid', 'path', 'discord_id'):
            self.assertFalse(self.call(action='add', content='changed', **{key: other['uuid']})['success'])
        self.assertEqual(self.store.current(other_identity), original)
        self.assertEqual(self.profiles.path.read_bytes(), registry)
        self.assertEqual(self.store.current(self.identity), self.initial)
        with self.assertRaises(ValueError):
            self.store.read('../outside')

    def test_symlinks_and_invalid_files_are_not_followed_or_overwritten(self):
        path = self.store.path(self.owner['uuid'])
        outside = self.root / 'outside.txt'
        outside.write_text('outside')
        path.unlink()
        path.symlink_to(outside)
        self.assertFalse(self.call(action='add', content='changed')['success'])
        self.assertEqual(outside.read_text(), 'outside')
        path.unlink()
        path.write_text('x' * (LIMIT + 1))
        with self.assertRaises(ValueError):
            self.store.current(self.identity)
        self.assertFalse(self.call(action='add', content='changed')['success'])
        self.assertEqual(path.read_text(), 'x' * (LIMIT + 1))

    def test_stale_update_retries_and_disk_failure_preserves_previous_text(self):
        self.store.save(self.owner['uuid'], '# Phat\nManual edit.', expected=self.initial)
        self.assertFalse(self.call(action='add', content='New fact.')['success'])
        self.assertTrue(self.call(action='add', content='New fact.')['success'])
        current = self.store.current(self.identity)
        with patch('contact_notes.os.replace', side_effect=OSError('synthetic disk failure')):
            self.assertFalse(self.call(action='add', content='new')['success'])
        self.assertEqual(self.store.current(self.identity), current)
        self.assertFalse(list(self.store.directory.glob('.character-*')))

    def test_current_sender_binding_refresh_and_clear_preserves_notes(self):
        class API:
            closing = threading.Event()
            def count(self, messages): return 20
            def reply(self, messages, reserve, **kwargs):
                self.sent = messages
                return 'answer', 'stop'
        api = API()
        convo = Conversation(api, 8192, self.profiles, self.owner, self.store)
        def metadata():
            return json.loads(api.sent[-1]['content'].split('\n', 1)[1].split('\n\nMessage:\n')[0])
        with patch('diagnostics.log'):
            convo.turn('hello')
            convo.pending.result()
            self.assertEqual(metadata()['contact_notes']['content'], self.initial)
            result = json.loads(api.tools[0].call(json.dumps({'action': 'add', 'content': 'Prefers brief answers.'})))
            self.assertTrue(result['success'])
            convo.turn('hello again', source='discord', sender_id='123')
            convo.pending.result()
            self.assertIn('brief answers', metadata()['contact_notes']['content'])
            self.assertEqual(api.tools[0].contact_uuid, self.owner['uuid'])
            convo.turn('/clear', source='discord', sender_id='123')
            self.assertEqual(convo.history, [])
            other = self.profiles.add('Other')
            convo.terminal_profile = other
            convo.turn('different person')
            convo.pending.result()
            self.assertNotIn('brief answers', metadata()['contact_notes']['content'])
            self.assertEqual(api.tools[0].contact_uuid, other['uuid'])
            self.assertIn('brief answers', self.store.current(self.identity))
            convo.turn('visitor', source='discord', sender_id='456')
            convo.pending.result()
            self.assertNotEqual(api.tools[0].contact_uuid, self.owner['uuid'])
            self.assertNotIn('brief answers', metadata()['contact_notes']['content'])

    def test_profile_is_resupplied_after_history_rollover_and_counted(self):
        class API:
            closing = threading.Event()
            def count(self, messages): return len(messages) * 60
            def prepare(self, messages): pass
            def reply(self, messages, reserve, **kwargs):
                self.sent = messages
                return 'answer', 'stop'
        api = API()
        convo = Conversation(api, 256, self.profiles, self.owner, self.store)
        with patch('diagnostics.log'):
            for _ in range(4):
                convo.turn('hello')
                convo.pending.result()
                self.assertIn('contact_notes', api.sent[-1]['content'])
                self.assertLess(api.count(api.sent) + convo.reserve, 256)
            self.assertLess(len(convo.history), 8)

    def test_real_coordinator_rejects_oversize_then_saves_corrected_notes(self):
        import httpx
        from openai import OpenAI
        from inference import API
        from test_coordination import response
        api = API('http://localhost')
        api.count = lambda messages: 20
        sent = []
        notes = '# Phat' + DELIMITER + 'Enjoys antique maps.'
        def handle(request):
            sent.append(json.loads(request.content))
            if len(sent) <= 2:
                content = 'x' * (LIMIT + 1) if len(sent) == 1 else 'Enjoys antique maps.'
                return response({'tool_calls': [{'index': 0, 'id': f'call_{len(sent)}',
                    'type': 'function', 'function': {'name': 'update_contact_notes',
                    'arguments': json.dumps({'action': 'add', 'content': content})}}]}, 'tool_calls')
            return response({'content': 'Saved.'}, 'stop')
        sdk = OpenAI(base_url='http://localhost/v1', api_key='EMPTY',
            http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        self.addCleanup(sdk.close)
        convo = Conversation(api, 8192, self.profiles, self.owner, self.store)
        with patch('inference.OpenAI', return_value=sdk), patch('diagnostics.log'), patch('conversation.Preparation'):
            self.assertEqual(convo.turn('I enjoy antique maps.'), ('Saved.', 'stop'))
        self.assertFalse(json.loads(sent[1]['messages'][-1]['content'])['success'])
        self.assertTrue(json.loads(sent[2]['messages'][-1]['content'])['success'])
        self.assertEqual(self.store.current(self.identity), notes)
        results = [json.loads(m['content']) for m in convo.history if m['role'] == 'function']
        self.assertEqual([r['success'] for r in results], [False, True])
        self.assertEqual(convo.history[-1]['content'], 'Saved.')

    def test_discord_registration_persists_and_failed_save_rolls_back(self):
        self.profiles.add('Discord 456')
        self.assertEqual(self.profiles.register_discord('00456'), '456')
        identity = self.profiles.resolve('discord', '456')
        self.assertEqual(identity['display_name'], 'Discord 456 (2)')
        reopened = ContactProfiles(self.profiles.path)
        reopened.register_discord('456')
        self.assertEqual(reopened.resolve('discord', '456'), identity)
        before = len(reopened.profiles)
        with patch.object(reopened, 'save', side_effect=OSError('synthetic failure')):
            with self.assertRaises(OSError):
                reopened.register_discord('789')
        self.assertEqual(len(reopened.profiles), before)
        for invalid in ('not-an-id', '0', '-1', str(2**64)):
            with self.assertRaises(ValueError):
                reopened.register_discord(invalid)

    def test_entries_add_patch_remove_preserve_other_notes_and_heading(self):
        self.assertTrue(self.call(action='add', content='Prefers short answers and green text.')['success'])
        self.assertTrue(self.call(action='add', content='Enjoys antique maps.')['success'])
        result = self.call(action='patch', old_text='short answers', content='detailed answers')
        self.assertTrue(result['success'])
        self.assertEqual(result['current_entries'], ['Prefers detailed answers and green text.', 'Enjoys antique maps.'])
        self.assertEqual(result['characters'], len(result['content']))
        result = self.call(action='remove', old_text='antique maps')
        self.assertTrue(result['success'])
        self.assertEqual(result['current_entries'], ['Prefers detailed answers and green text.'])
        self.assertFalse(self.call(action='patch', old_text='# Phat', content='# Other')['success'])
        self.assertTrue(self.call(action='remove', old_text='green text')['success'])
        self.assertEqual(self.store.current(self.identity), '# Phat\n')

    def test_ambiguous_missing_repeated_and_invalid_operations_leave_file_unchanged(self):
        for text in ('Likes maps.', 'Likes maps and maps.'):
            self.assertTrue(self.call(action='add', content=text)['success'])
        saved = self.store.path(self.owner['uuid']).read_bytes()
        invalid = [dict(action='patch', old_text='maps', content='books'),
                   dict(action='remove', old_text='missing'),
                   dict(action='patch', old_text='maps and maps', content=''),
                   dict(action='add', content='bad\n§\nentry'),
                   dict(action='add', content='Likes maps.'),
                   dict(action='replace', content='rewrite everything'),
                   dict(content='old whole-document request'),
                   dict(action='remove', old_text='Likes maps.', content='extra')]
        for args in invalid:
            with self.subTest(args=args):
                self.assertFalse(self.call(**args)['success'])
                self.assertEqual(self.store.path(self.owner['uuid']).read_bytes(), saved)
        # Exact whole-entry match wins even though another note contains it.
        self.assertTrue(self.call(action='add', content='Likes maps. Also books.')['success'])
        self.assertTrue(self.call(action='remove', old_text='Likes maps.')['success'])
        self.assertTrue(self.call(action='remove', old_text='Also books.')['success'])
        self.assertFalse(self.call(action='patch', old_text='maps', content='books')['success'])

    def test_legacy_paragraphs_migrate_without_fact_changes_and_restore(self):
        legacy = '# Phat\n\nFirst fact.\n\nSecond fact.\nContinued on another line.\n'
        self.store.save(self.owner['uuid'], legacy, expected=self.initial)
        self.tool = UpdateContactNotes(self.store, self.identity, legacy)
        self.assertEqual(self.store.current(self.identity), legacy)  # Read alone never rewrites.
        result = self.call(action='add', content='Third fact.')
        self.assertTrue(result['success'])
        self.assertEqual(result['current_entries'], ['First fact.', 'Second fact.\nContinued on another line.', 'Third fact.'])
        restored = self.root / 'restored-entries'
        shutil.copytree(self.store.directory, restored)
        self.assertEqual(ContactNotes(restored).read(self.owner['uuid']), result['content'])
        self.assertEqual(split_notes(result['content'])[1], result['current_entries'])
        # Blank lines inside a new single entry remain one entry on reopening.
        result = self.call(action='add', content='Multiline\n\nnote.')
        self.assertEqual(split_notes(self.store.current(self.identity))[1][-1], 'Multiline\n\nnote.')

    def test_conversion_overhead_cannot_bypass_limit_or_erase_legacy_notes(self):
        tail = '\n\nSecond fact.'
        first = 'a' * (LIMIT - len('# Phat\n\n') - len(tail))
        legacy = '# Phat\n\n' + first + tail
        self.store.save(self.owner['uuid'], legacy, expected=self.initial)
        self.tool = UpdateContactNotes(self.store, self.identity, legacy)
        result = self.call(action='patch', old_text='Second fact.', content='Second fact.')
        self.assertFalse(result['success'])
        self.assertIn('over the limit', result['error'])
        self.assertEqual(self.store.current(self.identity), legacy)
        result = self.call(action='patch', old_text=first, content=first[:-10])
        self.assertTrue(result['success'])
        self.assertEqual(result['current_entries'], [first[:-10], 'Second fact.'])
        self.assertLessEqual(result['characters'], LIMIT)
