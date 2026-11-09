"""Serialize client and raw runtime diagnostics into the existing log stream."""
import sys
import threading

_LOCK = threading.Lock()


def write(raw):
    with _LOCK:
        sys.stderr.buffer.write(raw)
        sys.stderr.buffer.flush()


def log(message):
    write(('Client: ' + message + '\n').encode())
