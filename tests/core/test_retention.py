"""Small-budget SQLite retention, persistent error windows, and recovery."""
from contextlib import closing
import io
import json
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
import retention
from storage import Store, SCHEMA, backup, open_read, view_log
from log_snapshot import database_snapshot


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'test.sqlite3'
        self.store = Store(self.path)
        self.addCleanup(lambda: self.store.close())
        self.session = self.store.start()
        with self.store.db:
            self.store.db.execute('UPDATE retention_state SET part_bytes=300,budget_bytes=900')

    def event(self, raw=b'routine diagnostic\n', stream='diagnostic'):
        return self.store.event(self.session, stream, raw)

    def scalar(self, sql):
        return self.store.db.execute(sql).fetchone()[0]

    def errors(self):
        return self.store.db.execute('SELECT * FROM failures ORDER BY id').fetchall()

    def test_rotation_preserves_messages_terminal_discord_and_ids(self):
        self.store.message(self.session,'discord:1','discord:2',None,'discord','2','user','input','keep','received')
        terminal = self.event(b'preserved terminal transcript', 'terminal')
        discord = self.event(b'{"role":"assistant","content":"keep"}\n', 'discord')
        for i in range(100):
            self.event(f'event {i:04d} '.encode() + b'x' * 90)
        self.assertLessEqual(self.scalar('SELECT sum(bytes) FROM diagnostic_batches'),900)
        self.assertEqual(self.scalar('SELECT count(*) FROM messages'),1)
        self.assertIsNotNone(self.store.db.execute('SELECT id FROM events WHERE id=?', (terminal,)).fetchone())
        self.assertIsNotNone(self.store.db.execute('SELECT id FROM events WHERE id=?', (discord,)).fetchone())
        maximum = self.scalar('SELECT max(id) FROM events')
        self.assertEqual(self.event(), maximum+1)
        self.assertEqual(self.scalar("SELECT sum(length(raw)) FROM events WHERE stream='diagnostic'"),self.scalar('SELECT sum(bytes) FROM diagnostic_batches'))
        self.assertEqual(self.scalar('PRAGMA integrity_check'),'ok')

    def test_twenty_before_after_survive_pruning_and_reopen(self):
        for i in range(25): self.event(f'before {i}\n'.encode())
        trigger = self.event(b'0.01 E srv send_error: synthetic error\n')
        failure = self.errors()[0]
        self.assertEqual(failure['before_count'],20)
        for i in range(10): self.event(f'after {i}\n'.encode())
        self.store.close()
        self.store = Store(self.path)
        for i in range(10,20): self.event(f'after {i}\n'.encode())
        failure = self.errors()[0]
        self.assertEqual((failure['state'],failure['remaining']),('complete',0))
        rows = self.store.db.execute('SELECT * FROM failure_events ORDER BY event_id').fetchall()
        self.assertEqual(len(rows),41)
        self.assertEqual([r['event_id'] for r in rows], list(range(trigger-20,trigger+21)))
        for i in range(100): self.event(b'padding' * 30)
        self.assertIsNone(self.store.db.execute('SELECT * FROM events WHERE id=?',(trigger,)).fetchone())
        self.assertIsNotNone(self.store.db.execute('SELECT * FROM error_evidence WHERE event_id=?',(trigger,)).fetchone())

    def test_distinct_errors_overlapping_windows_and_latest_twenty(self):
        for i in range(25): self.event(f'0.01 E runtime: failure {i}\n'.encode())
        self.assertEqual(len(self.errors()),20)
        self.assertEqual(self.errors()[0]['first_event'],6)
        evidence = self.scalar('SELECT count(*) FROM error_evidence')
        links = self.scalar('SELECT count(*) FROM failure_events')
        self.assertLess(evidence,links)  # Shared windows store original events once.
        for i in range(20): self.event()
        self.assertTrue(all(r['state']=='complete' for r in self.errors()))
        self.store.end(self.session)
        second = self.store.start()
        self.store.event(second,'diagnostic',b'0.01 E runtime: new session error\n')
        self.assertEqual(len(self.errors()),20)
        self.assertEqual(self.errors()[-1]['session_id'],second)

    def test_related_errors_group_but_prose_and_warning_do_not_trigger(self):
        prefix = b'Client: [message discord:1234] '
        self.event(prefix+b'Message input: "error failed failure"\n')
        self.event(prefix+b'Reasoning: "0.1 E synthetic"\n')
        self.event(b'0.1 W runtime: warning\n')
        self.assertEqual(self.errors(),[])
        self.event(prefix+b'[request 01] [tool 01] Tool Call failed: RuntimeError: synthetic\n')
        self.event(prefix+b'Message failed: RuntimeError: synthetic\n')
        self.event(prefix+b'Discord local request failed: synthetic\n')
        self.assertEqual(len(self.errors()),1)
        self.assertEqual(self.scalar("SELECT count(*) FROM failure_events WHERE relation='error'"),3)
        self.event(prefix+b'[request 01] [tool 02] Tool Call failed: RuntimeError: another failure\n')
        self.assertEqual(len(self.errors()),2)
        self.store.end(self.session)
        self.assertTrue(all(r['state']=='incomplete' for r in self.errors()))

    def test_discord_failures_and_last_following_event_are_grouped(self):
        def discord(title, **fields):
            self.event(('2026-11-11T00:00:00+00:00 '+title+' '+json.dumps(
                dict(log_message_id='discord:1234',sender_id='5678',**fields))+'\n').encode(),'discord')
        discord('Discord chunk failed.',error_type='HTTPException')
        discord('Discord turn failed; delivery may be partial; no automatic resend.',phase='delivery',error_type='HTTPException')
        self.assertEqual(len(self.errors()),1)
        for i in range(18): self.event()
        discord('Discord turn failed; delivery may be partial; no automatic resend.',phase='delivery',error_type='HTTPException')
        self.assertEqual(len(self.errors()),1)
        self.assertEqual(self.errors()[0]['state'],'complete')
        self.assertEqual(self.scalar('SELECT count(*) FROM failure_events'),21)
        self.event(b'{"role":"user","content":"Discord turn failed"}\n','discord')
        self.assertEqual(len(self.errors()),1)

    def test_evidence_truncation_and_transaction_rollback(self):
        with patch.object(retention,'EVIDENCE_BYTES',16):
            trigger=self.event(b'0.01 E runtime: '+b'x'*100)
        evidence=self.store.db.execute('SELECT * FROM error_evidence WHERE event_id=?',(trigger,)).fetchone()
        self.assertEqual(len(evidence['raw']),16)
        self.assertTrue(evidence['truncated'])
        before=self.scalar('SELECT next_event FROM retention_state')
        with self.assertRaises(RuntimeError), patch.object(retention,'prune',side_effect=RuntimeError('synthetic storage failure')):
            self.event(b'0.01 E runtime: rolled back\n')
        self.assertEqual(self.scalar('SELECT next_event FROM retention_state'),before)
        self.assertEqual(len(self.errors()),1)

    def test_snapshot_after_original_message_events_roll_out(self):
        identifier='discord:1234'
        self.store.message(self.session,identifier,'discord:5678',None,'discord','5678','user','input','synthetic','received')
        prefix=b'Client: [message discord:1234] '
        self.event(prefix+b'========== MESSAGE START | processing ==========\n')
        self.event(prefix+b'Conversation selected: discord:5678.\n')
        for i in range(25): self.event()  # Scope/start deliberately outside the window.
        self.event(prefix+b'Prompt budget: 100 tokens + 200 reply allowance < 512; removed_exchanges=0.\n')
        self.event(prefix+b'Message failed: RuntimeError: retained synthetic failure\n')
        self.event(prefix+b'========== MESSAGE END | processing | failed ==========\n')
        for i in range(100): self.event(b'padding'*30)
        self.assertEqual(self.scalar("SELECT count(*) FROM events WHERE message_id='discord:1234'"),0)
        result=database_snapshot(self.path,self.session,identifier,'discord:5678')
        self.assertEqual(result['context']['prompt_tokens'],100)
        self.assertEqual(result['processing']['status'],'incomplete')
        self.assertIn('retained synthetic failure',result['errors'][0]['message'])
        with self.assertRaises(ValueError):
            database_snapshot(self.path,self.session,identifier,'discord:9999')

    def test_backup_and_sql_restore_include_error_windows(self):
        self.event(b'0.1 E runtime: saved failure\n')
        for i in range(20): self.event()
        target=Path(self.temp.name)/'backup.sqlite3'
        backup(self.path,target)
        tables=('diagnostic_batches','retention_state','failures','failure_events','error_evidence','recent_diagnostics')
        dump=subprocess.check_output([sys.executable,str(ROOT/'src/marionette/storage.py'),str(self.path),'export'],text=True)
        with closing(open_read(target)) as restored, closing(sqlite3.connect(':memory:')) as portable:
            portable.executescript(dump)
            for table in tables:
                expected=[tuple(r) for r in self.store.db.execute(f'SELECT * FROM {table} ORDER BY 1')]
                self.assertEqual([tuple(r) for r in restored.execute(f'SELECT * FROM {table} ORDER BY 1')],expected)
                self.assertEqual(portable.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall(),expected)
            self.assertEqual(portable.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_v1_migration_preserves_records_and_backfills_errors(self):
        legacy=Path(self.temp.name)/'legacy.sqlite3'
        with closing(sqlite3.connect(legacy)) as db:
            db.executescript(SCHEMA)
            db.execute("INSERT INTO sessions VALUES ('old','time',NULL)")
            db.execute("INSERT INTO events VALUES (42,'old','2026-11-11T00:00:00+00:00','diagnostic','both',NULL,?)",(b'0.1 E runtime: legacy error\n',))
            db.commit()
        with closing(Store(legacy)) as migrated:
            self.assertEqual(migrated.db.execute('SELECT raw FROM events WHERE id=42').fetchone()[0],b'0.1 E runtime: legacy error\n')
            self.assertEqual(migrated.db.execute('SELECT first_event FROM failures').fetchone()[0],42)
            self.assertEqual(migrated.event('old','diagnostic',b'next\n'),43)
            self.assertEqual(migrated.db.execute('PRAGMA user_version').fetchone()[0],5)

    def test_crash_commits_partial_window_and_recovery_can_finish_it(self):
        code = """import os,sys
sys.path.insert(0, sys.argv[1])
from storage import Store
s=Store(sys.argv[2])
s.event(sys.argv[3], 'diagnostic', b'0.1 E runtime: crash fixture\\n')
os._exit(0)
"""
        subprocess.run([sys.executable,'-c',code,str(ROOT/'src/marionette'),str(self.path),self.session],check=True)
        self.assertEqual(self.errors()[0]['remaining'],20)
        self.assertEqual(self.errors()[0]['state'],'collecting')
        for i in range(20): self.event()
        self.assertEqual(self.errors()[0]['state'],'complete')
        self.assertEqual(self.scalar('PRAGMA integrity_check'),'ok')

    def test_migration_failure_rolls_back_without_losing_v1_data(self):
        legacy=Path(self.temp.name)/'rollback.sqlite3'
        with closing(sqlite3.connect(legacy)) as db:
            db.executescript(SCHEMA)
            db.execute("INSERT INTO sessions VALUES ('old','time',NULL)")
            db.execute("INSERT INTO events VALUES (1,'old','time','diagnostic','both',NULL,?)",(b'legacy',))
            db.commit()
        with patch.object(retention,'retain',side_effect=RuntimeError('synthetic migration interruption')):
            with self.assertRaises(RuntimeError): Store(legacy)
        with closing(sqlite3.connect(legacy)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT raw FROM events').fetchone()[0],b'legacy')
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='failures'").fetchone())
        with closing(Store(legacy)) as recovered:
            self.assertEqual(recovered.db.execute('PRAGMA user_version').fetchone()[0],5)

    def test_concurrent_writers_rotate_without_reusing_event_ids(self):
        errors=[]
        ids=[]
        def writer():
            try:
                with closing(Store(self.path)) as store:
                    for i in range(30):
                        ids.append(store.event(self.session,'diagnostic',b'synthetic concurrent '+b'x'*100))
            except Exception as error: errors.append(error)
        workers=[threading.Thread(target=writer) for _ in range(3)]
        for worker in workers: worker.start()
        for worker in workers: worker.join(5)
        self.assertFalse(any(w.is_alive() for w in workers))
        self.assertEqual(errors,[])
        self.assertEqual(len(set(ids)),90)
        self.assertLessEqual(self.scalar('SELECT sum(bytes) FROM diagnostic_batches'),900)
        self.assertEqual(self.scalar('PRAGMA integrity_check'),'ok')

    def test_operator_commands_and_database_snapshot_cli(self):
        prefix=b'Client: [message discord:1234] '
        self.event(prefix+b'Conversation selected: discord:5678.\n')
        self.event(prefix+b'Message failed: RuntimeError: operator fixture\n')
        command=[sys.executable,str(ROOT/'src/marionette/storage.py'),str(self.path)]
        status=json.loads(subprocess.check_output(command+['retention'],text=True))
        self.assertEqual(status['part_bytes'],300)
        failures=[json.loads(line) for line in subprocess.check_output(command+['errors'],text=True).splitlines()]
        evidence=subprocess.check_output(command+['error',str(failures[0]['id'])],text=True)
        self.assertIn('operator fixture',evidence)
        self.assertIn('truncated=False',evidence)
        result=subprocess.run(['bash',str(ROOT/'scripts/native-linux/log-snapshot.sh'),
            '--database',str(self.path),'--session',self.session,
            '--message-id','discord:1234','--conversation-id','discord:5678'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)['message']
        self.assertIn('operator fixture',report['errors'][0]['message'])
        self.assertEqual(self.scalar('SELECT count(*) FROM events'),2)

    def test_live_view_continues_across_pruning(self):
        # Synchronize after each visible event, so the test does not depend on sleeps.
        seen=threading.Event()
        class Output(io.BytesIO):
            def flush(inner): seen.set()
        output=Output()
        errors=[]
        def follow():
            try: view_log(self.path,self.session,'model',output,True)
            except Exception as error: errors.append(error)
        worker=threading.Thread(target=follow)
        worker.start()
        try:
            self.assertTrue(seen.wait(2))
            for i in range(8):
                seen.clear()
                self.event((f'visible-{i} '+ 'x'*250+'\n').encode())
                # A flush can race before insertion; verify output through bounded event waits.
                for attempt in range(30):
                    if f'visible-{i}'.encode() in output.getvalue(): break
                    seen.wait(.1); seen.clear()
                self.assertIn(f'visible-{i}'.encode(),output.getvalue())
        finally:
            self.store.end(self.session)
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors,[])
