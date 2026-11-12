"""Continuous scheduling and bounded internal turns, driven by the existing input loop."""
import json
import http.client
import time

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
        self.source, self.sender_id, self.message_id = 'terminal', None, None

    def wake(self, source, sender_id, message_id):
        self.source, self.sender_id, self.message_id = source, sender_id, message_id

    def ready(self):
        return self.enabled

    def complete(self, answer):
        # Summaries never control scheduling, including old action/wait outputs.
        try:
            result = json.loads(answer)
            if isinstance(result, dict) and isinstance(result.get('summary'), str):
                return result['summary']
        except (ValueError, TypeError):
            pass
        return answer

    def command(self, value):
        if value == 'on':
            self.enabled = True
        elif value == 'off':
            self.enabled = False
        elif value != 'status':
            return 'Use /thinking on, /thinking off, or /thinking status.'
        return 'Thinking cycle: ' + ('off' if not self.enabled else 'on; continuous between user turns') + '.'

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
                raise CycleInterrupted('Thinking step reached its time limit; continuing with the next step.')
        api.cycle_check = check
        api.cycle_active = True
        try:
            message = ('Application continuous-cycle trigger, not a new user request. '
                       'Review the active conversation and temporary scratchpads. '
                       f'Latest real input ID in this scope: {self.message_id or "none"}. '
                       'Make useful progress if possible, then briefly summarize this step. The next step follows automatically.')
            answer, finish = conversation.turn(message, source=self.source, sender_id=self.sender_id,
                                                on_delta=on_delta, internal=True)
            if finish != 'stop':
                return 'Cycle reached its generation limit; continuing with the next step.'
            return self.complete(answer)
        except CycleInterrupted as error:
            return str(error)
        except (RuntimeError, ValueError, OSError, http.client.HTTPException) as error:
            self.enabled = False
            return f'Thinking stopped after an error: {error} Use /thinking on to retry.'
        finally:
            api.cycle_check = None
            api.cycle_active = False
