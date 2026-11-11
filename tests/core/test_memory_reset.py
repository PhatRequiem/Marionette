"""Live reset with synthetic identities and real recorder subprocesses."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/marionette'))
from contacts import ContactProfiles
from contact_notes import ContactNotes
from soul import Soul
from conversation import Conversation
from storage import Store
from reset_boundary import BoundaryReader, marker
from commands import recognize
from ram_logs import RamLogs


class MemoryResetTests(unittest.TestCase):
    def test_marker_survives_every_chunk_boundary(self):
        token='00000000-0000-0000-0000-000000000001'
        value=b'before'+marker(token)+b'after'
        for cut in range(len(value)+1):
            reader=BoundaryReader()
            result=list(reader.feed(value[:cut]))+list(reader.feed(value[cut:]))
            self.assertEqual([g for g,p in result if g], [token])
            self.assertEqual(b''.join(p for g,p in result),b'beforeafter')

    def test_owner_reset_both_sources_keeps_model_and_cannot_resurrect_logs(self):
        for source in ('terminal','discord'):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                (root/'session').mkdir()
                profiles=ContactProfiles(root/'contacts/profiles.json')
                owner=profiles.profiles[0]
                owner['linked_accounts']=[{'service':'discord','account_id':'123'}]
                profiles.save()
                profiles.add('Other')
                notes=ContactNotes(root/'contact_notes')
                identity=profiles.resolve('terminal',owner['uuid'])
                notes.current(identity)
                notes.save(owner['uuid'],'# Phat\nPrivate old note',expected='# Phat\n')
                soul=Soul(root/'soul/profile.json')
                uid=soul.read()['uuid']
                soul.save('Old private soul',soul.read()['revisions'][-1],name='Before')
                (root/'soul/export.json').write_text('old private export')
                dbpath=root/'conversations/marionette.sqlite3'
                store=Store(dbpath)
                session=store.start()
                (root/'session/log-session.json').write_text(json.dumps({'database':str(dbpath),'session':session}))
                old_writer=Store(dbpath)
                store.message(session,'local:00000000-0000-0000-0000-000000000001','terminal:test',identity,'terminal','test','user','input','OLD_SECRET','received')
                api=Mock(closing=threading.Event(), tools=())
                conversation=Conversation(api,8192,profiles,owner,notes,store,session,soul)
                conversation.histories={'terminal:test':[{'role':'user','content':'OLD_SECRET'}], 'discord:123':[{'role':'user','content':'old'}]}
                capture=Path(__file__).resolve().parents[2]/'src/marionette/storage.py'
                processes=[]
                try:
                    for stream in ('diagnostic','terminal'):
                        processes.append(subprocess.Popen([sys.executable,str(capture),str(dbpath),'capture',session,stream],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE))
                    diag,terminal=processes
                    diag.stdin.write(b'0.1 E runtime: OLD_SECRET\n');diag.stdin.flush()
                    terminal.stdin.write(b'OLD_SECRET\n');terminal.stdin.flush()
                    # Ensure recorders have opened the old epoch before requesting reset.
                    deadline=time.monotonic()+5
                    while not store.db.execute('SELECT count(*) FROM events').fetchone()[0]:
                        if time.monotonic()>deadline: self.fail('Recorder did not start')
                        time.sleep(.02)
                    with patch('diagnostics.log'),patch('diagnostics.write',side_effect=lambda raw:(diag.stdin.write(raw),diag.stdin.flush())),patch('sys.stdout',Mock(buffer=terminal.stdin)):
                        answer,finish=conversation.turn('/resetmemory',source=source,sender_id='123' if source=='discord' else None)
                    self.assertEqual(finish,'resetmemory')
                    self.assertIn('Memory reset',answer)
                    api.reply.assert_not_called()
                    self.assertFalse(api.closing.is_set())
                    self.assertEqual(conversation.histories,{})
                    self.assertEqual(len(profiles.profiles),1)
                    self.assertEqual(profiles.profiles[0]['uuid'],owner['uuid'])
                    self.assertEqual(profiles.resolve('discord','123')['contact_uuid'],owner['uuid'])
                    self.assertEqual(soul.read()['uuid'],uid)
                    self.assertEqual(soul.read()['revisions'][-1]['content'],'')
                    self.assertEqual(len(soul.read()['revisions']),1)
                    self.assertEqual(list(notes.directory.iterdir()),[])
                    self.assertFalse((root/'soul/export.json').exists())
                    self.assertIsNone(old_writer.event(session,'discord',b'OLD_SECRET delayed'))
                    self.assertEqual(store.db.execute('SELECT count(*) FROM messages').fetchone()[0],0)
                    for proc in processes:proc.stdin.close()
                    for proc in processes:
                        self.assertEqual(proc.wait(timeout=5),0,proc.stderr.read().decode())
                    self.assertFalse(any(b'OLD_SECRET' in bytes(r[0]) for r in store.db.execute('SELECT raw FROM events')))
                    self.assertEqual(store.db.execute('SELECT count(*) FROM failures').fetchone()[0],0)
                    self.assertEqual(store.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                finally:
                    for proc in processes:
                        if proc.poll() is None:proc.kill();proc.wait()
                        if not proc.stdin.closed:proc.stdin.close()
                        proc.stderr.close()
                    old_writer.close();store.close()

    def test_nonowner_cannot_reset_or_invoke_model(self):
        with tempfile.TemporaryDirectory() as directory,patch('diagnostics.log'):
            profiles=ContactProfiles(Path(directory)/'profiles.json')
            api=Mock(closing=threading.Event())
            convo=Conversation(api,8192,profiles,profiles.profiles[0])
            convo.histories={'saved':[{'role':'user','content':'preserve'}]}
            with patch('memory_reset.reset_memory') as reset:
                answer,finish=convo.turn('/resetmemory',source='discord',sender_id='999')
                self.assertEqual(answer, 'Access denied. The /resetmemory command is restricted to the owner.')
                reset.assert_not_called();api.reply.assert_not_called()
                self.assertTrue(convo.histories['saved'])
            self.assertEqual(recognize('/resetmemory','discord'),'resetmemory')
            self.assertEqual(recognize('/resetmemory','terminal'),'resetmemory')

    def test_interrupted_boundary_never_saves_old_ram(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'db.sqlite3');session=store.start()
            ram=RamLogs(store,session)
            ram.append(b'0.1 E runtime: OLD_SECRET\n','both')
            store.reset_memory(session,'00000000-0000-0000-0000-000000000001')
            ram.save()
            self.assertEqual(store.db.execute('SELECT count(*) FROM events').fetchone()[0],0)
            self.assertEqual(store.db.execute('SELECT count(*) FROM failures').fetchone()[0],0)
            ram.close();store.close()

    def test_stale_queued_dm_is_discarded_without_reading_model(self):
        from concurrent.futures import Future
        import terminal
        api=Mock(closing=threading.Event())
        convo=Conversation(api,8192)
        future=Future();future.memory_epoch='old'
        convo.epoch='new'
        convo.incoming.put(('OLD_SECRET','123',future,time.monotonic(),None,None))
        self.assertTrue(terminal.display_discord(convo))
        self.assertIn('discarded',future.result()[0])
        api.reply.assert_not_called()
        self.assertFalse(convo.histories)
        self.assertIn('discarded',convo.submit_discord('OLD_SECRET',sender_id='123',generation='old')[0])

    def test_owner_claim_cannot_override_resolved_account(self):
        from permissions import require_reset
        with tempfile.TemporaryDirectory() as directory:
            profiles=ContactProfiles(Path(directory)/'profiles.json')
            owner=profiles.profiles[0]
            profiles.register_discord('999')
            with self.assertRaises(PermissionError):
                require_reset({'contact_uuid':owner['uuid'],'source':'discord','sender_id':'999'},profiles)
