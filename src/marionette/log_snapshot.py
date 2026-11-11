"""On-demand diagnostic extraction. Deliberately not registered as a model tool."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re

from diagnostics import message_id as validate_id

HEADER = re.compile(r'^\[event (\d+)\] \[([^\]]+)\](.*)\n$')
TAG = re.compile(r'^Client: \[message ([^\]]+)\] (.*)$', re.S)
BUDGET = re.compile(r'^(?:Prompt budget|Tool-loop prompt budget): (\d+) tokens \+ (\d+) reply allowance < (\d+)(?:; removed_exchanges=(\d+))?\.$')
BOUNDARY = re.compile(r'^========== MESSAGE (START|END) \| (processing|cache preparation)(?: \| (completed|failed|interrupted|finished))? ==========$')
CALL_TAGS = re.compile(r'^(?:\[request (\d+)\] )?(?:\[tool (\d+)\] )?')
OPERATION = re.compile(r'^---------- (MODEL REQUEST|TOOL CALL) (START|END)(?: \| (completed|returned|failed|interrupted))? ----------$')
MAX_SCAN = 512 * 1024 * 1024
MAX_EVENT = 4 * 1024 * 1024
MAX_MATCHES = 256
MAX_REPORT = 128 * 1024


def bounded_lines(path):
    """Read only the file length observed on opening; never follow a live writer."""
    with path.open('rb') as stream:
        size = stream.seek(0, 2)
        if size > MAX_SCAN:
            raise ValueError(f'Log exceeds {MAX_SCAN} byte scan limit: {path.name}')
        stream.seek(0)
        while stream.tell() < size:
            line = stream.readline(min(size - stream.tell(), MAX_EVENT + 1))
            if not line:
                raise ValueError('Log shrank during the read; retry with stable files.')
            if len(line) > MAX_EVENT:
                raise ValueError('Log row exceeds the event size limit.')
            yield line.decode('utf-8', errors='strict')


def decode_rows(rows):
    # Decode only the router's escapes, not Python/JSON escape syntax.
    text = ''.join(rows)
    return re.sub(r'\\(\\|x[0-9a-f]{2})',
                  lambda m: '\\' if m[1] == '\\' else chr(int(m[1][1:], 16)), text)


def diagnostic_events(path, issues):
    header, rows, length, damaged = None, [], 0, False
    def event():
        if header is None:
            return None
        if damaged or (not rows and '[blank line]' not in header[3]):
            if len(issues) >= MAX_MATCHES:
                raise ValueError('Too many damaged log events.')
            issues.append(f'{path.name}: incomplete event {header[1]} ignored')
            return None
        stamp = datetime.fromisoformat(header[2])
        if stamp.utcoffset() is None:
            raise ValueError('Log timestamps must include a UTC offset.')
        return int(header[1]), header[2], decode_rows(rows)
    previous = 0
    for line in bounded_lines(path):
        match = HEADER.fullmatch(line)
        if match:
            item = event()
            if item:
                yield item
            if int(match[1]) <= previous:
                raise ValueError('Diagnostic event numbers must increase within a session.')
            previous = int(match[1])
            header, rows, length, damaged = match, [], 0, False
        elif header is not None:
            if not line.startswith('    | ') or not line.endswith('\n'):
                damaged = True
                continue
            length += len(line.encode('utf-8'))
            if length > MAX_EVENT:
                raise ValueError('Log event exceeds the size limit.')
            rows.append(line[6:-1])
        elif line.strip():
            raise ValueError('Unsupported diagnostic format; message-ID logs are required.')
    item = event()
    if item:
        yield item


def snapshot(paths, identifier, conversation_id, *, discord_paths=()):
    """Return a new plain dict; no cache, writes, model calls, or history changes.

    Paths and conversation scope are operator-supplied here. A future tool must
    bind both itself, rather than accepting arbitrary model-selected files/scope.
    """
    if identifier is None:
        raise ValueError('An explicit message ID is required.')
    validate_id(identifier)
    if not isinstance(conversation_id, str) or not conversation_id:
        raise ValueError('An explicit conversation ID is required.')
    paths = [Path(p) for p in paths]
    stems = {re.sub(r'-(?:server|model)\.txt$', '', p.name) for p in paths}
    if not paths or len(paths) > 2 or len(stems) != 1 or any(
            not re.search(r'-(?:server|model)\.txt$', p.name) for p in paths):
        raise ValueError('Supply one session’s server/model log files only.')
    if len(set(p.resolve() for p in paths)) != len(paths):
        raise ValueError('Supply distinct diagnostic files.')
    if len({p.resolve().parent for p in paths}) != 1:
        raise ValueError('Session files must come from the same directory.')
    issues, matched = [], {}
    for path in paths:
        for number, stamp, text in diagnostic_events(path, issues):
            tag = TAG.fullmatch(text)
            if not tag or tag[1] != identifier:
                continue
            call_tags = CALL_TAGS.match(tag[2])
            body = tag[2][call_tags.end():]
            if body.startswith(('Message input:', 'Reasoning:', 'Discord input', 'Discord answer:',
                                   'Character supplied:', 'Character updated:')):
                continue
            record = {'at': stamp, 'text': body, 'request': call_tags[1], 'tool': call_tags[2], 'sources': [f'{path.name}:event {number}']}
            if number in matched:
                old = matched[number]
                if (old['at'], old['text'], old['request'], old['tool']) != (stamp, body, call_tags[1], call_tags[2]):
                    raise ValueError('Conflicting copies of the same diagnostic event.')
                old['sources'].extend(record['sources'])
            else:
                matched[number] = record
            if len(matched) > MAX_MATCHES:
                raise ValueError('Message exceeds the diagnostic event limit.')
    records = [matched[n] for n in sorted(matched)]
    scopes = {r['text'][len('Conversation selected: '):-1] for r in records
              if r['text'].startswith('Conversation selected: ') and r['text'].endswith('.')}
    if not records:
        raise LookupError('Message ID not found in the supplied session logs.')
    if scopes != {conversation_id}:
        raise ValueError('Message conversation is missing, ambiguous, or outside the requested scope.')

    report = {
        'schema_version': 2, 'captured_at': datetime.now(timezone.utc).isoformat(),
        'session': next(iter(stems)), 'message_id': identifier, 'conversation_id': conversation_id,
        'processing': {'status': 'unavailable', 'started_at': None, 'ended_at': None,
                       'elapsed_receipt_ms': None, 'finish_reason': None},
        'context': {'capacity_tokens': None, 'prompt_tokens': None,
                    'remaining_before_generation_tokens': None, 'reply_allowance_tokens': None,
                    'headroom_after_reply_allowance_tokens': None, 'removed_exchanges': None},
        'model': {'name': None, 'weight_precision': None, 'runtime_version': None, 'reasoning_enabled': None},
        'connections': {'model_server': None, 'transport': None},
        'model_requests': [], 'operations': [],
        'timing': {'time_to_first_token_ms': None, 'time_to_first_answer_ms': None,
                   'generation_tokens_per_second': None},
        'cache_preparation': {'status': 'unavailable', 'details': []},
        'delivery': {'status': 'unavailable', 'timings_ms': {}},
        'errors': [], 'warnings': [], 'evidence': [], 'limitations': issues,
    }
    report['limitations'].extend([
        'Only explicitly message-tagged records are attributed; raw runtime lines are excluded.',
        'null means unavailable. Empty errors/warnings mean none found in the supplied tagged records.',
        'Live files are read to their observed lengths; this is not an atomic view across files.',
    ])
    starts, ends = 0, 0
    for record in records:
        text = record['text']
        detail = {'at': record['at'], 'sources': record['sources']}
        if record['request'] is not None:
            detail['model_request_id'] = f"{identifier}/request-{int(record['request']):02d}"
        if record['tool'] is not None:
            detail['tool_call_id'] = f"{identifier}/tool-{int(record['tool']):02d}"
        used = True
        if match := OPERATION.fullmatch(text):
            kind, edge, outcome = match.groups()
            report['operations'].append(dict(detail, kind=kind, event=edge, outcome=outcome))
        elif text.startswith('Tool call identity: '):
            identity = json.loads(text.removeprefix('Tool call identity: '))
            if not isinstance(identity, dict):
                raise ValueError('Malformed tool call identity.')
            report['operations'].append(dict(detail, kind='TOOL CALL', event='identity',
                name=identity.get('name'), protocol_tool_call_id=identity.get('protocol_tool_call_id')))
        elif match := BOUNDARY.fullmatch(text):
            edge, phase, outcome = match.groups()
            if (edge == 'START' and outcome is not None) or (edge == 'END' and outcome is None):
                raise ValueError('Malformed message boundary.')
            if phase == 'processing':
                if edge == 'START' and ends:
                    raise ValueError('Processing boundaries are out of order.')
                starts += edge == 'START'
                ends += edge == 'END'
                report['processing']['started_at' if edge == 'START' else 'ended_at'] = record['at']
                report['processing']['status'] = 'incomplete' if edge == 'START' else outcome
            else:
                report['cache_preparation']['status'] = 'incomplete' if edge == 'START' else outcome
        elif text.startswith('========== MESSAGE'):
            raise ValueError('Malformed message boundary.')
        elif text.startswith('Conversation selected: '):
            pass  # Already checked above; retain provenance for the scope.
        elif match := BUDGET.fullmatch(text):
            prompt, reserve, capacity = map(int, match.groups()[:3])
            if prompt + reserve >= capacity:
                raise ValueError('Recorded prompt budget does not fit the context capacity.')
            report['context'].update(capacity_tokens=capacity, prompt_tokens=prompt,
                remaining_before_generation_tokens=capacity - prompt,
                reply_allowance_tokens=reserve,
                headroom_after_reply_allowance_tokens=capacity - prompt - reserve - 1)
            if match[4] is not None:
                report['context']['removed_exchanges'] = int(match[4])
        elif text.startswith(('Prompt budget:', 'Tool-loop prompt budget:')):
            raise ValueError('Malformed prompt budget.')
        elif text.startswith('Runtime usage: '):
            usage = json.loads(text.removeprefix('Runtime usage: '))
            if not isinstance(usage, dict):
                raise ValueError('Malformed runtime usage.')
            request = {name: usage.get(name) for name in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
            token_details = usage.get('completion_tokens_details') or {}
            request['reasoning_tokens'] = token_details.get('reasoning_tokens') if isinstance(token_details, dict) else None
            for value in request.values():
                if value is not None and (type(value) is not int or value < 0):
                    raise ValueError('Malformed runtime token count.')
            request['answer_tokens'] = None  # Completion can include tool syntax; do not infer.
            request['budget'] = report['context'].copy()
            request.update(detail)
            report['model_requests'].append(request)
        elif text.startswith('Reply completed: finish_reason='):
            reason = text.removeprefix('Reply completed: finish_reason=').removesuffix('.')
            report['processing']['finish_reason'] = reason
            if reason == 'length':
                report['warnings'].append(dict(detail, message='Generation allowance reached.'))
        elif text.startswith(('Message failed:', 'Message interrupted:', 'Discord local request failed:',
                              'Rollover preparation failed;', 'Model Request failed:', 'Tool Call failed:',
                              'Model Request interrupted:', 'Tool Call interrupted:')):
            report['errors'].append(dict(detail, message=text[:1500], truncated=len(text) > 1500))
        elif text.startswith(('Input-time rollover:', 'Rollover preparation stopped', 'Character update rejected:')):
            report['warnings'].append(dict(detail, message=text[:1500], truncated=len(text) > 1500))
        elif text.startswith(('Rollover preparation ', 'Prepared cache timings:', 'Preparation wait after input:')):
            report['cache_preparation']['details'].append(dict(detail, message=text[:1500]))
        else:
            used = False  # Exclude conversation prose, character notes, and reasoning.
        if used:
            report['evidence'].append(detail)
    if starts > 1 or ends > 1:
        raise ValueError('Message ID has multiple processing attempts; attribution is ambiguous.')
    processing = report['processing']
    if not starts or not ends:
        processing['status'] = 'incomplete'
        issues.append('Processing start/end pair is incomplete; failure or completion cannot be assumed.')
    if starts and ends:
        elapsed = (datetime.fromisoformat(processing['ended_at']) - datetime.fromisoformat(processing['started_at'])).total_seconds() * 1000
        if elapsed >= 0:
            processing['elapsed_receipt_ms'] = round(elapsed, 3)
        else:
            issues.append('Receipt clock moved backwards; elapsed time is unavailable.')
    # A budget describes the last formatted prompt, not the post-generation context.
    issues.append('Context is the last recorded prompt budget before generation; usage is listed per model call, not summed.')
    add_discord(report, discord_paths)
    if len(json.dumps(report, ensure_ascii=True, allow_nan=False).encode()) > MAX_REPORT:
        raise ValueError('Snapshot exceeds the report size limit.')
    return report


def add_discord(report, paths):
    count = 0
    paths = [Path(p) for p in paths]
    if len(paths) > 8 or len(set(p.resolve() for p in paths)) != len(paths):
        raise ValueError('Supply at most eight distinct Discord logs.')
    for path in paths:
        for line_number, line in enumerate(bounded_lines(path), 1):
            if not line.endswith('\n'):
                report['limitations'].append(f'{path.name}: incomplete final line ignored')
                continue
            if line.lstrip().startswith('{'):
                continue  # Conversation transcripts are not diagnostic evidence.
            stamp, _, rest = line.partition(' ')
            title, separator, payload = rest.partition(' {')
            if not separator:
                continue  # Includes JSON conversation transcripts, deliberately excluded.
            try:
                fields = json.loads('{' + payload)
            except ValueError:
                continue
            if not isinstance(fields, dict) or fields.get('log_message_id') != report['message_id']:
                continue
            if 'discord:' + str(fields.get('sender_id')) != report['conversation_id']:
                raise ValueError('Discord sender does not match the requested conversation.')
            count += 1
            if count > MAX_MATCHES:
                raise ValueError('Message exceeds the Discord event limit.')
            detail = {'at': stamp, 'sources': [f'{path.name}:line {line_number}']}
            if title == '========== MESSAGE END | Discord delivery ==========':
                if report['delivery']['status'] != 'unavailable':
                    raise ValueError('Multiple Discord delivery endings are ambiguous.')
                outcome = fields.get('outcome')
                if outcome not in ('delivered', 'failed', 'interrupted', 'unsupported', 'ignored'):
                    raise ValueError('Malformed delivery outcome.')
                report['delivery']['status'] = outcome
            for key in ('adapter_queue_ms', 'main_queue_ms', 'processing_ms', 'local_response_ms', 'total_ms'):
                value = fields.get(key)
                if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                    report['delivery']['timings_ms'][key] = value
            if title.startswith(('Discord turn failed;', 'Discord chunk failed.')):
                report['errors'].append(dict(detail, message=title,
                    **{key: fields[key] for key in ('phase', 'error_type', 'http_status', 'discord_code', 'confirmed_chunks') if key in fields}))
            report['evidence'].append(detail)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--message-id', required=True)
    parser.add_argument('--conversation-id', required=True)
    parser.add_argument('--discord-log', action='append', default=[])
    parser.add_argument('logs', nargs='+')
    args = parser.parse_args()
    try:
        result = snapshot(args.logs, args.message_id, args.conversation_id, discord_paths=args.discord_log)
    except (ValueError, LookupError, OSError) as error:
        parser.exit(1, f'Snapshot unavailable: {error}\n')
    print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
