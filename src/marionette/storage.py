"""Local conversation/event storage and operator export, backup, and live views.

No retrieval tool or history restoration is enabled here. Raw output is a BLOB;
formatting belongs to the viewers, not the stored evidence.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import sys
import time
import uuid

import retention

SCHEMA = '''
CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT);
CREATE TABLE events (
 id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
 recorded_at TEXT NOT NULL, stream TEXT NOT NULL, category TEXT NOT NULL,
 message_id TEXT, raw BLOB NOT NULL);
CREATE INDEX events_session ON events(session_id, id);
CREATE INDEX events_message ON events(session_id, message_id, id);
CREATE TABLE messages (
 id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
 message_id TEXT NOT NULL, conversation_id TEXT NOT NULL, person_uuid TEXT,
 source TEXT NOT NULL, sender_id TEXT, recorded_at TEXT NOT NULL,
 role TEXT NOT NULL, kind TEXT NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL);
CREATE INDEX messages_conversation ON messages(session_id, conversation_id, id);
CREATE INDEX messages_person ON messages(person_uuid, recorded_at);
PRAGMA user_version=1;
'''


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def open_read(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    if connection.execute('PRAGMA user_version').fetchone()[0] not in (1, 2):
        connection.close()
        raise ValueError('Unsupported log database version.')
    return connection


class Store:
    def __init__(self, path):
        if path is None:
            # SQLite is used as a RAM data structure; no database/WAL files exist.
            self.db = sqlite3.connect(':memory:', check_same_thread=False)
            self.db.execute('PRAGMA temp_store=MEMORY')
        else:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            os.close(fd)
            self.db = sqlite3.connect(path, timeout=10)
        self.db.row_factory = sqlite3.Row
        version = self.db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0, 1, 2):
            self.db.close()
            raise ValueError('Unsupported log database version; original left unchanged.')
        if version == 0:
            if self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                self.db.close()
                raise ValueError('Unrecognized database; original left unchanged.')
            self.db.executescript(SCHEMA)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA foreign_keys=ON')
        try:
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                if self.db.execute('PRAGMA user_version').fetchone()[0] == 1:
                    retention.migrate(self.db)
        except BaseException:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def start(self):
        session = str(uuid.uuid4())
        with self.db:
            self.db.execute('INSERT INTO sessions VALUES (?, ?, NULL)', (session, now()))
        return session

    def end(self, session):
        with self.db:
            self.db.execute('UPDATE sessions SET ended_at=? WHERE id=?', (now(), session))
            self.db.execute("UPDATE failures SET state='incomplete' WHERE session_id=? AND state='collecting'", (session,))

    def event(self, session, stream, raw, category='both'):
        # Only explicit client/Discord IDs are attributed, never neighboring runtime lines.
        match = re.search(rb'Client: \[message ([^\]\r\n]+)\]|"log_message_id":\s*"([^"]+)"', raw)
        identifier = next((x.decode() for x in match.groups() if x), None) if match else None
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            policy = self.db.execute('SELECT * FROM retention_state WHERE id=1').fetchone()
            event_id, stamp = policy['next_event'], now()
            self.db.execute('UPDATE retention_state SET next_event=next_event+1 WHERE id=1')
            batch = retention.batch_for(self.db, len(raw), policy) if stream == 'diagnostic' else None
            self.db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?)',
                            (event_id, session, stamp, stream, category, identifier, raw, batch))
            retention.retain(self.db, (event_id,session,stamp,stream,category,identifier,raw), policy)
            if stream == 'diagnostic':
                retention.prune(self.db, policy)
        return event_id

    def message(self, session, identifier, conversation, identity, source, sender, role, kind, content, status):
        with self.db:
            self.db.execute('''INSERT INTO messages(session_id,message_id,conversation_id,person_uuid,
                source,sender_id,recorded_at,role,kind,content,status) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (session, identifier, conversation, (identity or {}).get('person_uuid'), source,
                 sender, now(), role, kind, content, status))


def render_event(row, view):
    if view in ('server', 'model'):
        from log_router import format_event
        return format_event(row['id'], row['recorded_at'], row['raw'])
    return row['raw']


def records(db, session, view, after=0):
    stream = 'diagnostic' if view in ('server', 'model') else view
    query = 'SELECT * FROM events WHERE session_id=? AND stream=? AND id>?'
    args = [session, stream, after]
    if stream == 'diagnostic':
        query += ' AND category IN (?,?)'
        args += [view, 'both']
    return db.execute(query + ' ORDER BY id LIMIT 256', args).fetchall()


def view_log(path, session, view, output, follow=False, owner_pid=None):
    with closing(open_read(path)) as db:
        if not db.execute('SELECT 1 FROM sessions WHERE id=?', (session,)).fetchone():
            raise ValueError('Unknown session ID.')
        last = 0
        draining = not follow
        while True:
            live = None
            if view in ('server', 'model'):
                from ram_logs import read_live
                live = read_live(path, session, view, last)
            if live is not None:
                last, payload = live
                output.write(payload)
                output.flush()
                if not follow:
                    if payload:
                        continue
                    return
                if payload:
                    continue
                time.sleep(.1)
                continue
            rows = records(db, session, view, last)
            for row in rows:
                output.write(render_event(row, view))
                last = row['id']
            output.flush()
            if rows:
                continue
            if draining:
                return
            ended = db.execute('SELECT ended_at FROM sessions WHERE id=?', (session,)).fetchone()[0]
            if owner_pid is not None:
                try:
                    os.kill(owner_pid, 0)
                except ProcessLookupError:
                    ended = True
            if ended:
                # Re-read until empty: events may have committed after the first read.
                draining = True
                continue
            time.sleep(.1)


def capture(path, session, stream):
    # The producer owns Ctrl+C shutdown. Drain its pipe through EOF, including
    # final disconnect/exit records, instead of interrupting the recorder too.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    if stream == 'diagnostic':
        from ram_logs import capture as capture_ram
        return capture_ram(path, session)
    with closing(Store(path)) as store:
        if stream == 'terminal':
            while raw := os.read(sys.stdin.fileno(), 65536):
                store.event(session, stream, raw)
                sys.stdout.buffer.write(raw)
                sys.stdout.buffer.flush()
        else:
            for raw in sys.stdin.buffer:
                store.event(session, stream, raw)
                if stream == 'discord':
                    sys.stdout.buffer.write(raw)
                    sys.stdout.buffer.flush()


def backup(path, destination):
    # SQLite backup includes committed WAL data; copying only the live .db would not.
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        with closing(open_read(path)) as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup integrity check failed.')
    except BaseException:
        Path(destination).unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    sub.add_parser('start')
    sub.add_parser('sessions')
    sub.add_parser('retention', help='Diagnostic payload budget, batches, and protected evidence sizes')
    sub.add_parser('errors', help='List the latest retained failures')
    error = sub.add_parser('error', help='Read retained evidence for a failure')
    error.add_argument('failure_id', type=int)
    end = sub.add_parser('end'); end.add_argument('session')
    capture_parser = sub.add_parser('capture')
    capture_parser.add_argument('session'); capture_parser.add_argument('stream', choices=['diagnostic', 'terminal', 'discord'])
    view = sub.add_parser('view'); view.add_argument('session')
    view.add_argument('view', choices=['server', 'model', 'discord', 'terminal'])
    view.add_argument('--follow', action='store_true')
    view.add_argument('--owner-pid', type=int)
    sub.add_parser('export', help='Portable SQLite SQL dump with exact BLOB bytes and schema')
    copy = sub.add_parser('backup'); copy.add_argument('destination')
    args = parser.parse_args()
    if args.command in ('init', 'start', 'end'):
        with closing(Store(args.database)) as store:
            if args.command == 'start':
                print(store.start())
            elif args.command == 'end':
                store.end(args.session)
    elif args.command == 'capture':
        capture(args.database, args.session, args.stream)
    elif args.command == 'view':
        view_log(args.database, args.session, args.view, sys.stdout.buffer, args.follow, args.owner_pid)
    elif args.command == 'backup':
        backup(args.database, args.destination)
    else:
        with closing(open_read(args.database)) as db:
            if args.command in ('retention', 'errors', 'error'):
                db.execute('BEGIN')
            if args.command == 'retention':
                policy = dict(db.execute('SELECT * FROM retention_state').fetchone())
                policy['diagnostic_bytes'] = db.execute('SELECT coalesce(sum(bytes),0) FROM diagnostic_batches').fetchone()[0]
                policy['retained_evidence_bytes'] = db.execute('SELECT coalesce(sum(length(raw)),0) FROM error_evidence').fetchone()[0]
                policy['recent_context_bytes'] = db.execute('SELECT coalesce(sum(length(raw)),0) FROM recent_diagnostics').fetchone()[0]
                from ram_logs import read_live
                live = read_live(args.database, None, 'status', 0)
                policy['live_ram'] = json.loads(live[1]) if live else None
                print(json.dumps(policy))
            elif args.command == 'errors':
                for row in db.execute('SELECT * FROM failures ORDER BY recorded_at DESC,last_error DESC'):
                    print(json.dumps(dict(row)))
            elif args.command == 'error':
                failure = db.execute('SELECT * FROM failures WHERE id=?', (args.failure_id,)).fetchone()
                if failure is None:
                    raise ValueError('Unknown retained failure ID.')
                print(json.dumps(dict(failure)), flush=True)
                from log_router import format_event
                for row in db.execute('SELECT e.*,f.relation FROM error_evidence e JOIN failure_events f USING(event_id) WHERE failure_id=? ORDER BY event_id', (args.failure_id,)):
                    print(f"Evidence {row['event_id']} | {row['relation']} | truncated={bool(row['truncated'])} | original_bytes={row['original_bytes']}", flush=True)
                    sys.stdout.buffer.write(format_event(row['event_id'], row['recorded_at'], row['raw']))
                    sys.stdout.buffer.flush()
            elif args.command == 'sessions':
                for row in db.execute('SELECT * FROM sessions ORDER BY started_at'):
                    print(json.dumps(dict(row)))
            else:
                # A read transaction gives the dump a consistent multi-table snapshot.
                db.execute('BEGIN')
                for statement in db.iterdump():
                    print(statement)
                print(f"PRAGMA user_version={db.execute('PRAGMA user_version').fetchone()[0]};")


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, sqlite3.Error) as error:
        raise SystemExit(f'Log storage failed: {error}')
