"""JSONL records, lossless raw capture, and structured chat events; no recall."""
import base64
from contextlib import contextmanager
from contextvars import ContextVar
import datetime
import fcntl
import json
import os
from pathlib import Path
import sys
import uuid

_CONTEXT = ContextVar('log_context', default={})


def record(source, event_type, *, data=None, raw=None, sequence=None, session_id=None):
    event = {'version': 1, 'session_id': session_id or os.environ.get('MARIONETTE_SESSION_ID', 'standalone'),
             'event_id': str(uuid.uuid4()),
             'timestamp': datetime.datetime.now().astimezone().isoformat(timespec='microseconds'),
             'source': source, 'event_type': event_type, 'data': data or {}}
    if raw is not None:
        event['raw_b64'] = base64.b64encode(raw).decode('ascii')
    if sequence is not None:
        event['sequence'] = sequence
    return event


def encode(event):
    return (json.dumps(event, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode('utf-8')


def append(path, event):
    """Serialize each complete record across the terminal capture and app writers."""
    payload = encode(event)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, 'ab', buffering=0) as output:
        fcntl.flock(output, fcntl.LOCK_EX)
        remaining = memoryview(payload)
        while remaining:
            written = output.write(remaining)
            if not written:
                raise OSError('Log writer made no progress.')
            remaining = remaining[written:]


@contextmanager
def turn_context(**fields):
    token = _CONTEXT.set(fields)
    try:
        yield
    finally:
        _CONTEXT.reset(token)


def chat_event(event_type, **fields):
    path = os.environ.get('MARIONETTE_CHAT_LOG')
    if path:
        data = _CONTEXT.get() | fields
        append(path, record(data.get('source', 'application'), event_type, data=data))


def capture(source, path, kind, output=None):
    """Terminal chunks remain arbitrary bytes; Discord emits native JSON events."""
    session_id = os.environ.get('MARIONETTE_SESSION_ID') or Path(path).name.rsplit('-', 1)[0]
    sequence = 0
    while True:
        raw = source.read1(65536) if kind == 'terminal' else source.readline()
        if not raw:
            return
        sequence += 1
        event = None
        if kind == 'discord':
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and parsed.get('version') == 1 and parsed.get('source') == 'discord' and 'event_type' in parsed:
                    event = parsed
            except (ValueError, UnicodeError):
                pass
        if event is None:
            event = record(kind, 'terminal_output' if kind == 'terminal' else 'raw_output',
                           raw=raw, sequence=sequence, session_id=session_id)
        append(path, event)
        if output is not None:
            output.write(encode(event))
            output.flush()


def export_raw(path, output):
    """Recover recorded bytes in file order; structured records are skipped."""
    with open(path, encoding='utf-8') as source:
        for line in source:
            event = json.loads(line)
            if 'raw_b64' in event:
                output.write(base64.b64decode(event['raw_b64'], validate=True))


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] not in ('terminal', 'discord', 'export-raw'):
        raise SystemExit('Usage: log_store.py terminal|discord|export-raw LOG_FILE')
    mode, path = sys.argv[1:]
    if mode == 'export-raw':
        export_raw(path, sys.stdout.buffer)
    else:
        capture(sys.stdin.buffer, path, mode, sys.stdout.buffer if mode == 'discord' else None)
