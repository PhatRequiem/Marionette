"""Recognize supported chat commands and execute conversation-scoped actions."""
import diagnostics
from permissions import require_command

HELP_TEXT = 'Available commands: /clear, /resetmemory and /shutdown (owner only), /startdiscord and /stopdiscord (owner, terminal only), and /exit.'


def recognize(message, source):
    """Preserve terminal-only exit/help; Discord also accepts owner-only reset and shutdown."""
    command = message.strip()
    if command == '/shutdown':
        return 'shutdown'
    if command == '/resetmemory':
        return 'resetmemory'
    if command == '/clear':
        return 'clear'
    if source == 'terminal':
        if command in ('/startdiscord', '/stopdiscord'):
            return command[1:]
        if command == '/exit':
            return 'exit'
        if message.startswith('/'):
            return 'help'
    return None


def execute_clear(conversation, identity):
    """Called under the conversation lock; authorize before touching history."""
    try:
        require_command('/clear', identity, conversation.key)
    except PermissionError as error:
        diagnostics.log(f'Command denied: /clear; {error}')
        return str(error)
    conversation.finish_preparation()
    conversation.history = []
    diagnostics.log(f'Chat history cleared: conversation={conversation.key}.')
    return 'Chat history cleared.'
