"""Standalone setup-report preview. Not imported by chat or registered as a tool."""
from datetime import datetime, timezone

TOOL_PURPOSES = {
    'update_contact_notes': 'Add, patch, or remove entries about the current contact (1375 characters total).',
    'update_soul': 'Edit your persistent name (80 characters) and self-description (1375 characters).',
}
FIELDS = {
    'model_name': str, 'weight_precision': str, 'runtime_version': str,
    'device': str, 'reasoning_enabled': bool,
    'context_capacity_tokens': int, 'reasoning_answer_allowance_tokens': int,
    'local_inference': bool, 'terminal_available': bool, 'discord_connected': bool,
    'registered_tools': list,
}


def build_snapshot(evidence=None):
    """Format caller-supplied observations; never treat supplied values as live probes."""
    evidence = {} if evidence is None else evidence
    if not isinstance(evidence, dict) or set(evidence) - {'source', 'observed_at', 'synthetic', 'values'}:
        raise ValueError('Expected source, observed_at, synthetic, and values only.')
    values = evidence.get('values', {})
    if not isinstance(values, dict) or set(values) - FIELDS.keys():
        raise ValueError('Unknown observation field.')
    if evidence:
        if not isinstance(evidence.get('source'), str) or not evidence['source'].strip():
            raise ValueError('Evidence needs a source description.')
        stamp = datetime.fromisoformat(evidence.get('observed_at', ''))
        if stamp.utcoffset() is None:
            raise ValueError('Observation timestamp needs a timezone.')
        if type(evidence.get('synthetic')) is not bool:
            raise ValueError('Evidence must explicitly label synthetic true or false.')
    for name, value in values.items():
        if type(value) is not FIELDS[name]:
            raise ValueError(f'Invalid type for {name}.')
        if isinstance(value, str) and (not value.strip() or len(value) > 200 or not value.isprintable()):
            raise ValueError(f'Invalid text for {name}.')
        if type(value) is int and value <= 0:
            raise ValueError(f'{name} must be positive.')
    tools = values.get('registered_tools')
    if tools is not None:
        if any(not isinstance(t, str) or t not in TOOL_PURPOSES for t in tools) or len(tools) != len(set(tools)):
            raise ValueError('Unknown or repeated tool; update the report design before adding capabilities.')
    capacity = values.get('context_capacity_tokens')
    allowance = values.get('reasoning_answer_allowance_tokens')
    if capacity is not None and allowance is not None and allowance >= capacity:
        raise ValueError('Generation allowance must leave room for input.')
    def fact(name):
        return {'value': values.get(name), 'status': (
            'unverified' if name not in values else
            'synthetic_example' if evidence['synthetic'] else 'caller_reported')}
    return {
        'schema_version': 1,
        'report_type': 'application_setup_preview',
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'connected_to_model': False,
        'evidence': {key: evidence.get(key) for key in ('source', 'observed_at', 'synthetic')},
        'application': {'name': 'Marionette', 'local_inference': fact('local_inference')},
        'model': {key: fact(key) for key in ('model_name', 'weight_precision', 'reasoning_enabled')},
        'runtime': {key: fact(key) for key in ('runtime_version', 'device')},
        'limits': {**{key: fact(key) for key in ('context_capacity_tokens', 'reasoning_answer_allowance_tokens')},
                   'meaning': 'Capacity and generation allowance, not current token usage. The allowance is inside the context capacity.'},
        'interfaces': {key: fact(key) for key in ('terminal_available', 'discord_connected')},
        'tools': {'registered': fact('registered_tools'),
                  'purposes': None if tools is None else {t: TOOL_PURPOSES[t] for t in tools}},
        'application_policy': {
            'source': 'Current application design; descriptions are not runtime observations.',
            'conversation_history': 'Separate per Discord sender and terminal profile. Restart starts fresh histories; /clear clears only the originating history.',
            'contact_notes': 'Current contact notes are supplied automatically and persist across restart and /clear.',
            'soul': 'Shared persistent self-profile. Latest name and description become system context when nonempty; earlier revisions are not automatically supplied.',
            'logs': 'Saved records are not automatically recalled. The operator log snapshot is not connected to the model.',
            'access': 'No general file-reading, browsing, shell, or log-reading tools are implemented in this build.',
            'reset': 'Owner-only memory reset clears personal data; ordinary restart does not.',
        },
        'limitations': [
            'No live runtime or Discord probes are performed. Caller-reported evidence is not independently verified.',
            'Observation time is separate from report creation time. This preview does not refresh stale values.',
            'No personal data, credentials, ownership IDs, messages, or soul contents are read.',
            'This report describes the application, not an editable self-profile or a memory of past events.',
        ],
    }


def main():
    # Preserve the established entry point using the common report interface.
    from snapshot import main as snapshot_main
    snapshot_main('setup')


if __name__ == '__main__':
    main()
