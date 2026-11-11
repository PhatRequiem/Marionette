"""Command authorization for the resolved sender's own conversation."""


def require_command(command, identity, conversation_id):
    """No command can target a different conversation or unresolved sender."""
    if (command != '/clear' or not identity or not identity.get('contact_uuid')
            or identity.get('source') not in ('terminal', 'discord')
            or not identity.get('sender_id')
            or conversation_id != identity['source'] + ':' + identity['sender_id']):
        raise PermissionError('Permission denied: you can only clear your own conversation.')


def require_reset(identity, profiles):
    if not identity or profiles is None or identity.get('contact_uuid') != profiles.data['owner_uuid']:
        raise PermissionError('Permission denied: /resetmemory is owner-only.')
    try:
        resolved = profiles.resolve(identity['source'], identity['sender_id'])
    except (KeyError, ValueError):
        raise PermissionError('Permission denied: unresolved owner account.') from None
    if resolved['contact_uuid'] != profiles.data['owner_uuid']:
        raise PermissionError('Permission denied: /resetmemory is owner-only.')
