"""Startup capacity and address checks use synthetic diagnostic lines."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('session', ROOT / 'scripts/native-linux/session.py')
session = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session)


class StartupTests(unittest.TestCase):
    def test_latest_capacity_and_loopback_address(self):
        facts = {}
        lines = [
            '0.01 I llama_context: n_ctx_seq                 = 4096',
            '0.02 I llama_context: n_ctx_seq                 = 8192',
            '0.03 I srv  server_on_li: listening on http://127.0.0.1:54321',
        ]
        for line in lines:
            session.observe(line, facts)
        self.assertEqual(facts['context_tokens'], '8192')
        self.assertEqual(facts['local_server'], 'http://127.0.0.1:54321')


if __name__ == '__main__':
    unittest.main()
