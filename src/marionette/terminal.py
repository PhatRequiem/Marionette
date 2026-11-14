"""Terminal profile selection, input, and rendering for all chat sources."""
import http.client
import queue
import select
import sys
import time
import threading
import os
import codecs
from contextlib import contextmanager

from commands import HELP_TEXT, recognize
from style import COLORS, enabled, paint


def color(kind):
    if enabled():
        print(COLORS[kind], end='', flush=True)


class ReplyDisplay:
    """One renderer per reply; inference supplies text without knowing its UI."""
    def __init__(self):
        self.answer = False
        self.stream_color = None

    def __call__(self, phase, text):
        if phase == 'reasoning':
            return
        if not self.answer:
            color('answer_heading')
            print('Answer:', flush=True)
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
          + ' tokens. /clear starts fresh; /resetmemory wipes memory (owner); /shutdown stops her (owner); /exit quits.')


def display_discord(conversation, inputs=None):
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
        with (inputs or CancelInput()).watch(conversation):
            answer, finish = conversation.turn(message, on_delta=ReplyDisplay(), source='discord', sender_id=str(sender_id), message_id=message_id, display_name=getattr(future, 'discord_display_name', None))
        if recognize(message, 'discord') in ('clear', 'resetmemory', 'shutdown', 'help', 'ddm', 'status', 'connections', 'context', 'sync', 'cancel'):
            color('meta')
            print(answer)
        if finish == 'cancelled':
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
    inputs = CancelInput()
    while True:
        try:
            print()
            show_terminal_source(conversation)
            color('input')
            print('> ', end='', flush=True)
            try:
                if external:
                    while True:
                        if getattr(conversation, 'setup_refresh', None):
                            conversation.setup_refresh()
                        if display_discord(conversation, inputs):
                            if conversation.shutdown_requested:
                                return
                            show_terminal_source(conversation)
                            color('input')
                            print('> ', end='', flush=True)
                        if not inputs.deferred.empty() or select.select([sys.stdin], [], [], .1)[0]:
                            break
                message = inputs.deferred.get_nowait() if not inputs.deferred.empty() else input()
            finally:
                color('data')
        except EOFError:
            return
        command = recognize(message, 'terminal')
        if not message.strip():
            continue
        if command == 'exit':
            return
        print()
        if command in ('clear', 'resetmemory', 'shutdown', 'startdiscord', 'stopdiscord', 'refreshsetup', 'ddm', 'status', 'connections', 'context', 'sync', 'cancel'):
            try:
                answer, finish = conversation.turn(message)
            except (ValueError, RuntimeError, OSError) as error:
                answer = str(error)
            color('meta')
            print(answer)
            color('data')
            if conversation.shutdown_requested:
                return
            continue
        if command == 'help':
            print(HELP_TEXT)
            continue
        try:
            try:
                with inputs.watch(conversation):
                    answer, finish = conversation.turn(message, on_delta=ReplyDisplay())
                if finish == 'cancelled':
                    print(answer)
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


class CancelInput:
    """Read interactive /cancel during a turn; preserve other typed lines in order."""
    def __init__(self):
        self.deferred = queue.Queue()

    @contextmanager
    def watch(self, conversation):
        stop = threading.Event()
        thread = None
        if sys.stdin.isatty():
            def read():
                decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
                buffered = ''
                while not stop.is_set():
                    if select.select([sys.stdin], [], [], .05)[0]:
                        raw = os.read(sys.stdin.fileno(), 65536)
                        if not raw:
                            break
                        buffered += decoder.decode(raw)
                        while '\n' in buffered:
                            line, buffered = buffered.split('\n', 1)
                            if line.strip() == '/cancel':
                                print('\n' + conversation.cancel(), flush=True)
                            else:
                                self.deferred.put(line)
                if buffered:
                    self.deferred.put(buffered)
            thread = threading.Thread(target=read, name='terminal-cancel', daemon=True)
            thread.start()
        try:
            yield
        finally:
            stop.set()
            if thread:
                thread.join()
