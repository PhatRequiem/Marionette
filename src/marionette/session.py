#!/usr/bin/env python3
"""Terminal chat with an owned local server and between-turn cache preparation."""
from concurrent.futures import Future
from pathlib import Path
import queue
import select
import http.client
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

from style import COLORS, enabled, paint
from identity import Profiles, message_with_identity

LOG_LOCK = threading.Lock()


def color(kind):
    if enabled():
        print(COLORS[kind], end='', flush=True)


def log(message):
    with LOG_LOCK:
        sys.stderr.buffer.write(('Client: ' + message + '\n').encode())
        sys.stderr.buffer.flush()


def observe(line, facts):
    patterns = {
        'context_tokens': r'llama_context: n_ctx_seq\s*=\s*(\d+)',
        'local_server': r'server_on_li: listening on (http://127\.0\.0\.1:\d+)',
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, line)
        if match:
            facts[key] = match.group(1).strip()


class API:
    def __init__(self, address):
        self.address = address
        self.closing = threading.Event()
        self.worker = None
        # Local traffic must not use an inherited HTTP proxy.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def open(self, path, body=None):
        if self.closing.is_set():
            raise RuntimeError('Session is closing.')
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.address + path, data=data,
                                         headers={'Content-Type': 'application/json'})
        try:
            return self.opener.open(request, timeout=120)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'HTTP {error.code}: {error.read().decode(errors="replace")}') from error

    def json(self, path, body=None):
        with self.open(path, body) as response:
            result = json.load(response)
        if 'error' in result:
            raise RuntimeError(str(result['error']))
        return result

    @staticmethod
    def body(messages):
        return {'messages': messages, 'chat_template_kwargs': {'enable_thinking': True}}

    def tokenize(self, prompt):
        return self.json('/tokenize', {'content': prompt, 'add_special': True,
                                       'parse_special': True})['tokens']

    def count(self, messages):
        prompt = self.json('/apply-template', self.body(messages))['prompt']
        return len(self.tokenize(prompt))

    def prepare(self, messages):
        # Render with a following user turn so the template treats the last reply
        # as history (Qwen formats its final assistant turn differently).
        marker = 'MARIONETTE_NEXT_INPUT_' + secrets.token_hex(16)
        prompt = self.json('/apply-template', self.body(messages +
                           [{'role': 'user', 'content': marker}]))['prompt']
        if prompt.count(marker) != 1:
            raise RuntimeError('Cannot locate next-message boundary in chat template.')
        prefix = prompt.split(marker)[0]
        tokens = self.tokenize(prefix)
        # Leave the boundary token for the real input in case tokenization merges it.
        result = self.json('/completion', {'prompt': tokens[:-1], 'n_predict': 0,
                                          'cache_prompt': True})
        log('Prepared cache timings: ' + json.dumps(result.get('timings', {})))

    def reply(self, messages, reserve, *, display=True):
        body = self.body(messages) | {'stream': True, 'max_tokens': reserve,
                                      'stream_options': {'include_usage': True}}
        pieces, thoughts, finish = [], [], None
        stream_color = None
        with self.open('/v1/chat/completions', body) as response:
            for line in response:
                if self.closing.is_set():
                    raise RuntimeError('Session is closing.')
                if not line.startswith(b'data: '):
                    continue
                payload = line[6:].strip()
                if payload == b'[DONE]':
                    if finish is None:
                        raise RuntimeError('Response ended without a completion status.')
                    if thoughts:
                        log('Reasoning: ' + json.dumps(''.join(thoughts), ensure_ascii=False))
                    return ''.join(pieces), finish
                event = json.loads(payload)
                if 'error' in event:
                    raise RuntimeError(str(event['error']))
                for choice in event.get('choices', []):
                    delta = choice.get('delta', {})
                    reasoning = delta.get('reasoning_content') or ''
                    if reasoning:
                        if display:
                            if not thoughts:
                                color('reasoning_heading')
                                print('Reasoning:', flush=True)
                            if stream_color != 'data':
                                color('data')
                                stream_color = 'data'
                            print(reasoning, end='', flush=True)
                        thoughts.append(reasoning)
                    text = delta.get('content') or ''
                    if text:
                        if display and not pieces and thoughts:
                            color('answer_heading')
                            print('\n\nAnswer:', flush=True)
                        if display:
                            if stream_color != 'reply':
                                color('reply')
                                stream_color = 'reply'
                            print(text, end='', flush=True)
                        pieces.append(text)
                    finish = choice.get('finish_reason') or finish
                if event.get('usage'):
                    log('Runtime usage: ' + json.dumps(event['usage']))
        raise RuntimeError('Response stream closed early; partial reply was not kept.')


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
    def __init__(self, api, history, capacity, reserve):
        self.history = history
        self.thread = threading.Thread(target=self.work,
                                       args=(api, capacity, reserve), daemon=True)
        api.worker = self.thread
        self.thread.start()

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
            log(f'Rollover preparation started: removed_exchanges={removed}; '
                f'next_prompt_tokens={tokens}; next_message_allowance={incoming}; reply_allowance={reserve}.')
            if candidate:
                api.prepare(candidate)
            # Publish only after successful preparation. An empty history needs no cache.
            self.history = candidate
            log(f'Rollover preparation completed: removed_exchanges={removed}; '
                f'elapsed_ms={(time.monotonic() - started) * 1000:.2f}.')
        except (ValueError, RuntimeError, OSError, http.client.HTTPException) as error:
            if api.closing.is_set():
                log('Rollover preparation stopped with session shutdown.')
            else:
                log(f'Rollover preparation failed; history retained: {error}')

    def result(self):
        if self.thread.is_alive():
            started = time.monotonic()
            self.thread.join()
            log(f'Preparation wait after input: {(time.monotonic() - started) * 1000:.2f} ms.')
        return self.history


