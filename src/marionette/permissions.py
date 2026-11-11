"""Command authorization for the resolved sender's own conversation."""


def require_command(command, identity, conversation_id):
    """No command can target a different conversation or unresolved sender."""
    if (command != '/clear' or not identity or not identity.get('person_uuid')
            or identity.get('source') not in ('terminal', 'discord')
            or not identity.get('sender_id')
            or conversation_id != identity['source'] + ':' + identity['sender_id']):
        raise PermissionError('Permission denied: you can only clear your own conversation.')
