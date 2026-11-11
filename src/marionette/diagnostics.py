"""Serialize client and raw runtime diagnostics into the existing log stream."""
from contextlib import contextmanager
from contextvars import ContextVar
import re
import sys
import threading
import uuid

_LOCK = threading.Lock()
_MESSAGE = ContextVar('log_message_id', default=None)
_REQUEST = ContextVar('log_request_id', default=None)
_TOOL = ContextVar('log_tool_id', default=None)


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


@contextmanager
def operation_scope(kind, number, *, request=None):
    """Small per-message ordinals; the message ID supplies global uniqueness."""
    request_token = _REQUEST.set(number if kind == 'MODEL REQUEST' else request)
    tool_token = _TOOL.set(number if kind == 'TOOL CALL' else None)
    outcome = 'completed' if kind == 'MODEL REQUEST' else 'returned'
    try:
        log(f'---------- {kind} START ----------')
        yield
    except BaseException as error:
        outcome = 'interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit, GeneratorExit)) else 'failed'
        log(f'{kind.title()} {outcome}: {type(error).__name__}: {error}')
        raise
    finally:
        try:
            log(f'---------- {kind} END | {outcome} ----------')
        finally:
            _TOOL.reset(tool_token)
            _REQUEST.reset(request_token)


def write(raw):
    with _LOCK:
        sys.stderr.buffer.write(raw)
        sys.stderr.buffer.flush()


def log(message):
    identifier = _MESSAGE.get()
    prefix = f'Client: [message {identifier}] ' if identifier else 'Client: '
    if _REQUEST.get() is not None:
        prefix += f'[request {_REQUEST.get():02d}] '
    if _TOOL.get() is not None:
        prefix += f'[tool {_TOOL.get():02d}] '
    write((prefix + message + '\n').encode())
