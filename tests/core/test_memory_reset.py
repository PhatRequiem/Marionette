"""Live reset with synthetic identities and real recorder subprocesses."""
import io
import copy
import json
import os
import socket
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
from conversation_vault import sync
from reset_boundary import BoundaryReader, marker
from commands import recognize
from ram_logs import RamLogs
from clock_tool import GetCurrentTime
from contact_profile import UpdateContactProfile
from contact_notes import UpdateContactNotes
from connection import LocalConnection
from data_migration import migrate_personal_paths
from reset_boundary import INCOMPLETE, require_complete


class MemoryResetTests(unittest.TestCase):
    def test_alternate_vault_refused_before_any_memory_changes(self):
        from memory_reset import reset_memory
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'session').mkdir()
            (root/'session/log-session.json').write_text('{}')
            profiles = ContactProfiles(root/'contacts/profiles.json')
            soul = Soul(root/'soul/profile.json')
            notes = ContactNotes(root/'contact_notes')
            store = Store(root/'conversations/marionette.sqlite3')
            self.addCleanup(store.close)
            api = Mock()
            convo = Conversation(api,8192,profiles,profiles.profiles[0],notes,store,store.start(),soul)
            external = root/'alternate-vault'
            external.mkdir()
            old = external/'old.md'
            old.write_text('synthetic old memory')
            config = root/'scarecrow/connection.json'
            config.parent.mkdir()
            before = profiles.path.read_bytes(), soul.path.read_bytes()
            for enabled in (True, False):
                config.write_text(json.dumps({'enabled':enabled,'vault':str(external)}))
                with self.assertRaisesRegex(ValueError,'alternate Scarecrow vault'):
                    reset_memory(convo)
                api.prepare.assert_not_called()
                self.assertEqual(before,(profiles.path.read_bytes(),soul.path.read_bytes()))
                self.assertEqual(old.read_text(),'synthetic old memory')

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
                owner['linked_accounts']=[{'service':'discord','account_id':'123'},
                                          {'service':'discord','account_id':'456'},
                                          {'service':'example','account_id':'owner'}]
                owner['preferred_name']='Owner nickname'
                owner['timezone']='America/New_York'
                profiles.save()
                saved_owner=copy.deepcopy(owner)
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
                vault=Path(sync(dbpath)['vault'])
                (vault/'Annotations/private.md').write_text('OLD_SECRET')
                settings = vault/'.obsidian/plugins/scarecrow/data.json'
                settings.parent.mkdir(parents=True)
                settings.write_text('{"token":"synthetic-credential"}')
                plugin = settings.with_name('main.js')
                plugin.write_text('// synthetic plugin')
                (vault/'.obsidian/app.json').write_text('{"vimMode":true}')
                preserved = {p.relative_to(vault): p.read_bytes()
                             for p in (vault/'.obsidian').rglob('*') if p.is_file()}
                for name in ('contacts','contact_notes','soul','conversations','session',
                             'identities','characters','self'):
                    backup=root/name/'archive/nested'
                    backup.mkdir(parents=True)
                    (backup/'private-copy.json').write_text('OLD_SECRET')
                directories={p for p in root.rglob('*') if p.is_dir()}
                api=Mock(closing=threading.Event(), tools=())
                custom=Mock();custom.name='synthetic_tool'
                api.tools=(soul.bind(api),GetCurrentTime(),custom,
                           UpdateContactProfile(profiles,identity),UpdateContactNotes(notes,identity,'OLD_SECRET'))
                conversation=Conversation(api,8192,profiles,owner,notes,store,session,soul)
                conversation.bind_log_query()
                tool_names={t.name for t in api.tools}
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
                    paused,release=threading.Event(),threading.Event()
                    replies=[]
                    address=root/'session/chat.sock'
                    def delayed_log(line):
                        if 'Discord local request received.' in line:
                            paused.set()
                            if not release.wait(5):
                                raise RuntimeError('Synthetic handler gate timed out')
                        import diagnostics
                        diagnostics.log(line)
                    def request():
                        with socket.socket(socket.AF_UNIX) as client:
                            client.settimeout(10)
                            client.connect(str(address))
                            client.sendall((json.dumps({'sender_id':'123','message':'OLD_SECRET delayed request','generation':''})+'\n').encode())
                            with client.makefile('rb') as stream:
                                replies.append(json.loads(stream.readline()))
                    with patch('diagnostics.write',side_effect=lambda raw:(diag.stdin.write(raw),diag.stdin.flush())),patch('sys.stdout',Mock(buffer=terminal.stdin)):
                        with LocalConnection(address,conversation.submit_discord,delayed_log):
                            worker=threading.Thread(target=request)
                            worker.start()
                            try:
                                self.assertTrue(paused.wait(5))
                                answer,finish=conversation.turn('/resetmemory',source=source,sender_id='123' if source=='discord' else None)
                            finally:
                                release.set()
                                worker.join(5)
                            self.assertFalse(worker.is_alive())
                            self.assertIn('discarded',replies[0]['answer'])
                    self.assertEqual(finish,'resetmemory')
                    self.assertIn('Memory reset',answer)
                    self.assertIn('get_current_time', [t.name for t in api.tools])
                    self.assertEqual({t.name for t in api.tools},tool_names)
                    self.assertIn(custom,api.tools)
                    self.assertIsNone(next(t for t in api.tools if t.name=='update_contact_notes').content)
                    self.assertEqual(next(t for t in api.tools if t.name=='update_soul').current['content'],'')
                    api.prepare.assert_called_once_with([])
                    self.assertIsNone(api.system_prompt)
                    api.reply.assert_not_called()
                    self.assertFalse(api.closing.is_set())
                    self.assertEqual(conversation.histories,{})
                    self.assertEqual(len(profiles.profiles),1)
                    self.assertEqual(profiles.profiles[0]['uuid'],owner['uuid'])
                    self.assertEqual(profiles.profiles,[saved_owner])
                    self.assertEqual(json.loads(profiles.path.read_text())['profiles'],[saved_owner])
                    self.assertEqual(profiles.resolve('discord','123')['contact_uuid'],owner['uuid'])
                    self.assertEqual(soul.read()['uuid'],uid)
                    self.assertEqual(soul.read()['revisions'][-1]['content'],'')
                    self.assertEqual(len(soul.read()['revisions']),1)
                    self.assertFalse(any(p.is_file() for p in notes.directory.rglob('*')))
                    self.assertFalse((root/'soul/export.json').exists())
                    self.assertTrue(all(p.is_dir() for p in directories))
                    self.assertFalse(any(p.name=='private-copy.json' for p in root.rglob('*')))
                    self.assertFalse((root/INCOMPLETE).exists())
                    migrate_personal_paths(root)
                    self.assertEqual(preserved, {p.relative_to(vault): p.read_bytes()
                        for p in (vault/'.obsidian').rglob('*') if p.is_file()})
                    sync(dbpath)
                    self.assertTrue(all(p.is_dir() for p in directories))
                    self.assertTrue((vault/'Generated/.marionette-managed').is_file())
                    self.assertFalse(any('OLD_SECRET' in p.read_text()
                        for p in vault.rglob('*.md')))
                    for path, content in preserved.items():
                        self.assertEqual((vault/path).read_bytes(), content)
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

    def test_prepare_failure_preserves_tools_and_blocks_restart_and_export(self):
        import session
        with tempfile.TemporaryDirectory() as directory,patch('diagnostics.log'):
            root=Path(directory)
            (root/'session').mkdir()
            (root/'session/log-session.json').write_text('{}')
            profiles=ContactProfiles(root/'contacts/profiles.json')
            owner=copy.deepcopy(profiles.profiles[0])
            soul=Soul(root/'soul/profile.json')
            notes=ContactNotes(root/'contact_notes')
            store=Store(root/'conversations/marionette.sqlite3')
            self.addCleanup(store.close)
            api=Mock(closing=threading.Event(),tools=())
            api.tools=(soul.bind(api),GetCurrentTime())
            api.prepare.side_effect=RuntimeError('Synthetic preparation failure')
            convo=Conversation(api,8192,profiles,profiles.profiles[0],notes,store,store.start(),soul)
            with self.assertRaisesRegex(RuntimeError,'Synthetic preparation failure'):
                convo.turn('/resetmemory')
            self.assertTrue(convo.resetting)
            self.assertEqual({t.name for t in api.tools},{'update_soul','get_current_time'})
            self.assertEqual(profiles.profiles,[owner])
            self.assertTrue((root/INCOMPLETE).exists())
            with self.assertRaisesRegex(RuntimeError,'reset incomplete'):
                convo.turn('must not run')
            with self.assertRaisesRegex(RuntimeError,'reset is incomplete'):
                require_complete(root)
            with self.assertRaisesRegex(RuntimeError,'reset is incomplete'):
                sync(root/'conversations/marionette.sqlite3')
            with patch.dict(os.environ,{'MARIONETTE_DATA_DIR':str(root)}),patch('session.subprocess.Popen') as start:
                with self.assertRaisesRegex(RuntimeError,'reset is incomplete'):
                    session.run(['synthetic-model'])
                start.assert_not_called()
                with self.assertRaisesRegex(RuntimeError,'reset is incomplete'):
                    session.chat(api,8192)
            api.reply.assert_not_called()

    def test_nonowner_cannot_reset_or_invoke_model(self):
        with tempfile.TemporaryDirectory() as directory,patch('diagnostics.log'):
            profiles=ContactProfiles(Path(directory)/'profiles.json')
            api=Mock(closing=threading.Event())
            convo=Conversation(api,8192,profiles,profiles.profiles[0])
            convo.histories={'saved':[{'role':'user','content':'preserve'}]}
            with patch('memory_reset.reset_memory') as reset:
                answer,finish=convo.turn('/resetmemory',source='discord',sender_id='999')
                self.assertEqual(answer, 'Access Denied')
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
