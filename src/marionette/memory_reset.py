"""Owner-only live memory reset, called under the conversation turn lock."""
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

import diagnostics
from storage import now
from reset_boundary import marker


def preflight(conversation):
    root = conversation.profiles.path.parent.parent
    expected = (root/'contacts/profiles.json', root/'contact_notes', root/'soul/profile.json')
    if (conversation.profiles.path, conversation.contact_notes.directory, conversation.soul.path) != expected:
        raise ValueError('Reset requires the documented contact, notes, and soul paths.')
    if conversation.store is None or not conversation.session_id:
        raise ValueError('Reset requires a live conversation store.')
    database = Path(conversation.store.db.execute('PRAGMA database_list').fetchone()[2])
    if database.parent != root/'conversations':
        raise ValueError('Reset requires logs inside the active data directory; alternate paths need operator review.')
    for name in ('contacts', 'contact_notes', 'soul', 'conversations', 'session', 'identities', 'characters', 'self'):
        path = root/name
        if path.is_symlink() or (path.exists() and any(p.is_symlink() for p in path.rglob('*'))):
            raise ValueError('Reset refuses symbolic links in memory paths.')
    if not (root/'session/log-session.json').is_file():
        raise ValueError('Reset requires the active logging session descriptor.')
    return root, database


def reset_memory(conversation):
    root, database = preflight(conversation)
    owner_id = conversation.profiles.data['owner_uuid']
    owner = copy.deepcopy(next(p for p in conversation.profiles.profiles if p['uuid'] == owner_id))
    owner.update(name='Phat', preferred_name=None, timezone=None, created_at=now(), updated_at=now())
    owner['linked_accounts'] = [a for a in owner['linked_accounts'] if a['service'] == 'discord']
    soul_id = conversation.soul.read()['uuid']
    generation = str(uuid.uuid4())
    # Clear the native KV/cache through its existing empty-context preparation path.
    # No new prompt, inference setting, or model process is introduced.
    conversation.api.system_prompt = None
    conversation.api.tools = ()
    conversation.api.prepare([])
    conversation.resetting = True
    try:
        conversation.profiles.data = {'schema_version':2, 'owner_uuid':owner_id, 'profiles':[owner]}
        conversation.profiles.save()
        conversation.terminal_profile = owner
        conversation.soul.write({'schema_version':2, 'uuid':soul_id,
            'revisions':[conversation.soul.revision('', 'memory reset', '')]})
        conversation.store.reset_memory(conversation.session_id, generation)
        conversation.histories.clear()
        conversation.pending = None
        conversation.pending_key = None
        conversation.epoch = generation
        # Keep the live DB and sidecars open. Other memory copies are removed.
        keep = {database, Path(str(database)+'-wal'), Path(str(database)+'-shm'),
                conversation.profiles.path, conversation.soul.path}
        for name in ('contacts','contact_notes','soul','conversations','identities','characters','self'):
            directory = root/name
            if not directory.exists():
                continue
            for path in directory.iterdir():
                if path in keep:
                    continue
                if path.is_dir(): shutil.rmtree(path)
                else: path.unlink()
            if name in ('identities','characters','self'): directory.rmdir()
        for path in (root/'session').iterdir():
            if path.name not in ('chat.sock','log-session.json'):
                if path.is_dir(): shutil.rmtree(path)
                else: path.unlink()
        from vault_tool import configured_tools
        conversation.api.tools = (conversation.soul.bind(conversation.api),) + configured_tools(root)
        descriptor = root/'session/log-session.json'
        info = json.loads(descriptor.read_text())
        info['generation'] = generation
        temporary = descriptor.with_suffix('.tmp')
        temporary.write_text(json.dumps(info))
        temporary.chmod(0o600)
        os.replace(temporary, descriptor)
        # Ordered markers drain old pipe bytes before reopening capture for this epoch.
        diagnostics.write(marker(generation)+b'\n')
        sys.stdout.buffer.write(marker(generation)+b'\n')
        sys.stdout.buffer.flush()
        deadline = time.monotonic()+10
        while True:
            row = conversation.store.db.execute('SELECT ram_ack,terminal_ack FROM memory_epoch').fetchone()
            if tuple(row) == (generation, generation): break
            if time.monotonic() >= deadline:
                raise RuntimeError('Reset capture boundary was not acknowledged; chat is blocked. Restart before continuing.')
            time.sleep(.025)
        conversation.api.prepare([])
        conversation.resetting = False
        return 'Memory reset. Soul, contact notes, and all chat histories cleared. Your owner profile and both permanent IDs were preserved.'
    except BaseException:
        # Do not resume generation with a partially reset state.
        conversation.resetting = True
        raise
