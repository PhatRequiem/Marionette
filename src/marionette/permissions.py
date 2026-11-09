"""Command authorization for identities resolved by the application."""


def require_command(command, identity, owner_uuid):
    """Deny unknown commands and unidentified/non-owner senders by default."""
    if (command != '/clear' or not owner_uuid or not identity
            or identity.get('person_uuid') != owner_uuid):
        raise PermissionError('Permission denied: only the owner profile can clear shared history.')
