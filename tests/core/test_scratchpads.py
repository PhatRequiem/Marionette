"""Temporary working-state limits and native tool-loop integration."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from scratchpads import Scratchpads, UpdateScratchpad, LIMITS
from inference import API
from conversation import Conversation
from test_coordination import response


class ScratchpadTests(unittest.TestCase):
    def test_unicode_boundaries_clear_and_rejection_preserve_other_pads(self):
        pads = Scratchpads()
        tool = UpdateScratchpad(pads)
        for name, limit in LIMITS.items():
            result = json.loads(tool.call(json.dumps({'pad': name, 'content': 'é' * limit})))
            self.assertTrue(result['success'])
            before = pads.read()
            result = json.loads(tool.call(json.dumps({'pad': name, 'content': 'é' * (limit + 1)})))
            self.assertFalse(result['success'])
            self.assertEqual(pads.read(), before)
        for args in ({'pad': '../soul', 'content': 'x'}, {'pad': 'focus', 'content': 2},
                     {'pad': 'focus', 'content': '\x00'}, {'pad': 'focus'},
                     {'pad': 'focus', 'content': 'x', 'extra': True}):
            before = pads.read()
            self.assertFalse(json.loads(tool.call(json.dumps(args)))['success'])
            self.assertEqual(pads.read(), before)
        self.assertTrue(json.loads(tool.call('{"pad":"focus","content":""}'))['success'])
        self.assertEqual(pads.contents['focus'], '')
        self.assertEqual(len(pads.contents['working_space']), 3000)
        self.assertEqual(Scratchpads().contents, dict.fromkeys(LIMITS, ''))
        pads.clear()
        self.assertEqual(pads.contents, dict.fromkeys(LIMITS, ''))

    def test_real_coordinator_edits_reads_and_refreshes_next_conversation(self):
        pads = Scratchpads()
        api = API('http://localhost')
        api.count = lambda messages: 20
        pads.bind(api)
        conversation = Conversation(api, 8192, scratchpads=pads)
        sent = []
        def handle(request):
            sent.append(json.loads(request.content))
            n = len(sent)
            if n in (1, 2):
                name = 'update_scratchpad' if n == 1 else 'read_scratchpads'
                args = '{"pad":"focus","content":"Synthetic task"}' if n == 1 else '{}'
                return response({'tool_calls': [{'index': 0, 'id': f'call_{n}', 'type': 'function',
                                 'function': {'name': name, 'arguments': args}}]}, 'tool_calls')
            return response({'content': 'Done.'}, 'stop')
        def sdk(**kwargs):
            return OpenAI(base_url='http://localhost/v1', api_key='EMPTY',
                          http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        with patch('inference.OpenAI', side_effect=sdk), patch('conversation.Preparation'), patch('diagnostics.write'):
            conversation.turn('Set your focus')
            self.assertEqual(pads.contents['focus'], 'Synthetic task')
            self.assertIn('Synthetic task', sent[2]['messages'][-1]['content'])
            conversation.turn('/clear')
            self.assertEqual(pads.contents['focus'], 'Synthetic task')
            conversation.turn('Review', source='discord', sender_id='synthetic')
        self.assertIn('Synthetic task', sent[-1]['messages'][0]['content'])
        self.assertEqual({t['function']['name'] for t in sent[0]['tools']},
                         {'read_scratchpads', 'update_scratchpad'})
        pads.clear()
        self.assertNotIn('Synthetic task', api.with_system([])[0]['content'])
