"""Request-form handler tests use isolated synthetic data and sockets."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/marionette'))
from storage import Store
from log_query import handle,validate,records
from ram_logs import RamLogs,LiveView
from connection import LocalConnection


class QueryTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.path=self.root/'logs.sqlite3'
        self.store=Store(self.path);self.addCleanup(self.store.close)
        self.session=self.store.start();self.conversation='discord:42';self.identifier='discord:123'
        self.store.message(self.session,self.identifier,self.conversation,None,'discord','42','user','input','SECRET USER TEXT','received')
        self.args=dict(database=self.path,session=self.session,conversation=self.conversation,live=False)

    def event(self,text):
        return self.store.event(self.session,'diagnostic',('Client: [message discord:123] '+text+'\n').encode())

    def query(self,lookup,**kwargs):
        return handle({'lookup':lookup,'target':'message_id','message_id':self.identifier},**(self.args|kwargs))

    def test_tool_outcome_and_correlated_server_evidence(self):
        request_id='00000000-0000-0000-0000-000000000001'
        self.event('[request 01] [tool 01] Tool call identity: {"name":"read_vault","protocol_tool_call_id":"call_1"}')
        self.event('[request 01] [tool 01] Tool result summary: {"name":"read_vault","protocol_tool_call_id":"call_1","outcome":"Failed"}')
        self.event('[request 01] [tool 01] Connection event: '+json.dumps({'source':'Obsidian','event':'request_started','request_id':request_id}))
        for rid in (request_id, '00000000-0000-0000-0000-000000000002'):
            self.store.event(self.session,'diagnostic', ('Client: Connection event: '+json.dumps({
                'source':'Scarecrow','event':'request_failed','request_id':rid,'http_status':503,'duration_ms':12})+'\n').encode())
        processing=self.query('processing')['data']
        self.assertEqual(processing['tools'][0]['outcome'],'Failed')
        self.assertEqual(processing['tools'][0]['protocol_tool_call_id'],'call_1')
        self.assertEqual(len(processing['tools']),1)
        self.assertEqual(len(processing['connections']),2)
        self.assertEqual(processing['connections'][-1]['component'],'Scarecrow')
        self.assertEqual(processing['connections'][-1]['http_request_id'],request_id)
        failures=self.query('errors')['data']['failures']
        self.assertEqual({f['component'] for f in failures},{'tool','vault'})
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM failures WHERE component='tool'").fetchone()[0],1)

    def test_connection_join_live_and_after_shutdown(self):
        from contextlib import closing
        rid='00000000-0000-0000-0000-000000000001'
        with closing(RamLogs(self.store,self.session)) as buffer:
            buffer.append(('Client: [message discord:123] Connection event: '+json.dumps({
                'source':'Obsidian','event':'request_started','request_id':rid})+'\n').encode(),'server')
            buffer.append(('Client: Connection event: '+json.dumps({
                'source':'Scarecrow','event':'request_completed','request_id':rid,'http_status':200})+'\n').encode(),'server')
            with closing(LiveView(buffer,self.path)):
                before=self.query('processing',live=True)['data']['connections']
                self.assertEqual(len(before),2)
                self.assertEqual(self.store.db.execute('SELECT count(*) FROM events').fetchone()[0],0)
            buffer.save()
        after=self.query('processing')['data']['connections']
        self.assertEqual(before,after)

    def test_failed_tool_summary_alone_is_an_error(self):
        self.event('[request 01] [tool 01] Tool result summary: {"name":"update_soul","outcome":"Failed"}')
        self.assertEqual(self.query('errors')['data']['failures'][0]['component'],'tool')
        self.event('[request 01] [tool 01] Tool Call failed: synthetic failure')
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM failures WHERE component='tool'").fetchone()[0],1)

    def test_processing_scoped_and_no_conversation_prose(self):
        self.event('========== MESSAGE START | processing ==========')
        self.event('Prompt budget: 100 tokens + 200 reply allowance < 1000; removed_exchanges=0.')
        self.event('Message input: "SECRET USER TEXT"')
        self.event('[request 01] Runtime usage: {"prompt_tokens":100,"completion_tokens":20,"total_tokens":120}')
        self.event('[request 01] [tool 01] Tool call identity: {"name":"update_soul"}')
        self.event('Reply completed: finish_reason=stop.')
        self.event('========== MESSAGE END | processing | completed ==========')
        report=self.query('processing')
        self.assertEqual(report['data']['outcome'],'completed')
        self.assertEqual(report['data']['requests'][0]['total_tokens'],120)
        self.assertEqual(report['data']['tools'][0]['name'],'update_soul')
        self.assertNotIn('SECRET',json.dumps(report))
        with self.assertRaises(ValueError):self.query('processing',conversation='discord:99')

    def test_token_totals_separate_repeated_inputs_from_generated_tokens(self):
        for number, prompt, completion in [('01',1815,77),('02',3231,192)]:
            self.event(f'[request {number}] Runtime usage: '+json.dumps({'prompt_tokens':prompt,'completion_tokens':completion,'total_tokens':prompt+completion}))
        result=self.query('processing')
        totals=result['data']['recorded_token_totals']
        self.assertEqual(totals,{'usage_records':2,'input_tokens_summed':5046,'generated_tokens_including_reasoning':269})
        self.assertEqual(result['status'],'partial')
        self.assertIn('not unique context',result['field_meanings']['recorded_token_totals'])
        self.assertIn('Incoming user',result['message_id_meaning'])
        self.event('[request 03] Runtime usage: {"prompt_tokens":20}')
        self.assertIsNone(self.query('processing')['data']['recorded_token_totals']['generated_tokens_including_reasoning'])
        self.event('[request 03] Runtime usage: {"prompt_tokens":20}')
        with self.assertRaisesRegex(ValueError,'Repeated request usage'):self.query('processing')

    def test_delivery_timer_does_not_turn_failure_into_success(self):
        for title, extra in [('Local response completed.',{'processing_ms':3858.42,'local_response_ms':3948.21}),
                             ('Discord answer delivered.',{'total_ms':4350.13}),
                             ('Discord turn failed; synthetic notice failure',{'total_ms':4500})]:
            self.store.event(self.session,'discord',('2026-11-11T00:00:00+00:00 '+title+' '+json.dumps({'log_message_id':self.identifier,'sender_id':'42',**extra})+'\n').encode())
        result=self.query('delivery')
        timings=result['data']['timings_ms']
        self.assertEqual(timings['receipt_to_delivery_ms'],4350.13)
        self.assertEqual(timings['receipt_to_failure_ms'],4500)
        self.assertNotIn('total_ms',timings)
        self.assertEqual(result['data']['outcome'],'unknown')
        self.assertIn('not send-only',result['field_meanings']['receipt_to_delivery_ms'])

    def test_empty_usage_is_unknown_not_zero(self):
        totals=self.query('processing')['data']['recorded_token_totals']
        self.assertIsNone(totals['input_tokens_summed'])
        self.assertIsNone(totals['generated_tokens_including_reasoning'])

    def test_previous_is_relative_to_trigger_and_same_conversation(self):
        self.store.message(self.session,'discord:124','discord:99',None,'discord','99','user','input','OTHER','received')
        self.store.message(self.session,'discord:125',self.conversation,None,'discord','42','user','input','trigger','received')
        form={'lookup':'errors','target':'previous_message'}
        result=handle(form,**self.args,before_message_id='discord:125')
        self.assertEqual(result['message_id'],self.identifier)
        with self.assertRaises(ValueError):handle(form,**self.args)
        self.assertEqual(handle(form,**self.args,before_message_id=self.identifier)['status'],'unavailable')

    def test_delivery_and_errors_from_saved_discord(self):
        for title,extra in [('Discord chunk sent.',{'kind':'answer','outgoing_message_id':'999'}),
                            ('========== MESSAGE END | Discord delivery ==========',{'outcome':'delivered','total_ms':50})]:
            fields={'log_message_id':self.identifier,'sender_id':'42',**extra}
            raw=('2026-11-11T00:00:00+00:00 '+title+' '+json.dumps(fields)+'\n').encode()
            self.store.event(self.session,'discord',raw)
        result=self.query('delivery')
        self.assertEqual(result['data']['outcome'],'delivered')
        self.assertEqual(result['data']['chunks_sent'],1)
        self.assertEqual(self.query('errors')['status'],'no_matches')
        self.event('Message failed: RuntimeError: synthetic failure')
        errors=self.query('errors')
        self.assertEqual(len(errors['data']['failures']),1) # events + protected copy merged
        self.assertIn('synthetic failure',errors['data']['failures'][0]['detail'])

    def test_unknown_is_not_failure_and_bad_requests_fail(self):
        self.assertEqual(self.query('delivery')['data']['outcome'],'unknown')
        self.assertEqual(self.query('processing')['status'],'unavailable')
        for form in ({'lookup':'status','target':'startup'}, {'lookup':'status','target':'current','sql':'DROP TABLE events'},
                     {'lookup':'errors','target':'message_id'},
                     {'lookup':'errors','target':'message_id','message_id':None},
                     {'lookup':'errors','target':'message_id','message_id':'discord:123\n'}, {'lookup':[],'target':'current'}):
            with self.assertRaises(ValueError):validate(form)

    def test_live_ram_evidence_without_disk_payload_write(self):
        ram=RamLogs(self.store,self.session);self.addCleanup(ram.close)
        view=LiveView(ram,self.path);self.addCleanup(view.close)
        for text in ('========== MESSAGE START | processing ==========','========== MESSAGE END | processing | completed =========='):
            ram.append(('Client: [message discord:123] '+text+'\n').encode(),'both')
        result=self.query('processing',live=True)
        self.assertEqual(result['data']['outcome'],'completed')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM events').fetchone()[0],0)

    def test_status_fresh_probe_and_unavailable(self):
        path=self.root/'chat.sock'
        expected={'model_server':'online','discord':'unknown','tools':['synthetic_tool'],'processing':'idle','observed_at':'2026-11-11T00:00:00+00:00'}
        def no_turn(*args,**kwargs):raise AssertionError('Status must not invoke a model turn')
        with LocalConnection(path,no_turn,lambda _:None,status=lambda:expected):
            result=handle({'lookup':'status','target':'current'},socket_path=path)
            self.assertEqual(result['data'],expected)
            self.assertEqual(result['status'],'partial')
        self.assertEqual(handle({'lookup':'status','target':'current'},socket_path=path)['data']['model_server'],'unknown')

    def test_setup_uses_only_marked_section(self):
        path=self.root/'setup.md'
        path.write_text('SECRET OUTSIDE\n<!-- startup-observations:start -->\nUpdated (UTC): 2026-11-11T00:00:00+00:00\n| Fact | Value | Evidence |\n|---|---|---|\n| Model | Synthetic | Runtime |\n| Runtime version | 0.9.0-dev | Runtime --version |\n<!-- startup-observations:end -->\n')
        result=handle({'lookup':'setup','target':'startup'},datasheet=path)
        self.assertEqual(result['data']['fields'][0],{'name':'Model','value':'Synthetic','source':'Runtime'})
        self.assertEqual(result['data']['fields'][1]['name'],'llama.cpp runtime version')
        self.assertNotIn('SECRET',json.dumps(result))

    def test_bounded_evidence_and_conflicting_endings(self):
        self.event('========== MESSAGE END | processing | completed ==========')
        self.event('========== MESSAGE END | processing | failed ==========')
        with self.assertRaises(ValueError):self.query('processing')
        self.store.event(self.session,'diagnostic',b'Client: [message discord:123] '+b'x'*(1024*1024))
        with self.assertRaises(ValueError):records(self.store.db,self.session,self.identifier)


class DiscordStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_discord_states_without_model_or_gateway(self):
        import asyncio
        from operator_status import start,probe
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'chat.sock';bot=Mock()
            bot.is_closed.return_value=False;bot.is_ready.return_value=True
            server=await start(bot,path)
            try:
                self.assertEqual((await asyncio.to_thread(probe,path))['discord'],'online')
                bot.is_ready.return_value=False
                self.assertEqual((await asyncio.to_thread(probe,path))['discord'],'connecting')
                bot.is_closed.return_value=True
                self.assertEqual((await asyncio.to_thread(probe,path))['discord'],'offline')
            finally:
                server.close();await server.wait_closed()
            self.assertIsNone(await asyncio.to_thread(probe,path))


class DiscordStopControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_endpoint_and_status_share_existing_process(self):
        import asyncio
        from unittest.mock import AsyncMock, Mock
        from operator_status import start, probe, request_stop
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'chat.sock'
            bot=Mock()
            bot.is_closed.return_value=False
            bot.is_ready.return_value=True
            bot.close=AsyncMock()
            server=await start(bot,path)
            try:
                self.assertEqual((await asyncio.to_thread(probe,path))['discord'],'online')
                bot.close.assert_not_called()
                self.assertTrue(await asyncio.to_thread(request_stop,path))
                await asyncio.sleep(0)
                bot.close.assert_awaited_once()
            finally:
                server.close()
                await server.wait_closed()
