"""Synthetic persistence, provenance, raw-byte preservation, and recovery checks."""
from contextlib import closing
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/marionette'))
from storage import Store, open_read, view_log, backup
from log_router import format_event


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'log.sqlite3'
        self.store = Store(self.path)
        self.addCleanup(self.store.close)
        self.session = self.store.start()

    def rows(self, db):
        return {table: [tuple(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY 1')]
                for table in ('sessions', 'messages', 'events')}

    def seed(self):
        self.store.event(self.session, 'diagnostic', b'Client: [message discord:1234] test\x00\xff\x1b[32m\n')
        self.store.event(self.session, 'diagnostic', b'model only\n', 'model')
        self.store.event(self.session, 'terminal', 'hello 🌷\r\b'.encode())
        self.store.event(self.session, 'discord', b'{"log_message_id":"discord:1234", "sender_id":"42"}\n')
        self.store.message(self.session, 'discord:1234', 'discord:42', {'contact_uuid': 'synthetic'},
                           'discord', '42', 'user', 'input', 'hello 🌷', 'received')

    def test_raw_bytes_shared_views_and_indexed_correlation(self):
        self.seed()
        output = io.BytesIO()
        view_log(self.path, self.session, 'server', output)
        rows = self.store.db.execute('SELECT * FROM events ORDER BY id').fetchall()
        self.assertEqual(output.getvalue(), format_event(rows[0]['id'], rows[0]['recorded_at'], rows[0]['raw']))
        self.assertEqual(rows[0]['message_id'], 'discord:1234')
        self.assertEqual(rows[3]['message_id'], 'discord:1234')
        self.assertEqual(len(rows), 4)  # shared diagnostic stored once, displayed twice
        output = io.BytesIO()
        view_log(self.path, self.session, 'terminal', output)
        self.assertEqual(output.getvalue(), 'hello 🌷\r\b'.encode())
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_correlation_uses_envelopes_not_quoted_content(self):
        cases = [
            ('terminal', b'Client: [message discord:999] typed text\n', None),
            ('terminal', b'{"log_message_id":"discord:999"}\n', None),
            ('diagnostic', b'0.01 D model text: "Client: [message discord:999] hello"\n', None),
            ('diagnostic', b'Client: Reasoning: "Client: [message discord:999] hello"\n', None),
            ('diagnostic', b'Client: [message discord:123] quoted discord:999\n', 'discord:123'),
            ('diagnostic', b'Client: [message \xff] invalid bytes\n', None),
            ('diagnostic', b'Client: [message unassigned] failure\n', None),
            ('discord', b'{"content":{"log_message_id":"discord:999"}}\n', None),
            ('discord', b'{"log_message_id":123}\n', None),
            ('discord', b'{"log_message_id":"discord:123", "content":{"log_message_id":"discord:999"}}\n', 'discord:123'),
            ('discord', b'2026-11-11T00:00:00+00:00 Discord send completed. {"log_message_id":"discord:123"}\n', 'discord:123'),
            ('discord', b'2026-11-11T00:00:00+00:00 Discord failed. {"log_message_id":"discord:123",bad}\n', None),
        ]
        for stream, raw, expected in cases:
            with self.subTest(stream=stream, raw=raw):
                number = self.store.event(self.session, stream, raw)
                row = self.store.db.execute('SELECT message_id,raw FROM events WHERE id=?', (number,)).fetchone()
                self.assertEqual(row['message_id'], expected)
                self.assertEqual(row['raw'], raw)

    def test_backup_restore_and_sql_export_restore(self):
        self.seed()
        target = Path(self.temp.name) / 'backup.sqlite3'
        backup(self.path, target)  # source remains open with WAL
        with closing(open_read(target)) as restored:
            self.assertEqual(self.rows(restored), self.rows(self.store.db))
            self.assertEqual(restored.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        with self.assertRaises(FileExistsError):
            backup(self.path, target)
        dump = subprocess.check_output([sys.executable, str(ROOT / 'src/marionette/storage.py'), str(self.path), 'export'], text=True)
        with closing(sqlite3.connect(Path(self.temp.name) / 'imported.sqlite3')) as imported:
            imported.executescript(dump)
            self.assertEqual(self.rows(imported), self.rows(self.store.db))
            self.assertEqual(imported.execute('PRAGMA user_version').fetchone()[0], 5)

    def test_concurrent_writers_and_reader(self):
        failures = []
        def writer(number):
            try:
                with closing(Store(self.path)) as store:
                    for i in range(40):
                        store.event(self.session, 'diagnostic', f'{number}/{i}\n'.encode())
            except Exception as e:
                failures.append(e)
        threads = [threading.Thread(target=writer, args=(i,)) for i in range(3)]
        for thread in threads:
            thread.start()
        with closing(open_read(self.path)) as reader:
            reader.execute('SELECT count(*) FROM events').fetchone()
        for thread in threads:
            thread.join()
        self.assertFalse(failures)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM events').fetchone()[0], 120)

    def test_capture_discord_and_partial_terminal_bytes(self):
        for stream, raw in [('discord', b'{"role":"assistant","content":"hello"}\nlast'),
                            ('terminal', b'\x1b[32mhello\b\xff')]:
            result = subprocess.run([sys.executable, str(ROOT / 'src/marionette/storage.py'), str(self.path),
                                     'capture', self.session, stream], input=raw, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, raw)
            output = io.BytesIO()
            view_log(self.path, self.session, stream, output)
            self.assertEqual(output.getvalue(), raw)

    def test_invalid_version_and_failed_transaction_leave_data(self):
        self.seed()
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.event('not-a-session', 'diagnostic', b'lost')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM events').fetchone()[0], 4)
        self.store.db.execute('PRAGMA user_version=999')
        with self.assertRaises(ValueError):
            Store(self.path)
        self.assertEqual(self.store.db.execute('PRAGMA user_version').fetchone()[0], 999)

    def test_conversation_records_provenance_and_keeps_reasoning_out_of_history(self):
        from conversation import Conversation
        class API:
            closing = threading.Event()
            count = staticmethod(lambda messages: 10)
            def reply(self, messages, reserve, on_delta=None):
                on_delta('reasoning', 'Synthetic reasoning.')
                on_delta('answer', 'Synthetic answer.')
                return 'Synthetic answer.', 'stop'
        chat = Conversation(API(), 1000, store=self.store, session_id=self.session)
        with patch('diagnostics.log'), patch('conversation.Preparation'):
            answer, _ = chat.turn('hello')
        rows = self.store.db.execute('SELECT * FROM messages ORDER BY id').fetchall()
        self.assertEqual([r['kind'] for r in rows], ['input', 'reasoning', 'answer'])
        self.assertEqual(len({r['message_id'] for r in rows}), 1)
        self.assertEqual(rows[0]['conversation_id'], 'terminal:local')
        self.assertEqual(chat.history[-1]['content'], answer)
        self.assertNotIn('Synthetic reasoning.', str(chat.history))


if __name__ == '__main__':
    unittest.main()
