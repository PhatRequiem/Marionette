"""Active-only retrieval boundaries, bounded evidence, and streaming tool dispatch."""
import base64
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from log_reader import LogReader, discord_registration
from log_store import append, record
from log_router import route
from inference import API


def stream(events):
    return io.BytesIO((''.join('data: ' + json.dumps(e) + '\n\n' for e in events)
                       + 'data: [DONE]\n\n').encode())


def delta(value, finish=None):
    return {'choices': [{'delta': value, 'finish_reason': finish}]}


def tool_stream(name='read_logs', arguments='{"topic":"errors"}'):
    return stream([
        delta({'reasoning_content': 'I will check.'}),
        delta({'tool_calls': [{'index': 0, 'id': 'call-1', 'type': 'function',
                              'function': {'name': name, 'arguments': arguments[:12]}}]}),
        delta({'tool_calls': [{'index': 0, 'function': {'arguments': arguments[12:]}}]}, 'tool_calls'),
        {'choices': [], 'usage': {'completion_tokens': 20}}])


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.chat = self.root / 'current-chat.jsonl'
        self.address = self.root / 'chat.sock'
        self.address.touch()  # Identity only; no connection is made by the reader.
        self.reader = LogReader(self.chat, self.address)

    def test_active_chat_only_and_arguments_cannot_select_files(self):
        append(self.chat, record('terminal', 'message_received', data={'content': 'current evidence'}))
        append(self.root / 'old-chat.jsonl', record('terminal', 'message_received', data={'content': 'old secret'}))
        result = self.reader.read({'topic': 'messages'})
        self.assertIn('current evidence', json.dumps(result))
        self.assertNotIn('old secret', json.dumps(result))
        for arguments in [{'source': '../old', 'view': 'recent'},
                          {'topic': 'reasoning', 'query': 'invented phrase'},
                          {'topic': 'messages', 'path': '/etc/passwd'},
                          {'topic': 'messages', 'limit': True}]:
            with self.assertRaises(ValueError):
                self.reader.read(arguments)
        self.chat.unlink()
        self.chat.symlink_to(self.root / 'old-chat.jsonl')
        self.assertFalse(self.reader.read({'topic': 'messages'})['available'])

    def test_diagnostic_batch_errors_have_original_references(self):
        server, model = io.BytesIO(), io.BytesIO()
        route(io.BytesIO(b'0.01 I srv decode: ordinary\n0.02 W future: warning\n0.03 E future: error\xff\n'), server, model)
        self.chat.with_name('current-model.jsonl').write_bytes(model.getvalue())
        result = self.reader.read({'topic': 'errors'})
        self.assertEqual([r['reference'] for r in result['records']], ['2', '3'])
        self.assertIn('warning', result['records'][0]['text'])
        self.assertTrue(result['untrusted_log_data'])

    def test_results_are_bounded_and_partial_lines_reported(self):
        for n in range(30):
            append(self.chat, record('terminal', 'answer', data={'content': str(n) + 'x' * 4000}))
        with self.chat.open('ab') as output:
            output.write(b'{"partial":')
        result = self.reader.read({'topic': 'messages', 'limit': 20})
        self.assertLessEqual(len(json.dumps(result, ensure_ascii=False)), 12000)
        self.assertTrue(result['more_matches'])
        self.assertTrue(all(r['truncated'] for r in result['records']))
        self.assertEqual(result['coverage'][0]['skipped_records'], 1)
        with patch('log_reader.TAIL_BYTES', 5000):
            result = self.reader.read({'topic': 'messages'})
            self.assertTrue(result['coverage'][0]['tail_limited'])

    def test_discord_registration_excludes_detached_and_other_session(self):
        path = self.root / 'active-discord.jsonl'
        append(path, record('discord', 'status', data={'message': 'Discord answer delivered.'}))
        request = {'topic': 'delivery'}
        self.assertFalse(self.reader.read(request)['available'])
        with discord_registration(self.address, path):
            self.assertTrue(self.reader.read(request)['available'])
            with patch('log_reader.socket_key', return_value=[-1, -1, -1]):
                self.assertFalse(self.reader.read(request)['available'])
        self.assertFalse(self.reader.read(request)['available'])

    def test_reasoning_topic_uses_chat_and_matches_original_question(self):
        append(self.chat, record('terminal', 'message_received', data={'content': 'blue bird', 'turn_id': 'turn'}))
        append(self.chat, record('terminal', 'reasoning', data={'content': 'Recorded thought.', 'turn_id': 'turn'}))
        append(self.chat, record('terminal', 'answer', data={'content': 'Different final answer.', 'turn_id': 'turn'}))
        result = self.reader.read({'topic': 'reasoning'})
        self.assertEqual(len(result['records']), 1)
        self.assertEqual(result['records'][0]['source'], 'chat')
        self.assertIn('Recorded thought.', result['records'][0]['text'])
        self.assertEqual(result['records'][0]['in_reply_to'], 'blue bird')
        self.assertNotIn('Different final answer.', result['records'][0]['text'])
        self.assertIn('Recorded generated reasoning', result['records'][0]['meaning'])

    def test_tokens_distinguish_prompt_snapshot_from_generation_usage(self):
        append(self.chat, record('terminal', 'usage', data={'prompt_tokens': 1381, 'completion_tokens': 272, 'total_tokens': 1653}))
        event = record('terminal', 'context', data={'prompt_tokens': 1656, 'context_capacity': 65536, 'reply_allowance': 32768})
        event['timestamp'] = '2026-11-09T15:12:48.000000-05:00'
        append(self.chat, event)
        result = self.reader.read({'topic': 'tokens'})
        summary = result['summary']
        self.assertIn('not a live meter', summary['measurement_scope'])
        self.assertEqual(summary['latest_completed_generation']['values']['total_tokens'], 1653)
        prompt = summary['latest_prompt_snapshot']
        self.assertEqual(prompt['values']['prompt_tokens'], 1656)
        self.assertEqual(prompt['values']['prompt_percent_of_capacity'], 2.53)
        self.assertEqual(prompt['values']['spare_after_reply_reserve_tokens'], 31111)
        self.assertEqual(prompt['timestamp_utc'], '2026-11-09T20:12:48+00:00')
        self.assertIn('before generation', prompt['meaning'])

    def test_errors_deduplicate_shared_diagnostics(self):
        server, model = io.BytesIO(), io.BytesIO()
        route(io.BytesIO(b'0.01 W test: warning\n'), server, model)
        self.chat.with_name('current-model.jsonl').write_bytes(model.getvalue())
        self.chat.with_name('current-server.jsonl').write_bytes(server.getvalue())
        result = self.reader.read({'topic': 'errors'})
        self.assertEqual(len(result['records']), 1)
        self.assertEqual(result['records'][0]['also_in'], ['model'])
        self.assertEqual(len(result['coverage']), 4)


