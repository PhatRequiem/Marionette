"""Synthetic DM checks; never connect to Discord or use private credentials."""
import asyncio
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/marionette'))
import discord_bot as bot
import session


@contextlib.asynccontextmanager
async def typing():
    yield


def message(number=1, owner=123, guild=None, channel=None, content='hello', attachments=None):
    if channel is None:
        channel = Mock(spec=bot.discord.DMChannel)
        channel.send = AsyncMock()
        channel.typing = typing
    return SimpleNamespace(id=number, author=SimpleNamespace(id=owner, bot=False),
                           guild=guild, channel=channel, content=content,
                           attachments=attachments or [], stickers=[])


class FakeAPI:
    def __init__(self):
        self.closing = threading.Event()
        self.requests = []
    def count(self, messages):
        return 10
    def reply(self, messages, reserve, *, display):
        assert display is False
        self.requests.append(messages.copy())
        return 'Final answer.', 'stop'


class DMTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.api = FakeAPI()
        self.conversation = session.Conversation(self.api, 65536)
        async def request(address, text, sender_id):
            self.assertEqual(sender_id, 123)
            return self.conversation.turn(text)
        self.request = patch.object(bot, 'request', side_effect=request).start()
        self.client = bot.DMChat('/synthetic/socket', 123)
        self.logged = patch.object(session, 'log').start()
        patch.object(bot, 'log').start()
        self.transcript = patch.object(bot, 'transcript').start()
        self.addCleanup(patch.stopall)

    async def asyncTearDown(self):
        if self.conversation.pending:
            await asyncio.to_thread(self.conversation.pending.result)
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
        self.assertEqual([m['content'] for m in self.api.requests[1]], ['one', 'Final answer.', 'two'])
        await self.client.on_message(message(number=3, content='/clear'))
        await self.client.on_message(message(number=4, content='fresh'))
        self.assertEqual(self.api.requests[-1], [{'role': 'user', 'content': 'fresh'}])

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

    def test_reasoning_is_logged_but_never_returned_or_printed(self):
        events = [ {'choices': [{'delta': {'reasoning_content': 'PRIVATE_REASONING'}}]},
                   {'choices': [{'delta': {'content': 'PUBLIC_ANSWER'}, 'finish_reason': 'stop'}]} ]
        stream = io.BytesIO((''.join('data: '+json.dumps(e)+'\n\n' for e in events)+'data: [DONE]\n\n').encode())
        api = session.API('http://127.0.0.1:1')
        with patch.object(api, 'open', return_value=stream), patch.object(session, 'log') as logged, contextlib.redirect_stdout(io.StringIO()) as output:
            result = api.reply([{'role': 'user', 'content': 'test'}], 32768, display=False)
        self.assertEqual(result, ('PUBLIC_ANSWER', 'stop'))
        self.assertEqual(output.getvalue(), '')
        logged.assert_called_once_with('Reasoning: "PRIVATE_REASONING"')
