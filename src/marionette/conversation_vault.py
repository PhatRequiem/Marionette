"""Operator-only Markdown mirror of saved conversations; no model access."""
import argparse
from collections import defaultdict
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

from storage import now


def key(*parts):
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()[:32]


def label(value):
    """Plain visible labels; IDs, not labels, determine link targets."""
    return re.sub(r'[^\w .:@()\-]', ' ', str(value)).strip() or 'Unknown'


def literal(value):
    """Keep message markup, embeds and wiki links inert in Obsidian."""
    value = str(value)
    fence = '`' * max(3, max((len(m[0]) + 1 for m in re.finditer(r'`+', value)), default=3))
    return f'{fence}text\n{value}\n{fence}\n'


def atomic_write(path, content):
    if path.is_symlink():
        raise ValueError('Vault refuses symbolic links.')
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(content)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def sync(database, profiles=None):
    database = Path(database).absolute()
    vault = database.parent / 'obsidian-vault'
    # Destination is deliberately fixed under the reset-managed conversations folder.
    for path in (database, *database.parents):
        if path.is_symlink():
            raise ValueError('Vault refuses symbolic links.')
    if vault.is_symlink() or (vault.exists() and any(p.is_symlink() for p in vault.rglob('*'))):
        raise ValueError('Vault refuses symbolic links.')
    names = {}
    if profiles and Path(profiles).exists():
        names = {p['uuid']: p['name'] for p in json.loads(Path(profiles).read_text())['profiles']}
    # Reserve the SQLite writer while reading/publishing. No database data is changed.
    # This serializes with reset_memory's deletion transaction: an old export cannot
    # finish after reset has deleted the database's old messages and their copies.
    with closing(sqlite3.connect(database.as_uri() + '?mode=rw', uri=True, timeout=10)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN IMMEDIATE')
        if db.execute('PRAGMA user_version').fetchone()[0] not in (3, 4, 5):
            raise ValueError('Conversation vault requires schema 3–5.')
        groups = defaultdict(list)
        for row in db.execute("SELECT * FROM messages WHERE kind IN ('input','answer') ORDER BY id"):
            groups[(row['session_id'], row['conversation_id'], row['contact_uuid'])].append(row)
        pages, contacts, days = {}, defaultdict(set), defaultdict(lambda: defaultdict(set))
        captured = now()

        def folder(contact):
            # The ID suffix separates people with identical names. Names are only labels.
            name = label(names.get(contact, 'Unknown contact'))
            safe = re.sub(r'[^\w -]', '_', name)[:60].strip() or 'Contact'
            return f'Contacts/{safe}-{key(contact)}'

        def link(path, title):
            return f'[[Generated/{path}|{label(title)}]]'

        titles = {}
        for (session, conversation, contact), rows in groups.items():
            base = folder(contact)
            slug = base + '/Conversations/conversation-' + key(session, conversation, contact)
            titles[slug] = rows[0]['recorded_at'][:10] + ' ' + rows[0]['source'] + ' ' + key(session, conversation)[:8]
            contacts[contact].add(slug)
            front = {'session_id': session, 'conversation_id': conversation,
                     'contact_uuid': contact, 'synced_at': captured,
                     'first_message_at': rows[0]['recorded_at'],
                     'last_message_at': rows[-1]['recorded_at']}
            text = '---\n' + ''.join(f'{k}: {json.dumps(v)}\n' for k, v in front.items()) + '---\n\n'
            text += '# Conversation\n\nGenerated from SQLite. Saved replies do not prove delivery.\n\n'
            text += link(base + '/Profile', names.get(contact, 'Unknown contact')) + ' · ' + link(base + '/Dates', 'Dates') + '\n\n'
            for row in rows:
                day = row['recorded_at'][:10]
                days[contact][day].add(slug)
                speaker = 'Marionette' if row['role'] == 'assistant' else names.get(contact, row['role'])
                text += f"## {label(speaker)} — {row['recorded_at']}\n\nRecord {row['id']}\n\n"
                metadata = {k: row[k] for k in ('id','message_id','contact_uuid','source','sender_id','recorded_at','role','kind','status')}
                metadata['speaker_label'] = speaker
                text += literal(row['content']) + '\n'
                text += '> [!info]- Message identifiers and status\n' + ''.join('> ' + line + '\n' for line in literal(json.dumps(metadata, ensure_ascii=False, indent=2)).splitlines()) + '\n'
            pages[slug + '.md'] = text
        for contact, conversations in contacts.items():
            base = folder(contact)
            pages[base + '/Profile.md'] = '# ' + label(names.get(contact, 'Unknown contact')) + '\n\n' + literal(contact) + '\n' + link(base + '/Dates', 'Dates') + '\n\n' + ''.join('- ' + link(s, titles[s]) + '\n' for s in sorted(conversations))
            text = '# Dates\n\n' + link(base + '/Profile', 'Profile') + '\n\n'
            for day, conversations in sorted(days[contact].items(), reverse=True):
                text += '## ' + day + '\n\n' + ''.join('- ' + link(s, titles[s]) + '\n' for s in sorted(conversations)) + '\n'
            pages[base + '/Dates.md'] = text
        # Plain paths instead of a shared linking hub keep contact graph clusters separate.
        pages['Conversations.md'] = '# Conversations\n\nBrowse Generated/Contacts in the file explorer. Each contact has Profile, Dates and Conversations.\n\nGenerated pages are replaced on sync; keep your own notes in Annotations.\n\nLast synchronized: ' + captured + '\n\n' + ''.join(literal(folder(c)) + '\n' for c in sorted(contacts, key=lambda c: c or ''))
        generated = vault / 'Generated'
        if generated.exists() and not (generated / '.marionette-managed').is_file():
            raise ValueError('Refusing to overwrite an unrecognized Generated directory.')
        for directory in (vault, generated, vault / 'Annotations', generated / 'Contacts', generated / 'Groups'):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        atomic_write(generated / '.marionette-managed', 'Marionette conversation mirror v2\n')
        for filename, content in pages.items():
            destination = generated / filename
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            # mkdir(parents=True) uses default permissions for intermediate folders.
            for parent in destination.parents:
                if parent == generated:
                    break
                parent.chmod(0o700)
            atomic_write(destination, content)
        for old in generated.rglob('*.md'):
            if old.relative_to(generated).as_posix() not in pages:
                old.unlink()
        for old in sorted(generated.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if old.is_dir() and old not in (generated / 'Contacts', generated / 'Groups') and not any(old.iterdir()):
                old.rmdir()
        if not (vault / 'Welcome.md').exists():
            atomic_write(vault / 'Welcome.md', '# Marionette conversations\n\nStart at [[Conversations]]. Use search or graph view to explore.\n\nGenerated pages are replaced on sync. Keep your own notes in Annotations.\nAll vault contents, including annotations, are private memory and are cleared by a memory reset.\n')
        db.rollback()
    return {'vault': str(vault), 'conversations': len(groups), 'messages': sum(map(len, groups.values())), 'contacts': len(contacts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('--profiles', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    print(json.dumps(sync(args.database, args.profiles), indent=2))


if __name__ == '__main__':
    main()
