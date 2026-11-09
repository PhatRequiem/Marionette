"""Presentation checks: consistent colors, readable messages, retained fields."""
import io
import json
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
import log_view
from style import COLORS


class ViewTests(unittest.TestCase):
    def render(self, text, mode, colored=True):
        output = io.StringIO()
        log_view.render(io.StringIO(text), output, mode, colored)
        return output.getvalue()

    def test_discord_message_colors_metadata_newlines_and_controls(self):
        for role, kind in [('user', 'input'), ('assistant', 'reply')]:
            record = {'time': '2026-11-09T01:00:00-05:00', 'role': role,
                      'content': 'first\nsecond\x1b[31m', 'sender_id': '123', 'channel_id': '456',
                      'message_id': '789'}
            result = self.render(json.dumps(record) + '\n', 'discord')
            label = 'incoming sender_id' if role == 'assistant' else 'sender_id'
            self.assertIn(COLORS['meta'] + f'  {label}: "123"', result)
            self.assertIn(COLORS[kind] + 'first\nsecond\\x1b[31m', result)
            self.assertNotIn('\x1b[31m', result)
            plain = self.render(json.dumps(record) + '\n', 'discord', False)
            self.assertNotIn('\x1b', plain)
            for value in ('123', '456', '789', record['time'], role.upper(), 'first\nsecond'):
                self.assertIn(value, plain)

    def test_all_event_fields_remain_visible_and_error_is_red(self):
        fields = {'sender_id': '123', 'outgoing_message_id': '789', 'http_status': 403,
                  'discord_code': 50007, 'send_ms': 12.34, 'heartbeat_ms': None, 'chunk': 2,
                  'chunk_count': 3, 'confirmed_chunks': 1}
        text = '2026-11-09T01:00:00-05:00 Discord chunk failed. ' + json.dumps(fields) + '\n'
        result = self.render(text, 'discord')
        self.assertIn(COLORS['error'] + 'Discord chunk failed.', result)
        plain = self.render(text, 'discord', False)
        for key, value in fields.items():
            self.assertIn(f'{key}: {json.dumps(value)}', plain)

    def test_diagnostic_colors_keep_all_original_rows(self):
        original = ('[event 00000001] [time]\n'
                    '    | Client: Discord input [123]: "hello"\n'
                    '[event 00000002] [time]\n'
                    '    | Client: Discord answer: "hello back"\n'
                    '    | more answer\n'
                    '[event 00000003] [time]\n'
                    '    | "reasoning_content":"thought"\n'
                    '    | "content":"answer"\n'
                    '[event 00000004] [time]\n'
                    '    | 0.0 E srv send_error: error\n')
        result = self.render(original, 'diagnostic')
        self.assertIn(COLORS['reply'] + '    | more answer', result)
        self.assertIn(COLORS['data'] + '    | "reasoning_content"', result)
        self.assertIn(COLORS['reply'] + '    | "content"', result)
        self.assertIn(COLORS['meta'] + '    | Client: Discord input [123]: ', result)
        self.assertIn(COLORS['input'] + '"hello"', result)
        self.assertEqual(re.sub(r'\x1b\[[0-9;]*m', '', result), original)
        self.assertEqual(self.render(original, 'diagnostic', False), original)
