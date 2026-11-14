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
from commands import HELP_TEXT, execute_clear, recognize


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
        self.shutdown_requested = False
        self.discord_control = None
        self.setup_refresh = None
        self.discord_access = None
        self.started_at = time.monotonic()
        self.generating = False
        self.generation_lock = threading.Lock()

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
                         datasheet=Path(os.environ.get('MARIONETTE_SETUP_DATASHEET_PATH', root / 'docs/active/setup-and-maintenance/setup-datasheet.md')),
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
        if recognize(message, 'discord') == 'cancel':
            return self.cancel(source='discord', sender_id=str(sender_id)), 'stop'
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

    def cancel(self, source='terminal', sender_id=None):
        from permissions import require_reset
        try:
            sender = str(sender_id) if source == 'discord' else self.terminal_profile['uuid']
            require_reset(self.profiles.resolve(source, sender), self.profiles)
        except (PermissionError, ValueError, TypeError, AttributeError, KeyError):
            return 'Access Denied'
        with self.generation_lock:
            if not self.generating:
                return 'No generation is running.'
            self.api.cancel_reply()
        return 'Cancellation requested. Completed tool actions are not undone.'

    def turn(self, message, *, on_delta=None, source="terminal", sender_id=None, message_id=None, display_name=None):
        identifier = diagnostics.message_id(message_id)
        with self.lock:
            self.finish_preparation()
            with diagnostics.message_scope(identifier, 'processing'):
                result = self._turn(message, on_delta=on_delta, source=source, sender_id=sender_id, identifier=identifier, display_name=display_name)
            if result[1] not in ('blocked', 'cancelled') and recognize(message, source) not in ('clear', 'resetmemory', 'shutdown', 'startdiscord', 'stopdiscord', 'refreshsetup', 'help', 'ddm', 'status', 'connections', 'context', 'sync', 'cancel'):
                self.pending_key = self.key
                self.pending = Preparation(self.api, self.history, self.capacity, self.reserve,
                                           message_id=identifier)
            if self.setup_refresh is not None:
                self.setup_refresh(reason='command' if result[0] != 'Access Denied' and recognize(message, source) in ('startdiscord', 'stopdiscord', 'resetmemory', 'ddm') else None)
            return result

    def _turn(self, message, *, on_delta, source, sender_id, identifier, display_name=None):
        if self.shutdown_requested:
            raise RuntimeError('Session is shutting down.')
        if self.resetting:
            raise RuntimeError('Memory reset incomplete; restart the application before continuing.')
        if self.api.closing.is_set():
            raise RuntimeError('Session is closing.')
        if source == 'discord' and self.discord_access is not None and not self.discord_access.admits(sender_id):
            from permissions import require_reset
            try:
                require_reset(self.profiles.resolve(source, str(sender_id)) if self.profiles else None, self.profiles)
            except (ValueError, PermissionError):
                return 'Discord DMs are currently limited to the owner.', 'blocked'
        if recognize(message, source) == 'help':
            return HELP_TEXT, 'stop'
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
        if recognize(message, source) in ('status', 'connections', 'context', 'sync', 'cancel'):
            from commands import execute_operator
            return execute_operator(self, recognize(message, source), identity), 'stop'
        if recognize(message, source) == 'ddm':
            from permissions import require_reset
            try:
                require_reset(identity, self.profiles)
            except PermissionError as error:
                return str(error), 'stop'
            parts = message.strip().split()
            if self.discord_access is None:
                return 'Discord access controls are unavailable in this session.', 'stop'
            usage = 'Usage: /ddm [on|off] or /ddm allow|block <Discord user ID or mention>'
            if len(parts) == 3 and parts[1] in ('allow', 'block'):
                import re
                match = re.fullmatch(r'([0-9]+)|<@!?([0-9]+)>', parts[2])
                if not match or not 0 < int(match[1] or match[2]) < 2**64:
                    return usage, 'stop'
                sender = str(int(match[1] or match[2]))
                try:
                    target = self.profiles.resolve('discord', sender)
                except ValueError:
                    target = None
                if target and target['contact_uuid'] == self.profiles.data['owner_uuid']:
                    return 'Owner access always stays open.', 'stop'
                self.discord_access.set_rule(sender, parts[1] == 'allow')
                return 'Discord user ' + sender + (' allowed.' if parts[1] == 'allow' else ' blocked.'), 'stop'
            if len(parts) > 2 or (len(parts) == 2 and parts[1] not in ('on', 'off')):
                return usage, 'stop'
            if len(parts) == 2:
                self.discord_access.set_enabled(parts[1] == 'on')
            policy = self.discord_access.policy()
            state = ('ON' if policy['allow_other_dms'] else 'OFF') + ' — general access; allowed exceptions: ' + str(len(policy.get('allowed', []))) + '; blocked: ' + str(len(policy.get('blocked', []))) + '.'
            return 'Discord DMs: ' + state + ' Your access stays open.', 'stop'
        if recognize(message, source) in ('startdiscord', 'stopdiscord', 'refreshsetup'):
            from permissions import require_reset
            try:
                require_reset(identity, self.profiles)
            except PermissionError as error:
                return str(error), 'stop'
            if recognize(message, source) == 'refreshsetup':
                return ('Setup datasheet: ' + self.setup_refresh(force=True) if self.setup_refresh else 'Setup refresh unavailable.'), 'stop'
            if self.discord_control is None:
                return 'Discord controls are unavailable in this session.', 'stop'
            action = self.discord_control.start if recognize(message, source) == 'startdiscord' else self.discord_control.stop
            return action(), 'stop'
        if recognize(message, source) == 'shutdown':
            from permissions import require_reset
            try:
                require_reset(identity, self.profiles)  # Same saved-owner authorization, no reset.
            except PermissionError as error:
                return str(error), 'stop'
            save('user', 'input', message, 'received')
            answer = 'Shutting down Marionette. Saved memory will be kept.'
            save('assistant', 'notice', answer, 'shutdown')
            self.shutdown_requested = True
            diagnostics.log('Owner requested orderly shutdown.')
            return answer, 'shutdown'
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
            self.api.tools = tuple(t for t in getattr(self.api, "tools", ()) if t.name != "update_contact_notes") + (UpdateContactNotes(self.contact_notes, identity, content),)
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
            with self.generation_lock:
                if hasattr(self.api, 'cancelled'):
                    self.api.cancelled.clear()
                self.generating = True
            answer, finish = self.api.reply(candidate, self.reserve, on_delta=record_delta if self.store is not None else on_delta)
            with self.generation_lock:
                if getattr(self.api, 'cancelled', None) is not None and self.api.cancelled.is_set() is True:
                    raise RuntimeError('Generation cancelled.')
                self.generating = False
        except (RuntimeError, OSError) as error:
            if getattr(self.api, 'cancelled', None) is not None and self.api.cancelled.is_set() is True:
                finish = 'cancelled'
                return 'Generation cancelled. Active history is unchanged; completed tool actions remain.', finish
            raise
        finally:
            with self.generation_lock:
                self.generating = False
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
