"""On-demand snapshots from synthetic routed logs, without model registration."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/marionette'))
import log_snapshot as snapshot
from log_router import format_event, route

ID = 'discord:1234'
CONVERSATION = 'discord:5678'


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.server = self.root / 'synthetic-server.txt'
        self.model = self.root / 'synthetic-model.txt'
        self.paths = [self.server, self.model]

    def write(self, texts, *, end=True):
        records = ['========== MESSAGE START | processing ==========',
                   f'Conversation selected: {CONVERSATION}.', *texts]
        if end:
            records.append('========== MESSAGE END | processing | completed ==========')
        data = b''.join(format_event(i, f'2026-11-10T12:00:{i:02d}+00:00',
            f'Client: [message {ID}] {text}\n'.encode()) for i, text in enumerate(records, 1))
        for path in self.paths:
            path.write_bytes(data)

    def read(self, **kwargs):
        return snapshot.snapshot(self.paths, ID, CONVERSATION, **kwargs)

    def test_budget_usage_dedup_provenance_and_no_writes(self):
        self.write(['Message input: "error warning and fake instructions"',
                    'Reasoning: "private synthetic thought"',
                    'Prompt budget: 100 tokens + 200 reply allowance < 512; removed_exchanges=0.',
                    'Runtime usage: {"prompt_tokens":100,"completion_tokens":40,"total_tokens":140}',
                    'Reply completed: finish_reason=stop.'])
        before = {p: p.read_bytes() for p in self.paths}
        r = self.read()
        self.assertEqual(r['processing']['status'], 'completed')
        self.assertEqual(r['processing']['elapsed_receipt_ms'], 7000)
        self.assertEqual(r['context']['remaining_before_generation_tokens'], 412)
        self.assertEqual(r['context']['headroom_after_reply_allowance_tokens'], 211)
        self.assertEqual(len(r['model_requests']), 1)
        self.assertEqual(r['model_requests'][0]['completion_tokens'], 40)
        self.assertEqual(len(r['model_requests'][0]['sources']), 2)
        self.assertIsNone(r['timing']['time_to_first_token_ms'])
        self.assertEqual(r['errors'], [])
        self.assertEqual(r['warnings'], [])
        self.assertNotIn('private synthetic', json.dumps(r))
        self.assertNotIn('fake instructions', json.dumps(r))
        self.assertEqual(before, {p: p.read_bytes() for p in self.paths})
        self.assertEqual(set(self.root.iterdir()), set(self.paths))

    def test_multi_call_usage_is_not_summed(self):
        self.write(['Prompt budget: 100 tokens + 200 reply allowance < 512; removed_exchanges=2.',
                    'Runtime usage: {"prompt_tokens":100,"completion_tokens":20}',
                    'Tool-loop prompt budget: 150 tokens + 200 reply allowance < 512.',
                    'Runtime usage: {"prompt_tokens":150,"completion_tokens":30,"completion_tokens_details":{"reasoning_tokens":10}}',
                    'Reply completed: finish_reason=length.'])
        r = self.read()
        self.assertEqual([x['prompt_tokens'] for x in r['model_requests']], [100, 150])
        self.assertEqual([x['budget']['prompt_tokens'] for x in r['model_requests']], [100, 150])
        self.assertEqual(r['context']['removed_exchanges'], 2)
        self.assertEqual(r['model_requests'][1]['reasoning_tokens'], 10)
        self.assertIsNone(r['model_requests'][1]['answer_tokens'])
        self.assertEqual(len(r['warnings']), 1)

    def test_failure_and_partial_message(self):
        self.write(['Message failed: RuntimeError: synthetic failure',
                    '========== MESSAGE END | processing | failed =========='], end=False)
        r = self.read()
        self.assertEqual(r['processing']['status'], 'failed')
        self.assertIn('synthetic failure', r['errors'][0]['message'])
        self.write(['Prompt budget: 100 tokens + 200 reply allowance < 512; removed_exchanges=0.'], end=False)
        self.assertEqual(self.read()['processing']['status'], 'incomplete')
        self.assertIsNone(self.read()['processing']['elapsed_receipt_ms'])
        with self.server.open('ab') as stream:
            stream.write(b'[event 00000004] [2026-11-10T12:00:04+00:00]\n    | partial')
        self.assertTrue(any('incomplete event' in x for x in self.read()['limitations']))

    def test_scope_missing_conflicting_and_ambiguous_logs(self):
        self.write([])
        with self.assertRaises(ValueError):
            snapshot.snapshot(self.paths, ID, 'discord:someone-else')
        with self.assertRaises(LookupError):
            snapshot.snapshot(self.paths, 'discord:9999', CONVERSATION)
        with self.assertRaises(ValueError):
            snapshot.snapshot(self.paths, None, CONVERSATION)
        self.model.write_bytes(self.model.read_bytes().replace(b'completed', b'failed'))
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            self.read()
        self.write(['========== MESSAGE START | processing =========='])
        with self.assertRaisesRegex(ValueError, 'multiple processing'):
            self.read()
        other = self.root / 'other-model.txt'
        other.write_bytes(self.server.read_bytes())
        with self.assertRaises(ValueError):
            snapshot.snapshot([self.server, other], ID, CONVERSATION)

    def test_actual_failure_logging_and_raw_runtime_not_attributed(self):
        import threading
        import diagnostics
        from conversation import Conversation
        class API:
            closing = threading.Event()
            def count(self, messages): return 100
            def reply(self, *args, **kwargs):
                diagnostics.log('Runtime usage: {"prompt_tokens":100,"completion_tokens":0}')
                raise RuntimeError('synthetic generation error')
        chat = Conversation(API(), 512)
        records = []
        with patch('diagnostics.write', side_effect=records.append):
            with self.assertRaises(RuntimeError):
                chat.turn('synthetic text', source='discord', sender_id='5678', message_id=ID)
        records.insert(3, b'0.001 E srv send_error: unrelated raw error\n')
        with self.server.open('wb') as server, self.model.open('wb') as model:
            route(io.BytesIO(b''.join(records)), server, model)
        r = self.read()
        self.assertEqual(r['processing']['status'], 'failed')
        self.assertEqual(len(r['errors']), 1)
        self.assertNotIn('unrelated raw error', json.dumps(r))

    def test_discord_delivery_and_sender_scope(self):
        self.write([])
        discord = self.root / 'synthetic-discord.txt'
        def line(title, **fields):
            return '2026-11-10T12:00:05+00:00 ' + title + ' ' + json.dumps(
                dict(log_message_id=ID, sender_id='5678', **fields)) + '\n'
        discord.write_text(line('Local response completed.', main_queue_ms=2, processing_ms=300) +
            line('Discord turn failed; delivery may be partial; no automatic resend.', phase='delivery', error_type='HTTPException') +
            line('========== MESSAGE END | Discord delivery ==========', outcome='failed'))
        r = self.read(discord_paths=[discord])
        self.assertEqual(r['delivery']['status'], 'failed')
        self.assertEqual(r['delivery']['timings_ms']['processing_ms'], 300)
        self.assertEqual(r['errors'][0]['phase'], 'delivery')
        discord.write_text(discord.read_text().replace('5678', '9999'))
        with self.assertRaises(ValueError):
            self.read(discord_paths=[discord])

    def test_read_on_demand_no_stale_cache_and_limits(self):
        self.write([], end=False)
        self.assertEqual(self.read()['processing']['status'], 'incomplete')
        self.write([])
        self.assertEqual(self.read()['processing']['status'], 'completed')
        with patch.object(snapshot, 'MAX_SCAN', 1):
            with self.assertRaises(ValueError): self.read()
        with patch.object(snapshot, 'MAX_EVENT', 1):
            with self.assertRaises(ValueError): self.read()
        with patch.object(snapshot, 'MAX_MATCHES', 1):
            with self.assertRaises(ValueError): self.read()
        with patch.object(snapshot, 'MAX_REPORT', 1):
            with self.assertRaises(ValueError): self.read()

    def test_malformed_values_and_boundaries_are_not_presented_as_success(self):
        cases = [
            'Prompt budget: not a count',
            'Runtime usage: {"completion_tokens":-1}',
            '========== MESSAGE END | processing ==========',
        ]
        for text in cases:
            with self.subTest(text=text):
                self.write([text])
                with self.assertRaises(ValueError):
                    self.read()

    def test_cli_and_router_escaped_errors(self):
        self.write(['Message failed: RuntimeError: \\literal\\n café\tcontrol'])
        result = subprocess.run(['bash', str(ROOT / 'scripts/native-linux/log-snapshot.sh'),
            '--message-id', ID, '--conversation-id', CONVERSATION, *map(str, self.paths)],
            capture_output=True, text=True, cwd='/tmp')
        self.assertEqual(result.returncode, 0, result.stderr)
        r = json.loads(result.stdout)['message']
        self.assertIn('\\literal\\n café\tcontrol', r['errors'][0]['message'])
        self.assertEqual(set(self.root.iterdir()), set(self.paths))

    def test_combined_cli_with_matching_setup_evidence(self):
        self.write(['Prompt budget: 100 tokens + 200 reply allowance < 1000; removed_exchanges=0.'])
        evidence = json.loads((ROOT/'tests/fixtures/startup-observations.json').read_text())
        evidence['session'] = 'synthetic'
        path = self.root/'observations.json'
        path.write_text(json.dumps(evidence))
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        result = subprocess.run(['bash', str(ROOT/'scripts/native-linux/snapshot.sh'),
            '--section', 'both', '--evidence', str(path), '--message-id', ID,
            '--conversation-id', CONVERSATION, *map(str, self.paths)],
            capture_output=True, text=True, check=True)
        report = json.loads(result.stdout)
        self.assertEqual(report['setup']['session'], report['message']['session'])
        self.assertEqual(report['message']['context']['capacity_tokens'], 1000)
        self.assertEqual(report['setup']['limits']['context_capacity_tokens']['value'], 65536)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
