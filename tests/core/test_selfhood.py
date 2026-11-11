"""Self identity persistence and prompt integration using isolated synthetic state."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from selfhood import Selfhood, UpdateSelf
from inference import API
from conversation import Conversation
from characters import Characters, LIMIT
from identity import Profiles


class SelfhoodTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / 'self/identity.json'
        self.store = Selfhood(self.path)

    def test_starting_reference_restore_and_revision_provenance(self):
        state = self.store.read()
        self.assertEqual(state['revisions'][-1]['name'], '')
        self.assertEqual(state['revisions'][-1]['content'], '')
        self.store.save('Synthetic self description.', state['revisions'][-1], name='Test')
        reopened = Selfhood(self.path).read()
        self.assertEqual(reopened['uuid'], state['uuid'])
        self.assertEqual(reopened['revisions'][0], state['revisions'][0])
        self.assertEqual(reopened['revisions'][1]['source'], 'update_self_character')
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        backup = self.root / 'restored/identity.json'
        backup.parent.mkdir()
        shutil.copy2(self.path, backup)
        self.assertEqual(Selfhood(backup).read(), reopened)

    def test_limits_stale_edits_and_failed_write_preserve_identity(self):
        tool = UpdateSelf(self.store, self.store.read()['revisions'][-1])
        def call(**args): return json.loads(tool.call(json.dumps(args)))
        self.assertFalse(call(content='x'*(LIMIT+1))['success'])
        self.assertTrue(call(content='')['success'])
        self.assertFalse(call(name='x'*81)['success'])
        self.assertFalse(call(name='bad\nname')['success'])
        self.assertFalse(call()['success'])
        self.assertFalse(call(content='x', uuid='changed')['success'])
        self.assertTrue(call(content='é'*LIMIT)['success'])
        self.store.save('external change', self.store.read()['revisions'][-1], name='External')
        self.assertFalse(call(content='stale')['success'])
        self.assertEqual(tool.current['content'], 'external change')
        before = self.path.read_bytes()
        with patch('selfhood.os.replace', side_effect=OSError('disk failure')):
            self.assertFalse(call(content='new')['success'])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(list(self.path.parent.glob('.self-*')))

    def test_system_refresh_across_sources_clear_rollover_and_real_tool_loop(self):
        import httpx
        from openai import OpenAI
        from test_coordination import response
        profiles = Profiles(self.root / 'identities/profiles.json')
        owner = profiles.profiles[0]
        chars = Characters(self.root / 'characters')
        api = API('http://localhost')
        captured = []
        # Exercise the real API/Coordinator path; only HTTP and tokenization are synthetic.
        def handle(request):
            body = json.loads(request.content)
            captured.append(body)
            if len(captured) == 1:
                return response({'tool_calls': [{'index': 0, 'id': 'self_edit', 'type': 'function',
                    'function': {'name': 'update_self_character',
                    'arguments': json.dumps({'content': 'Synthetic evolving self.', 'name': 'Test'})}}]}, 'tool_calls')
            return response({'content': 'Done.'}, 'stop')
        def make_sdk(**kwargs):
            return OpenAI(base_url='http://localhost/v1', api_key='EMPTY',
                          http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        counted = []
        def count(messages):
            full = api.body(messages)['messages']
            counted.append(full)
            return len(full)*10
        api.count = count
        convo = Conversation(api, 256, profiles, owner, chars, selfhood=self.store)
        with patch('inference.OpenAI', side_effect=make_sdk), patch('diagnostics.log'):
            convo.turn('synthetic edit request')
            convo.finish_preparation()
            self.assertFalse(any(m['role'] == 'system' for m in captured[0]['messages']))
            self.assertTrue(json.loads(captured[1]['messages'][-1]['content'])['success'])
            convo.turn('visitor', source='discord', sender_id='123')
            convo.finish_preparation()
            self.assertEqual(captured[-1]['messages'][0]['content'], 'Name: Test\n\nSynthetic evolving self.')
            convo.turn('/clear', source='discord', sender_id='123')
            convo.history = [{'role': role, 'content': 'old'} for _ in range(10)
                             for role in ('user', 'assistant')]
            convo.turn('after rollover', source='discord', sender_id='123')
            convo.finish_preparation()
        self.assertEqual(sum(m['role']=='system' for m in captured[-1]['messages']), 1)
        self.assertIn('Synthetic evolving self.', counted[-1][0]['content'])
        self.assertLess(len(convo.history), 20)
        self.assertEqual(chars.current(profiles.resolve('terminal', owner['uuid'])), '# Phat\n')
        self.assertTrue(all(m['role'] != 'system' for m in convo.history))

    def test_invalid_state_is_not_reinitialized(self):
        self.path.write_text('{broken')
        with self.assertRaises(ValueError): Selfhood(self.path)
        self.assertEqual(self.path.read_text(), '{broken')

    def test_partial_updates_clearing_and_migration(self):
        state = self.store.read()
        legacy = {'schema_version': 1, 'uuid': state['uuid'], 'revisions': [
            {'content': 'Historical description.', 'source': 'original',
             'created_at': state['revisions'][0]['created_at']}]}
        self.path.write_text(json.dumps(legacy))
        migrated = Selfhood(self.path)
        state = migrated.read()
        self.assertEqual(state['uuid'], legacy['uuid'])
        self.assertEqual(state['schema_version'], 2)
        self.assertEqual(state['revisions'][0]['content'], 'Historical description.')
        api = API('http://localhost')
        tool = migrated.bind(api)
        result = json.loads(tool.call(json.dumps({'name': 'New name'})))
        self.assertTrue(result['success'])
        self.assertEqual(result['content'], 'Historical description.')
        result = json.loads(tool.call(json.dumps({'content': ''})))
        self.assertEqual(result['name'], 'New name')
        self.assertEqual(migrated.bind(api).current['name'], 'New name')
        self.assertEqual(api.system_prompt, 'Name: New name')
        result = json.loads(tool.call(json.dumps({'name': ''})))
        self.assertTrue(result['success'])
        migrated.bind(api)
        self.assertIsNone(api.system_prompt)
        self.assertEqual(api.body([{'role': 'user', 'content': 'hi'}])['messages'],
                         [{'role': 'user', 'content': 'hi'}])
        self.assertEqual(migrated.read()['revisions'][0]['content'], 'Historical description.')
        self.assertEqual(Selfhood(self.path).read(), migrated.read())
