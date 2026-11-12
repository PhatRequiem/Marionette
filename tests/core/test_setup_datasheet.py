"""Synthetic startup observations; never mutate the real setup datasheet."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src/marionette'))
import setup_datasheet as sheet


class DatasheetTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.path = Path(temp.name)/'setup.md'
        self.original = 'operator introduction\n'+sheet.START+'\nold facts\n'+sheet.END+'\noperator conclusion\n'
        self.path.write_text(self.original)

    def test_runtime_fields_and_context_refresh_preserve_operator_text(self):
        facts = {}
        for line in ('llama_model_loader: - kv 1: general.name str = Synthetic Model',
                     'print_info: file type   = Q4_K - Medium',
                     'main: build = 12211 (7d7f02875)',
                     'llama_model_load_from_file_impl: using device Vulkan0 (Synthetic GPU) (0000:03:00.0) - 100 MiB free',
                     'load_tensors: offloaded 33/33 layers to GPU',
                     'llama_context: n_ctx_seq = 8192',
                     'top_k = 20, top_p = 0.950, min_p = 0.000, temp = 1.000'):
            sheet.observe(line, facts)
        sheet.update(self.path,'ready',facts,capacity=8192)
        result=self.path.read_text()
        self.assertTrue(result.startswith('operator introduction\n'))
        self.assertTrue(result.endswith('\noperator conclusion\n'))
        for value in ('Synthetic Model','Q4_K - Medium','Synthetic GPU','33/33','12211','4096 tokens'):
            self.assertIn(value,result)
        self.assertIn('1024 tokens',result)
        sheet.update(self.path,'ready',{},capacity=65536)
        self.assertNotIn('Synthetic Model',self.path.read_text())
        self.assertIn('| Model name | Unverified |',self.path.read_text())

    def test_failure_pending_and_conflicts_never_reuse_verified_values(self):
        facts={}
        sheet.observe('print_info: general.name = First',facts)
        sheet.observe('print_info: general.name = Second',facts)
        sheet.update(self.path,'ready',facts,capacity=8192)
        self.assertIn('Conflicting startup observations',self.path.read_text())
        for status in ('starting','failed'):
            sheet.update(self.path,status,facts)
            self.assertNotIn('First',self.path.read_text())
            self.assertNotIn('Passed',self.path.read_text())
            self.assertIn(f'**{status}**',self.path.read_text())

    def test_escaping_and_unrecognized_lines(self):
        facts={}
        sheet.observe('Client: Message input: private conversation',facts)
        sheet.observe('a'*5000,facts)
        self.assertEqual(facts,{})
        sheet.observe('print_info: general.name = <script>|[link](url)',facts)
        sheet.update(self.path,'ready',facts,capacity=8192)
        result=self.path.read_text()
        self.assertNotIn('<script>',result)
        self.assertNotIn('[link]',result)
        self.assertIn('&#124;',result)

    def test_atomic_failure_and_invalid_markers_preserve_file(self):
        with patch.object(sheet.os,'replace',side_effect=OSError('synthetic failure')):
            with self.assertRaises(OSError): sheet.update(self.path,'ready',{})
        self.assertEqual(self.path.read_text(),self.original)
        self.assertEqual(list(self.path.parent.iterdir()),[self.path])
        for text in ('no markers',sheet.END+sheet.START,self.original+sheet.START):
            self.path.write_text(text)
            with self.assertRaises(ValueError): sheet.update(self.path,'starting',{})
            self.assertEqual(self.path.read_text(),text)
        link=self.path.parent/'link.md';link.symlink_to(self.path)
        with self.assertRaises(ValueError): sheet.update(link,'starting',{})

    def test_session_startup_failure_clears_prior_report(self):
        import session
        sheet.update(self.path,'ready',{'Model name': {'Old model'}},capacity=8192)
        with patch.dict('os.environ',{'MARIONETTE_SETUP_DATASHEET_PATH':str(self.path)}), \
             patch.object(session.subprocess,'Popen',side_effect=OSError('synthetic launch failure')), \
             patch.object(session.diagnostics,'log'):
            with self.assertRaises(OSError): session.run(['synthetic-server'])
        self.assertIn('Startup status: **failed**',self.path.read_text())
        self.assertNotIn('Old model',self.path.read_text())

    def test_bad_document_does_not_hide_startup_error(self):
        import session
        self.path.write_text('operator text without markers')
        with patch.dict('os.environ',{'MARIONETTE_SETUP_DATASHEET_PATH':str(self.path)}), \
             patch.object(session.subprocess,'Popen',side_effect=OSError('original error')), \
             patch.object(session.diagnostics,'log') as logged:
            with self.assertRaisesRegex(OSError,'original error'): session.run(['synthetic-server'])
        self.assertEqual(self.path.read_text(),'operator text without markers')
        self.assertTrue(any('Setup datasheet update failed' in c.args[0] for c in logged.call_args_list))
