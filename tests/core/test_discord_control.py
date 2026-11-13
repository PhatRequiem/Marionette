"""Background Discord process lifecycle using a synthetic bot, never Discord login."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/marionette'))
from discord_control import DiscordControl
from storage import Store

ROOT = Path(__file__).resolve().parents[2]


class DiscordControlTests(unittest.TestCase):
    def test_terminal_commands_launch_stop_and_cleanup_on_chat_exit(self):
        from test_setup import LauncherTests
        fixture=LauncherTests();fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        root=fixture.root
        python=root/'runtime/discord/bin/python'
        python.parent.mkdir(parents=True)
        python.symlink_to(sys.executable)
        (root/'src/marionette/discord_bot.py').write_text('''import os,signal,sys,time
from pathlib import Path
if '--check-config' in sys.argv:sys.exit(0)
signal.signal(signal.SIGINT,lambda *args:sys.exit(0))
address=Path(os.environ['MARIONETTE_DATA_DIR'])/'session/chat.sock'
print('synthetic background ready',flush=True)
while address.exists():time.sleep(.02)
print('synthetic background stopped',flush=True)
''')
        result=subprocess.run(['bash',str(fixture.launcher)],
            input='1\n/startdiscord\nhello\n/stopdiscord\n/startdiscord\nhello again\n/shutdown\n',
            text=True,capture_output=True,env=fixture.env,cwd='/tmp',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.count('Discord is starting.'),2)
        self.assertIn('Discord stopped. Marionette is still running.',result.stdout)
        self.assertIn('Shutting down Marionette',result.stdout)
        self.assertNotIn('synthetic background ready',result.stdout)
        self.assertNotIn('synthetic background stopped',result.stdout)
        self.assertIn('synthetic background ready',fixture.saved('server'))
        self.assertIn('synthetic background stopped',fixture.saved('server'))
        import fcntl
        with (root/'data/discord/.connection.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)  # Shutdown drained and released it.

    def test_start_duplicate_stop_restart_and_drain(self):
        import socket
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            data=root/'data'; (data/'session').mkdir(parents=True)
            address=data/'session/chat.sock'
            listener=socket.socket(socket.AF_UNIX)
            self.addCleanup(listener.close)
            listener.bind(str(address))
            python=root/'runtime/discord/bin/python'
            python.parent.mkdir(parents=True)
            python.symlink_to(sys.executable)
            shutil.copytree(ROOT/'src/marionette',root/'src/marionette')
            (root/'src/marionette/discord_bot.py').write_text('''import signal,sys,time
if '--check-config' in sys.argv:sys.exit(0)
def stop(*args):
 print('synthetic disconnected',flush=True)
 sys.exit(0)
signal.signal(signal.SIGINT,stop)
print('synthetic ready',flush=True)
while True:time.sleep(.01)
''')
            store=Store(data/'conversations/marionette.sqlite3')
            self.addCleanup(store.close)
            session=store.start()
            control=DiscordControl(data,address,data/'conversations/marionette.sqlite3',session,root)
            def cleanup():
                if control.watcher and control.watcher.is_alive(): control.stop()
            self.addCleanup(cleanup)
            with patch('diagnostics.log'):
                for cycle in range(2):
                    self.assertIn('starting',control.start())
                    deadline=time.monotonic()+5
                    while store.db.execute("SELECT count(*) FROM events WHERE stream='discord'").fetchone()[0] < cycle*2+1:
                        self.assertLess(time.monotonic(),deadline)
                        time.sleep(.02)
                    self.assertIn('already',control.start())
                    other=DiscordControl(data,address,data/'conversations/marionette.sqlite3',session,root)
                    self.assertIn('already',other.start())
                    self.assertIn('Discord stopped',control.stop())
                    self.assertFalse(control.watcher.is_alive())
                raw=b''.join(r[0] for r in store.db.execute("SELECT raw FROM events WHERE stream='discord'"))
                self.assertEqual(raw.count(b'synthetic disconnected'),2)
                self.assertEqual(raw.count(b'synthetic ready'),2)
