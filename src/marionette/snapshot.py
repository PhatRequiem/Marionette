"""Standalone setup and message snapshots. Never registered with the model."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

import log_snapshot
import startup_snapshot


def build_snapshot(evidence=None, message=None, *, include_setup=True):
    """Combine independent evidence without backfilling historical message facts."""
    if evidence is not None and not isinstance(evidence, dict):
        raise ValueError("Setup evidence must be an object.")
    setup = None
    if include_setup:
        supplied = {} if evidence is None else dict(evidence)
        session = supplied.pop('session', None)
        if session is not None and (not isinstance(session, str) or not session.strip()):
            raise ValueError('Setup session must be a nonempty string.')
        setup = startup_snapshot.build_snapshot(supplied)
        if message is not None and supplied.get('values'):
            if session != message['session']:
                raise ValueError('Combined setup evidence must identify the selected message session.')
        setup['session'] = session
        for key in ('schema_version', 'report_type', 'captured_at', 'connected_to_model'):
            setup.pop(key)
        # Each fact retains its own status and shares the explicitly dated source.
        for group in ('application', 'model', 'runtime', 'limits', 'interfaces', 'tools'):
            for fact in setup[group].values():
                if isinstance(fact, dict) and 'status' in fact:
                    fact['provenance'] = dict(setup['evidence'], session=session)
    elif evidence is not None:
        raise ValueError('Setup evidence requires the setup section.')
    if message is not None:
        message = dict(message)
        # These were reserved placeholders, never populated by the log reader.
        message.pop('model', None)
        message.pop('connections', None)
        message.pop('schema_version', None)
    report = {
        'schema_version': 1,
        'report_type': 'snapshot',
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'connected_to_model': False,
        'setup': setup,
        'message': message,
        'limitations': [
            'Setup observations and message evidence have separate scopes and times; setup values do not backfill message records.',
            'No live probes or model requests are performed. Supplied setup evidence remains caller-reported or synthetic.',
        ],
    }
    log_snapshot.check_size(report)
    return report


def main(default_section='setup'):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--section', choices=('setup', 'message', 'both'), default=default_section)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--message-id')
    parser.add_argument('--conversation-id')
    parser.add_argument('--database')
    parser.add_argument('--session')
    parser.add_argument('--discord-log', action='append', default=[])
    parser.add_argument('logs', nargs='*')
    args = parser.parse_args()
    try:
        evidence, message = None, None
        if args.evidence:
            with args.evidence.open('rb') as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                raise ValueError('Evidence exceeds 64 KiB.')
            evidence = json.loads(raw)
            if not isinstance(evidence, dict):
                raise ValueError('Setup evidence must be an object.')
        if args.section in ('message', 'both'):
            if not args.message_id or not args.conversation_id:
                raise ValueError('Message section requires message and conversation IDs.')
            if args.database:
                if not args.session or args.logs or args.discord_log:
                    raise ValueError('Database mode needs --session and cannot be mixed with text files.')
                message = log_snapshot.database_snapshot(args.database, args.session, args.message_id, args.conversation_id)
            else:
                if args.session:
                    raise ValueError('--session requires --database; text mode uses the log session name.')
                message = log_snapshot.snapshot(args.logs, args.message_id, args.conversation_id, discord_paths=args.discord_log)
        elif any((args.message_id, args.conversation_id, args.database, args.session, args.discord_log, args.logs)):
            raise ValueError('Message arguments require --section message or both.')
        result = build_snapshot(evidence, message, include_setup=args.section != 'message')
    except (ValueError, TypeError, LookupError, OSError, sqlite3.Error) as error:
        parser.exit(1, f'Snapshot unavailable: {error}\n')
    print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
