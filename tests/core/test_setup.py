"""Isolated synthetic checks; no real models, conversations, or desktop windows."""
import hashlib
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('setup', ROOT / 'scripts/native-linux/setup.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='marionette-setup-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_checksum_failure_preserves_existing_file_and_cleans_partial(self):
        target = self.root / 'model'
        target.write_bytes(b'original')
        config = {'url': 'https://invalid.test/model', 'sha256': '0' * 64}
        with patch.object(setup.urllib.request, 'urlopen', return_value=io.BytesIO(b'bad')):
            with self.assertRaisesRegex(RuntimeError, 'Checksum mismatch'):
                setup.download(config, target)
        self.assertEqual(target.read_bytes(), b'original')
        self.assertEqual(list(self.root.glob('*.part')), [])

    def test_verified_download_and_cached_rerun(self):
        target = self.root / 'model'
        config = {'url': 'https://invalid.test/model', 'sha256': hashlib.sha256(b'valid').hexdigest()}
        with patch.object(setup.urllib.request, 'urlopen', return_value=io.BytesIO(b'valid')) as fetch:
            setup.download(config, target)
            setup.download(config, target)
            self.assertEqual(fetch.call_count, 1)
        self.assertEqual(target.read_bytes(), b'valid')

    def test_runtime_install_repeat_and_corruption_detection(self):
        archive = self.root / 'runtime.tar.gz'
        with tarfile.open(archive, 'w:gz') as bundle:
            member = tarfile.TarInfo('bin/completion')
            member.mode = 0o755
            member.size = len(b'fake runtime')
            bundle.addfile(member, io.BytesIO(b'fake runtime'))
        destination = self.root / 'installed'
        setup.install_runtime(archive, destination, 'bin/completion')
        executable = destination / 'bin/completion'
        inode = executable.stat().st_ino
        setup.install_runtime(archive, destination, 'bin/completion')
        self.assertEqual(executable.stat().st_ino, inode)
        executable.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'Runtime differs'):
            setup.install_runtime(archive, destination, 'bin/completion')
        self.assertEqual(executable.read_bytes(), b'changed')


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='marionette launch test ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        scripts = self.root / 'scripts/native-linux'
        scripts.mkdir(parents=True)
        for name in ['chat.sh', 'view-log.sh']:
            shutil.copy2(ROOT / 'scripts/native-linux' / name, scripts / name)
        source = self.root / 'src/marionette'
        source.mkdir(parents=True)
        for name in ['commands.py', 'inference.py', 'context.py', 'conversation.py', 'terminal.py', 'diagnostics.py', 'permissions.py', 'identity.py', 'session.py', 'log_router.py', 'connection.py', 'style.py', 'log_view.py']:
            shutil.copy2(ROOT / 'src/marionette' / name, source / name)
        manifest = {'runtime': {'version': 'test', 'executable': 'bin/completion'}, 'model': {'filename': 'test.gguf'}}
        (scripts / 'downloads.json').write_text(json.dumps(manifest))
        runtime = self.root / 'runtime/llama.cpp/test/bin/completion'
        runtime.parent.mkdir(parents=True)
        runtime.write_text('#!/usr/bin/env python\n' + (ROOT / 'tests/core/fake_server.py').read_text())
        runtime.chmod(0o755)
        model = self.root / 'data/models/test.gguf'
        model.parent.mkdir(parents=True)
        model.write_bytes(b'synthetic')
        tools = self.root / 'tools'
        tools.mkdir()
        viewer = tools / 'xdg-terminal-exec'
        viewer.write_text('#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$VIEWER_CALLS"\nexit 2\n')
        viewer.chmod(0o755)
        self.logs = self.root / 'private logs'
        self.env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'], MARIONETTE_LOG_DIR=str(self.logs), TERM='dumb', VIEWER_CALLS=str(self.root / 'viewer-calls.txt'))
        self.launcher = scripts / 'chat.sh'

    def run_chat(self, *args):
        return subprocess.run(['bash', str(self.launcher), *args], input='1\nhello\n/exit\n', text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env, cwd='/tmp', timeout=20)

    def test_private_pairs_separation_quoting_and_viewer_failure(self):
        marker = self.root / 'must-not-exist'
        payload = 'literal $(touch ' + str(marker) + ') ; "quoted"'
        for _ in range(2):
            result = self.run_chat('--synthetic-argument', payload)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())
        calls = (self.root / 'viewer-calls.txt').read_text()
        self.assertEqual(calls.count('Connections and requests'), 2)
        self.assertEqual(calls.count('Model processing'), 2)
        chats = list(self.logs.glob('*-chat.txt'))
        self.assertEqual(len(chats), 2)
        for chat in chats:
            debug = chat.with_name(chat.name.replace('-chat.txt', '-model.txt'))
            self.assertIn('Synthetic reply.', chat.read_text())
            self.assertIn(payload, debug.read_text())
            self.assertNotIn('synthetic diagnostic', chat.read_text())
            self.assertIn('synthetic diagnostic', debug.read_text())
            self.assertIn('Exit status: 0', debug.read_text())
            self.assertFalse(list(self.logs.glob('*-setup.json')))
            self.assertIn('Debug window could not open', result.stderr)
            server = chat.with_name(chat.name.replace('-chat.txt', '-server.txt'))
            self.assertIn('synthetic diagnostic', server.read_text())
            self.assertFalse(list(self.logs.glob('*-debug.txt')))
            self.assertEqual(len(list(self.logs.iterdir())), 6)
            for path in [chat, debug, server]:
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                restored = self.root / ('restored-' + path.name)
                shutil.copy2(path, restored)
                self.assertEqual(restored.read_bytes(), path.read_bytes())

    def test_second_chat_is_rejected_before_creating_logs(self):
        with (self.root / 'data/.chat.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_chat()
        self.assertEqual(result.returncode, 1)
        self.assertIn('already running', result.stderr)
        self.assertFalse(self.logs.exists())

    def test_child_failure_is_recorded_and_returned(self):
        result = self.run_chat('--test-fail')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Chat exited with status 1', result.stderr)
        self.assertIn('status 7', next(self.logs.glob('*-model.txt')).read_text())

    def test_inspection_does_not_create_a_session(self):
        result = self.run_chat('--version')
        self.assertEqual(result.returncode, 0)
        self.assertIn('synthetic runtime', result.stdout)
        self.assertFalse(self.logs.exists())

    def test_missing_source_fails_before_creating_logs(self):
        (self.root / 'src/marionette/session.py').unlink()
        result = self.run_chat()
        self.assertEqual(result.returncode, 1)
        self.assertIn('Application source missing', result.stderr)
        self.assertFalse(self.logs.exists())

    def test_external_server_override_rejected_before_launch(self):
        result = self.run_chat('--server-base', 'http://example.invalid')
        self.assertEqual(result.returncode, 1)
        self.assertIn('unsupported override', result.stderr)
        self.assertFalse(self.logs.exists())


if __name__ == '__main__':
    unittest.main()
