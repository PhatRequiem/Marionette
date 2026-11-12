"""Synthetic search metadata, migration, retention and RAM-save checks."""
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src/marionette'))
from storage import Store
from ram_logs import RamLogs
from log_metadata import COLUMNS, extract


class MetadataTests(unittest.TestCase):
    def test_envelopes_not_prose(self):
        for stream, raw in [('terminal', b'Client: Runtime usage: {}'),
                            ('diagnostic', b'Client: [message discord:1] Message input: "Tool call identity: {}"'),
                            ('discord', b'{"content":"Discord chunk sent."}')]:
            data = dict(zip(COLUMNS, extract(stream, raw)))
            self.assertIsNone(data['tool_name'])
            self.assertIsNone(data['outgoing_message_id'])
            self.assertNotEqual(data['event_type'], 'tool_identity')
        data = dict(zip(COLUMNS, extract('diagnostic', b'Client: [message discord:1] [request 02] [tool 01] Tool call identity: {"name":"update_soul"}')))
        self.assertEqual((data['event_type'], data['request_number'], data['tool_number'], data['tool_name']),
                         ('tool_identity', '02', '01', 'update_soul'))
        data = dict(zip(COLUMNS, extract('discord', b'2026-11-11T00:00:00+00:00 Discord chunk sent. {"sender_id":"42","channel_id":"12","outgoing_message_id":"99"}')))
        self.assertEqual((data['conversation_id'],data['outgoing_message_id']), ('discord:42','99'))

    def test_sender_names_are_explicit_historical_labels(self):
        raw = b'Client: [message discord:1] Sender identity: {"sender_id":"42","contact_uuid":"test-contact","display_name":"Example","preferred_name":"Ex"}'
        data = dict(zip(COLUMNS, extract('diagnostic', raw)))
        self.assertEqual((data['contact_uuid'], data['display_name'], data['preferred_name']), ('test-contact','Example','Ex'))
        self.assertIsNone(data['conversation_id'])

    def test_ram_save_retained_evidence_and_reset(self):
        with tempfile.TemporaryDirectory() as temp:
            disk = Store(Path(temp)/'db'); self.addCleanup(disk.close)
            session = disk.start()
            ram = RamLogs(disk,session,part_bytes=100,budget_bytes=200);self.addCleanup(ram.close)
            raw = b'Client: [message discord:1] [request 01] Model Request failed: synthetic\n'
            identifier = ram.append(raw, 'both')
            for _ in range(10): ram.append(b'0.1 D '+b'x'*80+b'\n', 'model')
            self.assertEqual(disk.db.execute('SELECT count(*) FROM events').fetchone()[0],0)
            self.assertIsNone(ram.memory.db.execute('SELECT id FROM events WHERE id=?',(identifier,)).fetchone())
            row = ram.memory.db.execute('SELECT * FROM error_evidence WHERE event_id=?',(identifier,)).fetchone()
            self.assertEqual(row['event_type'],'model_request_failed')
            ram.save()
            row = disk.db.execute('SELECT * FROM error_evidence WHERE event_id=?',(identifier,)).fetchone()
            self.assertEqual((row['raw'],row['request_number']), (raw,'01'))
            self.assertEqual(disk.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            disk.reset_memory(session,'new-generation')
            self.assertEqual(disk.db.execute('SELECT count(*) FROM error_evidence').fetchone()[0],0)

    def test_schema_four_backfill_preserves_bytes_and_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'db'; store=Store(path);session=store.start()
            raw=b'Client: [message discord:1] Runtime usage: {"prompt_tokens":10}\n'
            identifier=store.event(session,'diagnostic',raw)
            # Reconstruct the exact pre-search schema by dropping added columns/indexes.
            for table in ('events','error_evidence'):
                store.db.execute(f'DROP INDEX {table}_type_time')
                store.db.execute(f'DROP INDEX {table}_operation')
                store.db.execute(f'DROP INDEX {table}_tool')
                for name in COLUMNS: store.db.execute(f'ALTER TABLE {table} DROP COLUMN {name}')
            store.db.execute('PRAGMA user_version=4');store.db.commit();store.close()
            migrated=Store(path);self.addCleanup(migrated.close)
            row=migrated.db.execute('SELECT * FROM events WHERE id=?',(identifier,)).fetchone()
            self.assertEqual((row['raw'],row['session_id'],row['event_type']), (raw,session,'model_usage'))
            self.assertEqual(migrated.db.execute('PRAGMA user_version').fetchone()[0],5)
            plan=migrated.db.execute("EXPLAIN QUERY PLAN SELECT id FROM events WHERE session_id=? AND event_type=? ORDER BY recorded_at,id",(session,'model_usage')).fetchall()
            self.assertTrue(any('events_type_time' in r[3] for r in plan))
            self.assertEqual(migrated.db.execute('PRAGMA foreign_key_check').fetchall(),[])
