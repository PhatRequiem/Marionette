"""Discord status and operator stop control on the existing bot's event loop; no helper process."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import struct


def address(chat_socket):
    key=hashlib.sha256(str(Path(chat_socket).resolve()).encode()).hexdigest()[:32]
    return '\0marionette-discord-status-'+str(os.getuid())+'-'+key


async def start(bot, chat_socket):
    async def answer(reader, writer):
        try:
            peer=writer.get_extra_info('socket')
            _,uid,_=struct.unpack('3i',peer.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            if uid!=os.getuid():return
            raw=await asyncio.wait_for(reader.readline(),2)
            if len(raw)>1024:return
            form=json.loads(raw)
            if form == {'command':'stop'}:
                writer.write(b'{"stopping":true}\n')
                await writer.drain()
                asyncio.create_task(bot.close())
                return
            if form != {'query':'status'}:return
            state='offline' if bot.is_closed() else 'online' if bot.is_ready() else 'connecting'
            writer.write((json.dumps({'discord':state,'observed_at':datetime.now(timezone.utc).isoformat()})+'\n').encode())
            await writer.drain()
        except (OSError,ValueError,TimeoutError):
            pass
        finally:
            writer.close()
            try:await writer.wait_closed()
            except OSError:pass
    return await asyncio.start_unix_server(answer,path=address(chat_socket),limit=1024)


def probe(chat_socket):
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(2);client.connect(address(chat_socket))
            _,uid,_=struct.unpack('3i',client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            if uid!=os.getuid():return None
            client.sendall(b'{"query":"status"}\n')
            with client.makefile('rb') as reader:raw=reader.readline(4097)
            if len(raw)>4096:return None
            data=json.loads(raw)
            if isinstance(data,dict) and data.get('discord') in ('online','offline','connecting') and isinstance(data.get('observed_at'),str):return data
    except (OSError,ValueError):pass
    return None


def request_stop(chat_socket):
    """Operator-only caller; this action is never exposed through query_logs."""
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(3)
            client.connect(address(chat_socket))
            _,uid,_=struct.unpack('3i',client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            if uid != os.getuid(): return False
            client.sendall(b'{"command":"stop"}\n')
            with client.makefile('rb') as reader:
                return json.loads(reader.readline(1025)) == {'stopping':True}
    except (OSError,ValueError):
        return False
