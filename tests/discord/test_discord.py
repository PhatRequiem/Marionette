"""Synthetic DM checks; never connect to Discord or use private credentials."""
import asyncio
import contextlib
import datetime
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/marionette'))
import discord_bot as bot
from conversation import Conversation
import terminal
from style import COLORS
from identity import Profiles


@contextlib.asynccontextmanager
async def typing():
    yield


def message(number=1, owner=123, guild=None, channel=None, content='hello', attachments=None):
    if channel is None:
        channel = Mock(spec=bot.discord.DMChannel)
        channel.id = 789
        channel.send = AsyncMock(return_value=SimpleNamespace(id=987))
        channel.typing = typing
    return SimpleNamespace(id=number, author=SimpleNamespace(id=owner, bot=False),
                           guild=guild, channel=channel, content=content,
                           created_at=datetime.datetime.now(datetime.timezone.utc),
                           attachments=attachments or [], stickers=[])


class FakeAPI:
    def __init__(self):
        self.closing = threading.Event()
        self.requests = []
    def count(self, messages):
        return 10
    def reply(self, messages, reserve, *, on_delta):
        assert on_delta is None
        self.requests.append(messages.copy())
        return 'Final answer.', 'stop'


class DMTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.api = FakeAPI()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        profiles = Profiles(Path(temporary.name) / 'profiles.json')
        profiles.profiles[0]['discord_id'] = '123'
        self.conversation = Conversation(self.api, 65536, profiles, profiles.profiles[0])
        async def request(address, text, sender_id):
            self.assertEqual(sender_id, 123)
            answer, finish = self.conversation.turn(text, source='discord', sender_id=str(sender_id))
            return {'answer': answer, 'finish': finish, 'timings': {'main_queue_ms': 2, 'processing_ms': 3}}
        self.request = patch.object(bot, 'request', side_effect=request).start()
        self.client = bot.DMChat('/synthetic/socket', 123)
        self.logged = patch('diagnostics.log').start()
        self.events = patch.object(bot, 'log').start()
        self.transcript = patch.object(bot, 'transcript').start()
        self.addCleanup(patch.stopall)

    async def asyncTearDown(self):
        await self.client.close()

    async def test_only_owner_one_to_one_dms_and_no_duplicate_events(self):
        foreign = message(owner=456)
        guild = message(guild=object())
        group = message(channel=Mock(spec=bot.discord.GroupChannel))
        automated = message(); automated.author.bot = True
        for item in (foreign, guild, group, automated):
            await self.client.on_message(item)
        self.assertEqual(self.api.requests, [])
        self.transcript.assert_not_called()
        accepted = message()
        await self.client.on_message(accepted)
        await self.client.on_message(accepted)
        self.assertEqual(len(self.api.requests), 1)
        self.assertEqual(accepted.channel.send.await_args.args, ('Final answer.',))
        self.assertFalse(accepted.channel.send.await_args.kwargs['allowed_mentions'].everyone)
        self.assertFalse(self.client.intents.message_content)
        self.assertTrue(self.client.intents.dm_messages)

    async def test_concurrent_dms_stay_in_order_and_clear_discards_history(self):
        first, second = message(content='one'), message(number=2, content='two')
        await asyncio.gather(self.client.on_message(first), self.client.on_message(second))
        self.assertEqual([m['content'].split('\n\nMessage:\n', 1)[-1] for m in self.api.requests[1]], ['one', 'Final answer.', 'two'])
        await self.client.on_message(message(number=3, content='/clear'))
        await self.client.on_message(message(number=4, content='fresh'))
        self.assertEqual(len(self.api.requests[-1]), 1)
        self.assertTrue(self.api.requests[-1][0]['content'].endswith('Message:\nfresh'))

    async def test_attachments_never_reach_model(self):
        await self.client.on_message(message(attachments=[object()]))
        self.assertEqual(self.api.requests, [])

    async def test_empty_answer_is_rejected_but_delivery_failure_keeps_shared_history(self):
        with patch.object(self.api, 'reply', return_value=('', 'length')):
            item = message()
            await self.client.on_message(item)
            self.assertEqual(self.conversation.history, [])
            self.assertIn('could not finish', item.channel.send.await_args.args[0])
        item = message(number=2)
        item.channel.send.side_effect = bot.discord.HTTPException(SimpleNamespace(status=500, reason='synthetic'), 'failed')
        await self.client.on_message(item)
        self.assertEqual(self.conversation.history[-1]['content'], 'Final answer.')

    async def test_long_answer_split_without_loss_or_reasoning(self):
        answer = ('line 😀 @everyone\n' * 500)
        item = message()
        with patch.object(self.api, 'reply', return_value=(answer, 'stop')):
            await self.client.on_message(item)
        parts = [call.args[0] for call in item.channel.send.await_args_list]
        self.assertEqual(''.join(parts), answer)
        self.assertTrue(all(len(part.encode('utf-16-le')) // 2 <= 1900 for part in parts))
        self.assertEqual(self.conversation.history[-1]['content'], answer)

    async def test_received_metadata_and_timing_breakdown(self):
        item = message()
        item.created_at -= datetime.timedelta(seconds=2)
        with patch.object(bot.DMChat, 'latency', new_callable=PropertyMock, return_value=.025):
            await self.client.on_message(item)
        events = {call.args[0]: call.kwargs for call in self.events.call_args_list}
        received = events['Discord message received.']
        self.assertEqual((received['sender_id'], received['channel_id'], received['message_id']),
                         ('123', '789', '1'))
        self.assertEqual(received['heartbeat_ms'], 25)
        self.assertGreaterEqual(received['receipt_delay_ms'], 2000)
        self.assertEqual(received['created_at'], item.created_at.isoformat())
        self.assertIn('received_at', received)
        self.assertGreaterEqual(events['Discord turn started.']['adapter_queue_ms'], 0)
        local = events['Local response completed.']
        self.assertEqual((local['main_queue_ms'], local['processing_ms']), (2, 3))
        self.assertGreaterEqual(local['local_response_ms'], 0)
        sent = events['Discord chunk sent.']
        self.assertEqual((sent['outgoing_message_id'], sent['chunk'], sent['chunk_count']), ('987', 1, 1))
        self.assertGreaterEqual(sent['send_ms'], 0)
        self.assertGreaterEqual(events['Discord answer delivered.']['total_ms'], 0)

    async def test_partial_send_logs_codes_and_progress_without_error_payload(self):
        item = message()
        error = bot.discord.HTTPException(SimpleNamespace(status=403, reason='Forbidden'),
                                          {'code': 50007, 'message': 'synthetic-secret-payload'})
        item.channel.send.side_effect = [SimpleNamespace(id=987), error, SimpleNamespace(id=988)]
        with patch.object(self.api, 'reply', return_value=('a' * 2000, 'stop')):
            await self.client.on_message(item)
        failure = next(call.kwargs for call in self.events.call_args_list
                       if call.args[0] == 'Discord chunk failed.')
        self.assertEqual((failure['chunk'], failure['chunk_count'], failure['confirmed_chunks']), (2, 2, 1))
        self.assertEqual((failure['http_status'], failure['discord_code']), (403, 50007))
        self.assertNotIn('synthetic-secret-payload', str(self.events.call_args_list))
        self.assertFalse(any(c.args[0] == 'Discord answer delivered.' for c in self.events.call_args_list))

    async def test_connection_events_and_unavailable_latency(self):
        with patch.object(bot.DMChat, 'latency', new_callable=PropertyMock, return_value=float('nan')):
            await self.client.on_connect()
            await self.client.on_disconnect()
            first_disconnect = self.client.disconnected_at
            await self.client.on_disconnect()
            self.assertEqual(self.client.disconnected_at, first_disconnect)
            await self.client.on_resumed()
        resumed = self.events.call_args.kwargs
        self.assertIsNone(resumed['heartbeat_ms'])
        self.assertGreaterEqual(resumed['downtime_ms'], 0)
        self.assertIsNone(self.client.disconnected_at)


class ConfigAndStreamingTests(unittest.TestCase):
    def test_main_chat_shutdown_disconnects_adapter(self):
        closed = []
        class Client:
            def __init__(self, *args):
                self.done = asyncio.Event()
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def start(self, token):
                await self.done.wait()
            async def close(self):
                closed.append(True)
                self.done.set()
        address = Mock()
        address.stat.side_effect = [SimpleNamespace(st_ino=123), FileNotFoundError()]
        with patch.object(bot, 'read_config', return_value=(123, 'synthetic')), \
             patch.object(bot, 'ADDRESS', address), patch.object(bot, 'DMChat', Client), \
             patch.object(bot, 'log'), patch.object(bot.sys, 'argv', ['discord_bot.py']), \
             patch.object(bot.asyncio, 'sleep', new_callable=AsyncMock):
            self.assertEqual(bot.main(), 0)
        self.assertEqual(closed, [True])

    def test_config_fails_closed_and_does_not_echo_token(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / '.env'
            p.write_text('DISCORD_ALLOWED_USER_ID=123\nDISCORD_BOT_TOKEN=synthetic-secret\n')
            p.chmod(0o600)
            self.assertEqual(bot.read_config(p), (123, 'synthetic-secret'))
            p.chmod(0o644)
            with self.assertRaises(ValueError) as error:
                bot.read_config(p)
            self.assertNotIn('synthetic-secret', str(error.exception))
            p.chmod(0o600)
            p.write_text('DISCORD_ALLOWED_USER_ID=\nDISCORD_BOT_TOKEN=synthetic-secret\n')
            with self.assertRaises(ValueError):
                bot.read_config(p)
