"""Guardrail: routine diagnostic payloads stay off disk until recorder shutdown."""
from contextlib import closing
import io
import json
from pathlib import Path
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/marionette'))
from storage import Store, view_log, open_read, backup
from ram_logs import RamLogs, LiveView, read_live


class RamLogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'logs.sqlite3'
        self.disk=Store(self.path)
        self.addCleanup(self.disk.close)
        self.session=self.disk.start()

    def buffer(self, **kwargs):
        buffer=RamLogs(self.disk,self.session,**kwargs)
        self.addCleanup(buffer.close)
        return buffer

    def test_default_policy_is_500mb_ram_in_20mb_batches(self):
        buffer=self.buffer()
        policy=buffer.memory.db.execute('SELECT * FROM retention_state').fetchone()
        self.assertEqual(policy['part_bytes'],20_000_000)
        self.assertEqual(policy['budget_bytes'],500_000_000)
        self.assertEqual(policy['error_limit'],20)
        self.assertEqual(policy['window_events'],20)

    def test_payloads_do_not_reach_disk_until_save_and_ids_survive(self):
        buffer=self.buffer(part_bytes=100,budget_bytes=300)
        disk_changes=self.disk.db.total_changes
        ids=[buffer.append(f'RAM {i} '.encode()+b'x'*44,'both') for i in range(12)]
        self.assertEqual(self.disk.db.total_changes-disk_changes,1)  # Only the ID-block reservation.
        self.assertEqual(self.disk.db.execute('SELECT count(*) FROM events').fetchone()[0],0)
        self.assertEqual(self.disk.db.execute('SELECT count(*) FROM recent_diagnostics').fetchone()[0],0)
        self.assertEqual(buffer.memory.db.execute('PRAGMA database_list').fetchone()[2],'')
        self.assertLessEqual(buffer.memory.db.execute('SELECT sum(bytes) FROM diagnostic_batches').fetchone()[0],300)
        retained=[tuple(r)[:7] for r in buffer.memory.db.execute('SELECT * FROM events ORDER BY id')]
        self.assertGreater(retained[0][0],ids[0])
        buffer.save()
        self.assertEqual([tuple(r)[:7] for r in self.disk.db.execute('SELECT * FROM events ORDER BY id')],retained)
        buffer.save()  # Idempotent shutdown saving.
        self.assertEqual(self.disk.db.execute('SELECT count(*) FROM events').fetchone()[0],len(retained))
        with self.assertRaises(ValueError): buffer.append(b'late','both')

    def test_protected_twenty_errors_survive_ram_rollover_and_restore(self):
        buffer=self.buffer(part_bytes=100,budget_bytes=300)
        for i in range(25): buffer.append(f'0.1 E runtime: failure {i}\n'.encode(),'both')
        for i in range(30): buffer.append(b'following event '+b'x'*50,'both')
        self.assertEqual(buffer.memory.db.execute('SELECT count(*) FROM failures').fetchone()[0],20)
        self.assertEqual(self.disk.db.execute('SELECT count(*) FROM failures').fetchone()[0],0)
        buffer.save()
        failures=self.disk.db.execute('SELECT * FROM failures').fetchall()
        self.assertEqual(len(failures),20)
        self.assertTrue(all(r['remaining']==0 for r in failures))
        self.assertGreater(self.disk.db.execute('SELECT count(*) FROM error_evidence').fetchone()[0],20)
        target=Path(self.temp.name)/'restore.sqlite3'
        backup(self.path,target)
        with closing(open_read(target)) as restored:
            self.assertEqual(restored.execute('SELECT count(*) FROM failures').fetchone()[0],20)
            self.assertEqual(restored.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_shutdown_merges_latest_twenty_with_previously_saved_errors(self):
        first=self.buffer()
        for i in range(20): first.append(f'0.1 E runtime: old {i}\n'.encode(),'both')
        first.save()
        old_ids={r[0] for r in self.disk.db.execute('SELECT first_event FROM failures')}
        self.session=self.disk.start()
        second=self.buffer()
        new_ids={second.append(f'0.1 E runtime: new {i}\n'.encode(),'both') for i in range(3)}
        second.save()
        kept={r[0] for r in self.disk.db.execute('SELECT first_event FROM failures')}
        self.assertEqual(len(kept),20)
        self.assertTrue(new_ids.issubset(kept))
        self.assertEqual(len(kept & old_ids),17)

    def test_failure_retention_uses_time_across_reserved_id_blocks(self):
        with self.disk.db:
            self.disk.db.execute('UPDATE retention_state SET error_limit=2')
        buffer=self.buffer()
        buffer.append(b'0.1 E runtime: old RAM failure\n','both')
        discord=b'2026-11-11T00:00:00+00:00 Discord chunk failed. {"sender_id":"1"}\n'
        older_disk=self.disk.event(self.session,'discord',discord)
        newer_ram=buffer.append(b'0.1 E runtime: newer RAM failure\n','both')
        self.assertLess(newer_ram,older_disk)  # Allocation blocks are not cross-stream time.
        buffer.save()
        latest_disk=self.disk.event(self.session,'discord',discord)
        kept={r[0] for r in self.disk.db.execute('SELECT first_event FROM failures')}
        self.assertEqual(kept,{newer_ram,latest_disk})

    def test_save_failure_is_atomic_and_retryable(self):
        buffer=self.buffer()
        buffer.append(b'0.1 E runtime: retained error\n','both')
        with patch('retention.prune',side_effect=RuntimeError('synthetic save failure')):
            with self.assertRaises(RuntimeError): buffer.save()
        self.assertFalse(buffer.saved)
        self.assertEqual(self.disk.db.execute('SELECT count(*) FROM events').fetchone()[0],0)
        self.assertEqual(self.disk.db.execute('SELECT count(*) FROM failures').fetchone()[0],0)
        buffer.save()
        self.assertEqual(self.disk.db.execute('SELECT state FROM failures').fetchone()[0],'incomplete')

    def test_live_view_reads_ram_then_saved_rows_without_id_changes(self):
        buffer=self.buffer()
        identifier=buffer.append(b'live synthetic diagnostic\n','both')
        with closing(LiveView(buffer,self.path)):
            last,payload=read_live(self.path,self.session,'model',0)
            self.assertEqual(last,identifier)
            self.assertIn(b'live synthetic diagnostic',payload)
            output=io.BytesIO()
            view_log(self.path,self.session,'model',output)
            self.assertEqual(output.getvalue(),payload)
            self.assertIsNone(read_live(self.path,'wrong-session','model',0))
            status=json.loads(subprocess.check_output([sys.executable,str(ROOT/'src/marionette/storage.py'),str(self.path),'retention'],text=True))
            self.assertEqual(status['diagnostic_bytes'],0)
            self.assertEqual(status['live_ram']['session'],self.session)
            self.assertGreater(status['live_ram']['diagnostic_bytes'],0)
            buffer.save()
        output=io.BytesIO()
        view_log(self.path,self.session,'model',output)
        self.assertEqual(output.getvalue(),payload)

    def test_id_reservations_do_not_collide_with_conversation_streams(self):
        buffer=self.buffer()
        with patch('ram_logs.ID_BLOCK',2):
            first=buffer.append(b'first\n','both')
            terminal=self.disk.event(self.session,'terminal',b'conversation')
            second=buffer.append(b'second\n','both')
            third=buffer.append(b'third\n','both')
        self.assertEqual(len({first,second,third,terminal}),4)
        self.assertLess(first,second)
        self.assertLess(second,third)
        buffer.save()
        self.assertEqual(self.disk.db.execute('SELECT count(*) FROM events').fetchone()[0],4)

    def test_oversized_event_is_rejected_without_losing_existing_buffer(self):
        buffer=self.buffer(part_bytes=10,budget_bytes=20)
        buffer.append(b'keep','both')
        with self.assertRaises(ValueError): buffer.append(b'x'*21,'both')
        buffer.save()
        self.assertEqual(self.disk.db.execute('SELECT raw FROM events').fetchone()[0],b'keep')

    def recorder(self):
        process=subprocess.Popen([sys.executable,str(ROOT/'src/marionette/storage.py'),str(self.path),
            'capture',self.session,'diagnostic'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.addCleanup(lambda: self.stop(process))
        process.stdin.write(b'0.1 E runtime: subprocess evidence\n')
        process.stdin.flush()
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            result=read_live(self.path,self.session,'model',0)
            if result and b'subprocess evidence' in result[1]: return process
            if process.poll() is not None: self.fail(process.stderr.read().decode())
            time.sleep(.02)
        self.fail('Recorder did not become ready')

    def stop(self,process):
        if process.poll() is None:
            process.kill()
        process.communicate()

    def test_eof_saves_buffer_and_partial_error_window(self):
        process=self.recorder()
        self.assertEqual(self.disk.db.execute('SELECT count(*) FROM events').fetchone()[0],0)
        _,error=process.communicate(timeout=5)
        self.assertEqual(process.returncode,0,error)
        self.assertEqual(self.disk.db.execute('SELECT count(*) FROM events').fetchone()[0],1)
        self.assertEqual(self.disk.db.execute('SELECT state FROM failures').fetchone()[0],'incomplete')

    def test_sigterm_saves_but_sigkill_cannot_save_ram(self):
        process=self.recorder()
        process.send_signal(signal.SIGTERM)
        _,error=process.communicate(timeout=5)
        self.assertEqual(process.returncode,143,error)
        before=self.disk.db.execute('SELECT count(*) FROM events').fetchone()[0]
        process=self.recorder()
        process.kill()
        process.communicate(timeout=5)
        self.assertEqual(self.disk.db.execute('SELECT count(*) FROM events').fetchone()[0],before)
