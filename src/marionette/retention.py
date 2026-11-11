"""Transactional diagnostic batches and independently retained failure evidence."""
import json
import re

PART_BYTES = 20_000_000
BUDGET_BYTES = 500_000_000
ERROR_LIMIT = 20
WINDOW = 20
EVIDENCE_BYTES = 1_000_000  # Per event; oversized evidence is explicitly marked.

DDL = '''
CREATE TABLE diagnostic_batches (
 id INTEGER PRIMARY KEY AUTOINCREMENT, bytes INTEGER NOT NULL DEFAULT 0,
 closed INTEGER NOT NULL DEFAULT 0);
ALTER TABLE events ADD COLUMN batch_id INTEGER REFERENCES diagnostic_batches(id);
CREATE INDEX events_batch ON events(batch_id);
CREATE TABLE retention_state (
 id INTEGER PRIMARY KEY CHECK(id=1), next_event INTEGER NOT NULL,
 part_bytes INTEGER NOT NULL, budget_bytes INTEGER NOT NULL,
 error_limit INTEGER NOT NULL, window_events INTEGER NOT NULL);
CREATE TABLE failures (
 id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL REFERENCES sessions(id),
 message_id TEXT, request_id TEXT, tool_id TEXT, component TEXT NOT NULL,
 first_event INTEGER NOT NULL, last_error INTEGER NOT NULL, recorded_at TEXT NOT NULL,
 remaining INTEGER NOT NULL, before_count INTEGER NOT NULL, state TEXT NOT NULL);
CREATE TABLE error_evidence (
 event_id INTEGER PRIMARY KEY, session_id TEXT NOT NULL, recorded_at TEXT NOT NULL,
 stream TEXT NOT NULL, category TEXT NOT NULL, message_id TEXT, raw BLOB NOT NULL,
 original_bytes INTEGER NOT NULL, truncated INTEGER NOT NULL);
CREATE INDEX evidence_message ON error_evidence(session_id,message_id,event_id);
CREATE TABLE failure_events (
 failure_id INTEGER NOT NULL REFERENCES failures(id) ON DELETE CASCADE,
 event_id INTEGER NOT NULL REFERENCES error_evidence(event_id),
 relation TEXT NOT NULL, PRIMARY KEY(failure_id,event_id));
CREATE TABLE recent_diagnostics (
 event_id INTEGER PRIMARY KEY, session_id TEXT NOT NULL, recorded_at TEXT NOT NULL,
 stream TEXT NOT NULL, category TEXT NOT NULL, message_id TEXT, raw BLOB NOT NULL,
 original_bytes INTEGER NOT NULL, truncated INTEGER NOT NULL);
'''


def migrate(db):
    """Called within BEGIN IMMEDIATE; legacy content is assigned, not deleted."""
    for statement in DDL.split(';'):
        if statement.strip():
            db.execute(statement)
    maximum = db.execute('SELECT coalesce(max(id),0) FROM events').fetchone()[0]
    db.execute('INSERT INTO retention_state VALUES (1,?,?,?,?,?)',
               (maximum + 1, PART_BYTES, BUDGET_BYTES, ERROR_LIMIT, WINDOW))
    # Row IDs and raw bytes survive migration; error detection uses explicit records.
    batch, size = None, 0
    for row in db.execute("SELECT id,length(raw) AS size FROM events WHERE stream='diagnostic' ORDER BY id"):
        if batch is None or (size and size + row['size'] > PART_BYTES):
            if batch is not None:
                db.execute('UPDATE diagnostic_batches SET closed=1 WHERE id=?', (batch,))
            batch = db.execute('INSERT INTO diagnostic_batches DEFAULT VALUES').lastrowid
            size = 0
        db.execute('UPDATE events SET batch_id=? WHERE id=?', (batch, row['id']))
        size += row['size']
        db.execute('UPDATE diagnostic_batches SET bytes=? WHERE id=?', (size, batch))
    policy = db.execute('SELECT * FROM retention_state').fetchone()
    for row in db.execute("SELECT id,session_id,recorded_at,stream,category,message_id,raw FROM events WHERE stream IN ('diagnostic','discord') ORDER BY id"):
        retain(db, tuple(row), policy)
    db.execute("UPDATE failures SET state='incomplete' WHERE state='collecting' AND session_id IN (SELECT id FROM sessions WHERE ended_at IS NOT NULL)")
    db.execute('PRAGMA user_version=2')


def failure_identity(stream, raw):
    """Match event types, never words inside conversation text or reasoning."""
    if stream == 'diagnostic':
        match = re.match(rb'Client: (?:\[message ([^\]\r\n]+)\] )?(?:\[request (\d+)\] )?(?:\[tool (\d+)\] )?(.*)', raw)
        if match:
            msg, request, tool, text = match.groups()
            for prefix, component in ((b'Model Request failed:', 'model'), (b'Tool Call failed:', 'tool'),
                                      (b'Message failed:', 'message'), (b'Discord local request failed:', 'bridge'),
                                      (b'Rollover preparation failed;', 'preparation'), (b'Client error:', 'client')):
                if text.startswith(prefix):
                    return tuple(x.decode() if x else None for x in (msg, request, tool)) + (component,)
        if re.match(rb'^\d[\d.]*\s+E\s+', raw):
            return None, None, None, 'runtime'
    elif stream == 'discord' and not raw.lstrip().startswith(b'{'):
        match = re.match(rb'\S+ (Discord (?:turn|chunk) failed[^\{]*) (\{.*\})\s*$', raw)
        if match:
            try:
                fields = json.loads(match[2])
            except ValueError:
                return None
            return fields.get('log_message_id'), None, None, 'delivery' if fields.get('phase') != 'local_response' else 'bridge'
    return None


