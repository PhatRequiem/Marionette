#!/usr/bin/env python3
"""Optional, owner-only Discord DM transport for the local chat engine."""
import asyncio
import datetime
import json
from pathlib import Path
import signal
import sys

import discord

from connection import request

ROOT = Path(__file__).resolve().parents[2]
ADDRESS = ROOT / 'data/session/chat.sock'


def log(message):
    print(f'{datetime.datetime.now().astimezone().isoformat()} {message}', flush=True)


def read_config(path):
    values = {}
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                key, separator, value = line.partition('=')
                if not separator or key not in ('DISCORD_ALLOWED_USER_ID', 'DISCORD_BOT_TOKEN'):
                    raise ValueError('Invalid Discord configuration line; use .env.example.')
                values[key] = value.strip()
    except FileNotFoundError:
        raise ValueError('Create data/discord/.env using .env.example; see the Discord guide.') from None
    owner = values.get('DISCORD_ALLOWED_USER_ID', '')
    token = values.get('DISCORD_BOT_TOKEN', '')
    if not owner.isascii() or not owner.isdecimal() or not 0 < int(owner) < 2**64 or not token:
        raise ValueError('Fill in DISCORD_ALLOWED_USER_ID and DISCORD_BOT_TOKEN in data/discord/.env.')
    if any(char.isspace() for char in token) or token.startswith(('"', "'")):
        raise ValueError('Enter the bot token without quotes or spaces.')
    if path.stat().st_mode & 0o077:
        raise ValueError('Discord credentials must be private: chmod 600 data/discord/.env')
    return int(owner), token


def chunks(text, limit=1900):
    """Respect Discord's message size even for characters using two UTF-16 units."""
    part, size = [], 0
    for char in text:
        width = len(char.encode('utf-16-le')) // 2
        if size + width > limit:
            yield ''.join(part)
            part, size = [], 0
        part.append(char)
        size += width
    if part:
        yield ''.join(part)


def transcript(role, content, message_id):
    print(json.dumps({'time': datetime.datetime.now().astimezone().isoformat(),
                      'message_id': str(message_id), 'role': role, 'content': content},
                     ensure_ascii=False), flush=True)


class DMChat(discord.Client):
    def __init__(self, address, owner):
        intents = discord.Intents.none()
        intents.dm_messages = True
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none(),
                         max_messages=None)
        self.address, self.owner = address, owner
        self.turn_lock = asyncio.Lock()
        self.last_message_id = 0

    async def on_ready(self):
        log('Discord connected; accepting only configured owner DMs.')
        print('Discord ready. Send the bot a DM. Ctrl+C disconnects Discord; main chat keeps running.', flush=True)

    async def on_error(self, event, *args, **kwargs):
        # Do not dump Gateway payloads or credentials through generic tracebacks.
        log(f'Discord event failed: {event}; {type(sys.exception()).__name__}.')

    async def on_message(self, message):
        # Filter before reading/logging content or touching conversation history.
        if (message.author.bot or message.author.id != self.owner
                or message.guild is not None or not isinstance(message.channel, discord.DMChannel)):
            return
        async with self.turn_lock:
            if message.id <= self.last_message_id:
                return
            self.last_message_id = message.id
            if message.attachments or message.stickers:
                await message.channel.send('Text only for now; please send your message without attachments.')
                return
            text = message.content.strip()
            if not text:
                return
            transcript('user', text, message.id)
            try:
                async with message.channel.typing():
                    answer, finish = await request(self.address, text)
                    transcript('assistant', answer, message.id)
                    for part in chunks(answer):
                        await message.channel.send(part, suppress_embeds=True,
                                                   allowed_mentions=discord.AllowedMentions.none())
                log(f'Discord answer delivered: message_id={message.id}.')
                if finish == 'length':
                    await message.channel.send('[Thinking and answer reached their shared token allowance.]')
            except (OSError, ValueError, RuntimeError, discord.HTTPException) as error:
                log(f'Discord turn failed: message_id={message.id}; {type(error).__name__}. '
                            'Delivery may be partial; no automatic resend.')
                try:
                    await message.channel.send('This turn could not finish. Please try again; details are in the local logs.')
                except discord.HTTPException:
                    log('Discord error notice could not be delivered.')


def main():
    owner, token = read_config(ROOT / 'data/discord/.env')
    if sys.argv[1:] == ['--check-config']:
        return 0

    identity = ADDRESS.stat().st_ino

    async def serve():
        async with DMChat(ADDRESS, owner) as bot:
            async def watch_session():
                while True:
                    await asyncio.sleep(1)
                    try:
                        alive = ADDRESS.stat().st_ino == identity
                    except FileNotFoundError:
                        alive = False
                    if not alive:
                        log('Main chat ended. Disconnecting Discord.')
                        await bot.close()
                        return
            watcher = asyncio.create_task(watch_session())
            try:
                await bot.start(token)
            finally:
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
    asyncio.run(serve())
    return 0


if __name__ == '__main__':
    def interrupt(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGHUP, interrupt)
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('Discord session stopped.', flush=True)
    except (OSError, ValueError, RuntimeError, discord.DiscordException) as error:
        # Never print the credential or HTTP request headers.
        if isinstance(error, ValueError):
            print(str(error), file=sys.stderr)
        else:
            print(f'Discord startup failed ({type(error).__name__}); check configuration and connection.', file=sys.stderr)
        raise SystemExit(1)
