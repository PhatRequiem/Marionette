"""Synthetic profile edits: protected fields, persistence and per-turn binding."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src/marionette'))
from contacts import ContactProfiles
from contact_profile import UpdateContactProfile
from conversation import Conversation


class ProfileToolTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.profiles = ContactProfiles(Path(temporary.name)/'profiles.json')
        self.owner = self.profiles.profiles[0]
        self.owner['linked_accounts'] = [{'service':'discord', 'account_id':'123'}]
        self.profiles.save()
        self.identity = self.profiles.resolve('terminal', self.owner['uuid'])
        self.tool = UpdateContactProfile(self.profiles, self.identity)

    def call(self, **fields):
        return json.loads(self.tool.call(json.dumps(fields)))

    def test_save_reload_clear_and_protected_identity(self):
        before = copy.deepcopy(self.owner)
        self.assertIsNone(self.identity['preferred_name'])
        self.assertTrue(self.call(name='Example', preferred_name='Jack', timezone='America/New_York')['success'])
        for field in ('uuid', 'linked_accounts', 'created_at', 'terminal_enabled'):
            self.assertEqual(self.owner[field], before[field])
        self.assertNotEqual(self.owner['updated_at'], before['updated_at'])
        self.assertEqual(self.profiles.data['owner_uuid'], before['uuid'])
        reloaded = ContactProfiles(self.profiles.path)
        self.assertEqual(reloaded.resolve('discord', '123')['preferred_name'], 'Jack')
        self.assertTrue(self.call(preferred_name=None, timezone=None)['success'])
        self.assertEqual(self.owner['name'], 'Example')
        self.assertIsNone(self.profiles.resolve('discord','123')['preferred_name'])

    def test_invalid_fields_and_disk_failure_leave_registry_unchanged(self):
        self.profiles.add('Taken')
        before = copy.deepcopy(self.profiles.data)
        raw = self.profiles.path.read_bytes()
        cases = [{}, {'uuid':'other'}, {'linked_accounts':[]}, {'created_at':'now'},
                 {'updated_at':'now'}, {'owner_uuid':'other'}, {'terminal_enabled':False},
                 {'name':'taken'}, {'name':''}, {'name':None}, {'preferred_name':''},
                 {'timezone':'not/a-zone'}, {'name':'Changed','contact_uuid':'other'}]
        for fields in cases:
            with self.subTest(fields=fields):
                self.assertFalse(self.call(**fields)['success'])
                self.assertEqual(self.profiles.data, before)
                self.assertEqual(self.profiles.path.read_bytes(), raw)
        with patch('contacts.os.replace', side_effect=OSError('synthetic failure')):
            self.assertFalse(self.call(preferred_name='Jack')['success'])
        self.assertEqual(self.profiles.data, before)
        self.assertEqual(self.profiles.path.read_bytes(), raw)

    def test_conversation_rebinds_and_next_turn_supplies_saved_preference(self):
        class API:
            closing = threading.Event()
            def count(self, messages): return 20
            def reply(self, messages, reserve, **kwargs):
                self.sent = messages
                return 'answer', 'stop'
        api = API()
        convo = Conversation(api, 8192, self.profiles, self.owner)
        def tool(): return next(t for t in api.tools if t.name == 'update_contact_profile')
        with patch('diagnostics.log'):
            convo.turn('call me Jack'); convo.pending.result()
            self.assertTrue(json.loads(tool().call('{"preferred_name":"Jack"}'))['success'])
            convo.turn('hello', source='discord', sender_id='123'); convo.pending.result()
            metadata = json.loads(api.sent[-1]['content'].split('\n',1)[1].split('\n\nMessage:')[0])
            self.assertEqual(metadata['preferred_name'], 'Jack')
            convo.turn('visitor', source='discord', sender_id='456'); convo.pending.result()
            self.assertNotEqual(tool().contact_uuid, self.owner['uuid'])
            self.assertTrue(json.loads(tool().call('{"preferred_name":"Visitor"}'))['success'])
            self.assertEqual(self.owner['preferred_name'], 'Jack')
            self.assertEqual(self.profiles.resolve('discord','456')['preferred_name'], 'Visitor')

    def test_native_coordinator_rejects_protected_field_then_saves_preference(self):
        import httpx
        from openai import OpenAI
        from inference import API
        from test_coordination import response
        api = API('http://localhost')
        api.count = lambda messages: 20
        sent = []
        def handle(request):
            sent.append(json.loads(request.content))
            if len(sent) <= 2:
                fields = {'preferred_name':'Jack', 'uuid':'forbidden'} if len(sent) == 1 else {'preferred_name':'Jack'}
                return response({'tool_calls':[{'index':0, 'id':f'call_{len(sent)}',
                    'type':'function', 'function':{'name':'update_contact_profile',
                    'arguments':json.dumps(fields)}}]}, 'tool_calls')
            return response({'content':'Saved.'}, 'stop')
        sdk = OpenAI(base_url='http://localhost/v1', api_key='EMPTY',
            http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        self.addCleanup(sdk.close)
        convo = Conversation(api, 8192, self.profiles, self.owner)
        with patch('inference.OpenAI', return_value=sdk), patch('diagnostics.log'), patch('conversation.Preparation'):
            self.assertEqual(convo.turn('Call me Jack.'), ('Saved.', 'stop'))
        self.assertIn('## update_contact_profile', sent[0]['messages'][0]['content'])
        self.assertFalse(json.loads(sent[1]['messages'][-1]['content'])['success'])
        self.assertTrue(json.loads(sent[2]['messages'][-1]['content'])['success'])
        self.assertEqual(self.owner['preferred_name'], 'Jack')
        self.assertEqual(self.owner['uuid'], self.identity['contact_uuid'])
