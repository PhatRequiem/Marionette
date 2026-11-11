"""Self identity persistence and prompt integration using isolated synthetic state."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from selfhood import Selfhood, UpdateSelf, INITIAL, INSTRUCTION
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
        reference = Path(__file__).resolve().parents[2] / 'docs/marionette-starting-sheet.md'
        self.assertEqual(reference.read_text().rstrip('\n'), INITIAL)
        state = self.store.read()
        self.assertLess(len(INITIAL), LIMIT)
        self.store.save('Synthetic self description.', INITIAL)
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
        tool = UpdateSelf(self.store, INITIAL)
        def call(**args): return json.loads(tool.call(json.dumps(args)))
        self.assertFalse(call(content='x'*(LIMIT+1))['success'])
        self.assertFalse(call(content='')['success'])
        self.assertFalse(call(content='x', uuid='changed')['success'])
        self.assertTrue(call(content='é'*LIMIT)['success'])
        self.store.save('external change', 'é'*LIMIT)
        self.assertFalse(call(content='stale')['success'])
        self.assertEqual(tool.content, 'external change')
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
                    'arguments': json.dumps({'content': 'Synthetic evolving self.'})}}]}, 'tool_calls')
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
            self.assertIn(INITIAL, captured[0]['messages'][0]['content'])
            self.assertEqual(captured[0]['messages'][0]['role'], 'system')
            self.assertTrue(json.loads(captured[1]['messages'][-1]['content'])['success'])
            convo.turn('visitor', source='discord', sender_id='123')
            convo.finish_preparation()
            self.assertEqual(captured[-1]['messages'][0]['content'], INSTRUCTION+'\n\nSynthetic evolving self.')
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
