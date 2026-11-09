#!/usr/bin/env python3
"""Supply a post-load setup snapshot to the first conversation turn."""
import datetime
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import signal
import subprocess
import sys
import time


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


def template(start, end):
    # Only the first message can carry the coordinator's unpredictable envelope.
    return """{% for message in messages %}{% if loop.first and message['role'] == 'user' and 'START' in message['content'] %}{% set parts = message['content'].split('END', 1) %}{% set prefix = parts[0].split('START', 1) %}{{ '<|im_start|>system\n' + prefix[1] + '<|im_end|>\n<|im_start|>user\n' + prefix[0] + parts[1] + '<|im_end|>\n' }}{% else %}{{ '<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>\n' }}{% endif %}{% endfor %}{% if add_generation_prompt %}{{ '<|im_start|>assistant\n<think>\n\n</think>\n\n' }}{% endif %}""".replace('START', start).replace('END', end)


def prepare_line(line, first, context, start, end):
    """Preserve native commands; supply context again after /clear."""
    if line.startswith(b'/clear'):
        return line + b'\n', True, False
    if not line.strip() or line.startswith((b'/exit', b'/regen', b'/read ', b'/glob ')):
        return line + b'\n', first, False
    if first:
        return (start + context + end).encode() + line + b'\n', False, True
    return line + b'\n', False, False


def snapshot(command, facts, debug_path):
    now = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
    lines = [f'Local runtime setup report generated {now}.',
             'This conversation runs in local llama-cli with an embedded loopback HTTP server, not a hosted chat API.']
    for key, label in [('runtime_version', 'Runtime version'), ('model_name', 'Loaded model name'), ('device', 'Runtime-selected device'),
                       ('gpu_offload', 'Layers reported offloaded to GPU'), ('context_tokens', 'Loaded context tokens'),
                       ('local_server', 'Local server address')]:
        lines.append(f'{label}: {facts.get(key, {}).get("value", "not reported; unverified")}.')
    lines += ['Configured: offline local-model operation, text conversation, reasoning disabled by an empty closed thinking block.',
              'Capabilities: receive your messages and generate replies. No tools for browsing, executing commands, or opening files.',
              'Local software saves chat and debug logs; the model cannot read those files or past sessions itself. The user can explicitly attach text through CLI commands.',
              f'Current debug log: {debug_path}.',
              f'Current chat log: {str(debug_path).removesuffix("-debug.txt")}-chat.txt.',
              'This is a startup snapshot, not continuous monitoring. Model-file checksums are verified by setup, not rechecked by this report.']
    # CLI input does not interpret escaped newlines. Keep the envelope one line.
    context = ' '.join(lines)
    data = {'schema_version': 1, 'generated_at': now, 'runtime_pid': None,
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


def run(debug_path, command):
    path = debug_path.with_name(debug_path.name.removesuffix('-debug.txt') + '-setup.json')
    nonce = secrets.token_hex(12)
    start, end = f'[setup-{nonce}]', f'[/setup-{nonce}]'
    command = command + ['--chat-template', template(start, end)]
    facts = {}
    for line in debug_path.read_text(errors='replace').splitlines():
        observe(line, facts)
    report = None
    pending = b''
    first = True
    started = time.monotonic()
    with debug_path.open('ab', buffering=0) as debug:
        child = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        os.set_blocking(child.stdin.fileno(), False)
        outgoing = bytearray()
        input_closed = False
        delivery_pending = False
        # The child shares our foreground process group and receives terminal signals.
        previous = signal.signal(signal.SIGINT, lambda *_: None)
        selector = selectors.DefaultSelector()
        selector.register(child.stderr, selectors.EVENT_READ, 'diagnostics')
        diagnostic_buffer = b''
        try:
            while selector.get_map():
                if report is None and time.monotonic() - started > 180:
                    raise RuntimeError('Model readiness was not reported within 180 seconds; no setup context delivered.')
                for key, _ in selector.select(timeout=0.2):
                    if key.data == 'write':
                        try:
                            count = os.write(key.fd, outgoing)
                        except BlockingIOError:
                            continue
                        except BrokenPipeError:
                            outgoing.clear()
                            selector.unregister(key.fileobj)
                            continue
                        del outgoing[:count]
                        if not outgoing:
                            selector.unregister(key.fileobj)
                            if delivery_pending:
                                report['delivery'] = 'supplied_with_first_message'
                                save(path, report)
                                debug.write(b'Coordinator: setup context supplied with first message.\n')
                                delivery_pending = False
                            if input_closed:
                                child.stdin.close()
                        continue
                    chunk = os.read(key.fd, 65536)
                    if key.data == 'diagnostics':
                        if not chunk:
                            selector.unregister(key.fileobj)
                            if report is None:
                                print('Model did not reach chat readiness; see the debug log.', file=sys.stderr)
                            continue
                        debug.write(chunk)
                        diagnostic_buffer += chunk
                        while b'\n' in diagnostic_buffer:
                            line, diagnostic_buffer = diagnostic_buffer.split(b'\n', 1)
                            line = line.decode('utf-8', errors='replace')
                            observe(line, facts)
                            if report is None and re.search(r'update_slots: all slots are idle$', line):
                                report = snapshot(command, facts, debug_path)
                                report['runtime_pid'] = child.pid
                                save(path, report)
                                debug.write(f'Coordinator: setup snapshot ready: {path}\n'.encode())
                                selector.register(sys.stdin, selectors.EVENT_READ, 'input')
                    else:
                        if not chunk:
                            selector.unregister(key.fileobj)
                            input_closed = True
                            if not outgoing:
                                child.stdin.close()
                            continue
                        pending += chunk
                        while b'\n' in pending:
                            line, pending = pending.split(b'\n', 1)
                            packet, first, delivered = prepare_line(line, first, report['context'], start, end)
                            outgoing.extend(packet)
                            delivery_pending |= delivered
                        if outgoing and child.stdin.fileno() not in selector.get_map():
                            selector.register(child.stdin, selectors.EVENT_WRITE, 'write')
                if child.poll() is not None:
                    # Drain the remaining diagnostics, but never wait for more terminal input.
                    for key in list(selector.get_map().values()):
                        if key.data in ('input', 'write'):
                            selector.unregister(key.fileobj)
            status = child.wait()
            return status if status else (0 if report is not None else 1)
        finally:
            selector.close()
            signal.signal(signal.SIGINT, previous)
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


if __name__ == '__main__':
    debug_path = Path(sys.argv[1])
    with debug_path.open('a', buffering=1) as errors:
        sys.stderr = errors
        try:
            status = run(debug_path, sys.argv[2:])
        except (OSError, RuntimeError) as error:
            print(f'Coordinator error: {error}', file=errors)
            status = 1
        raise SystemExit(status)
