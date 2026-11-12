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
        received = []
        with patch('inference.OpenAI', return_value=sdk), patch('diagnostics.log'), patch('sys.stdout', new_callable=io.StringIO) as output:
            result = api.reply([{'role': 'user', 'content': 'Test'}], 100,
                               on_delta=lambda phase, text: received.append((phase, text)))
        self.assertEqual(received, [('reasoning', 'Check '), ('reasoning', 'this.'),
                                    ('answer', 'An'), ('answer', 'swer.')])
        self.assertEqual(result, ('Answer.', 'stop'))
        self.assertEqual(output.getvalue(), '')

    def test_feature_prompt_is_separate_from_soul_and_not_duplicated(self):
        from types import SimpleNamespace
        api = API('http://localhost', tools=[SimpleNamespace(name='query_logs', function={})])
        messages = [{'role': 'user', 'content': 'what model are you?'}]
        api.system_prompt = 'Name: Synthetic soul'
        rendered = api.with_system(messages)
        self.assertIn('call `query_logs` with setup/startup', rendered[0]['content'])
        self.assertTrue(rendered[0]['content'].endswith('Name: Synthetic soul'))
        self.assertEqual(api.with_system(rendered), rendered)
        self.assertEqual(api.body(messages)['messages'], rendered)
        api.system_prompt = None
        self.assertIn('call `query_logs` with setup/startup', api.with_system(messages)[0]['content'])
        api.tools = ()
        self.assertEqual(api.with_system(messages), messages)

    def test_guidance_follows_registered_tools_without_overwriting_soul(self):
        from types import SimpleNamespace
        names = ['query_logs', 'update_contact_notes', 'update_soul']
        api = API('http://localhost')
        api.system_prompt = 'Name: Synthetic\n\nMy evolving description.'
        message = [{'role': 'user', 'content': 'hello'}]
        for name in names:
            api.tools = (SimpleNamespace(name=name, function={}),)
            content = api.with_system(message)[0]['content']
            self.assertEqual(content.count('# Tool guidance'), 1)
            self.assertIn('## ' + name, content)
            for other in set(names) - {name}:
                self.assertNotIn('## ' + other, content)
            self.assertTrue(content.endswith(api.system_prompt))
        api.tools = tuple(SimpleNamespace(name=n, function={}) for n in names)
        content = api.with_system(message)[0]['content']
        for name in names:
            self.assertEqual(content.count('## ' + name), 1)
        api.tools = ()
        self.assertEqual(api.with_system(message)[0]['content'], api.system_prompt)
