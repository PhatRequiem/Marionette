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
from vault_tool import ReadVault, MCP, plan, configured_tools, READ_TOOLS
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
        note_count=1
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                requests.append(('GET',self.path))
                if self.path == '/vault/Missing.md':
                    self.send_response(404); self.end_headers(); return
                self.send_response(200); self.send_header('Content-Type', self.headers.get('Accept') if '+json' in self.headers.get('Accept', '') else ('application/json' if self.path in ('/', '/vault/') else 'text/markdown')); self.end_headers()
                body = '# Synthetic note\nFixture only. #example\n'
                if self.path == '/':
                    payload = {'versions': {'obsidian': '1.0', 'self': '5.5.2'}}
                elif self.path == '/vault/':
                    payload = {'files': ['Note.md']}
                elif 'document-map' in self.headers.get('Accept', ''):
                    payload = {'headings': {'Synthetic note': {}}, 'blocks': [], 'frontmatterFields': []}
                elif 'note+json' in self.headers.get('Accept', ''):
                    payload = {'path': 'Note.md', 'content': body, 'frontmatter': {}, 'tags': ['example'],
                               'stat': {'ctime': 0, 'mtime': 0, 'size': len(body)}}
                else:
                    self.wfile.write(body.encode()); return
                self.wfile.write(json.dumps(payload).encode())
            def do_PUT(self):
                requests.append(('PUT',self.path)); self.send_response(500);self.end_headers()
            def do_POST(self):
                requests.append(('POST', self.path))
                self.rfile.read(int(self.headers.get('Content-Length', 0)))
                self.send_response(200 if self.path.startswith(('/open/', '/search/')) else 500)
                self.send_header('Content-Type', 'application/json'); self.end_headers()
                if self.path == '/search/':
                    self.wfile.write(json.dumps([{'filename':f'Note{i}.md','result':{
                        'path':'Note.md','content':'# Synthetic note\nFixture only. #example\n',
                        'tags':['example'],'frontmatter':{},'stat':{'ctime':0,'mtime':0,'size':40}}} for i in range(note_count)]).encode())
            do_DELETE=do_PUT
            do_PATCH=do_PUT
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        client=MCP({'api_key':'synthetic-only','base_url':f'http://127.0.0.1:{server.server_port}'})
        self.addCleanup(client.close)
        names={t['name'] for t in client.request('tools/list',{})['tools']}
        self.assertEqual(READ_TOOLS, names)
        self.assertFalse(any(word in n for n in names for word in ('write','append','delete','patch','replace','command','manage')))
        read=client.call('obsidian_get_note',{'target':{'type':'path','path':'Note.md'},'format':'content'})
        self.assertFalse(read.get('isError'));self.assertIn('Fixture only',json.dumps(read))
        for form in (
            {'action':'read','path':'Note.md','options':{'format':'document-map'}},
            {'action':'read','path':'Note.md','options':{'format':'section','section':{'type':'heading','target':'Synthetic note'}}},
            {'action':'list','options':{'depth':2}},
            {'action':'tags'},
            {'action':'search','query':'Fixture'},
            {'action':'search','options':{'mode':'jsonlogic','logic':{'==':[{'var':'path'},'Note.md']}}},
            {'action':'open','path':'Note.md','options':{'newLeaf':True}},
        ):
            with self.subTest(form=form):
                result=client.call(*plan(form))
                self.assertFalse(result.get('isError'), result)
        self.assertTrue(any(method == 'POST' and path.startswith('/open/') for method,path in requests))
        before_open=list(requests)
        missing=client.call(*plan({'action':'open','path':'Missing.md'}))
        self.assertTrue(missing.get('isError'))
        self.assertFalse(any(method == 'POST' for method,path in requests[len(before_open):]))
        note_count=51
        first=client.call(*plan({'action':'search','query':'Fixture'}))['structuredContent']['result']
        self.assertEqual(len(first['hits']),50)
        # Each production lookup starts a fresh process: verify cursor continuation there too.
        other=MCP({'api_key':'synthetic-only','base_url':f'http://127.0.0.1:{server.server_port}'})
        try:
            second=other.call(*plan({'action':'search','query':'Fixture',
                'options':{'cursor':first['nextCursor']}}))['structuredContent']['result']
            self.assertEqual(len(second['hits']),1)
            self.assertFalse(set(h['filename'] for h in first['hits']) & set(h['filename'] for h in second['hits']))
        finally: other.close()
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

    def test_extended_routing_and_edit_options_rejected(self):
        self.assertEqual(plan({'action':'open','path':'Note.md'})[1]['failIfMissing'], True)
        self.assertEqual(plan({'action':'list','options':{'depth':3}})[1]['depth'], 3)
        for form in (
            {'action':'open','path':'New.md','options':{'failIfMissing':False}},
            {'action':'tags','options':{'operation':'add'}},
            {'action':'read','options':{'target':{'type':'path','path':'.obsidian/config.md'}}},
            {'action':'search','options':{'mode':'omnisearch'}},
            {'action':'search','path':'Contacts','options':{'mode':'jsonlogic','logic':{}}},
        ):
            with self.subTest(form=form), self.assertRaises(ValueError): plan(form)
