"""Private local socket connecting optional inputs to the running conversation."""
import asyncio
import http.client
import json
from pathlib import Path
import socketserver
import threading

import diagnostics

MAX_REQUEST = 1024 * 1024


class LocalConnection:
    def __init__(self, address, turn, log):
        self.path = Path(address)
        self.path.unlink(missing_ok=True)  # Main launcher's lock excludes another owner.

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                message_id = None
                self.connection.settimeout(10)
                try:
                    raw = self.rfile.readline(MAX_REQUEST + 1)
                    if len(raw) > MAX_REQUEST or not raw.endswith(b'\n'):
                        raise ValueError('Invalid local request size.')
                    request = json.loads(raw)
                    message = request['message']
                    if not isinstance(message, str) or not message.strip():
                        raise ValueError('A text message is required.')
                    sender_id = request['sender_id']
                    if (not isinstance(sender_id, str) or not sender_id.isascii()
                            or not sender_id.isdecimal() or not 0 < int(sender_id) < 2**64):
                        raise ValueError('A numeric Discord sender ID is required.')
                    message_id = diagnostics.message_id(request.get('message_id'))
                    log(f'[message {message_id}] Discord input [{sender_id}]: ' + json.dumps(message, ensure_ascii=False))
                    timings = {}
                    answer, finish = turn(message, sender_id=sender_id, timings=timings, message_id=message_id)
                    log(f'[message {message_id}] Discord answer: ' + json.dumps(answer, ensure_ascii=False))
                    result = {'answer': answer, 'finish': finish, 'timings': timings}
                except (ValueError, KeyError, TypeError, OSError, RuntimeError, http.client.HTTPException) as error:
                    log(f'[message {message_id or "unassigned"}] Discord local request failed: {error}')
                    result = {'error': 'Local chat could not finish this turn; check model logs.'}
                try:
                    self.wfile.write((json.dumps(result) + '\n').encode())
                except OSError:
                    log(f'[message {message_id or "unassigned"}] Discord disconnected before receiving the result; completed history is retained.')

        class Server(socketserver.ThreadingUnixStreamServer):
            daemon_threads = True

        self.server = Server(str(self.path), Handler)
        self.path.chmod(0o600)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.path.unlink(missing_ok=True)


async def request(address, message, sender_id, *, message_id=None):
    """No generation timeout: a 32K thinking response can legitimately take minutes."""
    reader, writer = await asyncio.open_unix_connection(str(address), limit=4 * MAX_REQUEST)
    try:
        payload = (json.dumps({'message': message, 'sender_id': str(sender_id), 'message_id': message_id}) + '\n').encode()
        if len(payload) > MAX_REQUEST:
            raise ValueError('Message is too large for the local connection.')
        writer.write(payload)
        await writer.drain()
        raw = await reader.readline()
        if not raw:
            raise RuntimeError('Main chat disconnected.')
        result = json.loads(raw)
        if 'error' in result:
            raise RuntimeError(result['error'])
        return result
    finally:
        writer.close()
        await writer.wait_closed()
