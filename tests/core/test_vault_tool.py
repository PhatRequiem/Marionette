"""Synthetic read-only docs boundaries; never opens personal notes or Obsidian."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/marionette'))
from vault_tool import ReadDocs
from conversation import Conversation


class VaultTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'docs';self.root.mkdir()
        (self.root/'guide.md').write_text('synthetic')
        (self.root/'.obsidian').mkdir();(self.root/'.obsidian/secret.md').write_text('secret')
        (self.root/'alias.md').symlink_to(self.root/'.obsidian/secret.md')
        self.tool=ReadDocs(self.root)

    def test_invalid_actions_and_escape_never_reach_api(self):
        with patch.object(self.tool,'request') as request:
            for form in [{'action':'write','path':'guide.md'}, {'action':'read','path':'../private.md'},
                         {'action':'read','path':'/etc/passwd'}, {'action':'read','path':'.obsidian/secret.md'},
                         {'action':'read','path':'alias.md'}, {'action':'read','path':'guide.md','url':'http://elsewhere'},
                         {'action':'read','path':'guide.md','start_line':0}, {'action':'search','query':''}]:
                self.assertEqual(json.loads(self.tool.call(form))['status'],'error',form)
            request.assert_not_called()

    def test_read_pagination_and_search_scope(self):
        with patch.object(self.tool,'request',return_value='\n'.join(str(i) for i in range(250))):
            r=json.loads(self.tool.call({'action':'read','path':'guide.md'}))['data']
            self.assertEqual(r['next_line'],201);self.assertEqual(r['end_line'],200)
        response=[{'filename':'guide.md','matches':[{'context':'synthetic'}]},
                  {'filename':'.obsidian/secret.md','matches':[{'context':'secret'}]},
                  {'filename':'alias.md','matches':[{'context':'secret'}]}]
        with patch.object(self.tool,'request',return_value=json.dumps(response)) as request:
            r=json.loads(self.tool.call({'action':'search','query':'synthetic'}))
            self.assertEqual(len(r['data']['matches']),1)
            self.assertNotIn('secret',json.dumps(r));self.assertTrue(request.call_args.kwargs['search'])

    def test_list_filters_config_and_symlinks(self):
        with patch.object(self.tool,'request',return_value=json.dumps({'files':['guide.md','.obsidian/','alias.md']})):
            r=json.loads(self.tool.call({'action':'list'}))
            self.assertEqual(r['data']['entries'],['guide.md'])

    def test_explicit_binding_disconnects_logs(self):
        api=SimpleNamespace(tools=[SimpleNamespace(name='query_logs'),SimpleNamespace(name='update_soul')])
        chat=Conversation(api,8192,store=SimpleNamespace(generation=''),session_id='synthetic');chat.bind_vault()
        self.assertEqual([t.name for t in api.tools],['update_soul','read_docs'])
        chat.bind_vault();self.assertEqual(sum(t.name=='read_docs' for t in api.tools),1)

    def test_errors_do_not_leak_credentials(self):
        with patch.object(self.tool,'request',side_effect=RuntimeError('private credential')):
            self.assertNotIn('private credential',self.tool.call({'action':'list'}))

if __name__=='__main__':unittest.main()
