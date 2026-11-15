"""Owner-only live memory reset, called under the conversation turn lock."""
import json
import os
from pathlib import Path
import sys
import time
import uuid

import diagnostics
from reset_boundary import INCOMPLETE, marker, require_complete

MEMORY_DIRECTORIES = ('contacts', 'contact_notes', 'soul', 'conversations',
                      'session', 'identities', 'characters', 'self')


def preflight(conversation):
    root = conversation.profiles.path.parent.parent
    expected = (root/'contacts/profiles.json', root/'contact_notes', root/'soul/profile.json')
    if (conversation.profiles.path, conversation.contact_notes.directory, conversation.soul.path) != expected:
        raise ValueError('Reset requires the documented contact, notes, and soul paths.')
    require_complete(root)
    if conversation.store is None or not conversation.session_id:
        raise ValueError('Reset requires a live conversation store.')
    database = Path(conversation.store.db.execute('PRAGMA database_list').fetchone()[2])
    if database.parent != root/'conversations':
        raise ValueError('Reset requires logs inside the active data directory; alternate paths need operator review.')
    for name in MEMORY_DIRECTORIES:
        path = root/name
        if path.is_symlink() or (path.exists() and any(p.is_symlink() for p in path.rglob('*'))):
            raise ValueError('Reset refuses symbolic links in memory paths.')
    if not (root/'session/log-session.json').is_file():
        raise ValueError('Reset requires the active logging session descriptor.')
    config_path = root/'scarecrow/connection.json'
    if config_path.exists():
        config = json.loads(config_path.read_text())
        vault = config.get('vault') if isinstance(config, dict) else None
        if not isinstance(vault, str) or not Path(vault).is_absolute():
            raise ValueError('Reset requires a valid absolute Scarecrow vault path; operator review required.')
        if Path(vault).resolve() != (root/'conversations/obsidian-vault').resolve():
            raise ValueError('Reset refuses an alternate Scarecrow vault; operator review required.')
    return root, database


def clear_files(directory, keep, infrastructure):
    """Erase memory files without removing directories or following links."""
    if directory.is_symlink():
        raise ValueError('Reset refuses symbolic links in memory paths.')
    if not directory.exists() or directory == infrastructure:
        return
    for path in directory.iterdir():
        if path.is_symlink():
            raise ValueError('Reset refuses symbolic links in memory paths.')
        if path in keep:
            continue
        if path.is_dir():
            clear_files(path, keep, infrastructure)
        else:
            path.unlink()


def refresh_tools(conversation, owner):
    """Preserve registration, replacing only bindings that contain erased memory."""
    from contact_notes import UpdateContactNotes
    from contact_profile import UpdateContactProfile
    api = conversation.api
    identity = conversation.profiles.resolve('terminal', owner['uuid'])
    replacements = {
        'update_soul': conversation.soul.bind(api),
        'update_contact_profile': UpdateContactProfile(conversation.profiles, identity),
        # No old note text remains in the adapter. Ordinary turns bind fresh notes.
        'update_contact_notes': UpdateContactNotes(conversation.contact_notes, identity, None),
    }
    api.tools = tuple(replacements.get(tool.name, tool) for tool in api.tools)
    if any(tool.name == 'query_logs' for tool in api.tools):
        conversation.bind_log_query()
    api.response_messages = None


