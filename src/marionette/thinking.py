"""Idle scheduling and bounded internal turns, driven by the existing input loop."""
import json
import http.client
import time

IDLE_SECONDS = 30
STEP_SECONDS = 30
REPLY_TOKENS = 2048
MODEL_CALLS = 4
TOOL_CALLS = 8


class CycleInterrupted(RuntimeError):
    pass


class ThinkingCycle:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.enabled = True
        self.waiting = False
        self.due = clock() + IDLE_SECONDS
        self.source, self.sender_id, self.message_id = 'terminal', None, None

    def wake(self, source, sender_id, message_id):
        self.source, self.sender_id, self.message_id = source, sender_id, message_id
        self.waiting = False
        self.due = self.clock() + IDLE_SECONDS

    def ready(self):
        return self.enabled and not self.waiting and self.clock() >= self.due

    def complete(self, answer):
        try:
            result = json.loads(answer)
            if (set(result) != {'action', 'summary'} or result['action'] not in ('continue', 'wait')
                    or not isinstance(result['summary'], str) or len(result['summary']) > 1000):
                raise ValueError('Invalid cycle result.')
        except (ValueError, TypeError):
            self.waiting = True
            return 'Cycle paused: expected action and a short summary.'
        self.waiting = result['action'] == 'wait'
        self.due = self.clock() + IDLE_SECONDS
        return result['summary']

    def command(self, value):
        if value == 'on':
            self.enabled, self.waiting = True, False
            self.due = self.clock() + IDLE_SECONDS
        elif value == 'off':
            self.enabled = False
        elif value != 'status':
            return 'Use /thinking on, /thinking off, or /thinking status.'
        return 'Thinking cycle: ' + ('off' if not self.enabled else 'waiting for input' if self.waiting else 'on; runs after idle delay') + '.'

    def run(self, conversation, pending_input, on_delta=None):
        if not self.ready() or pending_input():
            return None
        conversation.finish_preparation()
        if pending_input():
            return None
        api = conversation.api
        started = self.clock()
        def check():
            if pending_input():
                raise CycleInterrupted('Thinking yielded to incoming input.')
            if self.clock() - started >= STEP_SECONDS:
                raise CycleInterrupted('Thinking step reached its time limit; waiting for input.')
        api.cycle_check = check
        api.cycle_active = True
        try:
            message = ('Application idle-cycle trigger, not a new user request. '
                       'Review the active conversation and temporary scratchpads. '
                       f'Latest real input ID in this scope: {self.message_id or "none"}. '
                       'Make useful progress if possible, then return your cycle decision.')
            answer, finish = conversation.turn(message, source=self.source, sender_id=self.sender_id,
                                                on_delta=on_delta, internal=True)
            if finish != 'stop':
                self.waiting = True
                return 'Cycle reached its generation limit; waiting for input.'
            return self.complete(answer)
        except (RuntimeError, ValueError, OSError, http.client.HTTPException) as error:
            self.waiting = True
            return str(error)
        finally:
            api.cycle_check = None
            api.cycle_active = False