class Conversation:
    """One history and one generation at a time, shared by every input."""
    def __init__(self, api, capacity, profiles=None, terminal_profile=None):
        self.profiles, self.terminal_profile = profiles, terminal_profile
        self.api, self.capacity = api, capacity
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

    def display_discord(self):
        try:
            message, sender_id, future, queued_at, timings = self.incoming.get_nowait()
        except queue.Empty:
            return False
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
            answer, finish = self.turn(message, display=True, source='discord', sender_id=str(sender_id))
            if message.strip() == '/clear':
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

    def turn(self, message, *, display=False, source="terminal", sender_id=None):
        with self.lock:
            if self.api.closing.is_set():
                raise RuntimeError('Session is closing.')
            if self.pending is not None:
                self.history = self.pending.result()
                self.pending = None
            identity = None
            if self.profiles is not None:
                sender_id = sender_id if source != 'terminal' else self.terminal_profile['uuid']
                identity = self.profiles.resolve(source, sender_id)
                log('Sender identity: ' + json.dumps(identity, ensure_ascii=False))
            if message.strip() == '/clear':
                self.history = []
                log('Chat history cleared.')
                return 'Chat history cleared.', 'stop'
            candidate, removed, tokens = fit_history(
                self.history, message_with_identity(message, identity) if identity else message,
                self.api.count, self.capacity, self.reserve)
            log(f'Prompt budget: {tokens} tokens + {self.reserve} reply allowance < '
                f'{self.capacity}; removed_exchanges={removed}.')
            if removed:
                log(f'Input-time rollover: removed_exchanges={removed}; preparing this request.')
            # The terminal renders both local and queued Discord turns.
            answer, finish = self.api.reply(candidate, self.reserve, display=display)
            if not answer.strip():
                raise RuntimeError('Model produced no final answer.')
            log(f'Reply completed: finish_reason={finish}.')
            self.history = candidate + [{'role': 'assistant', 'content': answer}]
            self.pending = Preparation(self.api, self.history, self.capacity, self.reserve)
            return answer, finish


