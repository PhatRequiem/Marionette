"""Qwen-Agent log access uses synthetic storage and actual framework dispatch."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from conversation import Conversation
from inference import API
from log_tool import QueryLogs
from storage import Store
from test_coordination import response


class LogToolTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'logs.sqlite3'
        self.store = Store(self.path)
        self.addCleanup(self.store.close)
        self.session = self.store.start()
        self.store.message(self.session, 'discord:123', 'discord:42', None, 'discord', '42',
                           'user', 'input', 'synthetic previous input', 'received')
        for text in ('========== MESSAGE START | processing ==========',
                     '========== MESSAGE END | processing | completed =========='):
            self.store.event(self.session, 'diagnostic',
                ('Client: [message discord:123] ' + text + '\n').encode())

    def test_real_agent_round_trip_and_rebinding(self):
        api = API('http://localhost')
        api.count = lambda messages: 20
        sent = []
        form = {'lookup': 'processing', 'target': 'previous_message'}
        def transport(request):
            sent.append(json.loads(request.content))
            if len(sent) == 1:
                return response({'tool_calls': [{'index': 0, 'id': 'query_1', 'type': 'function',
                    'function': {'name': 'query_logs', 'arguments': json.dumps(form)}}]}, 'tool_calls')
            facts = json.loads(sent[-1]['messages'][-1]['content'])
            self.assertEqual(facts['message_id'], 'discord:123')
            self.assertEqual(facts['data']['outcome'], 'completed')
            self.assertEqual(sent[-1]['messages'][-1]['tool_call_id'], 'query_1')
            return response({'content': 'Your previous message completed.'}, 'stop')
        sdk = OpenAI(base_url='http://localhost/v1', api_key='EMPTY',
            http_client=httpx.Client(transport=httpx.MockTransport(transport)))
        chat = Conversation(api, 8192, store=self.store, session_id=self.session)
        with patch('inference.OpenAI', return_value=sdk), patch('diagnostics.write'), patch('conversation.Preparation'):
            answer, finish = chat.turn('How was my previous message processed?', source='discord',
                                      sender_id='42', message_id='discord:124')
        self.assertEqual((answer, finish), ('Your previous message completed.', 'stop'))
        self.assertEqual(sent[0]['tools'][0]['function']['name'], 'query_logs')
        self.assertTrue(any(m['role'] == 'function' for m in chat.history))
        old = api.tools[0]
        chat.key = 'discord:99'
        chat.bind_log_query('discord:999')
        self.assertIsNot(old, api.tools[0])
        denied = api.tools[0].call(json.dumps({'lookup':'processing','target':'message_id','message_id':'discord:123'}))
        self.assertEqual(json.loads(denied)['status'], 'error')
        self.assertNotIn(str(self.path), denied)

    def test_extra_fields_cannot_override_bound_scope(self):
        tool = QueryLogs(database=self.path, session=self.session, conversation='discord:99', live=False)
        for extra in ({}, {'conversation':'discord:42'}, {'database':str(self.path)}, {'sql':'SELECT * FROM messages'}):
            result = tool.call(json.dumps({'lookup':'errors','target':'message_id','message_id':'discord:123',**extra}))
            self.assertEqual(json.loads(result)['status'], 'error')

    def test_setup_and_status_use_bound_sources(self):
        tool = QueryLogs(datasheet='synthetic-sheet', socket_path='synthetic-socket')
        with patch('log_tool.handle', return_value={'status':'ok'}) as handler:
            for form in ({'lookup':'setup','target':'startup'}, {'lookup':'status','target':'current'}):
                self.assertEqual(json.loads(tool.call(json.dumps(form)))['status'], 'ok')
                handler.assert_called_with(form, datasheet='synthetic-sheet', socket_path='synthetic-socket')
