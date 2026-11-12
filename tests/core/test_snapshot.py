"""Unified reports use synthetic evidence only and never contact a model."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/marionette'))
from snapshot import build_snapshot


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.evidence = json.loads((ROOT/'tests/fixtures/startup-observations.json').read_text())
        self.message = {'session': 'test-session', 'context': {'capacity_tokens': 4096},
                        'model': {'name': None}, 'connections': {'transport': None},
                        'evidence': [], 'schema_version': 2}

    def test_combined_requires_matching_session(self):
        for session in (None, 'other-session'):
            evidence = dict(self.evidence)
            if session is not None:
                evidence['session'] = session
            with self.assertRaises(ValueError):
                build_snapshot(evidence, self.message)

    def test_combined_preserves_scope_provenance_and_inputs(self):
        self.evidence['session'] = 'test-session'
        before = copy.deepcopy((self.evidence, self.message))
        report = build_snapshot(self.evidence, self.message)
        self.assertEqual((self.evidence, self.message), before)
        self.assertFalse(report['connected_to_model'])
        self.assertEqual(report['message']['context']['capacity_tokens'], 4096)
        fact = report['setup']['limits']['context_capacity_tokens']
        self.assertEqual(fact['value'], 65536)
        self.assertEqual(fact['status'], 'synthetic_example')
        self.assertEqual(fact['provenance']['observed_at'], self.evidence['observed_at'])
        self.assertEqual(fact['provenance']['session'], 'test-session')
        self.assertNotIn('model', report['message'])
        self.assertNotIn('connections', report['message'])

    def test_missing_setup_does_not_inherit_message_values(self):
        report = build_snapshot(message=self.message)
        self.assertIsNone(report['setup']['limits']['context_capacity_tokens']['value'])
        self.assertEqual(report['setup']['limits']['context_capacity_tokens']['status'], 'unverified')
        self.assertIsNone(build_snapshot()['message'])
        self.assertIsNone(build_snapshot(message=self.message, include_setup=False)['setup'])
        with self.assertRaises(ValueError):
            build_snapshot(self.evidence, include_setup=False)

    def test_cli_rejects_ignored_arguments_and_bad_scopes(self):
        for args in (['--message-id', 'local:test'], ['--section', 'both'],
                     ['--section', 'message', '--evidence', str(ROOT/'tests/fixtures/startup-observations.json')]):
            result = subprocess.run([sys.executable, str(ROOT/'src/marionette/snapshot.py'), *args], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
