#!/usr/bin/env python3
"""Number and route diagnostics to two files without a third raw log."""
import re
import base64
import datetime
import sys
import textwrap

from log_store import record, encode, raw_batches, timestamp

RECORD = re.compile(rb'^\d[\d.]*\s+([A-Z])\s+(.*)')
COMPONENT = re.compile(rb'^(srv|slot|que|res)\s+([^:]+):\s*(.*)')
SERVER_FUNCTIONS = {b'init_listene', b'server_setup', b'server_run_i', b'server_on_li',
                    b'server_strea', b'get_availabl', b'stop', b'init'}
MODEL_FUNCTIONS = {b'load_model', b'load', b'update', b'decode', b'process_sing',
                   b'eval_llama_c', b'update_slots', b'reset', b'launch_slot_',
                   b'create_check', b'init_sampler', b'process_toke',
                   b'handle_last_', b'print_timing', b'release'}
QUEUE_FUNCTIONS = {b'start_loop', b'post', b'process_new_', b'yield_to_que',
                   b'add_waiting_', b'remove_waiti', b'send'}
MODEL_PREFIXES = (b'llama_', b'ggml_', b'load_tensors:', b'print_info:',
                  b'print_meta:', b'build_graph:', b'common_init_', b'Parsed message:')


def category(line):
    # Unrecognized and unprefixed continuation lines are deliberately shared.
    record = RECORD.match(line)
    if not record:
        return 'both'
    level, message = record.groups()
    if level not in (b'I', b'D', b'T'):
        return 'both'
    component = COMPONENT.match(message)
    if component:
        owner, function, detail = component.groups()
        function = function.strip()
        if owner in (b'que', b'res') and function in QUEUE_FUNCTIONS:
            return 'server'
        if owner == b'srv' and (
            function in SERVER_FUNCTIONS or detail.startswith(b'http:')
            or b'terminating stream' in detail or b'cleaning up before exit' in detail
            or detail == b'all slots are idle'
        ):
            return 'server'
        if owner in (b'srv', b'slot') and (
            function in MODEL_FUNCTIONS or (owner == b'slot' and function == b'operator()')
        ):
            return 'model'
    if message.startswith(MODEL_PREFIXES):
        return 'model'
    return 'both'


def diagnostic_lines(event):
    """Expand old records or compact [sequence, microsecond offset, byte length] rows."""
    raw = base64.b64decode(event['raw_b64'], validate=True)
    if event['event_type'] == 'diagnostic':
        yield event['sequence'], event['timestamp'], raw
        return
    start = datetime.datetime.fromisoformat(event['timestamp'])
    position = 0
    for sequence, offset, length in event['data']['lines']:
        line = raw[position:position + length]
        if len(line) != length:
            raise ValueError('Truncated diagnostic payload')
        yield sequence, (start + datetime.timedelta(microseconds=offset)).isoformat(timespec='microseconds'), line
        position += length
    if position != len(raw):
        raise ValueError('Unindexed diagnostic bytes')


def route(source, server, model):
    number, pending = 0, b''
    def write(lines):
        if not lines:
            return
        start = lines[0][1]
        for name, output in [('server', server), ('model', model)]:
            selected = [(n, when, raw) for n, when, raw, destination in lines if destination in (name, 'both')]
            if not selected:
                continue
            event = record('diagnostic', 'diagnostic_batch',
                raw=b''.join(raw for _, _, raw in selected),
                data={'destination': name,
                      'lines': [[n, when - start, len(raw)] for n, when, raw in selected]})
            event['timestamp'] = timestamp(start)
            output.write(encode(event))
            output.flush()

    last_time = None
    for batch in raw_batches(source):
        lines = []
        for when, chunk in batch:
            last_time = when
            parts = (pending + chunk).split(b'\n')
            pending = parts.pop()
            for part in parts:
                number += 1
                raw = part + b'\n'
                lines.append((number, when, raw, category(raw)))
        write(lines)
    if pending:
        write([(number + 1, last_time, pending, category(pending))])


def format_event(number, now, line):
    """Readable blocks; no JSON parsing, truncation, or discarded source bytes."""
    header = f'[event {number:08d}] [{now}]'.encode()
    if line == b'\n':
        return header + b' [blank line]\n'
    # Escape controls instead of letting them move the cursor or recolor the log.
    # Escape literal backslashes too, so this representation is reversible.
    text = line.removesuffix(b'\n').decode('utf-8', errors='surrogateescape')
    def escape(text):
        visible = ''
        for char in text:
            code = ord(char)
            if char == '\\':
                visible += '\\\\'
            elif code < 32 or code == 127:
                visible += f'\\x{code:02x}'
            elif 0xdc80 <= code <= 0xdcff:
                visible += f'\\x{code - 0xdc00:02x}'
            else:
                visible += char
        return visible
    # Split JSON punctuation outside quoted strings without interpreting values.
    # Keeping the exact characters avoids losing duplicate keys or number precision.
    sections, start, quoted, escaped = [], 0, False, False
    json_start = text.find('{')
    for index, char in enumerate(text):
        if escaped:
            escaped = False
        elif char == '\\':
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif json_start >= 0 and index >= json_start and not quoted and char in '{[,}':
            sections.append(text[start:index + 1])
            start = index + 1
    sections.append(text[start:])
    rows = []
    for section in sections:
        if section:
            rows.extend(textwrap.wrap(escape(section), width=140, expand_tabs=False,
                                      replace_whitespace=False, drop_whitespace=False,
                                      break_on_hyphens=False))
    ending = b'' if line.endswith(b'\n') else b' [no final newline]'
    body = ''.join('    | ' + row + '\n' for row in rows).encode('utf-8')
    return header + ending + b'\n' + body


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: log-router.py SERVER_LOG MODEL_LOG')
    with open(sys.argv[1], 'ab', buffering=0) as server, open(sys.argv[2], 'ab', buffering=0) as model:
        route(sys.stdin.buffer, server, model)
