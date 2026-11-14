"""Recognize supported chat commands and execute conversation-scoped actions."""
import diagnostics
from permissions import require_command

HELP_TEXT = """Available commands:
/help — Show all commands and their descriptions.
/clear — Clear this conversation's active context; keep saved records and notes.
/resetmemory — Reset personal memory, conversations and logs; keep permanent IDs and owner mapping. Model stays loaded. (owner only)
/shutdown — Shut down Marionette and disconnect Discord; keep saved memory. (owner only)
/startdiscord — Start the Discord connection in the background. (owner, terminal only)
/stopdiscord — Disconnect Discord; keep main chat running. (owner, terminal only)
/refreshsetup — Recheck setup and refresh the setup sheet and its existing Obsidian copy. (owner, terminal only)
/exit — Exit main chat and disconnect Discord; keep saved memory. (terminal only)"""


def recognize(message, source):
    """Recognize shared commands while preserving terminal-only controls."""
    command = message.strip()
    if command == '/help':
        return 'help'
    if command == '/shutdown':
        return 'shutdown'
    if command == '/resetmemory':
        return 'resetmemory'
    if command == '/clear':
        return 'clear'
    if source == 'terminal':
        if command in ('/startdiscord', '/stopdiscord', '/refreshsetup'):
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
