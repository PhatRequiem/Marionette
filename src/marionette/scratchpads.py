"""Bounded session-only working state; shared by serialized conversations."""
import json

from jsonschema import ValidationError
from qwen_agent.tools import BaseTool

LIMITS = {'focus': 1500, 'working_space': 3000, 'intentions': 1500}


class Scratchpads:
    def __init__(self):
        self.clear()

    def clear(self):
        self.contents = dict.fromkeys(LIMITS, '')

    def read(self):
        return {name: {'content': text, 'characters': len(text),
                       'character_limit': LIMITS[name],
                       'remaining_characters': LIMITS[name] - len(text)}
                for name, text in self.contents.items()}

    def update(self, pad, content):
        if not isinstance(pad, str) or pad not in LIMITS:
            raise ValueError('Choose focus, working_space, or intentions.')
        if not isinstance(content, str):
            raise ValueError('Content must be a string.')
        if any(not c.isprintable() and c not in '\n\t' for c in content):
            raise ValueError('Only printable text, newlines and tabs are allowed.')
        if len(content) > LIMITS[pad]:
            raise ValueError(f'{pad} allows {LIMITS[pad]} characters; proposed {len(content)} '
                             f'exceeds the limit by {len(content) - LIMITS[pad]}. Shorten and retry.')
        self.contents[pad] = content

    def bind(self, api):
        api.scratchpads = self
        names = {'read_scratchpads', 'update_scratchpad'}
        api.tools = tuple(t for t in api.tools if t.name not in names) + (
            ReadScratchpads(self), UpdateScratchpad(self))


class ReadScratchpads(BaseTool):
    name = 'read_scratchpads'
    description = 'Read current Focus, Working Space and Intentions, including character limits. Session-only state shared across conversations.'
    parameters = {'type': 'object', 'properties': {}, 'required': []}

    def __init__(self, store):
        super().__init__()
        self.store = store

    def call(self, params, **kwargs):
        try:
            args = self._verify_json_format_args(params)
            if args:
                raise ValueError('No arguments are accepted.')
            return json.dumps({'success': True, 'pads': self.store.read()}, ensure_ascii=False)
        except (ValueError, ValidationError) as exc:
            return json.dumps({'success': False, 'error': str(exc)})


class UpdateScratchpad(ReadScratchpads):
    name = 'update_scratchpad'
    description = ('Replace one temporary scratchpad: focus (1500 characters), working_space (3000), '
                   'or intentions (1500). Supply its complete new content; empty clears it. '
                   'Other pads stay unchanged. State lasts until restart or memory reset; '
                   'intentions do not schedule or execute actions. A successful result confirms the edit.')
    parameters = {'type': 'object', 'properties': {
        'pad': {'type': 'string', 'enum': list(LIMITS)},
        'content': {'type': 'string', 'description': 'Complete replacement text, or empty to clear.'}},
        'required': ['pad', 'content']}

    def call(self, params, **kwargs):
        success, error = False, None
        try:
            args = self._verify_json_format_args(params)
            if set(args) != {'pad', 'content'}:
                raise ValueError('Supply only pad and content.')
            self.store.update(args['pad'], args['content'])
            success = True
        except (ValueError, ValidationError) as exc:
            error = str(exc)
        return json.dumps({'success': success, 'error': error, 'pads': self.store.read()}, ensure_ascii=False)
