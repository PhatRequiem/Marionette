"""Inference streaming can feed another interface without terminal output."""
import io
import json
from pathlib import Path
import sys
import unittest
import httpx
from openai import OpenAI
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from inference import API


class InferenceTests(unittest.TestCase):
    def test_stream_callback_preserves_order_and_separates_reasoning(self):
        events = [
            {'choices': [{'delta': {'reasoning_content': 'Check '}}]},
            {'choices': [{'delta': {'reasoning_content': 'this.', 'content': 'An'}}]},
            {'choices': [{'delta': {'content': 'swer.'}, 'finish_reason': 'stop'}]},
        ]
        payload = (''.join('data: ' + json.dumps(e) + '\n\n' for e in events)
                   + 'data: [DONE]\n\n').encode()
        sdk = OpenAI(base_url='http://127.0.0.1:1/v1', api_key='EMPTY',
            http_client=httpx.Client(transport=httpx.MockTransport(lambda request:
                httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=payload))))
        api = API('http://127.0.0.1:1')
        api.count = lambda messages: 10
        received = []
        with patch('inference.OpenAI', return_value=sdk), patch('diagnostics.log'), patch('sys.stdout', new_callable=io.StringIO) as output:
            result = api.reply([{'role': 'user', 'content': 'Test'}], 100,
                               on_delta=lambda phase, text: received.append((phase, text)))
        self.assertEqual(received, [('reasoning', 'Check '), ('reasoning', 'this.'),
                                    ('answer', 'An'), ('answer', 'swer.')])
        self.assertEqual(result, ('Answer.', 'stop'))
        self.assertEqual(output.getvalue(), '')

    def test_trimmed_history_persists_and_failed_turns_do_not_commit(self):
        from conversation import Conversation
        sent = []
        result = {'answer': 'OK', 'finish': 'stop'}
        def handle(request):
            sent.append(json.loads(request.content))
            event = {'choices': [{'delta': {'content': result['answer']}, 'finish_reason': result['finish']}]}
            return httpx.Response(200, headers={'content-type': 'text/event-stream'},
                text='data: ' + json.dumps(event) + '\n\ndata: [DONE]\n\n')
        api = API('http://localhost')
        api.count = lambda messages: 110
        conversation = Conversation(api, 128)
        original = [{'role': 'user', 'content': 'old ' * 200}, {'role': 'assistant', 'content': 'past'}]
        conversation.history = original.copy()
        def sdk(**kwargs):
            return OpenAI(base_url='http://localhost/v1', api_key='EMPTY',
                http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        with patch('inference.OpenAI', side_effect=sdk), patch('diagnostics.log'):
            for answer, finish in (('partial', None), ('', 'stop')):
                result.update(answer=answer, finish=finish)
                with self.assertRaises(RuntimeError):
                    conversation.turn('hello')
                self.assertEqual(conversation.history, original)
            result.update(answer='OK', finish='stop')
            conversation.turn('hello')
            self.assertEqual(conversation.history[:-1], sent[-1]['messages'])
            self.assertNotEqual(conversation.history[0], original[0])
            self.assertEqual(sent[-1]['max_tokens'], 17)
            conversation.turn('again')
            self.assertNotIn(original[0], sent[-1]['messages'])
            self.assertEqual(sent[-1]['messages'][-1]['content'], 'again')
            saved = conversation.history.copy()
            api.count = lambda messages: 128
            with self.assertRaisesRegex(ValueError, 'exceeds context'):
                conversation.turn('hello')
            self.assertEqual(conversation.history, saved)
            with self.assertRaisesRegex(ValueError, 'Shorten'):
                conversation.turn('huge ' * 200)
            self.assertEqual(conversation.history, saved)
