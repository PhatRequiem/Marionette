#!/usr/bin/env python3
"""Minimal terminal chat: own one local server, retain system context, trim history."""
import datetime
import http.client
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

LOG_LOCK = threading.Lock()
COLORS = {'input': '\033[92m', 'data': '\033[97m',
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
        'runtime_version': r'^version: (.+)',
        'model_name': r'general\.name\s+str\s*=\s*(.+)',
        'context_tokens': r'llama_context: n_ctx_seq\s*=\s*(\d+)',
        'gpu_offload': r'offloaded (\d+/\d+) layers to GPU',
        'device': r'using device (.+?) \(\d{4}:',
        'local_server': r'server_on_li: listening on (http://127\.0\.0\.1:\d+)',
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, line)
        if match:
            facts[key] = {'value': match.group(1).strip(), 'evidence': line.strip()}


def snapshot(command, facts, debug_path):
    now = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
    lines = [f'Local runtime setup report generated {now}.',
             'This conversation runs in a local terminal client connected to its own loopback llama-server process, not a hosted chat API.']
    for key, label in [('runtime_version', 'Runtime version'), ('model_name', 'Loaded model name'), ('device', 'Runtime-selected device'),
                       ('gpu_offload', 'Layers reported offloaded to GPU'), ('context_tokens', 'Context capacity limit (tokens, not current usage)'),
                       ('local_server', 'Local server address')]:
        lines.append(f'{label}: {facts.get(key, {}).get("value", "not reported; unverified")}.')
    lines += ['The context limit is the maximum capacity, not the number of tokens currently used. Current token usage is not measured by this startup report. Do not claim the context is full from its capacity; live usage requires runtime measurements.',
              'Configured: offline local-model operation, text conversation, reasoning disabled.',
              'Capabilities: receive your messages and generate replies. No tools for browsing, executing commands, or opening files.',
              'Local software saves chat and debug logs; the model cannot read those files or past sessions itself. Older complete exchanges are removed from active context when needed; the setup report is kept. Saved conversations are not reloaded as memory.',
              f'Current model-processing log: {debug_path}.',
              f'Current connections-and-requests log: {str(debug_path).removesuffix("-model.txt")}-server.txt.',
              f'Current chat log: {str(debug_path).removesuffix("-model.txt")}-chat.txt.',
              'This is a startup snapshot, not continuous monitoring. Model-file checksums are verified by setup, not rechecked by this report.']
    context = ' '.join(lines)
    data = {'schema_version': 2, 'generated_at': now, 'runtime_pid': None,
            'runtime_command': command, 'observed': facts.copy(), 'context': context,
            'delivery': 'pending_first_message'}
    return data


def save(path, data):
    temporary = path.with_suffix('.json.part')
    with temporary.open('w', encoding='utf-8') as out:
        json.dump(data, out, indent=2, ensure_ascii=False)
        out.write('\n')
    os.chmod(temporary, 0o600)
    temporary.replace(path)


class API:
    def __init__(self, address):
        self.address = address
        # Local traffic must not use an inherited HTTP proxy.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def open(self, path, body=None):
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
        return {'messages': messages, 'chat_template_kwargs': {'enable_thinking': False}}

    def count(self, messages):
        prompt = self.json('/apply-template', self.body(messages))['prompt']
        result = self.json('/tokenize', {'content': prompt, 'add_special': True, 'parse_special': True})
        return len(result['tokens'])

    def reply(self, messages, reserve):
        body = self.body(messages) | {'stream': True, 'max_tokens': reserve,
                                      'stream_options': {'include_usage': True}}
        pieces, finish = [], None
        with self.open('/v1/chat/completions', body) as response:
            for line in response:
                if not line.startswith(b'data: '):
                    continue
                payload = line[6:].strip()
                if payload == b'[DONE]':
                    if finish is None:
                        raise RuntimeError('Response ended without a completion status.')
                    return ''.join(pieces), finish
                event = json.loads(payload)
                if 'error' in event:
                    raise RuntimeError(str(event['error']))
                for choice in event.get('choices', []):
                    text = choice.get('delta', {}).get('content') or ''
                    if text:
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
        if len(candidate) <= 2:
            raise ValueError('This message plus the setup report is too large. Shorten the message; history is unchanged.')
        del candidate[1:3]  # oldest complete user/assistant exchange
        removed += 1


def chat(api, report, path, capacity):
    reserve = min(512, capacity // 4)
    system = {'role': 'system', 'content': report['context']}
    history = [system]
    if api.count(history + [{'role': 'user', 'content': ''}]) + reserve >= capacity:
        raise RuntimeError('Context is too small for the setup report and reply allowance.')
    log(f'Context policy: capacity={capacity}, reply_budget={reserve}, system report always retained.')
    print(f'Ready. Context limit: {capacity}; reply allowance: {reserve} tokens. /clear starts fresh; /exit quits.')
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
        if not message.strip():
            continue
        if message.strip() == '/exit':
            return
        print()
        if message.strip() == '/clear':
            history = [system]
            log('Chat history cleared; setup report retained.')
            print('Chat history cleared; setup report retained.')
            continue
        if message.startswith('/'):
            print('Available commands: /clear and /exit.')
            continue
        try:
            candidate, removed, tokens = fit_history(history, message, api.count, capacity, reserve)
            log(f'Prompt budget: {tokens} tokens + {reserve} reply allowance < {capacity}; removed_exchanges={removed}.')
            if removed:
                print(f'[Context rollover: leaving out {removed} oldest exchange(s); setup report retained.]')
            color('reply')
            try:
                answer, finish = api.reply(candidate, reserve)
            finally:
                color('data')
            print()
            log(f'Reply completed: finish_reason={finish}.')
            if report['delivery'] != 'supplied_with_first_message':
                delivered = report | {'delivery': 'supplied_with_first_message'}
                save(path, delivered)
                report.update(delivered)
            history = candidate + [{'role': 'assistant', 'content': answer}]
            if finish == 'length':
                print('[Reply reached its token allowance.]')
        except (ValueError, RuntimeError, OSError, http.client.HTTPException) as error:
            log(f'Request failed: {error}')
            print(f'\n{error}\nConversation history is unchanged; you can retry.')


def run(model_path, command):
    path = model_path.with_name(model_path.name.removesuffix('-model.txt') + '-setup.json')
    facts = {}
    for line in os.environ.get('MARIONETTE_RUNTIME_VERSION', '').splitlines():
        observe(line, facts)
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
        address = facts.get('local_server', {}).get('value')
        if not address:
            raise RuntimeError('No loopback server address was reported.')
        api = API(address)
        api.json('/health')
        capacity = int(api.json('/props')['default_generation_settings']['n_ctx'])
        observed = facts.get('context_tokens', {}).get('value')
        if str(capacity) != observed:
            raise RuntimeError(f'Context observations disagree: diagnostics={observed}, server={capacity}.')
        report = snapshot(command, facts, model_path)
        report['runtime_pid'] = child.pid
        report['reply_budget_tokens'] = min(512, capacity // 4)
        save(path, report)
        log(f'Setup snapshot ready: {path}')
        chat(api, report, path, capacity)
        return 0
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        reader.join(timeout=5)
        child.stdout.close()
        log('Local server stopped.')


if __name__ == '__main__':
    def interrupt(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGHUP, interrupt)
    try:
        status = run(Path(sys.argv[1]), sys.argv[2:])
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
