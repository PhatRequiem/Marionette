"""Attach/detach Discord to a synthetic running terminal session; no Discord login."""
import importlib.util
import io
import json
from contextlib import closing
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('launcher_fixtures', ROOT / 'tests/core/test_setup.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class DiscordLauncherTests(unittest.TestCase):
    def test_attach_detach_reuses_session_and_fourth_terminal(self):
        self.check_attach(False)

    def test_attach_with_alternate_data_directory(self):
        self.check_attach(True)

    def check_attach(self, alternate):
        fixture = fixtures.LauncherTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        root = fixture.root
        data = root / ('alternate data' if alternate else 'data')
        fixture.env['MARIONETTE_DATA_DIR'] = str(data)
        fixture.env['SYNTHETIC_PROFILE_FILE'] = str(data / 'contacts/profiles.json')
        (root / 'runtime').mkdir(exist_ok=True)
        (root / 'runtime/discord').symlink_to(sys.prefix, target_is_directory=True)
        config = data / 'discord/.env'
        config.parent.mkdir(parents=True)
        config.write_text('DISCORD_ALLOWED_USER_ID=123\nDISCORD_BOT_TOKEN=synthetic-token\n')
        config.chmod(0o600)
        source = root / 'src/marionette'
        shutil.copy2(ROOT / 'scripts/native-linux/discord.sh', root / 'scripts/native-linux/discord.sh')
        shutil.copy2(ROOT / 'src/marionette/discord_bot.py', source / 'adapter.py')
        (source / 'discord_bot.py').write_text('''import contextlib
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import adapter

@contextlib.asynccontextmanager
async def typing():
    yield

async def synthetic_start(self, token):
    assert token == 'synthetic-token'
    channel = Mock(spec=adapter.discord.DMChannel)
    channel.id = 789
    channel.send = AsyncMock(return_value=SimpleNamespace(id=987))
    channel.typing = typing
    await self.on_message(SimpleNamespace(id=1, author=SimpleNamespace(id=123, bot=False, display_name="Synthetic owner"),
        guild=None, channel=channel, content='Synthetic Discord hello', attachments=[], stickers=[],
        created_at=datetime.datetime.now(datetime.timezone.utc)))
    assert channel.send.call_args.args == ('Synthetic reply.',)

adapter.DMChat.start = synthetic_start
raise SystemExit(adapter.main())
''')
        runtime = fixture.runtime
        runtime.write_text(runtime.read_text().replace("{'content': 'Synthetic reply.'}",
            "{'reasoning_content': 'PRIVATE_THOUGHT', 'content': 'Synthetic reply.'}"))
        # Assert metadata at the HTTP inference boundary, not only in client history.
        runtime.write_text(runtime.read_text().replace(
            "        elif self.path == '/v1/chat/completions':",
            """        elif self.path == '/v1/chat/completions':
            import os
            from pathlib import Path
            profiles = json.loads(Path(os.environ['SYNTHETIC_PROFILE_FILE']).read_text())
            content = body['messages'][-1]['content']
            header, text = content.split('\\n\\nMessage:\\n', 1)
            identity = json.loads(header.split('\\n', 1)[1])
            assert identity['contact_uuid'] == profiles['owner_uuid']
            assert identity['display_name'] == 'Phat'
            expected_source = 'discord' if text == 'Synthetic Discord hello' else 'terminal'
            assert identity['source'] == expected_source
            assert identity['sender_id'] == ('123' if expected_source == 'discord' else profiles['owner_uuid'])
            print('Verified identity at inference: ' + expected_source, file=sys.stderr, flush=True)
"""))
        address = data / 'session/chat.sock'
        address.parent.mkdir(mode=0o700)
        from storage import Store, view_log
        database = fixture.logs / 'marionette.sqlite3'
        with closing(Store(database)) as store:
            session_id = store.start()
        (address.parent / 'log-session.json').write_text(json.dumps({'database': str(database), 'session': session_id}))
        env = fixture.env | {'MARIONETTE_SESSION_SOCKET': str(address),
                             'MARIONETTE_LOG_DB': str(database), 'MARIONETTE_LOG_SESSION': session_id}
        output_path = root / 'terminal.txt'
        with output_path.open('w') as output:
            main = subprocess.Popen([str(ROOT / 'runtime/agent/bin/python'), str(source / 'session.py'), str(runtime)],
                stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT, env=env, text=True)
            try:
                main.stdin.write('1\n')
                main.stdin.flush()
                deadline = time.monotonic() + 10
                while not address.exists():
                    self.assertIsNone(main.poll(), output_path.read_text())
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(.02)
                self.assertEqual(address.stat().st_mode & 0o777, 0o600)
                children = Path(f'/proc/{main.pid}/task/{main.pid}/children').read_text()
                for _ in range(2):
                    result = subprocess.run(['bash', str(root / 'scripts/native-linux/discord.sh')],
                        env=env, capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIsNone(main.poll())
                    self.assertEqual(Path(f'/proc/{main.pid}/task/{main.pid}/children').read_text(), children)
                self.assertFalse((root / 'viewer-calls.txt').exists())
                saved = io.BytesIO()
                view_log(database, session_id, 'discord', saved)
                log = saved.getvalue().decode()
                self.assertFalse(list(fixture.logs.glob('*.txt')))
                self.assertEqual(log.count('Discord answer delivered.'), 2)
                self.assertIn('Synthetic reply.', log)
                self.assertNotIn('PRIVATE_THOUGHT', log)
                self.assertIn('"channel_id": "789"', log)
                self.assertIn('"outgoing_message_id": "987"', log)
                self.assertIn('"main_queue_ms":', log)
                self.assertNotIn('"main_queue_ms": null', log)
                self.assertNotIn('"processing_ms": null', log)
                main.communicate('terminal still works\n/exit\n', timeout=10)
                self.assertEqual(main.returncode, 0)
                with closing(Store(database)) as store:
                    rows = store.db.execute("SELECT source, kind, content FROM messages ORDER BY id").fetchall()
                    self.assertTrue(any(r['source'] == 'discord' and r['kind'] == 'reasoning' and r['content'] == 'PRIVATE_THOUGHT' for r in rows))
                    self.assertTrue(any(r['source'] == 'terminal' and r['kind'] == 'answer' for r in rows))
                self.assertIn('[Discord · 123]\nSynthetic Discord hello', output_path.read_text())
                self.assertIn('Reasoning:\nPRIVATE_THOUGHT', output_path.read_text())
                self.assertIn('Answer:\nSynthetic reply.', output_path.read_text())
                self.assertIn('Verified identity at inference: terminal', output_path.read_text())
                self.assertEqual(output_path.read_text().count('Verified identity at inference: discord'), 2)
                self.assertFalse(address.exists())
                result = subprocess.run(['bash', str(root / 'scripts/native-linux/discord.sh')],
                                        env=env, capture_output=True, text=True, timeout=10)
                self.assertIn('Launch her', result.stderr)
            finally:
                if main.poll() is None:
                    main.terminate()
                    main.communicate(timeout=10)
