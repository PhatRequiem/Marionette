"""RAM diagnostics in the existing capture process; no extra helper process.

Routine raw events must never reach the disk Store.event path. Live viewers use
this recorder's private socket. EOF/SIGTERM saves the retained buffer atomically.
"""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import socketserver
import struct
import threading

import retention

ID_BLOCK = 65536


def address(path):
    # A short Linux abstract socket avoids filesystem path-length and stale-file issues.
    name = hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest()[:32]
    return '\0marionette-logs-' + str(os.getuid()) + '-' + name


class RamLogs:
    def __init__(self, disk, session, *, part_bytes=None, budget_bytes=None):
        from storage import Store
        self.disk, self.session = disk, session
        self.memory = Store(None)
        self.lock = threading.RLock()
        self.limit = 0
        row = disk.db.execute('SELECT * FROM sessions WHERE id=?', (session,)).fetchone()
        if row is None:
            self.memory.close()
            raise ValueError('Unknown diagnostic session.')
        with self.memory.db:
            self.memory.db.execute('INSERT INTO sessions VALUES (?,?,?)', tuple(row))
            self.memory.db.execute('UPDATE retention_state SET part_bytes=?,budget_bytes=?',
                                   (part_bytes or retention.PART_BYTES, budget_bytes or retention.BUDGET_BYTES))
        self.saved = False
        self.budget = budget_bytes or retention.BUDGET_BYTES

    def append(self, raw, category):
        if self.saved:
            raise ValueError('Cannot append after the shutdown buffer was saved.')
        if len(raw) > self.budget:
            raise ValueError('A diagnostic event exceeds the RAM budget; buffered evidence is preserved on exit.')
        with self.lock:
            next_id = self.memory.db.execute('SELECT next_event FROM retention_state').fetchone()[0]
            if next_id >= self.limit or self.limit == 0:
                # Reserve IDs only, never raw logs. Other persisted streams share the allocator.
                with self.disk.db:
                    self.disk.db.execute('BEGIN IMMEDIATE')
                    start = self.disk.db.execute('SELECT next_event FROM retention_state').fetchone()[0]
                    self.disk.db.execute('UPDATE retention_state SET next_event=next_event+? WHERE id=1', (ID_BLOCK,))
                with self.memory.db:
                    self.memory.db.execute('UPDATE retention_state SET next_event=?', (start,))
                self.limit = start + ID_BLOCK
            return self.memory.event(self.session, 'diagnostic', raw, category)

    def save(self):
        """One disk transaction; preserve original IDs and only surviving RAM rows."""
        if self.saved:
            return
        source, target = self.memory.db, self.disk.db
        with self.lock, target:
            target.execute('BEGIN IMMEDIATE')
            # Save as new disk batches; persisted diagnostics retain their existing budget.
            target.execute('UPDATE diagnostic_batches SET closed=1 WHERE closed=0')
            policy = target.execute('SELECT * FROM retention_state').fetchone()
            for row in source.execute('SELECT * FROM events ORDER BY id'):
                batch = retention.batch_for(target, len(row['raw']), policy)
                target.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?)', tuple(row)[:7] + (batch,))
            # Merge protected failures independently: their source events may have rolled out.
            for failure in source.execute('SELECT * FROM failures ORDER BY last_error'):
                values = list(tuple(failure)[1:])
                if values[-1] == 'collecting':
                    values[-1] = 'incomplete'
                failure_id = target.execute('''INSERT INTO failures(session_id,message_id,request_id,tool_id,component,
                    first_event,last_error,recorded_at,remaining,before_count,state) VALUES (?,?,?,?,?,?,?,?,?,?,?)''', values).lastrowid
                for evidence in source.execute('SELECT e.*,f.relation FROM error_evidence e JOIN failure_events f USING(event_id) WHERE failure_id=?', (failure['id'],)):
                    retention.copy_event(target, tuple(evidence)[:9])
                    target.execute('INSERT INTO failure_events VALUES (?,?,?)', (failure_id,evidence['event_id'],evidence['relation']))
            target.execute('DELETE FROM failures WHERE id NOT IN (SELECT id FROM failures ORDER BY recorded_at DESC,last_error DESC LIMIT ?)', (policy['error_limit'],))
            target.execute('DELETE FROM error_evidence WHERE event_id NOT IN (SELECT event_id FROM failure_events)')
            retention.prune(target, policy)
        self.saved = True

    def close(self):
        self.memory.close()


class LiveView:
    def __init__(self, buffer, path):
        from storage import records, render_event
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                # Abstract sockets lack filesystem permissions: enforce the OS peer UID.
                _, uid, _ = struct.unpack('3i', self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if uid != os.getuid():
                    return
                self.connection.settimeout(2)
                request = json.loads(self.rfile.readline(4097))
                if ((request.get('session') != buffer.session and request.get('view') != 'status')
                        or request.get('view') not in ('server','model','status')
                        or type(request.get('after')) is not int or request['after'] < 0):
                    return
                with buffer.lock:
                    if request['view'] == 'status':
                        state = dict(buffer.memory.db.execute('SELECT * FROM retention_state').fetchone())
                        state.update(session=buffer.session, diagnostic_bytes=buffer.memory.db.execute('SELECT coalesce(sum(bytes),0) FROM diagnostic_batches').fetchone()[0],
                                     failures=buffer.memory.db.execute('SELECT count(*) FROM failures').fetchone()[0])
                        payload, last = json.dumps(state).encode(), request['after']
                    else:
                        rows = records(buffer.memory.db, buffer.session, request['view'], request['after'])
                        payload = b''.join(render_event(row, request['view']) for row in rows)
                        last = rows[-1]['id'] if rows else request['after']
                try:
                    self.wfile.write(json.dumps({'last':last,'size':len(payload)}).encode()+b'\n')
                    self.wfile.write(payload)
                except OSError:
                    pass  # A viewer disconnect never stops recording.
        class Server(socketserver.ThreadingUnixStreamServer):
            daemon_threads = False
        self.server = Server(address(path), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


def read_live(path, session, view, after):
    """None means no matching live recorder; callers then read saved SQLite rows."""
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(3)
            client.connect(address(path))
            _, uid, _ = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid != os.getuid():
                raise PermissionError('RAM log server belongs to a different OS user.')
            client.sendall(json.dumps({'session':session,'view':view,'after':after}).encode()+b'\n')
            with client.makefile('rb') as reader:
                header = reader.readline(4097)
                if not header:
                    return None
                info = json.loads(header)
                if type(info.get('size')) is not int or not 0 <= info['size'] <= 1024*1024*1024:
                    raise ValueError('Invalid RAM log response size.')
                payload = reader.read(info['size'])
                if len(payload) != info['size']:
                    raise OSError('Incomplete RAM log response.')
                return info['last'], payload
    except (ConnectionRefusedError, FileNotFoundError, TimeoutError, ConnectionResetError, BrokenPipeError):
        return None


def capture(path, session):
    from storage import Store
    from log_router import category
    import sys
    # Existing recorder already ignores Ctrl+C. Orderly termination also flushes.
    def terminate(signum, frame):
        raise SystemExit(128 + signum)
    previous = signal.signal(signal.SIGTERM, terminate)
    with closing(Store(path)) as disk, closing(RamLogs(disk, session)) as buffer:
        with closing(LiveView(buffer, path)):
            try:
                for raw in sys.stdin.buffer:
                    buffer.append(raw, category(raw))
            finally:
                buffer.save()
    signal.signal(signal.SIGTERM, previous)
