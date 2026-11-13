"""Stable conversation citations shared by sender metadata and the vault exporter."""
import hashlib
import json
import posixpath
import re
from urllib.parse import quote


def conversation_reference(session, conversation, contact):
    identifier = hashlib.sha256(json.dumps((session, conversation, contact)).encode()).hexdigest()[:32]
    return 'marionette-conversation:' + identifier


def render_note_links(content, destinations, note_path):
    """Resolve citation destinations only; never infer sources from note wording."""
    def replace(match):
        destination = destinations.get(match[1])
        if destination is None:
            return match[0]  # Keep missing references visible; do not invent a target.
        relative = posixpath.relpath(destination, posixpath.dirname(note_path))
        return '](' + quote(relative, safe='/') + ')'
    return re.sub(r'\]\((marionette-conversation:[0-9a-f]{32})\)', replace, content)
