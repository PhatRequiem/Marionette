"""Terminal profile selection, input, and rendering for all chat sources."""
import http.client
import queue
import select
import sys
import time

from commands import HELP_TEXT, recognize
from style import COLORS, enabled, paint


def color(kind):
    if enabled():
        print(COLORS[kind], end='', flush=True)


class ReplyDisplay:
    """One renderer per reply; inference supplies text without knowing its UI."""
    def __init__(self):
        self.reasoning = False
        self.answer = False
        self.stream_color = None

    def __call__(self, phase, text):
        if phase == 'reasoning':
            if not self.reasoning:
                color('reasoning_heading')
                print('Reasoning:', flush=True)
            self.reasoning = True
            kind = 'data'
        else:
            if not self.answer and self.reasoning:
                color('answer_heading')
                print('\n\nAnswer:', flush=True)
            self.answer = True
            kind = 'reply'
        if self.stream_color != kind:
            color(kind)
            self.stream_color = kind
        print(text, end='', flush=True)


def select_profile(profiles):
    while True:
        print('\nWho is chatting?', flush=True)
        for number, profile in enumerate(profiles.profiles, 1):
            print(f'{number}. {profile["name"]}')
        print(f'{len(profiles.profiles) + 1}. Add new profile', flush=True)
        choice = input('Profile: ').strip()
        if choice.isascii() and choice.isdecimal():
            number = int(choice)
            if 1 <= number <= len(profiles.profiles):
                return profiles.profiles[number - 1]
            if number == len(profiles.profiles) + 1:
                try:
                    return profiles.add(input('Name: '))
                except ValueError as error:
                    print(error)
                    continue
        print('Choose a listed number.')


def show_ready(capacity, reserve):
    print(paint('Ready.', 'meta', enabled()) + paint(' Context limit: ', 'data', enabled()) + paint(str(capacity), 'tokens', enabled())
          + paint('; reasoning + answer allowance: ', 'data', enabled()) + paint(str(reserve), 'tokens', enabled())
          + ' tokens. /clear starts fresh; /resetmemory wipes memory (owner); /exit quits.')


def display_discord(conversation):
    try:
        message, sender_id, future, queued_at, timings, message_id = conversation.incoming.get_nowait()
    except queue.Empty:
        return False
    if getattr(future, 'memory_epoch', conversation.epoch) != conversation.epoch:
        future.set_result(('Message discarded because memory was reset. Please send it again.', 'stop'))
        return True
    processing_start = time.monotonic()
    if timings is not None:
        timings['main_queue_ms'] = round((processing_start - queued_at) * 1000, 2)
    print('\n')
    color('meta')
    print('[Discord · ', end='', flush=True)
    color('ids')
    print(sender_id, end='', flush=True)
    color('meta')
    print(']', flush=True)
    color('input')
    print(f'{message}\n', flush=True)
    color('data')
    try:
        answer, finish = conversation.turn(message, on_delta=ReplyDisplay(), source='discord', sender_id=str(sender_id), message_id=message_id)
        if recognize(message, 'discord') in ('clear', 'resetmemory'):
            color('meta')
            print(answer)
        if finish == 'length':
            color('warning')
            print('\n[Reasoning and answer reached their shared token allowance.]')
        if timings is not None:
            timings['processing_ms'] = round((time.monotonic() - processing_start) * 1000, 2)
        future.set_result((answer, finish))
    except (ValueError, RuntimeError, OSError, http.client.HTTPException) as error:
        color('data')
        color('error')
        print(f'\nDiscord request failed: {error}')
        future.set_exception(error)
    finally:
        color('data')
        print('\n')
    return True


def show_terminal_source(conversation):
    profile = conversation.terminal_profile
    sender = profile['uuid'] if profile else 'local'
    print(paint('[Terminal · ', 'meta', enabled()) + paint(sender, 'ids', enabled())
          + paint(']', 'meta', enabled()), flush=True)


def run(conversation, *, external=False):
    while True:
        try:
            print()
            show_terminal_source(conversation)
            color('input')
            print('> ', end='', flush=True)
            try:
                if external or conversation.thinking is not None:
                    while True:
                        if display_discord(conversation):
                            show_terminal_source(conversation)
                            color('input')
                            print('> ', end='', flush=True)
                        if select.select([sys.stdin], [], [], .1)[0]:
                            break
                        cycle = conversation.thinking
                        if cycle is not None and cycle.ready():
                            def pending_input():
                                return (not conversation.incoming.empty()
                                        or bool(select.select([sys.stdin], [], [], 0)[0]))
                            print('\n[Internal thinking cycle]', flush=True)
                            def internal_delta(phase, text):
                                if phase == 'reasoning':
                                    print(text, end='', flush=True)
                            summary = cycle.run(conversation, pending_input, internal_delta)
                            if summary is not None:
                                print('\n[Cycle] ' + summary, flush=True)
                            show_terminal_source(conversation)
                            color('input')
                            print('> ', end='', flush=True)
                message = input()
            finally:
                color('data')
        except EOFError:
            return
        if message.strip().startswith('/thinking'):
            cycle = conversation.thinking
            try:
                from permissions import require_reset
                identity = conversation.profiles.resolve('terminal', conversation.terminal_profile['uuid'])
                require_reset(identity, conversation.profiles)
                parts = message.strip().split()
                value = parts[1] if len(parts) == 2 and parts[0] == '/thinking' else 'status' if parts == ['/thinking'] else 'invalid'
                print(cycle.command(value) if cycle is not None else 'Thinking cycle unavailable.')
            except PermissionError as error:
                print(str(error))
            continue
        command = recognize(message, 'terminal')
        if not message.strip():
            continue
        if command == 'exit':
            return
        print()
        if command in ('clear', 'resetmemory'):
            try:
                answer, _ = conversation.turn(message)
            except (ValueError, RuntimeError, OSError) as error:
                answer = str(error)
            color('meta')
            print(answer)
            color('data')
            continue
        if command == 'help':
            print(HELP_TEXT)
            continue
        try:
            try:
                answer, finish = conversation.turn(message, on_delta=ReplyDisplay())
            finally:
                color('data')
            print()
            if finish == 'length':
                color('warning')
                print('[Reasoning and answer reached their shared token allowance.]')
                color('data')
        except (ValueError, RuntimeError, OSError, http.client.HTTPException) as error:
            color('error')
            print(f'\n{error}\nConversation history is unchanged; you can retry.')
            color('data')


def show_profile(profile):
    print(paint('Terminal profile: ', 'meta', enabled()) + paint(profile['name'], 'ids', enabled()))
