"""Serialize client and raw runtime diagnostics into the existing log stream."""
from contextlib import contextmanager
from contextvars import ContextVar
import re
import sys
import threading
import uuid

_LOCK = threading.Lock()
_MESSAGE = ContextVar('log_message_id', default=None)


def message_id(value=None):
    """Opaque log correlation only; never model metadata or a saved snapshot."""
    if value is None:
        return 'local:' + str(uuid.uuid4())
    pattern = (r'local:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
               r'|discord:[0-9]{1,20}')
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError('Invalid log message ID.')
    return value


@contextmanager
def message_scope(identifier, phase):
    token = _MESSAGE.set(identifier)
    outcome = 'finished' if phase == 'cache preparation' else 'completed'
    log(f'========== MESSAGE START | {phase} ==========')
    try:
        yield
    except BaseException as error:
        outcome = 'interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'failed'
        log(f'Message {outcome}: {type(error).__name__}: {error}')
        raise
    finally:
        try:
            log(f'========== MESSAGE END | {phase} | {outcome} ==========')
        finally:
            _MESSAGE.reset(token)


def write(raw):
    with _LOCK:
        sys.stderr.buffer.write(raw)
        sys.stderr.buffer.flush()


def log(message):
    identifier = _MESSAGE.get()
    prefix = f'Client: [message {identifier}] ' if identifier else 'Client: '
    write((prefix + message + '\n').encode())
