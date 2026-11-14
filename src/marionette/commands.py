"""Recognize supported chat commands and execute conversation-scoped actions."""
import diagnostics
from permissions import require_command

HELP_TEXT = """Available commands:
/help — Show all commands and their descriptions.
/ddm [on|off] — Set general Discord DM access; omit on/off to check. Per-user rules remain; your access stays open. (owner only)
/ddm allow <user> — Allow a Discord user ID or mention even when general DMs are off. (owner only)
/ddm block <user> — Block a Discord user ID or mention even when general DMs are on. (owner only)
/status — Show model availability, Discord, DM access, Scarecrow and uptime. (owner only)
/connections — Show terminal, Discord and Scarecrow connection states. (owner only)
/context — Show this conversation’s retained context usage and remaining budget.
/sync — Refresh the full Obsidian mirror now. (owner only)
/cancel — Stop current generation without clearing history or shutting down. (owner only)
/clear — Clear this conversation's active context; keep saved records and notes.
/resetmemory — Reset personal memory, conversations and logs; keep permanent IDs and owner mapping. Model stays loaded. (owner only)
/shutdown — Shut down Marionette and disconnect Discord; keep saved memory. (owner only)
/startdiscord — Start the Discord connection in the background. (owner, terminal only)
/stopdiscord — Disconnect Discord; keep main chat running. (owner, terminal only)
/refreshsetup — Recheck setup and refresh the setup sheet and its existing Obsidian copy. (owner, terminal only)
/exit — Exit main chat and disconnect Discord; keep saved memory. (terminal only)"""


def render_help(source='terminal', *, colored=False):
    """Keep ANSI presentation in terminal output, never Discord replies."""
    from style import paint
    colored = colored and source == 'terminal'
    lines = [paint('Available commands:', 'success', colored)]
    for line in HELP_TEXT.splitlines()[1:]:
        if source == 'discord' and 'terminal only)' in line:
            continue
        command, description = line.split(' — ', 1)
        restriction = ''
        if description.endswith(')') and ' (' in description:
            description, restriction = description.rsplit(' (', 1)
            restriction = ' (' + restriction
        lines.append(paint(command, 'meta', colored) + ' — ' +
                     paint(description, 'data', colored) + paint(restriction, 'warning', colored))
    return '\n'.join(lines)


def recognize(message, source):
    """Recognize shared commands while preserving terminal-only controls."""
    command = message.strip()
    if command.split()[:1] == ['/ddm']:
        return 'ddm'
    if command in ('/status', '/connections', '/context', '/sync', '/cancel'):
        return command[1:]
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


def execute_operator(conversation, command, identity):
    """Operator observations/actions use existing local components, never generation."""
    from permissions import require_reset
    from pathlib import Path
    import json
    import time
    import sqlite3
    import http.client
    c = conversation
    if command != 'context':
        try:
            require_reset(identity, c.profiles)
        except PermissionError as error:
            return str(error)
    if command == 'cancel':
        return c.cancel(identity['source'], identity['sender_id'])
    if command == 'context':
        tokens = c.api.count(c.history)
        remaining = max(0, c.capacity - c.reserve - tokens - 1)
        return (f'Retained context (including template/tools): {tokens} / {c.capacity} tokens.\n'
                f'Reply allowance: {c.reserve}; remaining input budget: {remaining} tokens.\n'
                'New message metadata and refreshed notes also use that input budget.')
    control = c.discord_control
    if control is None:
        return 'Operator connections are unavailable in this session.'
    if command == 'sync':
        if not control.database:
            return 'Conversation database unavailable; mirror not refreshed.'
        from conversation_vault import sync
        try:
            sync(control.database, control.data / 'contacts/profiles.json',
                 control.data / 'contact_notes', Path(__file__).resolve().parents[2] / 'docs')
        except sqlite3.Error as error:
            raise RuntimeError('Mirror sync failed; database unavailable or busy. Retry /sync.') from error
        if c.setup_refresh:
            c.setup_refresh(reason='sync')
        return 'Obsidian mirror refreshed: conversations, contact notes and Active documentation.'
    from operator_status import probe
    from vault_diagnostics import current_status
    discord = probe(control.address) if control.address else None
    vault = current_status(control.data)
    lines = ['Terminal: attached',
             'Discord: ' + (discord['discord'] if discord else 'unavailable'),
             'Scarecrow: ' + vault['status']]
    if command == 'status':
        health = 'unavailable'
        try:
            with c.api.opener.open(c.api.address + '/health', timeout=2) as response:
                health = 'online' if json.loads(response.read(4096)).get('status') == 'ok' else 'unhealthy'
        except (OSError, ValueError, http.client.HTTPException):
            pass
        policy = c.discord_access.policy() if c.discord_access else {}
        lines = [f'Model: {health}', f'Uptime: {int(time.monotonic() - c.started_at)} seconds',
                 'General Discord DMs: ' + ('ON' if policy.get('allow_other_dms') else 'OFF') +
                 f"; allowed exceptions: {len(policy.get('allowed', []))}; blocked: {len(policy.get('blocked', []))}", *lines]
    return '\n'.join(lines)
