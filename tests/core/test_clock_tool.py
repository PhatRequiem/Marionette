"""Clock contract and native tool dispatch, without real profiles or inference."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src/marionette'))
from clock_tool import GetCurrentTime
from coordination import tool_outcome


class ClockTests(unittest.TestCase):
    def test_fresh_utc_default(self):
        before = datetime.now(timezone.utc)
        result = json.loads(GetCurrentTime().call('{}'))
        after = datetime.now(timezone.utc)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['timezone'], 'UTC')
        instant = datetime.fromisoformat(result['current_time_utc'])
        self.assertLessEqual(before, instant)
        self.assertLessEqual(instant, after)
        self.assertEqual(result['current_time'], result['current_time_utc'])
        self.assertEqual(tool_outcome('get_current_time', result), 'Success')

    def test_daylight_saving_and_date_boundary(self):
        cases = [('2026-03-08T06:59:00+00:00', '2026-03-08T01:59:00-05:00', 'Sunday'),
                 ('2026-03-08T07:00:00+00:00', '2026-03-08T03:00:00-04:00', 'Sunday'),
                 ('2026-11-15T02:00:00+00:00', '2026-11-14T21:00:00-05:00', 'Saturday')]
        for utc, local, weekday in cases:
            with self.subTest(utc=utc), patch('clock_tool.datetime') as clock:
                clock.now.return_value = datetime.fromisoformat(utc)
                result = json.loads(GetCurrentTime().call('{"timezone":"America/New_York"}'))
                clock.now.assert_called_once_with(timezone.utc)
                self.assertEqual(result['current_time'], local)
                self.assertEqual(result['current_time_utc'], utc)
                self.assertEqual(result['weekday'], weekday)

    def test_invalid_input_never_falls_back(self):
        for args in ({'timezone':'No/SuchZone'}, {'timezone':None}, {'timezone':''},
                     {'timezone':'/etc/passwd'}, {'timezone':'../UTC'}, {'alarm':'tomorrow'}):
            with self.subTest(args=args):
                result = json.loads(GetCurrentTime().call(json.dumps(args)))
                self.assertEqual(result['status'], 'error')
                self.assertNotIn('current_time', result)
                self.assertEqual(tool_outcome('get_current_time', result), 'Failed')

    def test_native_tool_loop_returns_clock_and_guidance(self):
        import httpx
        from openai import OpenAI
        from inference import API
        from test_coordination import response
        api = API('http://localhost')
        api.tools = (GetCurrentTime(),)
        api.count = lambda messages: 20
        sent = []
        def handle(request):
            sent.append(json.loads(request.content))
            if len(sent) == 1:
                return response({'tool_calls':[{'index':0, 'id':'clock_call', 'type':'function',
                    'function':{'name':'get_current_time','arguments':'{"timezone":"UTC"}'}}]}, 'tool_calls')
            return response({'content':'Clock checked.'}, 'stop')
        sdk = OpenAI(base_url='http://localhost/v1', api_key='EMPTY',
                     http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        self.addCleanup(sdk.close)
        with patch('inference.OpenAI', return_value=sdk), patch('diagnostics.log'):
            api.reply([{'role':'user','content':'What time is it?'}], 1024)
        self.assertEqual(len(sent), 2)
        self.assertIn('## get_current_time', sent[0]['messages'][0]['content'])
        self.assertEqual(sent[0]['tools'][0]['function']['name'], 'get_current_time')
        self.assertEqual(json.loads(sent[1]['messages'][-1]['content'])['status'], 'ok')
