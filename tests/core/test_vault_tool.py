"""Synthetic read-only routing and real Qwen-Agent dispatch; no private data."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import httpx
from openai import OpenAI
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from vault_tool import ReadVault, MCP, plan, configured_tools
from inference import API
from conversation import Conversation
from test_coordination import response

class VaultTests(unittest.TestCase):
    def test_invalid_forms_never_start_connector(self):
        with patch('vault_tool.MCP') as connector:
            for form in ({'action':'write','path':'x.md'}, {'action':'read','path':'../secret.md'},
                         {'action':'read','path':'.obsidian/secret.md'}, {'action':'read','path':'/x.md'},
                         {'action':'read','path':'x.md','content':'oops'}, {'action':'search','query':''}):
                self.assertEqual(json.loads(ReadVault('/absent').call(form))['status'],'unavailable')
            connector.assert_not_called()
        self.assertEqual(plan({'action':'read','path':'Welcome.md'})[0], 'obsidian_get_note')
        self.assertEqual(plan({'action':'search','query':'Example'})[0], 'obsidian_search_notes')
        with self.assertRaises(ValueError): MCP.call(None,'obsidian_write_note',{})
        with self.assertRaises(ValueError): MCP({'base_url':'https://example.com','api_key':'synthetic'})

    def test_disabled_and_reset_vault_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp, patch('vault_tool.MCP') as connector:
            root=Path(tmp); self.assertEqual(configured_tools(root),())
            config=root/'obsidian/connection.json';config.parent.mkdir()
            config.write_text(json.dumps({'enabled':False}))
            self.assertEqual(configured_tools(root),())
            config.write_text(json.dumps({'enabled':True,'vault':tmp}))
            self.assertEqual(json.loads(ReadVault(config).call({'action':'list'}))['status'],'unavailable')
            connector.assert_not_called()

    def test_agent_dispatch_history_and_read_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'Generated').mkdir(); (root/'Generated/.marionette-managed').touch()
            config=root/'connection.json';config.write_text(json.dumps({'enabled':True,'vault':tmp}))
            tool=ReadVault(config); api=API('http://localhost',tools=(tool,));api.count=lambda messages:20
            sent=[]
            def transport(request):
                sent.append(json.loads(request.content))
                if len(sent)==1:
                    return response({'tool_calls':[{'index':0,'id':'vault_1','type':'function',
                        'function':{'name':'read_vault','arguments':json.dumps({'action':'read','path':'Welcome.md'})}}]},'tool_calls')
                facts=json.loads(sent[-1]['messages'][-1]['content'])
                self.assertEqual(facts['data']['content'],'Synthetic vault welcome')
                return response({'content':'Synthetic vault welcome'},'stop')
            sdk=OpenAI(base_url='http://localhost/v1',api_key='EMPTY',http_client=httpx.Client(transport=httpx.MockTransport(transport)))
            with patch('vault_tool.MCP') as connector, patch('inference.OpenAI',return_value=sdk), patch('diagnostics.write'), patch('conversation.Preparation'):
                connector.return_value.call.return_value={'structuredContent':{'content':'Synthetic vault welcome'}}
                chat=Conversation(api,8192)
                answer,finish=chat.turn('Read the vault welcome')
            self.assertEqual((answer,finish),('Synthetic vault welcome','stop'))
            self.assertIn('Vault reading',sent[0]['messages'][0]['content'])
            self.assertTrue(any(m.get('role')=='function' for m in chat.history))
            connector.return_value.close.assert_called_once()

    @unittest.skipUnless((Path(__file__).resolve().parents[2]/'runtime/obsidian-mcp/node_modules/obsidian-mcp-server/dist/index.js').exists(), 'optional pinned connector not installed')
    def test_real_cyanheads_reads_and_rejects_writes_before_http(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                requests.append(('GET',self.path))
                self.send_response(200); self.send_header('Content-Type','text/markdown'); self.end_headers()
                self.wfile.write(b'# Synthetic note\nFixture only.\n')
            def do_PUT(self):
                requests.append(('PUT',self.path)); self.send_response(500);self.end_headers()
            do_POST=do_PUT
            do_DELETE=do_PUT
            do_PATCH=do_PUT
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        client=MCP({'api_key':'synthetic-only','base_url':f'http://127.0.0.1:{server.server_port}'})
        self.addCleanup(client.close)
        names={t['name'] for t in client.request('tools/list',{})['tools']}
        self.assertTrue({'obsidian_get_note','obsidian_list_notes','obsidian_search_notes'} <= names)
        self.assertFalse(any(word in n for n in names for word in ('write','append','delete','patch','replace','command','manage')))
        read=client.call('obsidian_get_note',{'target':{'type':'path','path':'Note.md'},'format':'content'})
        self.assertFalse(read.get('isError'));self.assertIn('Fixture only',json.dumps(read))
        before=list(requests)
        for name,args in [('obsidian_write_note',{'target':{'type':'path','path':'Note.md'},'content':'CHANGED'}),
                          ('obsidian_delete_note',{'target':{'type':'path','path':'Note.md'}}),
                          ('obsidian_execute_command',{'commandId':'app:quit'})]:
            try: denied=client.request('tools/call',{'name':name,'arguments':args})
            except ValueError: pass
            else: self.assertTrue(denied.get('isError'),name)
        self.assertEqual(requests,before)

    def test_contact_rebinding_preserves_vault_tool(self):
        from contacts import ContactProfiles
        from contact_notes import ContactNotes
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); profiles=ContactProfiles(root/'profiles.json'); owner=profiles.profiles[0]
            tool=ReadVault(root/'connection.json')
            api=API('http://localhost',tools=(tool,));api.count=lambda messages:20
            api.reply=lambda *args,**kwargs:('Synthetic answer','stop')
            api.prepare=lambda *args:None
            chat=Conversation(api,8192,profiles,owner,ContactNotes(root/'notes'))
            with patch('diagnostics.log'):
                chat.turn('Synthetic turn one');chat.finish_preparation()
                chat.turn('Synthetic turn two');chat.finish_preparation()
            self.assertIn(tool,api.tools)
            self.assertEqual([t.name for t in api.tools].count('update_contact_notes'),1)
