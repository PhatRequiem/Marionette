"""Synthetic HTTP event stream, recorder routing, and lifecycle checks."""
import json
from pathlib import Path
import sys
import subprocess
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from vault_diagnostics import VaultDiagnostics, clean_event
from log_router import category
from retention import failure_identity
import test_vault_tool


class VaultDiagnosticsTests(unittest.TestCase):
    setUp = test_vault_tool.ScarecrowTests.setUp
    stop = test_vault_tool.ScarecrowTests.stop
    # Reuse only the isolated Node fixture lifecycle, not its test methods.
    def test_live_events_and_shutdown(self):
        rows=[]
        def wait_for(event):
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                if any(json.loads(row.split('Connection event: ',1)[1])['event']==event for row in rows):
                    return
                time.sleep(.01)
            self.fail(f'Missing {event}')
        with patch('diagnostics.log',side_effect=rows.append):
            with VaultDiagnostics(self.root, retry=.05) as monitor:
                wait_for('ready')
                result=json.loads(self.tool.call({'action':'read','path':'Welcome.md'}))
                self.assertEqual(result['status'],'ok')
                deadline=time.monotonic()+5
                while time.monotonic()<deadline and not any('Scarecrow' in r and 'request_completed' in r for r in rows):
                    time.sleep(.01)
                self.assertTrue(any('Scarecrow' in r and 'request_completed' in r for r in rows))
                self.process.terminate();self.process.wait(timeout=5)
                wait_for('unavailable')
                self.process.stdout.close()
                self.process = subprocess.Popen(['node', str(test_vault_tool.ROOT/'tests/scarecrow/fixture.js'),
                    str(self.vault), str(self.settings['port'])], stdout=subprocess.PIPE, text=True)
                self.assertEqual(json.loads(self.process.stdout.readline())['port'], self.settings['port'])
                wait_for('reconnected')
            self.assertFalse(monitor.thread.is_alive())
        events=[json.loads(r.split('Connection event: ',1)[1]) for r in rows]
        client=next(e for e in events if e['event']=='request_started')
        server=next(e for e in events if e['source']=='Scarecrow' and e['event']=='request_completed')
        self.assertEqual(client['request_id'],server['request_id'])
        self.assertIn('duration_ms',server)
        for private in ('STRAW-42', 'Welcome.md', self.settings['token']):
            self.assertNotIn(private, ''.join(rows))

    def test_clean_metadata_and_failure_routing(self):
        result=clean_event({'source':'Scarecrow','event':'request_failed','content':'private','http_status':503})
        self.assertNotIn('content',result)
        raw=('Client: Connection event: '+json.dumps(result)+'\n').encode()
        self.assertEqual(category(raw),'server')
        self.assertEqual(failure_identity('diagnostic',raw)[-1],'vault')
        raw=b'Client: Reasoning: "Connection event: request_failed"\n'
        self.assertIsNone(failure_identity('diagnostic',raw))
