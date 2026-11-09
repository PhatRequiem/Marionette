"""Snapshot checks use only synthetic diagnostic lines."""
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('session', ROOT / 'scripts/native-linux/session.py')
session = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session)


class SnapshotTests(unittest.TestCase):
    def test_last_observation_wins_with_provenance(self):
        facts = {}
        lines = [
            'version: build-test',
            '0.01 I llama_prepare_model_devices: using device Vulkan0 (Synthetic GPU) (0000:03:00.0) - 999 MiB free',
            '0.01 I model: general.name str = Synthetic Model',
            '0.01 I llama_context: n_ctx_seq                 = 4096',
            '0.02 I llama_context: n_ctx_seq                 = 8192',
            '0.02 I load_tensors: offloaded 12/12 layers to GPU',
            '0.03 I srv  server_on_li: listening on http://127.0.0.1:54321',
        ]
        for line in lines:
            session.observe(line, facts)
        self.assertEqual(facts['context_tokens']['value'], '8192')
        self.assertEqual(facts['context_tokens']['evidence'], lines[4])
        self.assertEqual(facts['device']['value'], 'Vulkan0 (Synthetic GPU)')
        self.assertEqual(facts['local_server']['value'], 'http://127.0.0.1:54321')
        report = session.snapshot(['synthetic-runtime'], facts, Path('/tmp/test-model.txt'))
        self.assertIn('Synthetic GPU', report['context'])
        self.assertIn('No tools', report['context'])
        self.assertIn('not current usage', report['context'])
        self.assertIn('Current token usage is not measured', report['context'])
        self.assertEqual(report['delivery'], 'pending_first_message')

    def test_commands_and_clear_preserve_report_delivery(self):
        first = True
        for command in [b'', b'/read example.txt', b'/glob *.txt', b'/regen']:
            packet, first, delivered = session.prepare_line(command, first, 'SETUP', '[start]', '[end]')
            self.assertEqual(packet, command + b'\n')
            self.assertTrue(first)
            self.assertFalse(delivered)
        packet, first, delivered = session.prepare_line(b'hello', first, 'SETUP', '[start]', '[end]')
        self.assertEqual(packet, b'[start]SETUP[end]hello\n')
        self.assertTrue(delivered)
        packet, first, _ = session.prepare_line(b'/clear', first, 'SETUP', '[start]', '[end]')
        self.assertEqual(packet, b'/clear\n')
        self.assertTrue(first)
        packet, first, delivered = session.prepare_line(b'/exit', first, 'SETUP', '[start]', '[end]')
        self.assertEqual(packet, b'/exit\n')
        self.assertFalse(delivered)

    def test_unknown_hardware_is_not_invented_and_snapshot_is_portable(self):
        report = session.snapshot(['synthetic-runtime'], {}, Path('/tmp/test-model.txt'))
        self.assertIn('not reported; unverified', report['context'])
        self.assertNotIn('Radeon', report['context'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'setup.json'
            session.save(path, report)
            self.assertEqual(json.loads(path.read_text()), report)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertFalse(path.with_suffix('.json.part').exists())

    def test_report_delivery_once_and_no_readiness_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            engine = root / 'engine.py'
            engine.write_text("import sys\nprint('0.0 I srv  update_slots: all slots are idle', file=sys.stderr, flush=True)\nfor line in sys.stdin: print(line, end='', flush=True)\n")
            debug = root / 'test-model.txt'
            debug.touch()
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/native-linux/session.py'), str(debug), sys.executable, str(engine)], input='\nhello\n' + ('next message\n' * 20000), capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.count('Local runtime setup report'), 1)
            self.assertTrue(result.stdout.endswith('next message\n'))
            report = json.loads((root / 'test-setup.json').read_text())
            self.assertEqual(report['delivery'], 'supplied_with_first_message')
            self.assertIn('not reported; unverified', report['context'])
            engine.write_text('pass\n')
            failure_debug = root / 'failed-model.txt'
            failure_debug.touch()
            failure = subprocess.run([sys.executable, str(ROOT / 'scripts/native-linux/session.py'), str(failure_debug), sys.executable, str(engine)], input='', capture_output=True, text=True, timeout=10)
            self.assertEqual(failure.returncode, 1)
            self.assertFalse((root / 'failed-setup.json').exists())


if __name__ == '__main__':
    unittest.main()
