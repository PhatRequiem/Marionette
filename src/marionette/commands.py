"""Recognize supported chat commands and execute shared-history actions."""
import diagnostics
from permissions import require_command

HELP_TEXT = 'Available commands: /clear and /exit.'


def recognize(message, source):
    """Preserve terminal-only exit/help; Discord only interprets /clear."""
    command = message.strip()
    if command == '/clear':
        return 'clear'
    if source == 'terminal':
        if command == '/exit':
            return 'exit'
        if message.startswith('/'):
            return 'help'
    return None


def execute_clear(conversation, identity):
    """Called under the conversation lock; authorize before touching history."""
    owner_uuid = conversation.profiles.data['owner_uuid'] if conversation.profiles else None
    try:
        require_command('/clear', identity, owner_uuid)
    except PermissionError as error:
        diagnostics.log(f'Command denied: /clear; {error}')
        return str(error)
    if conversation.pending is not None:
        conversation.pending.result()
        conversation.pending = None
    conversation.history = []
    diagnostics.log('Chat history cleared.')
    return 'Chat history cleared.'
