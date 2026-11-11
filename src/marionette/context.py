"""Context fitting and between-turn cache preparation."""
import http.client
import threading
import time

import diagnostics


def fit_history(history, message, count, capacity, reserve):
    """Return a fitted copy; never mutate history on oversized input or failure."""
    candidate = history + [{'role': 'user', 'content': message}]
    removed = 0
    while True:
        tokens = count(candidate)
        # One spare token also keeps the prompt below the server's strict limit.
        if tokens + reserve < capacity:
            return candidate, removed, tokens
        if len(candidate) <= 1:
            raise ValueError('This message is too large. Shorten the message; history is unchanged.')
        del candidate[:2]  # oldest complete user/assistant exchange
        removed += 1


class Preparation:
    """One worker; only the chat thread commits history after joining it."""
    def __init__(self, api, history, capacity, reserve, *, message_id=None):
        self.history = history
        self.message_id = message_id
        self.thread = threading.Thread(target=self.run,
                                       args=(api, capacity, reserve, message_id), daemon=True)
        api.worker = self.thread
        self.thread.start()

    def run(self, api, capacity, reserve, message_id):
        if message_id is None:
            self.work(api, capacity, reserve)
        else:
            with diagnostics.message_scope(message_id, 'cache preparation'):
                self.work(api, capacity, reserve)

    def work(self, api, capacity, reserve):
        started = time.monotonic()
        try:
            incoming = min(2048, capacity // 8)
            probe = [{'role': 'user', 'content': ''}]
            candidate = self.history.copy()
            tokens = api.count(candidate + probe)
            if tokens + incoming + reserve < capacity:
                return
            target = min(capacity * 3 // 4, capacity - incoming - reserve - 1)
            removed = 0
            while candidate and tokens > target:
                del candidate[:2]
                removed += 1
                tokens = api.count(candidate + probe)
            diagnostics.log(f'Rollover preparation started: removed_exchanges={removed}; '
                f'next_prompt_tokens={tokens}; next_message_allowance={incoming}; reply_allowance={reserve}.')
            if candidate:
                api.prepare(candidate)
            # Publish only after successful preparation. An empty history needs no cache.
            self.history = candidate
            diagnostics.log(f'Rollover preparation completed: removed_exchanges={removed}; '
                f'elapsed_ms={(time.monotonic() - started) * 1000:.2f}.')
        except (ValueError, RuntimeError, OSError, http.client.HTTPException) as error:
            if api.closing.is_set():
                diagnostics.log('Rollover preparation stopped with session shutdown.')
            else:
                diagnostics.log(f'Rollover preparation failed; history retained: {error}')

    def result(self):
        if self.thread.is_alive():
            started = time.monotonic()
            self.thread.join()
            prefix = f'[message {self.message_id}] ' if self.message_id else ''
            diagnostics.log(prefix + f'Preparation wait after input: {(time.monotonic() - started) * 1000:.2f} ms.')
        return self.history
