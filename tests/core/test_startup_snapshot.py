"""Synthetic setup-report checks; no model, account, or personal data access."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/marionette'))
from startup_snapshot import build_snapshot


class StartupSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.example = json.loads((ROOT/'tests/fixtures/startup-observations.json').read_text())

    def test_missing_is_not_false_or_configured_default(self):
        report = build_snapshot()
        self.assertEqual(report['interfaces']['discord_connected'], {'value': None, 'status': 'unverified'})
        self.assertIsNone(report['limits']['context_capacity_tokens']['value'])
        self.assertIsNone(report['tools']['purposes'])
        self.assertFalse(report['connected_to_model'])

    def test_example_provenance_and_capacity(self):
        original = copy.deepcopy(self.example)
        report = build_snapshot(self.example)
        self.assertEqual(report['model']['model_name']['status'], 'synthetic_example')
        self.assertEqual(report['limits']['context_capacity_tokens']['value'], 65536)
        self.assertEqual(self.example, original)

    def test_reported_is_not_independently_verified(self):
        self.example['synthetic'] = False
        self.example['values']['registered_tools'] = []
        report = build_snapshot(self.example)
        self.assertEqual(report['runtime']['device']['status'], 'caller_reported')
        self.assertEqual(report['tools']['purposes'], {})
        self.assertEqual(report['evidence']['observed_at'], self.example['observed_at'])

    def test_bad_evidence_rejected(self):
        for field, value in [('device', 'GPU\nInjected text'), ('context_capacity_tokens', True),
                             ('reasoning_enabled', 'yes'), ('registered_tools', ['shell']),
                             ('registered_tools', ['update_soul', 'update_soul']),
                             ('reasoning_answer_allowance_tokens', 65536), ('unknown_field', 'x')]:
            with self.subTest(field=field, value=value):
                evidence = copy.deepcopy(self.example)
                evidence['values'][field] = value
                with self.assertRaises(ValueError): build_snapshot(evidence)
        for field, value in [('source', ''), ('synthetic', 'false'), ('observed_at', '2026-11-11')]:
            evidence = copy.deepcopy(self.example); evidence[field] = value
            with self.assertRaises(ValueError): build_snapshot(evidence)

    def test_cli_is_standalone_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(['bash', str(ROOT/'scripts/native-linux/startup-snapshot.sh'),
                '--evidence', str(ROOT/'tests/fixtures/startup-observations.json')],
                cwd=temp, capture_output=True, text=True, check=True)
            self.assertEqual(list(Path(temp).iterdir()), [])
            self.assertTrue(json.loads(result.stdout)['evidence']['synthetic'])

    def test_cli_bad_input_has_no_partial_report(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/'bad.json';p.write_text('{broken')
            result = subprocess.run([sys.executable, str(ROOT/'src/marionette/startup_snapshot.py'),
                '--evidence', str(p)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
