"""Forward Scarecrow's live metadata into the existing diagnostic recorder."""
import http.client
import json
from pathlib import Path
import re
import socket
import threading

import diagnostics

EVENTS = {'listener_observed', 'listener_started', 'listener_failed', 'plugin_stopping',
          'ready', 'indexing', 'mirror_unavailable', 'request_started', 'request_received', 'request_completed', 'request_failed', 'request_aborted'}


def record(source, event, **fields):
    diagnostics.log('Connection event: ' + json.dumps({'source': source, 'event': event, **fields}, ensure_ascii=True))


def clean_event(data):
    """Accept only diagnostic metadata, never arbitrary plugin text or payloads."""
    if not isinstance(data, dict) or data.get('source') not in ('Scarecrow', 'Obsidian') or data.get('event') not in EVENTS:
        raise ValueError('Invalid diagnostic event')
    result = {key: data[key] for key in ('source', 'event')}
    for key, pattern in [('request_id', r'[a-f0-9-]{36}'), ('time', r'[0-9T:.Z+-]{20,35}')]:
        value = data.get(key)
        if isinstance(value, str) and re.fullmatch(pattern, value):
            result[key] = value
    for key, allowed in [('route', ('query', 'status', 'unknown')),
                         ('action', ('list', 'search', 'read', 'inspect', 'tags', 'links', 'open'))]:
        if isinstance(data.get(key), str) and data[key] in allowed:
            result[key] = data[key]
    status = data.get('http_status')
    if type(status) is int and 100 <= status <= 599:
        result['http_status'] = status
    duration = data.get('duration_ms')
    if type(duration) in (float, int) and 0 <= duration < 1e12:
        result['duration_ms'] = duration
    return result


class VaultDiagnostics:
    """One reader thread inside main chat; no helper process or replay storage."""
    def __init__(self, data, *, retry=2, on_setup_change=None):
        self.path = Path(data) / 'scarecrow/connection.json'
        self.retry = retry
        self.on_setup_change = on_setup_change
        self.stop = threading.Event()
        self.connection = None
        self.thread = None

    def __enter__(self):
        try:
            enabled = json.loads(self.path.read_text()).get('enabled') is True
        except (OSError, ValueError, AttributeError):
            enabled = False
        if enabled:
            self.thread = threading.Thread(target=self.run, name='scarecrow-diagnostics', daemon=True)
            self.thread.start()
        return self

    def run(self):
        state = None
        while not self.stop.is_set():
            connection = None
            try:
                config = json.loads(self.path.read_text())
                port = config['port']
                if config.get('enabled') is not True:
                    break
                if type(port) is not int or not 1024 <= port <= 65535:
                    raise ValueError('Invalid port')
                connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
                self.connection = connection
                connection.request('GET', '/v1/events', headers={'Authorization': 'Bearer ' + config['token']})
                response = connection.getresponse()
                if response.status != 200 or response.getheader('X-Vault-ID') != config['vault_id']:
                    raise ValueError('Diagnostic stream unavailable')
                if connection.sock:
                    connection.sock.settimeout(20)
                record('Obsidian', 'connected' if state is None else 'reconnected')
                state = 'connected'
                while not self.stop.is_set():
                    raw = response.readline(8193)
                    if not raw or len(raw) > 8192:
                        raise ValueError('Diagnostic stream ended')
                    if raw.strip():
                        event = clean_event(json.loads(raw))
                        record(**event)
                        if self.on_setup_change and event['event'] in ('listener_observed', 'ready', 'mirror_unavailable'):
                            self.on_setup_change()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, http.client.HTTPException):
                if not self.stop.is_set() and state != 'unavailable':
                    record('Obsidian', 'unavailable')
                    state = 'unavailable'
            finally:
                if connection:
                    connection.close()
                self.connection = None
            self.stop.wait(self.retry)
        record('Obsidian', 'monitor_stopped')

    def __exit__(self, *_):
        self.stop.set()
        connection = self.connection
        if connection and connection.sock:
            try:
                connection.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if self.thread:
            self.thread.join(timeout=5)


def current_status(data):
    """A fresh authenticated probe; never infer readiness from tool registration."""
    from datetime import datetime, timezone
    result = {'status': 'unknown', 'observed_at': None}
    connection = None
    try:
        path = Path(data) / 'scarecrow/connection.json'
        if not path.exists():
            result['status'] = 'not_configured'
            return result
        config = json.loads(path.read_text())
        if config.get('enabled') is not True:
            result['status'] = 'disabled'
            return result
        port = config['port']
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError('Invalid port')
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=1)
        connection.request('GET', '/v1/status', headers={'Authorization': 'Bearer ' + config['token']})
        response = connection.getresponse()
        raw = response.read(4097)
        if len(raw) > 4096:
            raise ValueError('Invalid status response')
        fields = json.loads(raw)
        if response.status == 200 and fields.get('vault_id') == config['vault_id'] and fields.get('status') == 'ok':
            result['status'] = 'ready'
            loaded = fields.get('version')
            if isinstance(loaded, str) and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?', loaded):
                result['version'] = loaded
        else:
            result['status'] = 'unavailable'
    except (OSError, ValueError, TypeError, KeyError, AttributeError, http.client.HTTPException):
        result['status'] = 'unavailable'
    finally:
        if connection:
            connection.close()
        result['observed_at'] = datetime.now(timezone.utc).isoformat()
    return result
