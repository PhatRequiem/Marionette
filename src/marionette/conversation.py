"""Separate conversation histories with one serialized model and preparation worker."""
from concurrent.futures import Future
import json
import queue
import threading
import time

import diagnostics
from context import Preparation, fit_history
from contacts import message_with_identity
from conversation_refs import conversation_reference
from commands import execute_clear, recognize


class Conversation:
    """One history per terminal profile or Discord sender; one generation at a time."""
    def __init__(self, api, capacity, profiles=None, terminal_profile=None, contact_notes=None, store=None, session_id=None, soul=None):
        self.profiles, self.terminal_profile = profiles, terminal_profile
        self.contact_notes = contact_notes
        self.soul = soul
        self.store, self.session_id = store, session_id
        self.api, self.capacity = api, capacity
        self.api.capacity = capacity
        self.reserve = min(32768, capacity // 2)
        self.key = 'terminal:' + (terminal_profile['uuid'] if terminal_profile else 'local')
        self.histories = {}
        self.pending = None
        self.pending_key = None
        self.lock = threading.Lock()
        self.incoming = queue.Queue()
        self.epoch = store.generation if store else ''
        self.resetting = False

    def bind_log_query(self, identifier=None):
        if self.store is None or not self.session_id:
            return
        from pathlib import Path
        import os
        from log_tool import QueryLogs
        database = self.store.db.execute('PRAGMA database_list').fetchone()[2]
        if not database:
            return  # RAM-only test stores have no read-only database path.
        root = Path(__file__).resolve().parents[2]
        tool = QueryLogs(database=database, session=self.session_id,
                         conversation=self.key, before_message_id=identifier,
                         datasheet=Path(os.environ.get('MARIONETTE_SETUP_DATASHEET_PATH', root / 'docs/setup-datasheet.md')),
                         socket_path=os.environ.get('MARIONETTE_SESSION_SOCKET'))
        self.api.tools = tuple(t for t in getattr(self.api, 'tools', ()) if t.name != tool.name) + (tool,)

    @property
    def history(self):
        return self.histories.setdefault(self.key, [])

    @history.setter
    def history(self, value):
        self.histories[self.key] = value

    def finish_preparation(self):
        # Commit to the conversation that started the worker, before switching
        # the model/tool binding. Only one worker ever owns the shared API.
        if self.pending is not None:
            self.histories[self.pending_key] = self.pending.result()
            self.pending = None
            self.pending_key = None

    def submit_discord(self, message, *, sender_id, timings=None, message_id=None, generation=None, display_name=None):
        # The terminal thread owns rendering, including while awaiting local input.
        epoch = self.epoch if generation is None else generation
        if self.resetting or epoch != self.epoch:
            return 'Message discarded because memory was reset. Please send it again.', 'stop'
        future = Future()
        future.memory_epoch = epoch
        future.discord_display_name = display_name
        self.incoming.put((message, sender_id, future, time.monotonic(), timings, message_id))
        while not self.api.closing.is_set():
            try:
                return future.result(timeout=.1)
            except TimeoutError:
                if future.done():
                    return future.result()  # Also handle completion at the timeout boundary.
        raise RuntimeError('Session is closing.')

    def turn(self, message, *, on_delta=None, source="terminal", sender_id=None, message_id=None, display_name=None):
        identifier = diagnostics.message_id(message_id)
        with self.lock:
            self.finish_preparation()
            with diagnostics.message_scope(identifier, 'processing'):
                result = self._turn(message, on_delta=on_delta, source=source, sender_id=sender_id, identifier=identifier, display_name=display_name)
            if recognize(message, source) not in ('clear', 'resetmemory'):
                self.pending_key = self.key
                self.pending = Preparation(self.api, self.history, self.capacity, self.reserve,
                                           message_id=identifier)
            return result

    def _turn(self, message, *, on_delta, source, sender_id, identifier, display_name=None):
        if self.resetting:
            raise RuntimeError('Memory reset incomplete; restart the application before continuing.')
        if self.api.closing.is_set():
            raise RuntimeError('Session is closing.')
        identity = None
        if self.profiles is not None:
            sender_id = sender_id if source != 'terminal' else self.terminal_profile['uuid']
            if source == 'discord':
                sender_id = self.profiles.register_discord(sender_id, display_name)
            identity = self.profiles.resolve(source, sender_id)
            diagnostics.log('Sender identity: ' + json.dumps(identity, ensure_ascii=False))
        if source not in ('terminal', 'discord'):
            raise ValueError('Unknown message source.')
        self.key = source + ':' + (str(sender_id) if sender_id is not None else 'local')
        diagnostics.log(f'Conversation selected: {self.key}.')
        diagnostics.log('Message input: ' + json.dumps(message, ensure_ascii=False))
        if identity is not None:
            identity['conversation_id'] = self.key
            if self.store is not None and self.session_id:
                identity['conversation_reference'] = conversation_reference(self.session_id, self.key, identity['contact_uuid'])
        def save(role, kind, content, status):
            if self.store is not None:
                self.store.message(self.session_id, identifier, self.key, identity, source,
                                   sender_id, role, kind, content, status)
        if recognize(message, source) == 'resetmemory':
            from permissions import require_reset
            from memory_reset import reset_memory
            try:
                require_reset(identity, self.profiles)
            except PermissionError as error:
                return str(error), 'stop'
            return reset_memory(self), 'resetmemory'
        save('user', 'input', message, 'received')
        if recognize(message, source) == 'clear':
            answer = execute_clear(self, identity)
            save('assistant', 'notice', answer, 'stop')
            return answer, 'stop'
        if self.contact_notes is not None:
            if identity is None:
                raise ValueError('Contact notes require a resolved sender identity.')
            from contact_notes import LIMIT, UpdateContactNotes
            content = self.contact_notes.current(identity)
            # turn() joins the previous worker before rebinding the current-contact tool.
            self.api.tools = (UpdateContactNotes(self.contact_notes, identity, content),)
            identity['contact_notes'] = {'content': content, 'characters': len(content),
                                             'character_limit': LIMIT}
            diagnostics.log(f"Contact notes supplied: contact_uuid={identity['contact_uuid']}; characters={len(content)}; limit={LIMIT}.")
        if self.soul is not None:
            tool = self.soul.bind(self.api)
            self.api.tools = tuple(t for t in self.api.tools if t.name != tool.name) + (tool,)
        self.bind_log_query(identifier)
        candidate, removed, tokens = fit_history(
            self.history, message_with_identity(message, identity) if identity else message,
            self.api.count, self.capacity, self.reserve)
        diagnostics.log(f'Prompt budget: {tokens} tokens + {self.reserve} reply allowance < '
            f'{self.capacity}; removed_exchanges={removed}.')
        if removed:
            diagnostics.log(f'Input-time rollover: removed_exchanges={removed}; preparing this request.')
        # The caller decides how streamed reasoning and answers are displayed.
        reasoning = []
        def record_delta(kind, text):
            if kind == 'reasoning':
                reasoning.append(text)
            if on_delta is not None:
                on_delta(kind, text)
        finish = 'interrupted'
        self.api.response_messages = None
        try:
            answer, finish = self.api.reply(candidate, self.reserve, on_delta=record_delta if self.store is not None else on_delta)
        finally:
            if reasoning:
                save('assistant', 'reasoning', ''.join(reasoning), finish)
        if not answer.strip():
            raise RuntimeError('Model produced no final answer.')
        diagnostics.log(f'Reply completed: finish_reason={finish}.')
        save('assistant', 'answer', answer, finish)
        exchange = self.api.response_messages
        self.api.response_messages = None
        self.history = candidate + (exchange if exchange is not None else [{'role': 'assistant', 'content': answer}])
        return answer, finish
