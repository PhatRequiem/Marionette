"""Exercise Discord launch/log plumbing with synthetic HTTP and no Discord login."""
import importlib.util
from pathlib import Path
import shutil
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('launcher_fixtures', ROOT / 'tests/native-linux/test_setup.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class DiscordLauncherTests(unittest.TestCase):
    def test_foreground_launch_routes_reasoning_locally_and_releases_lock(self):
        fixture = fixtures.LauncherTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        root = fixture.root
        (root / 'runtime/discord').symlink_to(sys.prefix, target_is_directory=True)
        config = root / 'data/discord/.env'
        config.parent.mkdir()
        config.write_text('DISCORD_ALLOWED_USER_ID=123\nDISCORD_BOT_TOKEN=synthetic-token\n')
        config.chmod(0o600)
        source = root / 'src/marionette'
        shutil.copy2(ROOT / 'src/marionette/discord_bot.py', source / 'adapter.py')
        (source / 'discord_bot.py').write_text('''import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import adapter

@contextlib.asynccontextmanager
async def typing():
    yield

async def synthetic_start(self, token):
    assert token == 'synthetic-token'
    channel = Mock(spec=adapter.discord.DMChannel)
    channel.send = AsyncMock()
    channel.typing = typing
    await self.on_message(SimpleNamespace(id=1, author=SimpleNamespace(id=123, bot=False),
        guild=None, channel=channel, content='Synthetic hello', attachments=[], stickers=[]))
    assert channel.send.call_args.args == ('Synthetic reply.',)
    if self.pending:
        await asyncio.to_thread(self.pending.result)

adapter.DMChat.start = synthetic_start
raise SystemExit(adapter.main())
''')
        runtime = root / 'runtime/llama.cpp/test/bin/completion'
        runtime.write_text(runtime.read_text().replace("{'content': 'Synthetic reply.'}",
            "{'reasoning_content': 'PRIVATE_THOUGHT', 'content': 'Synthetic reply.'}"))
        fixture.env['MARIONETTE_MODE'] = 'discord'
        # A second run also proves normal shutdown releases the singleton lock.
        for _ in range(2):
            result = fixture.run_chat()
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((root / 'viewer-calls.txt').exists())
        self.assertEqual(len(list(fixture.logs.iterdir())), 6)
        for chat in fixture.logs.glob('*-chat.txt'):
            self.assertIn('discord_', chat.name)
            self.assertIn('Synthetic reply.', chat.read_text())
            self.assertNotIn('PRIVATE_THOUGHT', chat.read_text())
            model = chat.with_name(chat.name.replace('-chat.txt', '-model.txt')).read_text()
            self.assertIn('PRIVATE_THOUGHT', model)
            self.assertIn('Discord answer delivered', model)
            self.assertIn('Exit status: 0', model)
