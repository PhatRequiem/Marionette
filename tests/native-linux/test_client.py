"""Conversation policy: system preservation, exact budgets, and failed turns."""
import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('client', ROOT / 'scripts/native-linux/session.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class ClientTests(unittest.TestCase):
    def test_rollover_removes_whole_exchanges_and_keeps_system(self):
        system = {'role': 'system', 'content': 'setup'}
        history = [system]
        for i in range(8):
            history += [{'role': 'user', 'content': str(i)}, {'role': 'assistant', 'content': str(i)}]
        original = history.copy()
        fitted, removed, tokens = client.fit_history(history, 'new', lambda messages: len(messages)*10, 85, 20)
        self.assertEqual(history, original)
        self.assertEqual(removed, 6)
        self.assertIs(fitted[0], system)
        self.assertEqual([m['role'] for m in fitted], ['system', 'user', 'assistant', 'user', 'assistant', 'user'])
        self.assertEqual(fitted[1]['content'], '6')
        self.assertLess(tokens + 20, 85)

    def test_oversized_message_does_not_mutate_history(self):
        history = [{'role': 'system', 'content': 'setup'}, {'role': 'user', 'content': 'old'}, {'role': 'assistant', 'content': 'answer'}]
        original = history.copy()
        with self.assertRaisesRegex(ValueError, 'Shorten'):
            client.fit_history(history, 'huge', lambda _: 100, 100, 20)
        self.assertEqual(history, original)

    def test_exact_boundary_reserves_spare_token(self):
        with self.assertRaises(ValueError):
            client.fit_history([{'role': 'system', 'content': 'setup'}], 'new', lambda _: 80, 100, 20)

    def test_failed_stream_not_kept_and_clear_retains_system(self):
        class FakeAPI:
            def __init__(self):
                self.sent = []
            def count(self, _):
                return 30
            def reply(self, messages, reserve):
                self.sent.append(messages.copy())
                if len(self.sent) == 1:
                    raise RuntimeError('stream interrupted')
                return 'answer', 'stop'
        api = FakeAPI()
        report = {'context': 'setup', 'delivery': 'pending_first_message'}
        with tempfile.TemporaryDirectory() as directory, patch('builtins.input', side_effect=['failed', 'good', '/clear', 'fresh', '/exit']), patch.object(client, 'log'), patch('sys.stdout', io.StringIO()):
            client.chat(api, report, Path(directory)/'snapshot.json', 8192)
        self.assertEqual([m['content'] for m in api.sent[1]], ['setup', 'good'])
        self.assertEqual([m['content'] for m in api.sent[2]], ['setup', 'fresh'])
        self.assertEqual(report['delivery'], 'supplied_with_first_message')

    def test_eof_and_termination_stop_owned_server(self):
        for action in ('eof', 'terminate'):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'test-model.txt'
                process = subprocess.Popen([sys.executable, str(ROOT / 'scripts/native-linux/session.py'), str(path), sys.executable, str(ROOT / 'tests/native-linux/fake_server.py')], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    snapshot = path.with_name('test-setup.json')
                    deadline = time.monotonic() + 10
                    while not snapshot.exists() and process.poll() is None and time.monotonic() < deadline:
                        time.sleep(.05)
                    self.assertTrue(snapshot.exists())
                    pid = json.loads(snapshot.read_text())['runtime_pid']
                    if action == 'terminate':
                        process.send_signal(signal.SIGTERM)
                    stdout, stderr = process.communicate('', timeout=10)
                    self.assertEqual(process.returncode, 0, stdout + stderr)
                    with self.assertRaises(ProcessLookupError):
                        os.kill(pid, 0)
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.communicate(timeout=10)