def eligible(stream, raw):
    return stream == 'diagnostic' or (stream == 'discord' and not raw.lstrip().startswith(b'{'))


def copy_event(db, row):
    db.execute('INSERT OR IGNORE INTO error_evidence VALUES (?,?,?,?,?,?,?,?,?)', tuple(row))


def retain(db, row, policy):
    """Capture evidence before pruning; all mutations share the event transaction."""
    event_id, session, stamp, stream, category, msg, raw = row
    if not eligible(stream, raw):
        return
    evidence = (event_id, session, stamp, stream, category, msg, raw[:EVIDENCE_BYTES], len(raw), int(len(raw) > EVIDENCE_BYTES))
    window, limit = policy['window_events'], policy['error_limit']
    pending = db.execute("SELECT id,remaining FROM failures WHERE session_id=? AND state='collecting'", (session,)).fetchall()
    pending_ids = {failure['id'] for failure in pending}
    for failure in pending:
        copy_event(db, evidence)
        db.execute('INSERT OR IGNORE INTO failure_events VALUES (?,?,?)', (failure['id'], event_id, 'after'))
        remaining = failure['remaining'] - 1
        db.execute('UPDATE failures SET remaining=?,state=? WHERE id=?',
                   (remaining, 'complete' if remaining == 0 else 'collecting', failure['id']))
    identity = failure_identity(stream, raw)
    if identity:
        msg, request, tool, component = identity
        prior = None
        if msg:
            candidates = db.execute("SELECT * FROM failures WHERE session_id=? AND message_id=? ORDER BY id DESC", (session, msg)).fetchall()
            for candidate in candidates:
                if candidate['id'] not in pending_ids:
                    continue
                # Propagated parent/bridge errors join the latest child failure.
                related = (component in ('message', 'bridge') and candidate['component'] not in ('delivery', 'preparation'))
                related |= component == 'delivery' and candidate['component'] == 'delivery'
                related |= (component == 'model' and candidate['request_id'] == request and candidate['component'] == 'tool')
                if related:
                    prior = candidate['id']
                    break
        is_new = prior is None
        if is_new:
            previous = db.execute('SELECT * FROM recent_diagnostics WHERE session_id=? ORDER BY event_id DESC LIMIT ?', (session, window)).fetchall()
            prior = db.execute('''INSERT INTO failures(session_id,message_id,request_id,tool_id,component,
                first_event,last_error,recorded_at,remaining,before_count,state) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (session,msg,request,tool,component,event_id,event_id,stamp,window,len(previous),'collecting')).lastrowid
            for previous_row in previous:
                copy_event(db, previous_row)
                db.execute('INSERT INTO failure_events VALUES (?,?,?)', (prior,previous_row['event_id'],'before'))
        copy_event(db, evidence)
        db.execute('INSERT OR REPLACE INTO failure_events VALUES (?,?,?)', (prior,event_id,'error'))
        db.execute('UPDATE failures SET last_error=? WHERE id=?', (event_id,prior))
        db.execute('DELETE FROM failures WHERE id NOT IN (SELECT id FROM failures ORDER BY recorded_at DESC,last_error DESC LIMIT ?)', (limit,))
        db.execute('DELETE FROM error_evidence WHERE event_id NOT IN (SELECT event_id FROM failure_events)')
    db.execute('INSERT INTO recent_diagnostics VALUES (?,?,?,?,?,?,?,?,?)', evidence)
    db.execute('DELETE FROM recent_diagnostics WHERE event_id NOT IN (SELECT event_id FROM recent_diagnostics ORDER BY event_id DESC LIMIT ?)', (window,))


def batch_for(db, size, policy):
    batch = db.execute('SELECT * FROM diagnostic_batches WHERE closed=0 ORDER BY id DESC LIMIT 1').fetchone()
    if batch and batch['bytes'] and batch['bytes'] + size > policy['part_bytes']:
        db.execute('UPDATE diagnostic_batches SET closed=1 WHERE id=?', (batch['id'],))
        batch = None
    if batch is None:
        number = db.execute('INSERT INTO diagnostic_batches DEFAULT VALUES').lastrowid
    else:
        number = batch['id']
    db.execute('UPDATE diagnostic_batches SET bytes=bytes+? WHERE id=?', (size,number))
    return number


def prune(db, policy):
    total = db.execute('SELECT coalesce(sum(bytes),0) FROM diagnostic_batches').fetchone()[0]
    for batch in db.execute('SELECT * FROM diagnostic_batches WHERE closed=1 ORDER BY id').fetchall():
        if total <= policy['budget_bytes']:
            break
        db.execute('DELETE FROM events WHERE batch_id=?', (batch['id'],))
        db.execute('DELETE FROM diagnostic_batches WHERE id=?', (batch['id'],))
        total -= batch['bytes']
