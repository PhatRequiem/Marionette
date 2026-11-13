import importlib.util
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/marionette'))
from vault_tool import configured_tools


class ScarecrowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / 'vault'
        self.process = subprocess.Popen(['node', str(ROOT / 'tests/scarecrow/fixture.js'), str(self.vault)], stdout=subprocess.PIPE, text=True)
        self.addCleanup(self.stop)
        self.settings = json.loads(self.process.stdout.readline())
        self.config = self.root / 'scarecrow/connection.json'
        self.config.parent.mkdir()
        self.config.write_text(json.dumps(dict(self.settings, enabled=True, vault=str(self.vault))))
        self.tool = configured_tools(self.root)[0]

    def stop(self):
        self.process.terminate()
        self.process.wait(timeout=5)
        self.process.stdout.close()

    def test_real_http_and_source_identity(self):
        result = json.loads(self.tool.call({'action':'read','path':'Welcome.md'}))
        self.assertEqual(result['status'], 'ok')
        self.assertIn('STRAW-42', result['data']['content'])
        self.assertNotIn(self.settings['token'], json.dumps(result))
        config = json.loads(self.config.read_text());config['vault_id']='wrong'
        self.config.write_text(json.dumps(config))
        self.assertEqual(json.loads(self.tool.call({'action':'list'}))['status'], 'unavailable')

    def test_reset_disabled_and_errors(self):
        for form in ({'action':'write'},{'action':'read','path':'../secret'}):
            self.assertEqual(json.loads(self.tool.call(form))['status'], 'unavailable')
        (self.vault/'Generated/.marionette-managed').unlink()
        self.assertEqual(json.loads(self.tool.call({'action':'list'}))['status'], 'unavailable')
        self.config.write_text('{"enabled": false}')
        self.assertEqual(configured_tools(self.root), ())

    def test_native_agent_dispatch_and_history(self):
        import httpx
        from openai import OpenAI
        from inference import API
        from conversation import Conversation
        from test_coordination import response
        sent=[]
        def transport(request):
            sent.append(json.loads(request.content))
            if len(sent)==1:
                return response({'tool_calls':[{'index':0,'id':'vault_1','type':'function','function':{'name':'read_vault','arguments':json.dumps({'action':'read','path':'Welcome.md'})}}]},'tool_calls')
            self.assertIn('STRAW-42',sent[-1]['messages'][-1]['content'])
            self.assertEqual(sent[-1]['messages'][-1]['tool_call_id'],'vault_1')
            return response({'content':'STRAW-42'},'stop')
        sdk=OpenAI(base_url='http://localhost/v1',api_key='EMPTY',http_client=httpx.Client(transport=httpx.MockTransport(transport)))
        self.addCleanup(sdk.close)
        api=API('http://localhost');api.tools=(self.tool,);api.count=lambda messages:20
        chat=Conversation(api,8192)
        with patch('inference.OpenAI',return_value=sdk),patch('diagnostics.write'),patch('conversation.Preparation'):
            self.assertEqual(chat.turn('Read Welcome.'),('STRAW-42','stop'))
        self.assertTrue(any(m['role']=='function' for m in chat.history))
        self.assertIn('read_vault',[t['function']['name'] for t in sent[0]['tools']])
        self.assertNotIn(self.settings['token'],json.dumps(sent))

    def test_cli_vault_defaults_follow_selected_paths(self):
        checkout = self.root/'checkout'
        script = checkout/'scripts/native-linux/setup-scarecrow.py'
        script.parent.mkdir(parents=True)
        shutil.copy2(ROOT/'scripts/native-linux/setup-scarecrow.py',script)
        shutil.copytree(ROOT/'plugins/scarecrow',checkout/'plugins/scarecrow')
        environment = dict(os.environ)
        for key in ('MARIONETTE_DATA_DIR','MARIONETTE_LOG_DIR'):
            environment.pop(key,None)
        cases = [
            ('default', [], {}, checkout/'data', checkout/'data/conversations/obsidian-vault'),
            ('data argument', ['--data',str(self.root/'argument data')], {}, self.root/'argument data', self.root/'argument data/conversations/obsidian-vault'),
            ('data environment', [], {'MARIONETTE_DATA_DIR':str(self.root/'env data')}, self.root/'env data', self.root/'env data/conversations/obsidian-vault'),
            ('logs', ['--data',str(self.root/'log config')], {'MARIONETTE_LOG_DIR':str(self.root/'logs')}, self.root/'log config', self.root/'logs/obsidian-vault'),
            ('explicit vault', ['--data',str(self.root/'explicit data'),'--vault',str(self.root/'explicit vault')], {'MARIONETTE_DATA_DIR':str(self.root/'unused data'),'MARIONETTE_LOG_DIR':str(self.root/'unused logs')}, self.root/'explicit data', self.root/'explicit vault'),
        ]
        for name, arguments, overrides, data, vault in cases:
            with self.subTest(name=name):
                (vault/'Generated').mkdir(parents=True)
                (vault/'Generated/.marionette-managed').write_text('synthetic')
                result = subprocess.run([sys.executable,str(script),*arguments],
                    env=environment|overrides,capture_output=True,text=True,check=True)
                config = json.loads((data/'scarecrow/connection.json').read_text())
                self.assertEqual(config['vault'],str(vault))
                self.assertTrue((vault/'.obsidian/plugins/scarecrow/main.js').is_file())

    def test_repeatable_setup_and_preserved_plugins(self):
        spec=importlib.util.spec_from_file_location('setup_scarecrow',ROOT/'scripts/native-linux/setup-scarecrow.py')
        setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)
        config_dir=self.vault/'.obsidian';config_dir.mkdir(exist_ok=True)
        (config_dir/'community-plugins.json').write_text('["other-plugin"]')
        setup.install(self.vault,self.root,27124)
        first=json.loads(self.config.read_text())
        setup.install(self.vault,self.root,27124)
        self.assertEqual(first,json.loads(self.config.read_text()))
        self.assertEqual(json.loads((config_dir/'community-plugins.json').read_text()),['other-plugin','scarecrow'])
        self.assertEqual(self.config.stat().st_mode & 0o777,0o600)
        self.assertIn('STRAW-42',(self.vault/'Welcome.md').read_text())
        built = config_dir / 'plugins/scarecrow/main.js'
        self.assertEqual(built.read_text(), setup.bundle())
        # Obsidian evaluates one file: relative imports must be resolved by our
        # assembled module table, not the caller's filesystem require.
        check = """
const vm=require('node:vm'), fs=require('node:fs');
const context={module:{exports:{}},require:name=>{
 if(name==='obsidian') return {Plugin:class {},PluginSettingTab:class {},Setting:class {},Notice:class {}};
 if(name.startsWith('.')) throw Error('Unexpected external relative import');
 return require(name);
}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context);
if(typeof context.module.exports!=='function') throw Error('Plugin class missing');
"""
        subprocess.run(['node','-e',check,str(built)],check=True)