def verify(conversation, owner, soul_id, names, keep, infrastructure, directories, root):
    registry = json.loads(conversation.profiles.path.read_text())
    if registry['owner_uuid'] != owner['uuid'] or registry['profiles'] != [owner]:
        raise RuntimeError('Reset verification failed: owner profile does not match the cleared identity.')
    state = conversation.soul.read()
    if (state['uuid'] != soul_id or len(state['revisions']) != 1 or
            state['revisions'][0]['name'] or state['revisions'][0]['content']):
        raise RuntimeError('Reset verification failed: soul was not cleared.')
    if conversation.histories or conversation.pending is not None:
        raise RuntimeError('Reset verification failed: active history remains.')
    if {tool.name for tool in conversation.api.tools} != names:
        raise RuntimeError('Reset verification failed: tool registration changed.')
    for table in ('messages', 'failures', 'error_evidence', 'failure_events'):
        if conversation.store.db.execute('SELECT count(*) FROM ' + table).fetchone()[0]:
            raise RuntimeError('Reset verification failed: old stored memory remains.')
    if conversation.store.db.execute('SELECT count(*) FROM sessions').fetchone()[0] != 1:
        raise RuntimeError('Reset verification failed: old sessions remain.')
    for directory in directories:
        if not directory.is_dir() or directory.is_symlink():
            raise RuntimeError('Reset verification failed: directory structure changed.')
    for name in MEMORY_DIRECTORIES:
        for path in (root/name).rglob('*'):
            if path == infrastructure or path.is_relative_to(infrastructure):
                continue
            if path.is_symlink() or (not path.is_dir() and path not in keep):
                raise RuntimeError('Reset verification failed: a memory copy remains.')


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def reset_memory(conversation):
    root, database = preflight(conversation)
    owner_id = conversation.profiles.data['owner_uuid']
    previous_owner = next(p for p in conversation.profiles.profiles if p['uuid'] == owner_id)
    # Retain only identity/account authorization. A neutral name and terminal
    # access keep the schema and profile chooser usable without old personal data.
    # save() supplies a fresh updated_at; the old creation time is forgotten.
    owner = {'uuid': owner_id, 'name': 'Owner', 'preferred_name': None,
             'timezone': None, 'created_at': None, 'updated_at': None,
             'terminal_enabled': True,
             'linked_accounts': [{'service': 'discord', 'account_id': link['account_id']}
                                 for link in previous_owner['linked_accounts']
                                 if link['service'] == 'discord']}
    soul_id = conversation.soul.read()['uuid']
    names = {tool.name for tool in conversation.api.tools}
    descriptor = root/'session/log-session.json'
    info = json.loads(descriptor.read_text())
    if not isinstance(info, dict):
        raise ValueError('Invalid logging session descriptor.')
    infrastructure = root/'conversations/obsidian-vault/.obsidian'
    directories = {path for name in MEMORY_DIRECTORIES if (root/name).exists()
                   for path in (root/name, *(root/name).rglob('*'))
                   if path.is_dir() and path != infrastructure and not path.is_relative_to(infrastructure)}
    generation = str(uuid.uuid4())
    incomplete = root/INCOMPLETE
    fd = os.open(incomplete, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    conversation.resetting = True
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write('{"schema_version":1,"state":"incomplete"}\n')
            stream.flush()
            os.fsync(stream.fileno())
        sync_directory(root)
        if conversation.reset_input is not None:
            conversation.reset_input()
        conversation.profiles.data = {'schema_version':2, 'owner_uuid':owner_id, 'profiles':[owner]}
        conversation.profiles.save()
        conversation.terminal_profile = conversation.profiles.profiles[0]
        conversation.soul.write({'schema_version':2, 'uuid':soul_id,
            'revisions':[conversation.soul.revision('', 'memory reset', '')]})
        conversation.store.reset_memory(conversation.session_id, generation)
        conversation.histories.clear()
        conversation.pending = None
        conversation.pending_key = None
        conversation.epoch = generation
        keep = {database, Path(str(database)+'-wal'), Path(str(database)+'-shm'),
                conversation.profiles.path, conversation.soul.path,
                root/'session/chat.sock', descriptor}
        for name in MEMORY_DIRECTORIES:
            clear_files(root/name, keep, infrastructure)
        # Keep the empty mirror's directories recognizable without enabling reads
        # from Obsidian's old cache. Only a completed full sync restores its marker.
        generated = root/'conversations/obsidian-vault/Generated'
        if generated.is_dir():
            reset_marker = generated/'.marionette-reset'
            reset_marker.write_text('Marionette cleared mirror v1\n')
            keep.add(reset_marker)
        refresh_tools(conversation, owner)
        info['generation'] = generation
        temporary = descriptor.with_suffix('.tmp')
        temporary.write_text(json.dumps(info))
        temporary.chmod(0o600)
        os.replace(temporary, descriptor)
        # Prepare with the same tools and application guidance, and a blank soul.
        # A failure leaves registrations intact and the persistent guard in place.
        conversation.api.prepare([])
        diagnostics.write(marker(generation)+b'\n')
        sys.stdout.buffer.write(marker(generation)+b'\n')
        sys.stdout.buffer.flush()
        deadline = time.monotonic()+10
        while True:
            row = conversation.store.db.execute('SELECT ram_ack,terminal_ack FROM memory_epoch').fetchone()
            if tuple(row) == (generation, generation):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('Reset capture boundary was not acknowledged; stop and finish the maintenance reset.')
            time.sleep(.025)
        verify(conversation, owner, soul_id, names, keep, infrastructure, directories, root)
        if conversation.reset_input is not None:
            conversation.reset_input()
        # Last fallible step: any earlier error retains the restart guard. A crash
        # before this unlink reaches disk can conservatively restore that guard.
        incomplete.unlink()
        conversation.resetting = False
        return 'Memory reset. Soul, contact notes, and all chat histories cleared. Owner profile details cleared; your UUID, Discord links, and owner status remain. Soul UUID, tools, and folders were preserved.'
    except BaseException:
        conversation.resetting = True
        raise
