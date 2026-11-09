#!/usr/bin/env python3
"""Optional, owner-only Discord DM transport for the local chat engine."""
import asyncio
import datetime
import math
import time
from pathlib import Path
import signal
import sys

import discord

from connection import request
from log_store import record, encode

ROOT = Path(__file__).resolve().parents[2]
ADDRESS = ROOT / 'data/session/chat.sock'


def log(message, **fields):
    print(encode(record('discord', 'status', data={'message': message, **fields})).decode(), end='', flush=True)


def elapsed(start):
    return round((time.monotonic() - start) * 1000, 2)


def error_fields(error):
    # Numeric codes only: exception text/headers may include credentials or payloads.
    fields = {'error_type': type(error).__name__}
    for name in ('status', 'code'):
        value = getattr(error, name, None)
        if isinstance(value, int):
            fields['http_status' if name == 'status' else 'discord_code'] = value
    return fields


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


def transcript(role, content, message_id, **fields):
    print(encode(record('discord', 'message_received' if role == 'user' else 'answer',
        data={'message_id': str(message_id), 'role': role, 'content': content, **fields})).decode(), end='', flush=True)


class DMChat(discord.Client):
    def __init__(self, address, owner):
        intents = discord.Intents.none()
        intents.dm_messages = True
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none(),
                         max_messages=None)
        self.address, self.owner = address, owner
        self.turn_lock = asyncio.Lock()
        self.last_message_id = 0
        self.disconnected_at = None

    def heartbeat_ms(self):
        return round(self.latency * 1000, 2) if math.isfinite(self.latency) else None

    async def on_connect(self):
        log('Discord transport connected; awaiting ready/resume.')

    async def on_disconnect(self):
        if self.disconnected_at is None:
            self.disconnected_at = time.monotonic()
        log('Discord disconnected.', heartbeat_ms=self.heartbeat_ms())

    def connection_ready(self, event):
        log(event, heartbeat_ms=self.heartbeat_ms(),
            downtime_ms=elapsed(self.disconnected_at) if self.disconnected_at is not None else None)
        self.disconnected_at = None

    async def on_resumed(self):
        self.connection_ready('Discord session resumed.')

    async def on_ready(self):
        self.connection_ready('Discord ready; accepting only configured owner DMs.')
        print('Discord ready. Send the bot a DM. Ctrl+C disconnects Discord; main chat keeps running.', flush=True)

    async def on_error(self, event, *args, **kwargs):
        log('Discord event failed.', event=event, **error_fields(sys.exception()))

    async def send_parts(self, channel, text, context, *, kind='answer'):
        parts = list(chunks(text))
        started = time.monotonic()
        log('Discord send started.', **context, kind=kind, chunk_count=len(parts))
        for index, part in enumerate(parts, 1):
            part_start = time.monotonic()
            try:
                sent = await channel.send(part, suppress_embeds=True,
                                          allowed_mentions=discord.AllowedMentions.none())
            except (OSError, discord.HTTPException) as error:
                log('Discord chunk failed.', **context, kind=kind, chunk=index,
                    chunk_count=len(parts), confirmed_chunks=index - 1,
                    send_ms=elapsed(part_start), **error_fields(error))
                raise
            log('Discord chunk sent.', **context, kind=kind, chunk=index, chunk_count=len(parts),
                outgoing_message_id=str(sent.id), send_ms=elapsed(part_start))
        log('Discord send completed.', **context, kind=kind, chunk_count=len(parts),
            send_ms=elapsed(started))

    async def on_message(self, message):
        # Filter before reading/logging content or touching conversation history.
        if (message.author.bot or message.author.id != self.owner
                or message.guild is not None or not isinstance(message.channel, discord.DMChannel)):
            return
        received = datetime.datetime.now(datetime.timezone.utc)
        started = time.monotonic()
        context = {'message_id': str(message.id), 'sender_id': str(message.author.id),
                   'channel_id': str(message.channel.id)}
        log('Discord message received.', **context, created_at=message.created_at.isoformat(),
            received_at=received.isoformat(),
            receipt_delay_ms=round((received - message.created_at).total_seconds() * 1000, 2),
            heartbeat_ms=self.heartbeat_ms())
        async with self.turn_lock:
            if message.id <= self.last_message_id:
                log('Discord duplicate/older message ignored.', **context)
                return
            self.last_message_id = message.id
            log('Discord turn started.', **context, adapter_queue_ms=elapsed(started))
            phase = 'input'
            local_start = None
            try:
                if message.attachments or message.stickers:
                    await self.send_parts(message.channel,
                        'Text only for now; please send your message without attachments.', context, kind='notice')
                    return
                text = message.content.strip()
                if not text:
                    log('Discord empty message ignored.', **context)
                    return
                transcript('user', text, **context)
                async with message.channel.typing():
                    phase = 'local_response'
                    local_start = time.monotonic()
                    result = await request(self.address, text, message.author.id)
                    answer, finish = result['answer'], result['finish']
                    timings = result.get('timings', {})
                    log('Local response completed.', **context, local_response_ms=elapsed(local_start),
                        main_queue_ms=timings.get('main_queue_ms'),
                        processing_ms=timings.get('processing_ms'), finish_reason=finish)
                    transcript('assistant', answer, **context)
                    phase = 'delivery'
                    await self.send_parts(message.channel, answer, context)
                log('Discord answer delivered.', **context, total_ms=elapsed(started))
                if finish == 'length':
                    phase = 'notice'
                    await self.send_parts(message.channel,
                        '[Reasoning and answer reached their shared token allowance.]', context, kind='notice')
            except (OSError, ValueError, RuntimeError, discord.HTTPException) as error:
                log('Discord turn failed; delivery may be partial; no automatic resend.',
                    **context, phase=phase, total_ms=elapsed(started),
                    local_response_ms=elapsed(local_start) if phase == 'local_response' and local_start else None,
                    **error_fields(error))
                try:
                    await self.send_parts(message.channel,
                        'This turn could not finish. Please try again; details are in the local logs.',
                        context, kind='error_notice')
                except (OSError, discord.HTTPException):
                    pass  # send_parts has already recorded the failure and codes.


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
        log('Discord session stopped.')
    except (OSError, ValueError, RuntimeError, discord.DiscordException) as error:
        # Never print the credential or HTTP request headers.
        if isinstance(error, ValueError):
            print(str(error), file=sys.stderr)
        else:
            log('Discord startup failed; check configuration and connection.', **error_fields(error))
        raise SystemExit(1)
