"""Persistent soul identity and revisioned soul, independent of senders."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import uuid

from qwen_agent.tools import BaseTool
from jsonschema import ValidationError
from contact_notes import ContactNotes, LIMIT


class Soul:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.exists():
            self.write({'schema_version': 2, 'uuid': str(uuid.uuid4()),
                        'revisions': [self.revision('', 'blank initialization', '')]})
        state = self.read()
        if state['schema_version'] == 1:
            state['schema_version'] = 2
            for revision in state['revisions']:
                revision['name'] = ''
            self.write(state)

    @staticmethod
    def revision(content, source, name):
        return {'content': content, 'name': name, 'source': source,
                'created_at': datetime.now(timezone.utc).isoformat()}

    def read(self):
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise ValueError('Soul paths must not be symbolic links.')
        state = json.loads(self.path.read_text(encoding='utf-8'))
        try:
            if state['schema_version'] not in (1, 2) or str(uuid.UUID(state['uuid'])) != state['uuid']:
                raise ValueError('Invalid soul identity.')
            if not isinstance(state['revisions'], list) or not state['revisions']:
                raise ValueError('Soul needs at least one revision.')
            for revision in state['revisions']:
                ContactNotes.validate(revision['content'])
                if state['schema_version'] == 2:
                    self.validate_name(revision['name'])
                if not isinstance(revision['source'], str):
                    raise ValueError('Invalid revision source.')
                datetime.fromisoformat(revision['created_at'])
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError('Malformed soul identity; restore a valid backup.') from exc
        return state

    def write(self, state):
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise ValueError('Soul paths must not be symbolic links.')
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix='.self-')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(state, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            Path(name).unlink(missing_ok=True)

    @staticmethod
    def validate_name(name):
        if not isinstance(name, str) or len(name) > 80 or any(not c.isprintable() for c in name):
            raise ValueError('Name must be printable text of at most 80 characters, or empty.')

    def save(self, content, expected, *, name, source='update_soul'):
        ContactNotes.validate(content)
        self.validate_name(name)
        state = self.read()
        if state['revisions'][-1] != expected:
            raise ValueError('Soul changed; use the returned current state and retry.')
        if (content, name) != (expected['content'], expected['name']):
            state['revisions'].append(self.revision(content, source, name))
            self.write(state)

    def bind(self, api):
        current = self.read()['revisions'][-1]
        # No personal identity text until saved; tool guidance is composed separately.
        parts = (["Name: " + current['name']] if current['name'] else [])
        if current['content']:
            parts.append(current['content'])
        api.system_prompt = '\n\n'.join(parts) or None
        return UpdateSoul(self, current)


class UpdateSoul(BaseTool):
    name = 'update_soul'
    description = ('Proactively maintain your soul: your own name and personal description. '
        'Supply name (up to 80 characters) and/or content (complete personal description, up to 1375 characters). '
        'This describes you, not your contacts; use update_contact_notes for facts about them. Omitted fields are unchanged; empty strings clear fields. '
        'Edits persist and become system context next turn. The ID and revision history are fixed. '
        'Use the returned current state after a rejected edit; only claim a save after success.')
    parameters = {'type': 'object', 'properties': {
        'name': {'type': 'string', 'description': 'Your chosen name, or empty to clear.'},
        'content': {'type': 'string', 'description': 'Complete replacement soul, or empty to clear.'}},
        'required': []}

    def __init__(self, store, current):
        super().__init__()
        self.store, self.current = store, current

    def call(self, params, **kwargs):
        success, error = False, None
        try:
            args = self._verify_json_format_args(params)
            if not args or set(args) - {'name', 'content'}:
                raise ValueError('Supply name and/or content only.')
            if self.current is None:
                raise ValueError('Soul unavailable; repair it before editing.')
            self.store.save(args.get('content', self.current['content']), self.current,
                            name=args.get('name', self.current['name']))
            success = True
        except (ValueError, ValidationError, OSError) as exc:
            error = str(exc)
        try:
            state = self.store.read()
            self.current = state['revisions'][-1]
            uid = state['uuid']
        except (ValueError, OSError):
            self.current, uid = None, None
        content = self.current['content'] if self.current else None
        count = len(content) if content is not None else None
        return json.dumps({'success': success, 'uuid': uid,
                           'name': self.current['name'] if self.current else None,
                           'content': content, 'characters': count, 'character_limit': LIMIT,
                           'remaining_characters': LIMIT-count if count is not None else None,
                           'error': error}, ensure_ascii=False)
