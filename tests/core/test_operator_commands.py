"""Operator controls use synthetic state and never touch real profiles or vaults."""
import io
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from contacts import ContactProfiles
from conversation import Conversation
from discord_access import DiscordAccess


class OperatorTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.profiles = ContactProfiles(self.root / 'contacts/profiles.json')
        self.owner = self.profiles.profiles[0]
        self.owner['linked_accounts'] = [{'service': 'discord', 'account_id': '123'}]
        self.profiles.save()
        self.api = Mock(closing=threading.Event(), cancelled=threading.Event(), tools=())
        self.api.address = 'http://127.0.0.1:1'
        self.api.count.return_value = 100
        self.c = Conversation(self.api, 8192, self.profiles, self.owner)
        self.c.discord_access = DiscordAccess(self.root)
        self.c.discord_control = SimpleNamespace(data=self.root, address='synthetic', database=self.root/'db')
        self.logs = patch('diagnostics.log').start()
        self.addCleanup(patch.stopall)

    def test_status_connections_context_and_permissions_without_generation(self):
        self.api.opener.open.return_value = io.BytesIO(b'{"status":"ok"}')
        with patch('operator_status.probe', return_value={'discord':'online'}), patch('vault_diagnostics.current_status', return_value={'status':'ready'}):
            self.assertIn('Model: online', self.c.turn('/status')[0])
            self.assertIn('Scarecrow: ready', self.c.turn('/connections')[0])
        self.assertIn('100 / 8192', self.c.turn('/context')[0])
        self.assertIn('3995', self.c.turn('/context')[0])
        self.c.terminal_profile = self.profiles.add('Guest')
        for command in ('status', 'connections', 'sync', 'cancel'):
            self.assertEqual(self.c.turn('/'+command)[0], 'Access Denied')
        self.assertIn('100 / 8192', self.c.turn('/context')[0])
        self.api.reply.assert_not_called()
        self.assertIsNone(self.c.pending)

    def test_sync_uses_existing_exporter_and_reports_failures(self):
        with patch('conversation_vault.sync') as sync:
            self.assertIn('mirror refreshed', self.c.turn('/sync')[0])
            self.assertEqual(sync.call_args.args[:3], (self.root/'db', self.root/'contacts/profiles.json', self.root/'contact_notes'))
            import sqlite3
            sync.side_effect = sqlite3.OperationalError('busy')
            with self.assertRaisesRegex(RuntimeError, 'Retry /sync'): self.c.turn('/sync')
            sync.side_effect = OSError('synthetic write failure')
            with self.assertRaises(OSError): self.c.turn('/sync')
        self.api.reply.assert_not_called()

    def test_dm_rules_persist_override_general_access_and_protect_owner(self):
        self.c.turn('/ddm off')
        self.assertIn('allowed', self.c.turn('/ddm allow <@456>')[0])
        self.assertTrue(DiscordAccess(self.root).admits('456'))
        self.assertFalse(self.c.discord_access.admits('789'))
        self.c.turn('/ddm block 456')
        self.c.turn('/ddm on')
        self.assertFalse(self.c.discord_access.admits('456'))
        self.c.turn('/ddm allow 456')
        self.assertTrue(self.c.discord_access.admits('456'))
        self.assertIn('stays open', self.c.turn('/ddm block 123')[0])
        for value in ('name', '<@123', '123>', '0', str(2**64)):
            self.assertIn('Usage:', self.c.turn('/ddm allow '+value)[0])

    def test_cancel_bypasses_turn_queue_preserves_history_and_can_resume(self):
        entered = threading.Event()
        self.api.cancel_reply.side_effect = self.api.cancelled.set
        def reply(*args, **kwargs):
            entered.set()
            self.assertTrue(self.api.cancelled.wait(3))
            raise RuntimeError('interrupted')
        self.api.reply.side_effect = reply
        original = [{'role':'user','content':'existing'}]
        self.c.history = original.copy()
        result = []
        thread = threading.Thread(target=lambda: result.append(self.c.turn('new input')))
        thread.start()
        self.assertTrue(entered.wait(2))
        self.assertEqual(self.c.cancel('discord', '456'), 'Access Denied')
        stale, _ = self.c.submit_discord('/cancel', sender_id='123', generation='stale')
        self.assertIn('discarded', stale)
        self.assertFalse(self.api.cancelled.is_set())
        answer, _ = self.c.submit_discord('/cancel', sender_id='123')
        self.assertIn('Cancellation requested', answer)
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result[0][1], 'cancelled')
        self.assertEqual(self.c.history, original)
        self.assertIsNone(self.c.pending)
        self.assertFalse(self.api.closing.is_set())
        self.assertEqual(self.c.cancel(), 'No generation is running.')
        self.api.reply.side_effect = lambda *a, **k: ('next answer', 'stop')
        self.assertEqual(self.c.turn('next')[0], 'next answer')
        self.c.finish_preparation()
        self.assertFalse(self.api.cancelled.is_set())

    def test_terminal_reads_cancel_during_turn_and_keeps_other_input(self):
        import os
        from terminal import CancelInput
        reader, writer = os.pipe()
        cancelled = threading.Event()
        control = Mock()
        control.cancel.side_effect = lambda: (cancelled.set() or 'Cancellation requested')
        try:
            with os.fdopen(reader) as stream, patch('sys.stdin', stream), patch.object(stream, 'isatty', return_value=True), patch('sys.stdout', io.StringIO()):
                inputs = CancelInput()
                with inputs.watch(control):
                    os.write(writer, b'next message\n/cancel\n')
                    self.assertEqual(inputs.deferred.get(timeout=2), 'next message')
                    self.assertTrue(cancelled.wait(2))
                control.cancel.assert_called_once_with()
        finally:
            os.close(writer)

    def test_interactive_terminal_cancel_then_queued_exit(self):
        import os
        import select
        import subprocess
        import time
        script = '''
import sys, threading
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0, sys.argv[1])
from contacts import ContactProfiles
from conversation import Conversation
from terminal import run
profiles = ContactProfiles(Path(sys.argv[2]) / 'contacts/profiles.json')
api = Mock(closing=threading.Event(), cancelled=threading.Event(), tools=())
api.count.return_value = 100
api.cancel_reply.side_effect = api.cancelled.set
def reply(*args, **kwargs):
    print('GENERATION_STARTED', flush=True)
    if not api.cancelled.wait(5): raise RuntimeError('cancel timed out')
    raise RuntimeError('cancelled')
api.reply.side_effect = reply
run(Conversation(api, 8192, profiles, profiles.profiles[0]))
'''
        master, slave = os.openpty()
        process = subprocess.Popen([sys.executable, '-c', script,
            str(Path(__file__).resolve().parents[2]/'src/marionette'), str(self.root)],
            stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        output = b''
        try:
            os.write(master, b'hello\n')
            deadline = time.monotonic() + 5
            while b'GENERATION_STARTED' not in output and time.monotonic() < deadline:
                if select.select([master], [], [], .1)[0]: output += os.read(master, 65536)
            self.assertIn(b'GENERATION_STARTED', output)
            os.write(master, b'/cancel\n/exit\n')
            deadline = time.monotonic() + 5
            while process.poll() is None and time.monotonic() < deadline:
                if select.select([master], [], [], .1)[0]:
                    try: output += os.read(master, 65536)
                    except OSError: break
            self.assertEqual(process.wait(timeout=2), 0, output.decode())
            self.assertIn(b'Generation cancelled.', output)
            self.assertNotIn(b'cancel timed out', output)
        finally:
            if process.poll() is None:
                process.kill(); process.wait()
            os.close(master)