class ToolTests(unittest.TestCase):
    def test_fragmented_call_is_executed_then_returned_as_tool_result(self):
        class Reader:
            def read(self, arguments):
                self.arguments = arguments
                return {'records': [{'reference': '17', 'text': 'test warning'}]}
        reader = Reader()
        api = API('http://127.0.0.1:1', reader, 8192)
        final = stream([delta({'reasoning_content': 'Found evidence.', 'content': 'Warning at 17.'}, 'stop')])
        visible = []
        with patch.object(api, 'open', side_effect=[tool_stream(), final]) as requests, patch.object(api, 'count', return_value=200), patch('diagnostics.log'):
            result = api.reply([{'role': 'user', 'content': 'Check logs'}], 100, on_delta=lambda *x: visible.append(x))
        self.assertEqual(result, ('Warning at 17.', 'stop'))
        self.assertEqual(reader.arguments, {'topic': 'errors'})
        body = requests.call_args_list[1].args[1]
        self.assertEqual(body['max_tokens'], 80)
        self.assertEqual(body['messages'][-1]['role'], 'tool')
        self.assertEqual(body['messages'][-1]['tool_call_id'], 'call-1')
        self.assertIn('test warning', body['messages'][-1]['content'])
        self.assertEqual(body['messages'][-2]['reasoning_content'], 'I will check.')
        self.assertTrue(any(phase == 'tool' for phase, _ in visible))
        self.assertEqual(body['tools'][0]['function']['name'], 'read_logs')

    def test_unknown_tool_is_not_executed(self):
        from unittest.mock import Mock
        reader = Mock()
        api = API('http://127.0.0.1:1', reader, 8192)
        final = stream([delta({'content': 'Cannot do that.'}, 'stop')])
        with patch.object(api, 'open', side_effect=[tool_stream(name='read_file'), final]) as request, patch.object(api, 'count', return_value=100), patch('diagnostics.log'):
            api.reply([], 100)
        reader.read.assert_not_called()
        self.assertIn('Only read_logs', request.call_args.args[1]['messages'][-1]['content'])

    def test_repeated_calls_stop_at_generation_budget(self):
        from unittest.mock import Mock
        reader = Mock()
        reader.read.return_value = {'records': []}
        api = API('http://127.0.0.1:1', reader, 8192)
        with patch.object(api, 'open', side_effect=[tool_stream() for _ in range(5)]) as request, patch.object(api, 'count', return_value=100), patch('diagnostics.log'):
            with self.assertRaisesRegex(RuntimeError, 'generation allowance'):
                api.reply([], 100)
        self.assertEqual(reader.read.call_count, 5)
        self.assertEqual(request.call_args.args[1]['tool_choice'], 'auto')
        self.assertEqual(request.call_args.args[1]['max_tokens'], 20)

    def test_followup_context_capacity_is_checked_before_generation(self):
        from unittest.mock import Mock
        reader = Mock()
        reader.read.return_value = {'records': []}
        api = API('http://127.0.0.1:1', reader, 100)
        with patch.object(api, 'open', return_value=tool_stream()) as request, patch.object(api, 'count', return_value=100), patch('diagnostics.log'):
            with self.assertRaisesRegex(RuntimeError, 'context'):
                api.reply([], 100)
        self.assertEqual(request.call_count, 1)

    def test_interrupted_call_never_executes(self):
        from unittest.mock import Mock
        reader = Mock()
        api = API('http://127.0.0.1:1', reader, 8192)
        partial = io.BytesIO(('data: ' + json.dumps(delta({'tool_calls': [{'index': 0,
            'id': 'partial', 'function': {'name': 'read_logs', 'arguments': '{'}}]})) + '\n').encode())
        with patch.object(api, 'open', return_value=partial), patch('diagnostics.log'):
            with self.assertRaisesRegex(RuntimeError, 'closed early'):
                api.reply([], 100)
        reader.read.assert_not_called()

    def test_tool_evidence_does_not_change_whole_exchange_history(self):
        from unittest.mock import Mock
        from conversation import Conversation
        reader = Mock()
        reader.read.return_value = {'records': []}
        api = API('http://127.0.0.1:1', reader, 8192)
        conversation = Conversation(api, 8192)
        final = stream([delta({'content': 'Checked.'}, 'stop')])
        with patch.object(api, 'open', side_effect=[tool_stream(), final]), patch.object(api, 'count', return_value=100), patch('diagnostics.log'):
            self.assertEqual(conversation.turn('Check logs'), ('Checked.', 'stop'))
            api.worker.join()
        self.assertEqual(conversation.history, [{'role': 'user', 'content': 'Check logs'},
                                               {'role': 'assistant', 'content': 'Checked.'}])

    def test_more_than_two_lookups_can_finish_with_an_answer(self):
        from unittest.mock import Mock
        reader = Mock()
        reader.read.return_value = {'records': []}
        api = API('http://127.0.0.1:1', reader, 8192)
        final = stream([delta({'content': 'Here are the findings.'}, 'stop')])
        with patch.object(api, 'open', side_effect=[tool_stream() for _ in range(4)] + [final]) as requests, patch.object(api, 'count', return_value=200) as count, patch('diagnostics.log'):
            self.assertEqual(api.reply([], 100), ('Here are the findings.', 'stop'))
        body = requests.call_args.args[1]
        self.assertEqual(reader.read.call_count, 4)
        self.assertFalse(any(m['role'] == 'system' for m in body['messages']))
        self.assertEqual(body['tool_choice'], 'auto')
        self.assertEqual(count.call_args.args[0], body['messages'])
        self.assertEqual(body['max_tokens'], 20)

    def test_unparsed_tool_syntax_cannot_be_delivered_as_final_answer(self):
        from unittest.mock import Mock
        reader = Mock()
        reader.read.return_value = {'records': []}
        api = API('http://127.0.0.1:1', reader, 8192)
        final = stream([delta({'content': '<tool_call>wrong</tool_call>'}, 'stop')])
        visible = []
        with patch.object(api, 'open', side_effect=[tool_stream(), tool_stream(), final]), patch.object(api, 'count', return_value=200), patch('diagnostics.log'):
            with self.assertRaisesRegex(RuntimeError, 'no final answer was accepted'):
                api.reply([], 100, on_delta=lambda *x: visible.append(x))
        # Malformed text may stream locally, but reply() must not return it to Discord.
