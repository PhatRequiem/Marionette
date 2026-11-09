"""Lossless JSONL storage, concurrent writers, and semantic reply provenance."""
import base64
from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
import inference
import log_store
import log_view


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'session-chat.jsonl'

    def test_raw_capture_and_backup_restore_are_byte_exact(self):
        raw = bytes(range(256)) * 300 + b'\x1b[32mtext\b\r\n' + '🙂'.encode() + b'no newline'
        log_store.capture(io.BytesIO(raw), self.path, 'terminal')
        log_store.append(self.path, log_store.record('terminal', 'answer', data={'content': 'separate'}))
        restored = self.path.with_name('restored.jsonl')
        shutil.copy2(self.path, restored)
        output = io.BytesIO()
        log_store.export_raw(restored, output)
        self.assertEqual(output.getvalue(), raw)
        self.assertEqual(restored.read_bytes(), self.path.read_bytes())
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        events = list(map(json.loads, self.path.read_text().splitlines()))
        self.assertEqual([e['sequence'] for e in events[:-1]], [1, 2])
        self.assertTrue(all(e['version'] == 1 for e in events))

    def test_concurrent_large_records_do_not_interleave(self):
        def write(number):
            log_store.append(self.path, log_store.record('test', 'large', data={'n': number, 'text': 'x' * 70000}))
        with ThreadPoolExecutor(max_workers=4) as workers:
            list(workers.map(write, range(20)))
        events = list(map(json.loads, self.path.read_text().splitlines()))
        self.assertEqual({e['data']['n'] for e in events}, set(range(20)))
        self.assertEqual(len({e['event_id'] for e in events}), 20)
        self.assertTrue(all(e['data']['text'] == 'x' * 70000 for e in events))

    def test_discord_native_events_and_unknown_bytes(self):
        native = log_store.record('discord', 'answer', data={'content': 'Hello\nthere'})
        raw = b'unknown \xff\x1b[31m\n'
        visible = io.BytesIO()
        log_store.capture(io.BytesIO(log_store.encode(native) + raw), self.path, 'discord', visible)
        events = list(map(json.loads, self.path.read_text().splitlines()))
        self.assertEqual(events[0], native)
        self.assertEqual(base64.b64decode(events[1]['raw_b64']), raw)
        self.assertEqual(visible.getvalue(), self.path.read_bytes())
        output = io.StringIO()
        log_view.render(io.StringIO(visible.getvalue().decode()), output, 'discord', False)
        self.assertIn('Hello\nthere', output.getvalue())
        self.assertNotIn('\x1b', output.getvalue())

    def test_completed_and_interrupted_replies_keep_identity_and_partial_text(self):
        for completed in (True, False):
            self.path.unlink(missing_ok=True)
            event = {'choices': [{'delta': {'reasoning_content': 'Check.', 'content': 'Four.'}, 'finish_reason': 'stop'}]}
            stream = io.BytesIO(('data: ' + json.dumps(event) + '\n\n' +
                                 ('data: [DONE]\n\n' if completed else '')).encode())
            api = inference.API('http://127.0.0.1:1')
            with patch.dict(os.environ, {'MARIONETTE_CHAT_LOG': str(self.path)}), patch.object(api, 'open', return_value=stream), patch('diagnostics.log'):
                with log_store.turn_context(source='discord', sender_id='123', person_uuid='synthetic', turn_id='turn'):
                    log_store.chat_event('message_received', content='hello')
                    if completed:
                        self.assertEqual(api.reply([], 100), ('Four.', 'stop'))
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'closed early'):
                            api.reply([], 100)
                log_store.chat_event('session_stopped')
            events = list(map(json.loads, self.path.read_text().splitlines()))
            self.assertEqual([e['event_type'] for e in events], ['message_received', 'reasoning', 'answer', 'session_stopped'])
            for event in events[:3]:
                self.assertEqual(event['data']['turn_id'], 'turn')
                self.assertEqual(event['data']['sender_id'], '123')
            self.assertNotIn('turn_id', events[-1]['data'])
            self.assertEqual(events[1]['data']['content'], 'Check.')
            self.assertEqual(events[2]['data']['content'], 'Four.')
            self.assertEqual(events[2]['data']['complete'], completed)

    def test_diagnostic_view_matches_legacy_presentation(self):
        from log_router import format_event
        raw = b'Client: Discord answer: "Hello"\n'
        event = log_store.record('diagnostic', 'diagnostic', raw=raw, sequence=12)
        output, legacy = io.StringIO(), io.StringIO()
        log_view.render(io.StringIO(log_store.encode(event).decode()), output, 'diagnostic', True)
        log_view.render(io.StringIO(format_event(12, event['timestamp'], raw).decode()), legacy, 'diagnostic', True)
        self.assertEqual(output.getvalue(), legacy.getvalue())

    def test_pipe_batches_flush_during_idle_and_at_eof(self):
        import threading
        import time
        read_fd, write_fd = os.pipe()
        results, flushed = [], threading.Event()
        def consume():
            with os.fdopen(read_fd, 'rb', buffering=0) as source:
                for batch in log_store.raw_batches(source, interval=.03):
                    results.append(b''.join(raw for _, raw in batch))
                    flushed.set()
        thread = threading.Thread(target=consume)
        thread.start()
        try:
            os.write(write_fd, b'a')
            os.write(write_fd, b'b')
            self.assertTrue(flushed.wait(1), 'Idle pipe must flush without waiting for more output')
            os.write(write_fd, b'last')
        finally:
            os.close(write_fd)
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(b''.join(results), b'ablast')

    def test_diagnostic_batches_preserve_split_lines_order_and_timestamps(self):
        import log_router
        chunks = [[(1000000, b'first\npart')], [(1000100, b'ial\n\xfftail')]]
        server, model = io.BytesIO(), io.BytesIO()
        with patch.object(log_router, 'raw_batches', return_value=iter(chunks)):
            log_router.route(None, server, model)
        decoded = []
        expected_display = io.StringIO()
        for line in server.getvalue().splitlines():
            event = json.loads(line)
            decoded.extend(log_router.diagnostic_lines(event))
        self.assertEqual([x[2] for x in decoded], [b'first\n', b'partial\n', b'\xfftail'])
        self.assertEqual([x[0] for x in decoded], [1, 2, 3])
        self.assertEqual(decoded[1][1], log_store.timestamp(1000100))
        for number, when, raw in decoded:
            log_view.render(io.StringIO(log_router.format_event(number, when, raw).decode()), expected_display, 'diagnostic', True)
        actual = io.StringIO()
        log_view.render(io.StringIO(server.getvalue().decode()), actual, 'diagnostic', True)
        self.assertEqual(actual.getvalue(), expected_display.getvalue())
        counterpart = [entry for line in model.getvalue().splitlines()
                       for entry in log_router.diagnostic_lines(json.loads(line))]
        self.assertEqual(decoded, counterpart)
