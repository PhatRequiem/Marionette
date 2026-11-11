"""Private stream boundary for the owner-authorized live memory reset."""
import json
from pathlib import Path
import uuid

PREFIX = b'\x1eMARIONETTE_RESET:'
SUFFIX = b'\x1f'


def marker(generation):
    return PREFIX + str(uuid.UUID(generation)).encode() + SUFFIX


class BoundaryReader:
    """Separate markers from arbitrary terminal chunks without buffering prompts."""
    def __init__(self):
        self.pending = b''

    def feed(self, raw):
        data = self.pending + raw
        self.pending = b''
        while data:
            index = data.find(PREFIX)
            if index < 0:
                keep = next((n for n in range(min(len(data), len(PREFIX)-1), 0, -1)
                             if data.endswith(PREFIX[:n])), 0)
                if keep:
                    self.pending = data[-keep:]
                    data = data[:-keep]
                if data:
                    yield None, data
                return
            if index:
                yield None, data[:index]
            data = data[index:]
            length = len(PREFIX) + 36 + len(SUFFIX)
            if len(data) < length:
                self.pending = data
                return
            try:
                token = data[len(PREFIX):length-1].decode('ascii')
                if data[length-1:length] != SUFFIX or marker(token) != data[:length]:
                    raise ValueError('Invalid marker')
            except (ValueError, UnicodeError):
                yield None, data[:1]
                data = data[1:]
                continue
            yield token, b''
            data = data[length:]


def current_generation(address):
    """Shared private session descriptor; no model-accessible control channel."""
    try:
        return json.loads(Path(address).with_name('log-session.json').read_text()).get('generation', '')
    except FileNotFoundError:
        return ''
