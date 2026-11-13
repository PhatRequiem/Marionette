"""Tool summaries report explicit outcomes without exposing payloads."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from threading import Event

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from coordination import Coordinator, tool_action, tool_outcome
from log_view import render
from test_coordination import EchoTool


class ToolSummaryTests(unittest.TestCase):
    def test_contract_outcomes(self):
        for name in ('update_soul', 'update_contact_notes'):
            self.assertEqual(tool_outcome(name, '{"success":true}'), 'Success')
            self.assertEqual(tool_outcome(name, '{"success":false}'), 'Failed')
            self.assertEqual(tool_outcome(name, '{"success":"true"}'), 'Returned (unverified)')
        for name in ('query_logs', 'read_vault'):
            for status, label in [('ok', 'Success'), ('partial', 'Partial'), ('error', 'Failed'),
                                  ('unavailable', 'Unavailable'), ('no_matches', 'No matches')]:
                self.assertEqual(tool_outcome(name, json.dumps({'status': status})), label)
        for value in ('broken', '[]', 'null', '{"status":[]}', '{"status":"unexpected"}'):
            self.assertEqual(tool_outcome('read_vault', value), 'Returned (unverified)')
        self.assertEqual(tool_outcome('unknown', '{"status":"ok"}'), 'Returned (unverified)')

    def test_labels_do_not_copy_user_arguments(self):
        self.assertEqual(tool_action('read_vault', '{"action":"search","query":"private"}'), 'search')
        for value in ('null', '[]', 'bad', '{"action":"private"}', '{"action":[]}'):
            self.assertIsNone(tool_action('read_vault', value))

    def test_framework_and_raised_failures_keep_correlated_summaries(self):
        tool = EchoTool()
        agent = Coordinator({'model': 'synthetic', 'model_server': 'http://localhost:1234/v1'}, [tool], Event())
        agent.protocol_tool_id = 'call_123'
        agent.request_number = 2
        for error in (ValueError('private details'), RuntimeError('private details')):
            with patch.object(tool, 'call', side_effect=error), patch('diagnostics.log') as log:
                result = agent._call_tool(tool.name)
            self.assertIn('An error occurred', result)
            rows = [c.args[0] for c in log.call_args_list if 'summary: ' in c.args[0]]
            self.assertEqual(len(rows), 2)
            self.assertIn('"outcome": "Failed"', rows[-1])
            self.assertIn('"protocol_tool_call_id": "call_123"', rows[-1])
            self.assertNotIn('private details', ''.join(rows))
        agent.closing.set()
        with patch('diagnostics.log') as log, self.assertRaises(RuntimeError):
            agent._call_tool(tool.name)
        self.assertTrue(any('"outcome": "Failed"' in c.args[0] for c in log.call_args_list))

    def test_render_and_metadata_preserve_ids(self):
        item = {'name': 'read_vault', 'action': 'search', 'request': 2, 'tool': 1,
                'protocol_tool_call_id': 'call_123', 'outcome': 'Unavailable'}
        output = io.StringIO()
        raw = 'Client: [message test:1] [request 02] [tool 01] Tool result summary: ' + json.dumps(item)
        line = json.dumps({'kind': 'tool_result_summary', 'raw': raw}) + '\n'
        render(io.StringIO(line), output, 'reasoning', False)
        for text in ('[Result]', 'read_vault', 'Unavailable', 'Model request 2', 'Tool call 1', 'call_123'):
            self.assertIn(text, output.getvalue())
