"""Idle scheduling, contact scoping, cancellation and bounded native tool use."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import httpx
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from thinking import ThinkingCycle, CycleInterrupted
from conversation import Conversation
from inference import API
from contacts import ContactProfiles
from contact_notes import ContactNotes
from soul import Soul
from scratchpads import Scratchpads
from storage import Store
from test_coordination import response


class ThinkingTests(unittest.TestCase):
    def test_schedule_wait_continue_disable_and_invalid_results(self):
        now = [0]
        cycle = ThinkingCycle(lambda: now[0])
        self.assertFalse(cycle.ready())
        now[0] = 30
        self.assertTrue(cycle.ready())
        self.assertEqual(cycle.complete('{"action":"continue","summary":"Next"}'), 'Next')
        self.assertFalse(cycle.ready())
        now[0] = 60
        self.assertTrue(cycle.ready())
        cycle.complete('{"action":"wait","summary":"No work"}')
        now[0] = 999
        self.assertFalse(cycle.ready())
        cycle.wake('discord', '123', 'discord:456')
        self.assertEqual(cycle.message_id, 'discord:456')
        cycle.command('off')
        now[0] += 30
        self.assertFalse(cycle.ready())
        cycle.command('on')
        now[0] += 30
        self.assertTrue(cycle.ready())
        for value in ('not json', '[]', '{}', '{"action":"continue","summary":null}'):
            cycle.complete(value)
            self.assertTrue(cycle.waiting)

    def test_input_priority_and_deadline_restore_api(self):
        now = [0]
        cycle = ThinkingCycle(lambda: now[0])
        now[0] = 31
        conversation = Mock(api=API('http://localhost'))
        self.assertIsNone(cycle.run(conversation, lambda: True))
        conversation.turn.assert_not_called()
        def turn(*args, **kwargs):
            now[0] += 31
            conversation.api.cycle_check()
        conversation.turn.side_effect = turn
        self.assertIn('time limit', cycle.run(conversation, lambda: False))
        self.assertTrue(cycle.waiting)
        self.assertIsNone(conversation.api.cycle_check)
        self.assertFalse(conversation.api.cycle_active)

    def test_all_tools_bound_real_loop_and_no_fake_user_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profiles = ContactProfiles(root/'contacts/profiles.json')
            owner = profiles.profiles[0]
            notes, soul = ContactNotes(root/'contact_notes'), Soul(root/'soul/profile.json')
            store = Store(root/'conversations/test.sqlite3')
            self.addCleanup(store.db.close)
            session = store.start()
            now = [0]
            cycle = ThinkingCycle(lambda: now[0])
            api = API('http://localhost')
            api.count = lambda messages: 30
            pads = Scratchpads()
            conversation = Conversation(api, 8192, profiles, owner, notes, store, session, soul, pads, cycle)
            sent = []
            def handle(request):
                sent.append(json.loads(request.content))
                if len(sent) == 1:
                    return response({'tool_calls': [{'index': 0, 'id': 'call_pad', 'type': 'function',
                        'function': {'name': 'update_scratchpad', 'arguments': '{"pad":"focus","content":"Review complete"}'}}]}, 'tool_calls')
                return response({'content': '{"action":"wait","summary":"Updated focus."}'}, 'stop')
            sdk = OpenAI(base_url='http://localhost/v1', api_key='EMPTY',
                         http_client=httpx.Client(transport=httpx.MockTransport(handle)))
            now[0] = 31
            with patch('inference.OpenAI', return_value=sdk), patch('diagnostics.write'):
                self.assertEqual(cycle.run(conversation, lambda: False), 'Updated focus.')
            self.assertTrue(cycle.waiting)
            self.assertEqual(pads.contents['focus'], 'Review complete')
            self.assertEqual({t['function']['name'] for t in sent[0]['tools']},
                             {'update_soul', 'update_contact_notes', 'query_logs', 'read_scratchpads', 'update_scratchpad'})
            self.assertEqual(sent[0]['max_tokens'], 2048)
            self.assertIn('Internal thinking cycle', sent[0]['messages'][0]['content'])
            self.assertEqual(store.db.execute("SELECT count(*) FROM messages WHERE role='user' AND kind='input'").fetchone()[0], 0)
            self.assertEqual(store.db.execute("SELECT count(*) FROM messages WHERE kind='cycle_result'").fetchone()[0], 1)
            self.assertEqual(len(conversation.histories), 1)
            self.assertIsNone(conversation.pending)
            self.assertFalse(api.cycle_active)
            self.assertNotIn('Internal thinking cycle', api.with_system([])[0]['content'])

    def test_incoming_input_cancels_stream_before_edit_and_retains_history(self):
        pads = Scratchpads()
        api = API('http://localhost')
        pads.bind(api)
        api.count = lambda messages: 20
        checks = []
        def cancel_on_stream():
            checks.append(True)
            if len(checks) >= 2:
                raise CycleInterrupted('New input')
        api.cycle_check = cancel_on_stream
        def handle(request):
            return response({'tool_calls': [{'index': 0, 'id': 'call_cancel', 'type': 'function',
                             'function': {'name': 'update_scratchpad',
                                          'arguments': '{"pad":"focus","content":"wrong"}'}}]}, 'tool_calls')
        sdk = OpenAI(base_url='http://localhost/v1', api_key='EMPTY',
                     http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        conversation = Conversation(api, 8192, scratchpads=pads)
        previous = [{'role': 'user', 'content': 'Keep this'}, {'role': 'assistant', 'content': 'Kept'}]
        conversation.history = previous.copy()
        with patch('inference.OpenAI', return_value=sdk), patch('diagnostics.write'):
            with self.assertRaises(CycleInterrupted):
                conversation.turn('Internal test', internal=True)
        self.assertEqual(conversation.history, previous)
        self.assertEqual(pads.contents['focus'], '')

    def test_model_request_and_tool_dispatch_caps(self):
        from coordination import Coordinator
        coordinator = object.__new__(Coordinator)
        coordinator.check = lambda: None
        coordinator.tool_number = 8
        with self.assertRaisesRegex(RuntimeError, 'tool-call limit'):
            coordinator._call_tool('read_scratchpads', '{}')
        api = API('http://localhost')
        pads = Scratchpads()
        pads.bind(api)
        api.count = lambda messages: 20
        api.cycle_check = lambda: None
        api.cycle_active = True
        calls = []
        def handle(request):
            calls.append(request)
            return response({'tool_calls': [{'index': 0, 'id': f'call_{len(calls)}', 'type': 'function',
                             'function': {'name': 'read_scratchpads', 'arguments': '{}'}}]}, 'tool_calls')
        sdk = OpenAI(base_url='http://localhost/v1', api_key='EMPTY',
                     http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        with patch('inference.OpenAI', return_value=sdk), patch('diagnostics.write'):
            with self.assertRaisesRegex(RuntimeError, 'model-call limit'):
                api.reply([{'role': 'user', 'content': 'Internal test'}], 2048)
        self.assertEqual(len(calls), 4)
        self.assertIsNone(api.response_messages)
