"""Search metadata from explicit envelopes, never from conversation prose."""
import json
import re

COLUMNS = ('event_type', 'request_number', 'tool_number', 'tool_name',
           'conversation_id', 'sender_id', 'channel_id', 'outgoing_message_id',
           'contact_uuid', 'display_name', 'preferred_name', 'protocol_tool_call_id')
PREFIXES = {
    'Conversation selected: ': 'conversation_selected',
    'Sender identity: ': 'sender_identity',
    'Prompt budget: ': 'prompt_budget', 'Tool-loop prompt budget: ': 'prompt_budget',
    'Runtime usage: ': 'model_usage', 'Reply completed: ': 'reply_completed',
    'Contact notes supplied: ': 'contact_notes_supplied',
    'Contact notes update rejected: ': 'contact_notes_rejected',
    'Character update rejected: ': 'soul_update_rejected',
    'Rollover preparation failed;': 'cache_preparation_failed',
    'Model Request interrupted: ': 'model_request_interrupted',
    'Tool Call interrupted: ': 'tool_call_interrupted',
    'Connection event: ': 'connection_event',
    'Tool summary: ': 'tool_summary', 'Tool result summary: ': 'tool_result_summary',
    'Tool call identity: ': 'tool_identity', 'Message input: ': 'message_input',
    'Reasoning delta: ': 'reasoning_delta', 'Reasoning: ': 'reasoning', 'Message failed: ': 'message_failed',
    'Message interrupted: ': 'message_interrupted',
    'Model Request failed: ': 'model_request_failed', 'Tool Call failed: ': 'tool_call_failed',
}
DISCORD = {
    'Discord session resumed.': 'discord_resumed',
    'Discord ready; accepting human one-to-one DMs; histories are separate.': 'discord_ready',
    'Discord send started.': 'discord_send_start',
    'Discord send completed.': 'discord_send_end',
    'Local response completed.': 'discord_local_response',
    '========== MESSAGE START | Discord delivery ==========': 'discord_delivery_start',
    'Discord message received.': 'discord_received',
    'Discord chunk sent.': 'discord_chunk_sent',
    'Discord chunk failed.': 'discord_chunk_failed',
    'Discord answer delivered.': 'discord_delivered',
    'Discord disconnected.': 'discord_disconnected',
    'Discord transport connected; awaiting ready/resume.': 'discord_connected',
    '========== MESSAGE END | Discord delivery ==========': 'discord_delivery_end',
    'Discord turn failed; delivery may be partial; no automatic resend.': 'discord_turn_failed',
}


def extract(stream, raw):
    result = dict.fromkeys(COLUMNS)
    if stream not in ('diagnostic', 'discord') or (stream == 'diagnostic' and not raw.startswith(b'Client: ')):
        return tuple(result.values())
    text = raw.decode('utf-8', errors='replace').rstrip('\n')
    if stream == 'diagnostic':
        match = re.fullmatch(r'Client: (?:\[message [^\]\r\n]+\] )?(?:\[request (\d+)\] )?(?:\[tool (\d+)\] )?(.*)', text, re.S)
        if not match:
            return tuple(result.values())
        request, tool, body = match.groups()
        result.update(request_number=request, tool_number=tool)
        for prefix, kind in PREFIXES.items():
            if body.startswith(prefix):
                result['event_type'] = kind
                break
        boundary = re.fullmatch(r'---------- (MODEL REQUEST|TOOL CALL) (START|END)(?: \| (?:completed|returned|failed|interrupted))? ----------', body)
        phase = re.fullmatch(r'========== MESSAGE (START|END) \| (processing|cache preparation)(?: \| (?:completed|failed|interrupted|finished))? ==========', body)
        if boundary:
            result['event_type'] = '_'.join(boundary.groups()).lower().replace(' ', '_')
        elif phase:
            result['event_type'] = phase[2].replace(' ', '_') + '_' + phase[1].lower()
        if result['event_type'] == 'conversation_selected':
            result['conversation_id'] = body[len('Conversation selected: '):].removesuffix('.')
        elif result['event_type'] in ('tool_identity', 'sender_identity'):
            try:
                fields = json.loads(body.split(': ', 1)[1])
                if isinstance(fields, dict):
                    keys = ('name', 'protocol_tool_call_id') if result['event_type'] == 'tool_identity' else ('sender_id', 'contact_uuid', 'display_name', 'preferred_name')
                    for key in keys:
                        value = fields.get(key)
                        if isinstance(value, str):
                            result['tool_name' if key == 'name' else key] = value
            except ValueError:
                pass
    elif stream == 'discord':
        # JSON transcript rows deliberately do not supply diagnostic metadata.
        match = re.fullmatch(r'\d{4}-\d{2}-\d{2}T\S+ (.*?) (\{.*\})', text, re.S)
        if match:
            try:
                fields = json.loads(match[2])
                if isinstance(fields, dict):
                    result['event_type'] = DISCORD.get(match[1])
                    for key in ('sender_id', 'channel_id', 'outgoing_message_id'):
                        value = fields.get(key)
                        if isinstance(value, str) and value.isascii() and value.isdigit():
                            result[key] = value
                    if result['sender_id']:
                        result['conversation_id'] = 'discord:' + result['sender_id']
            except ValueError:
                pass
    return tuple(result.values())


def populate(db, table, identifier, stream, raw, *, truncated=False):
    key = 'id' if table == 'events' else 'event_id'
    values = (None,) * len(COLUMNS) if truncated else extract(stream, raw)
    if not any(value is not None for value in values):
        return
    db.execute(f"UPDATE {table} SET " + ','.join(f'{name}=?' for name in COLUMNS) + f' WHERE {key}=?', (*values, identifier))


def migrate(db):
    for table in ('events', 'error_evidence'):
        existing = {r[1] for r in db.execute(f'PRAGMA table_info({table})')}
        for name in COLUMNS:
            if name not in existing:
                db.execute(f'ALTER TABLE {table} ADD COLUMN {name} TEXT')
        key = 'id' if table == 'events' else 'event_id'
        for row in db.execute(f'SELECT * FROM {table}'):
            populate(db, table, row[key], row['stream'], row['raw'],
                     truncated=table == 'error_evidence' and bool(row['truncated']))
        db.execute(f'CREATE INDEX IF NOT EXISTS {table}_type_time ON {table}(session_id,event_type,recorded_at,{key})')
        db.execute(f'CREATE INDEX IF NOT EXISTS {table}_operation ON {table}(session_id,message_id,request_number,tool_number)')
        db.execute(f'CREATE INDEX IF NOT EXISTS {table}_tool ON {table}(session_id,tool_name,{key})')
    db.execute('CREATE INDEX IF NOT EXISTS messages_message ON messages(session_id,message_id)')
    db.execute('CREATE INDEX IF NOT EXISTS messages_sender_time ON messages(source,sender_id,recorded_at)')
    db.execute('PRAGMA user_version=5')
