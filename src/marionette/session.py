#!/usr/bin/env python3
"""Compose the chat components and own the local model server's lifetime."""
from contextlib import nullcontext, closing
import http.client
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import sys
import threading
import time

import diagnostics
import setup_datasheet
import terminal
from connection import LocalConnection
from conversation import Conversation
from contacts import ContactProfiles
from data_migration import migrate_personal_paths
from contact_notes import ContactNotes
from soul import Soul
from inference import API
from storage import Store


def observe(line, facts):
    patterns = {
        'context_tokens': r'llama_context: n_ctx_seq\s*=\s*(\d+)',
        'local_server': r'server_on_li: listening on (http://127\.0\.0\.1:\d+)',
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, line)
        if match:
            facts[key] = match.group(1).strip()


def chat(api, capacity, store=None, session_id=None, *, on_startup=None):
    data = Path(os.environ.get('MARIONETTE_DATA_DIR', Path(__file__).resolve().parents[2] / 'data'))
    migrate_personal_paths(data)
    profiles = ContactProfiles(data / 'contacts/profiles.json')
    profiles.link_owner(data / 'discord/.env')
    try:
        selected = terminal.select_profile(profiles)
    except EOFError:
        return
    terminal.show_profile(selected)
    soul = Soul(data / 'soul/profile.json')
    api.tools = (soul.bind(api),)
    api.prepare([])
    conversation = Conversation(api, capacity, profiles, selected, ContactNotes(data / 'contact_notes'),
                                store, session_id, soul=soul)
    diagnostics.log(f'Context policy: capacity={capacity}, reply_budget={conversation.reserve}, '
        f'next_message_allowance={min(2048, capacity // 8)}; no setup report.')
    terminal.show_ready(capacity, conversation.reserve)
    address = os.environ.get('MARIONETTE_SESSION_SOCKET')
    if address:
        def operator_status():
            from datetime import datetime, timezone
            import json
            health = 'unknown'
            try:
                with api.opener.open(api.address + '/health', timeout=2) as response:
                    health = 'online' if json.loads(response.read(4096)).get('status') == 'ok' else 'unhealthy'
            except (OSError, ValueError):
                pass
            return {'model_server': health, 'discord': 'unknown',
                    'tools': sorted(tool.name for tool in api.tools),
                    'processing': 'busy' if conversation.lock.locked() else 'idle',
                    'cache_preparation': bool(api.worker and api.worker.is_alive()),
                    'observed_at': datetime.now(timezone.utc).isoformat()}
        connection = LocalConnection(address, conversation.submit_discord, diagnostics.log, status=operator_status)
    else:
        connection = nullcontext()
    try:
        if on_startup is not None:
            on_startup(conversation, bool(address))
        with connection:
            terminal.run(conversation, external=bool(address))
    finally:
        api.closing.set()


def run(command):
    facts = {}
    setup_facts = {}
    setup_details = {}
    datasheet = Path(os.environ.get('MARIONETTE_SETUP_DATASHEET_PATH',
        Path(__file__).resolve().parents[2] / 'docs/setup-datasheet.md'))
    def refresh(status, capacity=None):
        try:
            setup_datasheet.update(datasheet, status, setup_facts, capacity=capacity, details=setup_details)
        except (OSError, ValueError) as error:
            diagnostics.log(f'Setup datasheet update failed ({type(error).__name__}); previous file left intact.')
    refresh('starting')
    startup_verified = False
    api = None
    ready = threading.Event()
    # Own the server's lifetime; terminal Ctrl+C is handled by this client.
    try:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, start_new_session=True)
    except BaseException:
        refresh('failed')
        raise

    def read_diagnostics():
        for raw in child.stdout:
            diagnostics.write(raw)
            line = raw.decode('utf-8', errors='replace').rstrip('\r\n')
            if not ready.is_set():
                observe(line, facts)
                setup_datasheet.observe(line, setup_facts)
                if 'update_slots: all slots are idle' in line:
                    ready.set()

    reader = threading.Thread(target=read_diagnostics, daemon=True)
    reader.start()
    diagnostics.log(f'Local server started: pid={child.pid}.')
    try:
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
        if api.json('/health').get('status') != 'ok':
            raise RuntimeError('Server health check did not report ok.')
        properties = api.json('/props')
        capacity = int(properties['default_generation_settings']['n_ctx'])
        setup_details.update(setup_datasheet.configuration(command, properties,
            os.environ.get('MARIONETTE_RUNTIME_VERSION_OBSERVATION', '')))
        observed = facts.get('context_tokens')
        if str(capacity) != observed:
            raise RuntimeError(f'Context observations disagree: diagnostics={observed}, server={capacity}.')
        setup_details['Application'] = ('Starting', 'Waiting for profile selection')
        refresh('ready', capacity)
        startup_verified = True
        database = os.environ.get('MARIONETTE_LOG_DB')
        with closing(Store(database)) if database else nullcontext() as store:
            def capture_application(conversation, bridge_bound):
                setup_details.update(setup_datasheet.application(api, conversation, store, bridge_bound))
                refresh('ready', capacity)
            chat(api, capacity, store, os.environ.get('MARIONETTE_LOG_SESSION'), on_startup=capture_application)
        return 0
    finally:
        if not startup_verified:
            refresh('failed')
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
    except (OSError, ValueError, RuntimeError, sqlite3.Error, http.client.HTTPException) as error:
        diagnostics.log(f'Client error: {error}')
        print(f'Chat could not continue: {error}', file=sys.stdout)
        status = 1
    finally:
        terminal.color('reset')
    raise SystemExit(status)