def terminal(conversation, *, external=False):
    while True:
        try:
            print()
            color('input')
            print('> ', end='', flush=True)
            try:
                if external:
                    while True:
                        if conversation.display_discord():
                            color('input')
                            print('> ', end='', flush=True)
                        if select.select([sys.stdin], [], [], .1)[0]:
                            break
                message = input()
            finally:
                color('data')
        except EOFError:
            return
        command = message.strip()
        if not command:
            continue
        if command == '/exit':
            return
        print()
        if command == '/clear':
            conversation.turn('/clear')
            color('meta')
            print('Chat history cleared.')
            color('data')
            continue
        if message.startswith('/'):
            print('Available commands: /clear and /exit.')
            continue
        try:
            try:
                answer, finish = conversation.turn(message, display=True)
            finally:
                color('data')
            print()
            if finish == 'length':
                color('warning')
                print('[Reasoning and answer reached their shared token allowance.]')
                color('data')
        except (ValueError, RuntimeError, OSError, http.client.HTTPException) as error:
            log(f'Request failed: {error}')
            color('error')
            print(f'\n{error}\nConversation history is unchanged; you can retry.')
            color('data')


def chat(api, capacity):
    data = Path(os.environ.get('MARIONETTE_DATA_DIR', Path(__file__).resolve().parents[2] / 'data'))
    profiles = Profiles(data / 'identities/profiles.json')
    profiles.link_owner(data / 'discord/.env')
    try:
        selected = profiles.select()
    except EOFError:
        return
    print(paint('Terminal profile: ', 'meta', enabled()) + paint(selected['name'], 'ids', enabled()))
    conversation = Conversation(api, capacity, profiles, selected)
    log(f'Context policy: capacity={capacity}, reply_budget={conversation.reserve}, '
        f'next_message_allowance={min(2048, capacity // 8)}; no setup report.')
    print(paint('Ready.', 'meta', enabled()) + paint(' Context limit: ', 'data', enabled()) + paint(str(capacity), 'tokens', enabled())
          + paint('; reasoning + answer allowance: ', 'data', enabled()) + paint(str(conversation.reserve), 'tokens', enabled())
          + ' tokens. /clear starts fresh; /exit quits.')
    from contextlib import nullcontext
    address = os.environ.get('MARIONETTE_SESSION_SOCKET')
    if address:
        from connection import LocalConnection
        connection = LocalConnection(address, conversation.submit_discord, log)
    else:
        connection = nullcontext()
    try:
        with connection:
            terminal(conversation, external=bool(address))
    finally:
        api.closing.set()


def run(command):
    facts = {}
    api = None
    ready = threading.Event()
    # Own the server's lifetime; terminal Ctrl+C is handled by this client.
    child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, start_new_session=True)

    def diagnostics():
        for raw in child.stdout:
            with LOG_LOCK:
                sys.stderr.buffer.write(raw)
                sys.stderr.buffer.flush()
            line = raw.decode('utf-8', errors='replace').rstrip('\r\n')
            if not ready.is_set():
                observe(line, facts)
                if 'update_slots: all slots are idle' in line:
                    ready.set()

    reader = threading.Thread(target=diagnostics, daemon=True)
    reader.start()
    log(f'Local server started: pid={child.pid}.')
    try:
        color('meta')
        print('Loading model...', flush=True)
        color('data')
        deadline = time.monotonic() + 180
        while not ready.wait(.1):
            status = child.poll()
            if status is not None:
                reader.join(timeout=5)
                raise RuntimeError(f'Server exited before readiness (status {status}).')
            if time.monotonic() > deadline:
                raise RuntimeError('Server did not become ready within 180 seconds.')
        address = facts.get('local_server')
        if not address:
            raise RuntimeError('No loopback server address was reported.')
        api = API(address)
        api.json('/health')
        capacity = int(api.json('/props')['default_generation_settings']['n_ctx'])
        observed = facts.get('context_tokens')
        if str(capacity) != observed:
            raise RuntimeError(f'Context observations disagree: diagnostics={observed}, server={capacity}.')
        chat(api, capacity)
        return 0
    finally:
        if api is not None:
            api.closing.set()
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        if api is not None and api.worker is not None:
            api.worker.join(timeout=5)
        reader.join(timeout=5)
        child.stdout.close()
        log('Local server stopped.')


if __name__ == '__main__':
    def interrupt(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGHUP, interrupt)
    try:
        status = run(sys.argv[1:])
    except KeyboardInterrupt:
        color('meta')
        print('\nExiting...')
        status = 0
    except (OSError, ValueError, RuntimeError, http.client.HTTPException) as error:
        log(f'Client error: {error}')
        print(f'Chat could not continue: {error}', file=sys.stdout)
        status = 1
    finally:
        color('reset')
    raise SystemExit(status)
