#!/usr/bin/env python3
"""Terminal chat with an owned local server and between-turn cache preparation."""
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

LOG_LOCK = threading.Lock()
COLORS = {'input': '\033[38;2;57;255;20m', 'data': '\033[97m',
          'reply': '\033[38;2;255;128;191m', 'reset': '\033[0m'}


def color(kind):
    if sys.stdout.isatty() and os.environ.get('TERM') != 'dumb':
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

    def reply(self, messages, reserve):
        body = self.body(messages) | {'stream': True, 'max_tokens': reserve,
                                      'stream_options': {'include_usage': True}}
        pieces, thoughts, finish = [], [], None
        with self.open('/v1/chat/completions', body) as response:
            for line in response:
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
                        color('data')
                        if not thoughts:
                            print('Thinking:', flush=True)
                        thoughts.append(reasoning)
                        print(reasoning, end='', flush=True)
                    text = delta.get('content') or ''
                    if text:
                        if not pieces and thoughts:
                            color('data')
                            print('\n\nAnswer:', flush=True)
                        color('reply')
                        pieces.append(text)
                        print(text, end='', flush=True)
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


def chat(api, capacity):
    reserve = min(2048, capacity // 4)
    history = []
    pending = None
    log(f'Context policy: capacity={capacity}, reply_budget={reserve}, '
        f'next_message_allowance={min(2048, capacity // 8)}; no setup report.')
    print(f'Ready. Context limit: {capacity}; thinking + answer allowance: {reserve} tokens. /clear starts fresh; /exit quits.')
    while True:
        try:
            print()
            color('input')
            print('> ', end='', flush=True)
            try:
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
        if pending is not None:
            history = pending.result()
            pending = None
        if command == '/clear':
            history = []
            log('Chat history cleared.')
            print('Chat history cleared.')
            continue
        if message.startswith('/'):
            print('Available commands: /clear and /exit.')
            continue
        try:
            candidate, removed, tokens = fit_history(history, message, api.count, capacity, reserve)
            log(f'Prompt budget: {tokens} tokens + {reserve} reply allowance < {capacity}; removed_exchanges={removed}.')
            if removed:
                log(f'Input-time rollover: removed_exchanges={removed}; preparing this request.')
            try:
                answer, finish = api.reply(candidate, reserve)
            finally:
                color('data')
            print()
            log(f'Reply completed: finish_reason={finish}.')
            history = candidate + [{'role': 'assistant', 'content': answer}]
            pending = Preparation(api, history, capacity, reserve)
            if finish == 'length':
                print('[Thinking and answer reached their shared token allowance.]')
        except (ValueError, RuntimeError, OSError, http.client.HTTPException) as error:
            log(f'Request failed: {error}')
            print(f'\n{error}\nConversation history is unchanged; you can retry.')


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
        color('data')
        print('Loading model...', flush=True)
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
        print('\nExiting...')
        status = 0
    except (OSError, ValueError, RuntimeError, http.client.HTTPException) as error:
        log(f'Client error: {error}')
        print(f'Chat could not continue: {error}', file=sys.stdout)
        status = 1
    finally:
        color('reset')
    raise SystemExit(status)
