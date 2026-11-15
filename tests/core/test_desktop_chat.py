"""Desktop transport uses the existing owner conversation, with synthetic data."""
import copy
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/marionette'))
from connection import LocalConnection
from contacts import ContactProfiles
from contact_notes import ContactNotes
from conversation import Conversation
from soul import Soul
from storage import Store
import terminal


class SyntheticAPI:
    def __init__(self):
        self.closing = threading.Event()
        self.tools = ()
        self.sent = []
    def count(self, messages):
        return 10
    def prepare(self, messages):
        pass
    def reply(self, messages, reserve, on_delta=None):
        self.sent.append(copy.deepcopy(messages))
        if on_delta:
            on_delta('reasoning', 'PRIVATE_THINKING')
            on_delta('answer', 'Synthetic desktop answer.')
        return 'Synthetic desktop answer.', 'stop'


class DesktopChatTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root/'session').mkdir()
        self.profiles = ContactProfiles(self.root/'contacts/profiles.json')
        self.owner = self.profiles.profiles[0]
        self.other = self.profiles.add('Other contact')
        self.store = Store(self.root/'conversations/marionette.sqlite3')
        self.addCleanup(self.store.close)
        self.session = self.store.start()
        self.address = self.root/'session/chat.sock'
        self.descriptor = self.root/'session/log-session.json'
        self.write_epoch('')
        self.api = SyntheticAPI()
        self.conversation = Conversation(self.api,8192,self.profiles,self.other,
            ContactNotes(self.root/'contact_notes'),self.store,self.session,Soul(self.root/'soul/profile.json'))
        self.addCleanup(self.conversation.finish_preparation)
        self.addCleanup(patch.stopall)
        patch('diagnostics.log').start()
        patch('sys.stdout',io.StringIO()).start()
        patch('sys.stdin.isatty',return_value=False).start()
        server = LocalConnection(self.address,self.conversation.submit_discord,lambda _: None,
                                 desktop_turn=self.conversation.submit_desktop)
        self.enterContext(server)

    def write_epoch(self, generation):
        self.descriptor.write_text(json.dumps({'session':self.session,'generation':generation}))

    def request(self, message, *, process=True, **fields):
        payload = {'source':'desktop','session':self.session,'generation':'','message':message,**fields}
        results = []
        def call():
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(5)
                client.connect(str(self.address))
                client.sendall(json.dumps(payload).encode()+b'\n')
                with client.makefile('rb') as reader:
                    results.append(json.loads(reader.readline()))
        worker = threading.Thread(target=call)
        worker.start()
        if process:
            item = self.conversation.incoming.get(timeout=3)
            self.assertEqual(item[2].source,'terminal')
            self.conversation.incoming.put(item)
            self.assertTrue(terminal.display_external(self.conversation))
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(results),1)
        return results[0]

    def test_owner_routing_shared_history_and_only_final_answer(self):
        self.conversation.turn('Other private conversation')
        answer = self.request('Owner desktop input')
        self.assertEqual(answer['answer'],'Synthetic desktop answer.')
        self.assertNotIn('PRIVATE_THINKING',json.dumps(answer))
        self.assertEqual(answer['session'],self.session)
        self.assertEqual(answer['generation'],'')
        self.assertEqual(self.conversation.terminal_profile,self.other)
        rows = self.store.db.execute("SELECT contact_uuid,source,content FROM messages WHERE kind='input' ORDER BY id").fetchall()
        self.assertEqual(tuple(rows[-1]),(self.owner['uuid'],'terminal','Owner desktop input'))
        self.assertNotIn('Other private conversation',json.dumps(self.api.sent[-1]))
        self.conversation.terminal_profile = self.owner
        self.conversation.turn('Owner terminal continuation')
        self.assertIn('Owner desktop input',json.dumps(self.api.sent[-1]))
        self.request('/clear')
        self.assertFalse(self.conversation.histories['terminal:'+self.owner['uuid']])
        self.assertTrue(self.conversation.histories['terminal:'+self.other['uuid']])

    def test_identity_override_stale_session_and_epoch_are_rejected(self):
        for fields in ({'sender_id':self.other['uuid']},{'display_name':'Owner'},
                       {'source':'unknown'},{'session':'old-session'},{'generation':'old-epoch'}):
            with self.subTest(fields=fields):
                self.assertIn('error',self.request('must not enter history',process=False,**fields))
        self.assertTrue(self.conversation.incoming.empty())
        self.assertFalse(self.api.sent)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM messages').fetchone()[0],0)

    def test_desktop_help_explains_detach_without_stopping_main_chat(self):
        answer = self.request('/help',process=False)
        self.assertIn('/exit — Close the desktop puppet',answer['answer'])
        self.assertNotIn('terminal only)',answer['answer'])
        self.assertFalse(self.api.sent)
        self.assertFalse(self.conversation.shutdown_requested)

    def test_owner_reset_reply_carries_new_epoch(self):
        def reset(conversation):
            self.assertEqual(conversation.key,'terminal:'+self.owner['uuid'])
            conversation.epoch = 'fresh-epoch'
            self.write_epoch('fresh-epoch')
            return 'Memory reset.'
        with patch('memory_reset.reset_memory',side_effect=reset) as reset_call:
            answer = self.request('/resetmemory')
        reset_call.assert_called_once_with(self.conversation)
        self.assertEqual(answer['finish'],'resetmemory')
        self.assertEqual(answer['generation'],'fresh-epoch')
        self.assertFalse(self.api.sent)
        self.assertIn('error',self.request('stale pending input',process=False))

    def test_queued_desktop_input_is_discarded_after_reset(self):
        result = []
        worker = threading.Thread(target=lambda: result.append(
            self.conversation.submit_desktop('OLD_SECRET',generation='')))
        worker.start()
        item = self.conversation.incoming.get(timeout=3)
        self.conversation.incoming.put(item)
        self.conversation.epoch = 'fresh-epoch'
        terminal.display_external(self.conversation)
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertIn('discarded',result[0][0])
        self.assertFalse(self.api.sent)
        self.assertFalse(self.conversation.histories)
