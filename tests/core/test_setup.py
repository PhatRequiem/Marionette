"""Isolated synthetic checks; no real models, conversations, or desktop windows."""
from contextlib import closing
import hashlib
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import signal
import time
import stat
import sqlite3
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src/marionette"))
from storage import open_read, view_log
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

    def test_setup_uses_shared_model_and_app_libraries(self):
        home = self.root / 'synthetic home'
        for override in ['', str(self.root / 'custom model library')]:
            with self.subTest(override=override), patch.dict(os.environ, MARIONETTE_MODELS_DIR=override, MARIONETTE_APPS_DIR=override), \
                    patch.object(Path, 'home', return_value=home), patch.object(setup, 'ROOT', self.root), \
                    patch.object(setup.subprocess, 'run'), patch.object(setup, 'download') as download, patch.object(setup, 'install_runtime') as install_runtime:
                setup.install()
                model = setup.MANIFEST['model']
                expected_root = Path(override) if override else home / 'AI Infrastructure' / 'AI Local Models'
                self.assertEqual(download.call_args.args, (model, expected_root / model['directory'] / model['filename']))
                self.assertFalse((self.root / 'data/models').exists())
                runtime = setup.MANIFEST['runtime']
                expected_apps = Path(override) if override else home / 'AI Infrastructure' / 'AI Apps'
                archive = self.root / 'data/downloads' / runtime['url'].rsplit('/', 1)[-1]
                self.assertEqual(install_runtime.call_args.args, (archive, expected_apps / runtime['directory'] / runtime['version'], runtime['executable']))
                self.assertFalse((self.root / 'runtime/llama.cpp').exists())


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='marionette launch test ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        scripts = self.root / 'scripts/native-linux'
        scripts.mkdir(parents=True)
        for name in ['chat.sh', 'view-log.sh']:
            shutil.copy2(ROOT / 'scripts/native-linux' / name, scripts / name)
        shutil.copytree(ROOT / 'prompts', self.root / 'prompts')
        source = self.root / 'src/marionette'
        source.mkdir(parents=True)
        for name in ['conversation_vault.py', 'conversation_refs.py', 'memory_reset.py', 'reset_boundary.py', 'data_migration.py', 'storage.py', 'operator_status.py', 'log_tool.py', 'log_query.py', 'setup_datasheet.py', 'log_metadata.py', 'retention.py', 'ram_logs.py', 'soul.py', 'contact_notes.py', 'coordination.py', 'commands.py', 'inference.py', 'context.py', 'conversation.py', 'terminal.py', 'diagnostics.py', 'permissions.py', 'contacts.py', 'session.py', 'log_router.py', 'connection.py', 'style.py', 'log_view.py']:
            shutil.copy2(ROOT / 'src/marionette' / name, source / name)
        manifest = {'runtime': {'directory': 'Inference Engines/Language Models/llama.cpp', 'version': 'test', 'executable': 'bin/completion'}, 'model': {'directory': 'Language/test', 'filename': 'test.gguf'}}
        (scripts / 'downloads.json').write_text(json.dumps(manifest))
        (self.root / 'runtime').mkdir()
        (self.root / 'runtime/agent').symlink_to(ROOT / 'runtime/agent', target_is_directory=True)
        self.home = self.root / 'synthetic home'
        self.runtime = self.home / 'AI Infrastructure/AI Apps' / manifest['runtime']['directory'] / 'test/bin/completion'
        runtime = self.runtime
        runtime.parent.mkdir(parents=True)
        runtime.write_text('#!/usr/bin/env python\n' + (ROOT / 'tests/core/fake_server.py').read_text())
        runtime.chmod(0o755)
        self.model = self.home / 'AI Infrastructure/AI Local Models/Language/test/test.gguf'
        model = self.model
        model.parent.mkdir(parents=True)
        model.write_bytes(b'synthetic')
        (self.root / 'docs/active/setup-and-maintenance').mkdir(parents=True)
        shutil.copy2(ROOT / 'docs/active/setup-and-maintenance/setup-datasheet.md', self.root / 'docs/active/setup-and-maintenance/setup-datasheet.md')
        (self.root / 'data').mkdir()
        tools = self.root / 'tools'
        tools.mkdir()
        viewer = tools / 'xdg-terminal-exec'
        viewer.write_text('#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$VIEWER_CALLS"\nexit 2\n')
        viewer.chmod(0o755)
        self.logs = self.root / 'private logs'
        self.env = dict(os.environ, HOME=str(self.home), MARIONETTE_MODELS_DIR='', MARIONETTE_APPS_DIR='', PATH=str(tools) + os.pathsep + os.environ['PATH'], MARIONETTE_LOG_DIR=str(self.logs), TERM='dumb', VIEWER_CALLS=str(self.root / 'viewer-calls.txt'))
        self.launcher = scripts / 'chat.sh'

    def run_chat(self, *args):
        return subprocess.run(['bash', str(self.launcher), *args], input='1\nhello\n/exit\n', text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env, cwd='/tmp', timeout=20)

    def test_owner_shutdown_uses_orderly_launcher_cleanup(self):
        result = subprocess.run(['bash', str(self.launcher)],
            input='1\nhello before shutdown\n/shutdown\n', text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env, cwd='/tmp', timeout=25)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Shutting down Marionette', result.stdout)
        self.assertIn('Conversation vault refreshed.', result.stdout)
        vault = self.logs / 'obsidian-vault'
        pages = list((vault / 'Generated/Contacts').rglob('*conversation-*.md'))
        self.assertTrue(pages)
        self.assertTrue(any('hello before shutdown' in p.read_text() for p in pages))
        self.assertTrue((vault / 'Generated/Self documentation/active/setup-and-maintenance/setup-datasheet.md').exists())
        with closing(open_read(self.logs / 'marionette.sqlite3')) as db:
            self.assertIsNotNone(db.execute('SELECT ended_at FROM sessions').fetchone()[0])
            self.assertIn('hello before shutdown', [r[0] for r in db.execute("SELECT content FROM messages WHERE kind='input'")])
            self.assertGreater(db.execute("SELECT count(*) FROM events WHERE stream='diagnostic'").fetchone()[0], 0)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_shutdown_export_failure_reports_error_and_preserves_saved_data(self):
        (self.root / 'src/marionette/conversation_vault.py').write_text("raise RuntimeError('synthetic export failure')\n")
        result = self.run_chat()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Conversation vault refresh failed', result.stderr)
        with closing(open_read(self.logs / 'marionette.sqlite3')) as db:
            self.assertIsNotNone(db.execute('SELECT ended_at FROM sessions').fetchone()[0])
            self.assertIn('hello', [r[0] for r in db.execute("SELECT content FROM messages WHERE kind='input'")])
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_live_reset_through_launcher_keeps_server_and_clears_previous_turn(self):
        self.logs = self.root / 'data/conversations'
        self.env['MARIONETTE_LOG_DIR'] = str(self.logs)
        result = subprocess.run(['bash', str(self.launcher)],
            input='1\nOLD_RESET_SENTINEL\n/resetmemory\nnew turn\n/exit\n', text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env, cwd='/tmp', timeout=25)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Memory reset. Soul, contact notes', result.stdout)
        self.assertNotIn('MARIONETTE_RESET:', result.stdout)
        with closing(open_read(self.logs / 'marionette.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0],1)
            self.assertEqual([r[0] for r in db.execute("SELECT content FROM messages WHERE kind='input'")], ['new turn'])
            self.assertFalse(any(b'OLD_RESET_SENTINEL' in bytes(r[0]) for r in db.execute('SELECT raw FROM events')))
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')

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
        database = self.logs / 'marionette.sqlite3'
        with closing(open_read(database)) as db:
            sessions = db.execute('SELECT * FROM sessions').fetchall()
            self.assertEqual(len(sessions), 2)
            self.assertTrue(all(row['ended_at'] for row in sessions))
            self.assertEqual(db.execute('SELECT count(*) FROM messages WHERE kind="answer"').fetchone()[0], 2)
        for session in sessions:
            chat = self.saved('terminal', session['id'])
            debug = self.saved('model', session['id'])
            self.assertIn('Synthetic reply.', chat)
            self.assertIn(payload, debug)
            self.assertIn(str(self.model), debug)
            self.assertIn('--cache-ram 5120', debug)
            self.assertIn('--parallel 1', debug)
            self.assertNotIn('synthetic diagnostic', chat)
            self.assertIn('synthetic diagnostic', debug)
            self.assertIn('Exit status: 0', debug)
            self.assertIn('Debug window could not open', result.stderr)
            self.assertIn('synthetic diagnostic', self.saved('server', session['id']))
        self.assertFalse(list(self.logs.glob('*.txt')))
        self.assertEqual(stat.S_IMODE(database.stat().st_mode), 0o600)

    def saved(self, view, session=None):
        database = self.logs / 'marionette.sqlite3'
        if session is None:
            with closing(open_read(database)) as db:
                session = db.execute('SELECT id FROM sessions ORDER BY started_at DESC').fetchone()[0]
        output = io.BytesIO()
        view_log(database, session, view, output)
        return output.getvalue().decode()

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
        self.assertIn('status 7', self.saved('model'))

    def test_inspection_does_not_create_a_session(self):
        result = self.run_chat('--version')
        self.assertEqual(result.returncode, 0)
        self.assertIn('synthetic runtime', result.stdout)
        self.assertFalse(self.logs.exists())

    def test_custom_shared_library_with_spaces(self):
        library = self.root / 'custom model library'
        target = library / 'Language/test/test.gguf'
        target.parent.mkdir(parents=True)
        self.model.rename(target)
        self.env['MARIONETTE_MODELS_DIR'] = str(library)
        result = self.run_chat()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(target), self.saved('model'))
        self.assertFalse((self.root / 'data/models').exists())

    def test_custom_shared_runtime_with_spaces(self):
        apps = self.root / 'custom app library'
        target = apps / 'Inference Engines/Language Models/llama.cpp/test/bin/completion'
        target.parent.mkdir(parents=True)
        self.runtime.rename(target)
        self.env['MARIONETTE_APPS_DIR'] = str(apps)
        result = self.run_chat()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Synthetic reply.', self.saved('terminal'))
        self.assertFalse((self.root / 'runtime/llama.cpp').exists())

    def test_ctrl_c_drains_recorders_and_stops_server(self):
        output = self.root / 'interrupt.txt'
        with output.open('w') as stream:
            process = subprocess.Popen(['bash', str(self.launcher)], stdin=subprocess.PIPE,
                stdout=stream, stderr=subprocess.STDOUT, env=self.env, text=True, start_new_session=True)
            try:
                process.stdin.write('1\n'); process.stdin.flush()
                deadline = time.monotonic() + 10
                while 'Ready.' not in output.read_text():
                    self.assertIsNone(process.poll(), output.read_text())
                    self.assertLess(time.monotonic(), deadline, output.read_text())
                    time.sleep(.02)
                os.killpg(process.pid, signal.SIGINT)
                process.communicate(timeout=10)
                self.assertEqual(process.returncode, 0, output.read_text())
                self.assertIn('Local server stopped.', self.saved('model'))
                self.assertIn('Exit status: 0', self.saved('model'))
                self.assertFalse((self.root / 'data/session/chat.sock').exists())
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.communicate(timeout=10)

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
