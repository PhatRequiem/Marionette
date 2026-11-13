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
from urllib.parse import quote

from storage import now
from conversation_refs import conversation_reference, render_note_links


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
    with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(content if isinstance(content, bytes) else content.encode('utf-8'))
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def sync(database, profiles=None, contact_notes=None, docs=None):
    database = Path(database).absolute()
    vault = database.parent / 'obsidian-vault'
    # Destination is deliberately fixed under the reset-managed conversations folder.
    for path in (database, *database.parents):
        if path.is_symlink():
            raise ValueError('Vault refuses symbolic links.')
    if vault.is_symlink() or (vault.exists() and any(p.is_symlink() for p in vault.rglob('*'))):
        raise ValueError('Vault refuses symbolic links.')
    notes_directory = Path(contact_notes).absolute() if contact_notes else None
    if notes_directory and any(p.is_symlink() for p in (notes_directory, *notes_directory.parents)):
        raise ValueError('Contact notes source refuses symbolic links.')
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

        def title(contact):
            name = label(names.get(contact, 'Unknown contact'))
            return re.sub(r'[^\w -]', '_', name)[:60].strip() or 'Contact'

        def note(contact, kind=''):
            return folder(contact) + '/' + title(contact) + (' - ' + kind if kind else '')

        def folder(contact):
            # The ID suffix separates people with identical names. Names are only labels.
            return f'Contacts/{title(contact)}-{key(contact)}'

        def link(path, title):
            return f'[[Generated/{path}|{label(title)}]]'

        titles = {}
        destinations = {}
        for (session, conversation, contact), rows in groups.items():
            base = folder(contact)
            slug = base + '/Conversations/' + title(contact) + ' - ' + rows[0]['recorded_at'][:10] + ' - conversation-' + key(session, conversation, contact)[:12]
            destinations[conversation_reference(session, conversation, contact)] = slug + '.md'
            titles[slug] = rows[0]['recorded_at'][:10] + ' ' + rows[0]['source'] + ' ' + key(session, conversation)[:8]
            contacts[contact].add(slug)
            front = {'session_id': session, 'conversation_id': conversation,
                     'contact_uuid': contact, 'synced_at': captured,
                     'first_message_at': rows[0]['recorded_at'],
                     'last_message_at': rows[-1]['recorded_at']}
            text = '---\n' + ''.join(f'{k}: {json.dumps(v)}\n' for k, v in front.items()) + '---\n\n'
            text += '# Conversation\n\nGenerated from SQLite. Saved replies do not prove delivery.\n\n'
            text += link(note(contact), names.get(contact, 'Unknown contact')) + ' · ' + link(note(contact, 'Dates'), 'Dates') + '\n\n'
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
            notes = None
            if notes_directory and contact:
                if not re.fullmatch(r'[A-Za-z0-9_-]+', contact):
                    raise ValueError('Invalid contact ID for notes filename.')
                source = notes_directory / (contact + '.md')
                if source.is_symlink():
                    raise ValueError('Contact notes source refuses symbolic links.')
                if source.exists():
                    # Read the saved Markdown without initializing or editing the source.
                    with source.open(encoding='utf-8', newline='') as handle:
                        notes = handle.read()
            pages[note(contact, 'Notes') + '.md'] = render_note_links(notes, destinations, note(contact, 'Notes') + '.md') if notes is not None else '# Contact notes\n\nNo saved contact-notes file was available at sync time.\n'
            pages[note(contact) + '.md'] = '# ' + label(names.get(contact, 'Unknown contact')) + '\n\n' + literal(contact) + '\n' + link(note(contact, 'Dates'), 'Dates') + ' · ' + link(note(contact, 'Notes'), 'Contact notes') + '\n\n' + ''.join('- ' + link(s, titles[s]) + '\n' for s in sorted(conversations))
            text = '# Dates\n\n' + link(note(contact), 'Profile') + '\n\n'
            for day, conversations in sorted(days[contact].items(), reverse=True):
                text += '## ' + day + '\n\n' + ''.join('- ' + link(s, titles[s]) + '\n' for s in sorted(conversations)) + '\n'
            pages[note(contact, 'Dates') + '.md'] = text
        # The contact index is the explicit shared navigation hub; dates stay local.
        pages['Contacts.md'] = '# Contacts\n\nChoose a contact to browse their profile, dates and conversations.\n\nLast synchronized: ' + captured + '\n\n' + ''.join('- ' + link(note(c), names.get(c, 'Unknown contact')) + '\n' for c in sorted(contacts, key=lambda c: (names.get(c, '').casefold(), c or '')))
        documentation_count = 0
        if docs is not None:
            source_docs = Path(docs).absolute() / 'active'
            if any(p.is_symlink() for p in (source_docs, *source_docs.parents)):
                raise ValueError('Documentation source refuses symbolic links.')
            if not source_docs.is_dir():
                raise ValueError('Active documentation source directory is missing.')
            index = '# Self documentation\n\nOne-way mirror of active project documentation. Refresh with the vault sync command.\n\nCurrent operation describes how Marionette works. Setup and maintenance covers installation and upkeep. Experiments, history and ideas stay outside this vault.\n\nLinks within active documentation are preserved. Files outside docs/active are not mirrored.\n\n'
            for source in sorted(source_docs.rglob('*')):
                relative = source.relative_to(source_docs)
                if any(part.startswith('.') for part in relative.parts):
                    continue  # Vault/editor settings are not project documentation.
                if source.is_symlink():
                    raise ValueError('Documentation source refuses symbolic links.')
                if not source.is_file():
                    continue
                destination = 'Self documentation/active/' + relative.as_posix()
                pages[destination] = source.read_bytes()
                section_index = len(relative.parts) == 2 and relative.stem == relative.parent.name and relative.suffix == '.md'
                if len(relative.parts) == 1 or section_index:
                    heading = relative.stem.replace('-', ' ').capitalize() if section_index else relative.stem
                    index += '- [' + label(heading) + '](' + quote(destination, safe='/') + ')\n'
                documentation_count += 1
            pages['Self documentation.md'] = index
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
        for old in generated.rglob('*'):
            managed_document = old.is_relative_to(generated / 'Self documentation')
            if old.is_file() and (old.suffix == '.md' or managed_document) and old.relative_to(generated).as_posix() not in pages:
                old.unlink()
        for old in sorted(generated.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if old.is_dir() and old not in (generated / 'Contacts', generated / 'Groups') and not any(old.iterdir()):
                old.rmdir()
        welcome = '# Welcome to Marionette’s vault\n\nBrowse Marionette’s saved records and reference material.\n\n- [[Generated/Contacts|Contacts]] — profiles, contact notes and conversations, organized by contact with their own date indexes.\n'
        if docs is not None:
            welcome += '- [[Generated/Self documentation|Self documentation]] — current operation, setup and maintenance guides. Experiments, history and ideas stay outside the vault.\n'
        welcome += '\nThis vault is a local mirror. Original records and project files remain authoritative; editing a mirrored page does not update its source. Marionette has no access to this vault yet.\n\nThe mirror refreshes on orderly main-chat shutdown. Refresh manually with `./scripts/native-linux/sync-conversation-vault.sh` when needed.\n\nWelcome and Generated pages are replaced on sync. Keep your own notes in Annotations.\n\nMemory reset clears this entire vault, including annotations and mirrored documentation. Original project documentation is preserved and can be mirrored again.\n'
        atomic_write(vault / 'Welcome.md', welcome)
        db.rollback()
    return {'vault': str(vault), 'conversations': len(groups), 'messages': sum(map(len, groups.values())), 'contacts': len(contacts), 'documentation_files': documentation_count}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('--profiles', type=Path)
    parser.add_argument('--contact-notes', type=Path)
    parser.add_argument('--docs', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    print(json.dumps(sync(args.database, args.profiles, args.contact_notes, args.docs), indent=2))


if __name__ == '__main__':
    main()
