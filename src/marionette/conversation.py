"""Shared history, serial turns, identity checks, and command authorization."""
from concurrent.futures import Future
import json
import queue
import threading
import time

import diagnostics
from context import Preparation, fit_history
from identity import message_with_identity
from commands import execute_clear, recognize


class Conversation:
    """One history and one generation at a time, shared by every input."""
    def __init__(self, api, capacity, profiles=None, terminal_profile=None, characters=None):
        self.profiles, self.terminal_profile = profiles, terminal_profile
        self.characters = characters
        self.api, self.capacity = api, capacity
        self.api.capacity = capacity
        self.reserve = min(32768, capacity // 2)
        self.history = []
        self.pending = None
        self.lock = threading.Lock()
        self.incoming = queue.Queue()

    def submit_discord(self, message, *, sender_id, timings=None):
        # The terminal thread owns rendering, including while awaiting local input.
        future = Future()
        self.incoming.put((message, sender_id, future, time.monotonic(), timings))
        while not self.api.closing.is_set():
            try:
                return future.result(timeout=.1)
            except TimeoutError:
                if future.done():
                    return future.result()  # Also handle completion at the timeout boundary.
        raise RuntimeError('Session is closing.')

    def turn(self, message, *, on_delta=None, source="terminal", sender_id=None):
        with self.lock:
            if self.api.closing.is_set():
                raise RuntimeError('Session is closing.')
            identity = None
            if self.profiles is not None:
                sender_id = sender_id if source != 'terminal' else self.terminal_profile['uuid']
                identity = self.profiles.resolve(source, sender_id)
                diagnostics.log('Sender identity: ' + json.dumps(identity, ensure_ascii=False))
            if recognize(message, source) == 'clear':
                return execute_clear(self, identity), 'stop'
            if self.pending is not None:
                self.history = self.pending.result()
                self.pending = None
            if self.characters is not None:
                if identity is None:
                    raise ValueError('Character profiles require a resolved sender identity.')
                from characters import LIMIT, UpdateCharacter
                content = self.characters.current(identity)
                # Join the previous preparation worker before rebinding the current-person tool.
                self.api.tools = (UpdateCharacter(self.characters, identity, content),)
                identity['character_profile'] = {'content': content, 'characters': len(content),
                                                 'character_limit': LIMIT}
                diagnostics.log(f"Character supplied: person_uuid={identity['person_uuid']}; characters={len(content)}; limit={LIMIT}.")
            candidate, removed, tokens = fit_history(
                self.history, message_with_identity(message, identity) if identity else message,
                self.api.count, self.capacity, self.reserve)
            diagnostics.log(f'Prompt budget: {tokens} tokens + {self.reserve} reply allowance < '
                f'{self.capacity}; removed_exchanges={removed}.')
            if removed:
                diagnostics.log(f'Input-time rollover: removed_exchanges={removed}; preparing this request.')
            # The caller decides how streamed reasoning and answers are displayed.
            answer, finish = self.api.reply(candidate, self.reserve, on_delta=on_delta)
            if not answer.strip():
                raise RuntimeError('Model produced no final answer.')
            diagnostics.log(f'Reply completed: finish_reason={finish}.')
            self.history = candidate + [{'role': 'assistant', 'content': answer}]
            self.pending = Preparation(self.api, self.history, self.capacity, self.reserve)
            return answer, finish
