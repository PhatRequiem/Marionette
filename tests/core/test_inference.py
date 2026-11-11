"""Inference streaming can feed another interface without terminal output."""
import io
import json
from pathlib import Path
import sys
import unittest
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
        stream = io.BytesIO((''.join('data: ' + json.dumps(e) + '\n\n' for e in events)
                             + 'data: [DONE]\n\n').encode())
        api = API('http://127.0.0.1:1')
        received = []
        with patch.object(api, 'open', return_value=stream), patch('diagnostics.log'), patch('sys.stdout', new_callable=io.StringIO) as output:
            result = api.reply([{'role': 'user', 'content': 'Test'}], 100,
                               on_delta=lambda phase, text: received.append((phase, text)))
        self.assertEqual(received, [('reasoning', 'Check '), ('reasoning', 'this.'),
                                    ('answer', 'An'), ('answer', 'swer.')])
        self.assertEqual(result, ('Answer.', 'stop'))
        self.assertEqual(output.getvalue(), '')
