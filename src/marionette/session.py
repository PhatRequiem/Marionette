#!/usr/bin/env python3
"""Compose the chat components and own the local model server's lifetime."""
from contextlib import nullcontext
import http.client
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time

import diagnostics
import terminal
from connection import LocalConnection
from conversation import Conversation
from identity import Profiles
from inference import API
from log_store import chat_event


def observe(line, facts):
    patterns = {
        'context_tokens': r'(?:llama_context: n_ctx_seq|\bn_ctx_slot)\s*=\s*(\d+)',
        'local_server': r'server_on_li: listening on (http://127\.0\.0\.1:\d+)',
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, line)
        if match:
            facts[key] = match.group(1).strip()


def chat(api, capacity):
    data = Path(os.environ.get('MARIONETTE_DATA_DIR', Path(__file__).resolve().parents[2] / 'data'))
    profiles = Profiles(data / 'identities/profiles.json')
    profiles.link_owner(data / 'discord/.env')
    try:
        selected = terminal.select_profile(profiles)
    except EOFError:
        return
    chat_event('profile_selected', person_uuid=selected['uuid'], display_name=selected['name'], source='terminal')
    terminal.show_profile(selected)
    conversation = Conversation(api, capacity, profiles, selected)
    diagnostics.log(f'Context policy: capacity={capacity}, reply_budget={conversation.reserve}, '
        f'next_message_allowance={min(2048, capacity // 8)}; no setup report.')
    chat_event('ready', context_capacity=capacity, reply_allowance=conversation.reserve)
    terminal.show_ready(capacity, conversation.reserve)
    address = os.environ.get('MARIONETTE_SESSION_SOCKET')
    if address:
        connection = LocalConnection(address, conversation.submit_discord, diagnostics.log)
    else:
        connection = nullcontext()
    try:
        with connection:
            terminal.run(conversation, external=bool(address))
    finally:
        api.closing.set()


def run(command):
    facts = {}
    api = None
    ready = threading.Event()
    # Own the server's lifetime; terminal Ctrl+C is handled by this client.
    child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, start_new_session=True)

    def read_diagnostics():
        for raw in child.stdout:
            diagnostics.write(raw)
            line = raw.decode('utf-8', errors='replace').rstrip('\r\n')
            if not ready.is_set():
                observe(line, facts)
                if 'local_server' in facts:
                    ready.set()

    reader = threading.Thread(target=read_diagnostics, daemon=True)
    reader.start()
    diagnostics.log(f'Local server started: pid={child.pid}.')
    try:
        chat_event('session_started', server_pid=child.pid)
        terminal.color('meta')
        print('Loading model...', flush=True)
        terminal.color('data')
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
        diagnostics.log('Local server stopped.')
        chat_event('session_stopped')


if __name__ == '__main__':
    def interrupt(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGHUP, interrupt)
    try:
        status = run(sys.argv[1:])
    except KeyboardInterrupt:
        terminal.color('meta')
        print('\nExiting...')
        status = 0
    except (OSError, ValueError, RuntimeError, http.client.HTTPException) as error:
        diagnostics.log(f'Client error: {error}')
        print(f'Chat could not continue: {error}', file=sys.stdout)
        status = 1
    finally:
        terminal.color('reset')
    raise SystemExit(status)
