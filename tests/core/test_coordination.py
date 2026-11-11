"""Real Qwen-Agent tool orchestration over synthetic local HTTP responses."""
import io
import json
import tempfile
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAI
from qwen_agent.tools import BaseTool

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from inference import API
from conversation import Conversation


class EchoTool(BaseTool):
    name = 'synthetic_echo'
    description = 'Returns the supplied synthetic value.'
    parameters = {'type': 'object', 'properties': {'value': {'type': 'string', 'description': 'Value'}},
                  'required': ['value']}

    def __init__(self):
        super().__init__()
        self.calls = []

    def call(self, params, **kwargs):
        value = self._verify_json_format_args(params)['value']
        self.calls.append(value)
        return 'tool result: ' + value


def response(delta, finish):
    event = {'choices': [{'delta': delta, 'finish_reason': finish}],
             'usage': {'prompt_tokens': 20, 'completion_tokens': 4, 'total_tokens': 24}}
    return httpx.Response(200, headers={'content-type': 'text/event-stream'},
        text='data: ' + json.dumps(event) + '\n\ndata: [DONE]\n\n')


class CoordinationTests(unittest.TestCase):
    def run_turn(self, *, name='synthetic_echo', finish='tool_calls', budget_failure=False, exhausted=False):
        tool = EchoTool()
        api = API('http://localhost', tools=[tool])
        counts = []
        def count(messages):
            counts.append(messages)
            if budget_failure and any(m['role'] == 'tool' for m in messages):
                return 8192
            return 20
        api.count = count
        sent = []
        def handle(request):
            sent.append(json.loads(request.content))
            if len(sent) == 1:
                return response({'reasoning_content': 'Private thought.', 'content': 'Checking.',
                    'tool_calls': [{'index': 0, 'id': 'call_1', 'type': 'function',
                        'function': {'name': name, 'arguments': '{"value":"test"}'}}]}, finish)
            return response({'reasoning_content': 'Another thought.', 'content': 'Final answer.'}, 'stop')
        sdk = OpenAI(base_url='http://localhost/v1', api_key='EMPTY',
            http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        conversation = Conversation(api, 8192)
        received = []
        self.log_records = []
        with patch('inference.OpenAI', return_value=sdk), patch('diagnostics.write', side_effect=self.log_records.append), patch('conversation.Preparation'):
            if name != tool.name or finish != 'tool_calls' or budget_failure or exhausted:
                with self.assertRaises((RuntimeError, ValueError)):
                    conversation.turn('test', on_delta=lambda *x: received.append(x), message_id='discord:1234')
                self.assertEqual(conversation.history, [])
            else:
                self.assertEqual(conversation.turn('test', on_delta=lambda *x: received.append(x), message_id='discord:1234'),
                                 ('Final answer.', 'stop'))
                self.assertEqual(conversation.history,
                    [{'role': 'user', 'content': 'test'}, {'role': 'assistant', 'content': 'Final answer.'}])
                self.assertEqual([x for x in received if x[0] == 'answer'], [('answer', 'Final answer.')])
                self.assertEqual(''.join(x[1] for x in received if x[0] == 'reasoning'),
                                 'Private thought.Another thought.')
                self.assertEqual(sent[1]['messages'][-1],
                    {'role': 'tool', 'content': 'tool result: test', 'tool_call_id': 'call_1'})
                self.assertEqual(sent[0]['tools'][0]['function']['name'], tool.name)
                self.assertFalse(any(m['role'] == 'system' for m in sent[0]['messages']))
                self.assertEqual(tool.calls, ['test'])
        return tool, sent

    def test_tool_result_returns_to_model_and_only_final_answer_enters_history(self):
        self.run_turn()
        text = b''.join(self.log_records).decode()
        prefix = 'Client: [message discord:1234] '
        self.assertIn(prefix + '[request 01] ---------- MODEL REQUEST START', text)
        self.assertIn(prefix + '[request 01] ---------- MODEL REQUEST END | completed', text)
        self.assertIn(prefix + '[request 01] [tool 01] ---------- TOOL CALL START', text)
        self.assertIn('"protocol_tool_call_id": "call_1"', text)
        self.assertIn(prefix + '[request 02] ---------- MODEL REQUEST START', text)
        self.assertIn(prefix + '[request 02] ---------- MODEL REQUEST END | completed', text)
        self.assertIn(prefix + 'Reply completed:', text)
        # End-to-end routed logs remain readable by the disconnected snapshot reader.
        from log_router import route
        from log_snapshot import snapshot
        with tempfile.TemporaryDirectory() as directory:
            server = Path(directory) / 'synthetic-server.txt'
            model = Path(directory) / 'synthetic-model.txt'
            with server.open('wb') as a, model.open('wb') as b:
                route(io.BytesIO(b''.join(self.log_records)), a, b)
            report = snapshot([server, model], 'discord:1234', 'terminal:local')
            self.assertEqual([x['model_request_id'] for x in report['model_requests']],
                ['discord:1234/request-01', 'discord:1234/request-02'])
            calls = [x for x in report['operations'] if x['event'] == 'identity']
            self.assertEqual(calls[0]['model_request_id'], 'discord:1234/request-01')
            self.assertEqual(calls[0]['tool_call_id'], 'discord:1234/tool-01')
            self.assertEqual(calls[0]['protocol_tool_call_id'], 'call_1')
            self.assertIn('[message discord:1234] [request 01] [tool 01] [TOOL CALL START]', server.read_text())

    def test_unknown_tool_never_executes(self):
        tool, sent = self.run_turn(name='not_registered')
        self.assertEqual(tool.calls, [])
        self.assertEqual(len(sent), 1)
        self.assertIn(b'TOOL CALL END | failed', b''.join(self.log_records))

    def test_incomplete_tool_stream_never_executes(self):
        tool, sent = self.run_turn(finish=None)
        self.assertEqual(tool.calls, [])
        self.assertIn(b'MODEL REQUEST END | failed', b''.join(self.log_records))
        self.assertNotIn(b'TOOL CALL START', b''.join(self.log_records))

    def test_tool_result_over_budget_does_not_send_next_request(self):
        tool, sent = self.run_turn(budget_failure=True)
        self.assertEqual(tool.calls, ['test'])
        self.assertEqual(len(sent), 1)
        self.assertIn(b'[request 02] ---------- MODEL REQUEST END | failed', b''.join(self.log_records))

    def test_truncated_tool_stream_never_executes(self):
        tool, sent = self.run_turn(finish='length')
        self.assertEqual(tool.calls, [])

    def test_exhausted_loop_is_not_reported_as_a_completed_answer(self):
        with patch('qwen_agent.agents.fncall_agent.MAX_LLM_CALL_PER_RUN', 1):
            tool, sent = self.run_turn(exhausted=True)
        self.assertEqual(tool.calls, ['test'])
        self.assertEqual(len(sent), 1)

    def test_tool_service_failure_becomes_a_recoverable_turn_error(self):
        from qwen_agent.tools.base import ToolServiceError
        with patch.object(EchoTool, 'call', side_effect=ToolServiceError(message='Synthetic failure')):
            tool, sent = self.run_turn(exhausted=True)
        self.assertEqual(len(sent), 1)
        self.assertIn(b'TOOL CALL END | failed', b''.join(self.log_records))

    def test_multiple_calls_of_same_tool_have_distinct_ids(self):
        tool = EchoTool()
        api = API('http://localhost', tools=[tool])
        api.count = lambda messages: 20
        sent, logs = [], []
        def handle(request):
            sent.append(json.loads(request.content))
            if len(sent) == 1:
                return response({'tool_calls': [
                    {'index': n, 'id': f'wire_{n}', 'type': 'function',
                     'function': {'name': tool.name, 'arguments': json.dumps({'value': str(n)})}}
                    for n in range(2)]}, 'tool_calls')
            return response({'content': 'done'}, 'stop')
        sdk = OpenAI(base_url='http://localhost/v1', api_key='EMPTY',
            http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        with patch('inference.OpenAI', return_value=sdk), patch('diagnostics.write', side_effect=logs.append), patch('conversation.Preparation'):
            Conversation(api, 8192).turn('synthetic', message_id='discord:1234')
        text = b''.join(logs).decode()
        for n in range(2):
            self.assertIn(f'[request 01] [tool {n+1:02d}] Tool call identity: {{"name": "synthetic_echo", "protocol_tool_call_id": "wire_{n}"}}', text)
        self.assertEqual(tool.calls, ['0', '1'])
        self.assertEqual([m['tool_call_id'] for m in sent[1]['messages'] if m['role'] == 'tool'], ['wire_0', 'wire_1'])

    def test_returned_framework_error_is_not_logged_as_tool_success(self):
        with patch.object(EchoTool, 'call', side_effect=ValueError('synthetic recoverable error')):
            # The real framework returns ordinary exceptions as tool text.
            self.run_turn(exhausted=True, budget_failure=True)
        text = b''.join(self.log_records)
        self.assertIn(b'TOOL CALL END | returned', text)
        self.assertNotIn(b'TOOL CALL END | completed', text)
