#!/usr/bin/env python3
"""Human-readable, colored views of saved diagnostics; never rewrite evidence."""
import json
import re
import sys
import textwrap

from style import enabled, paint, safe


def severity(text):
    if re.search(r'(?:Session (?:started|ended|stopped)|Chat history cleared|Local server (?:started|stopped)|Discord session stopped)', text, re.I):
        return 'meta'
    if re.search(r'\b(?:failed|failure|error)\b', text, re.I):
        return 'error'
    if re.search(r'\b(?:disconnect|disconnected|warning|ignored|retry|retrying)\b', text, re.I):
        return 'warning'
    if 'send started' in text.lower() or 'rollover preparation started' in text.lower():
        return 'warning'
    if re.search(r'\b(?:connected|ready|resumed|delivered|sent|completed)\b', text, re.I):
        return 'success'
    return 'data'


def field_kind(key, default='data'):
    if key == 'confirmed_chunks':
        return 'success'
    if key.endswith('_id'):
        return 'ids'
    if key.endswith('_at') or key in ('time', 'timestamp'):
        return 'muted'
    if key.endswith('_ms') or 'timing' in key or 'latency' in key:
        return 'timing'
    if 'token' in key or 'context' in key or key in ('capacity', 'reply_budget'):
        return 'tokens'
    return default


def metadata_rows(fields, default='data'):
    rows, previous_group = [], None
    for key, value in fields.items():
        kind = field_kind(key, default if key in ('chunk', 'http_status', 'discord_code', 'error_type') else 'data')
        group = ('identity' if kind == 'ids' else 'timing' if kind in ('timing', 'muted')
                 else 'delivery' if key in ('chunk', 'chunk_count', 'confirmed_chunks', 'kind') else 'details')
        if previous_group is not None and group != previous_group:
            rows.append(('data', ''))
        previous_group = group
        value_text = json.dumps(value, ensure_ascii=False)
        if key.endswith('_ms') and isinstance(value, (int, float)):
            value_text += ' ms'
        wrapped = textwrap.wrap(safe(f'{key}: {value_text}'), 116,
                                replace_whitespace=False, drop_whitespace=False) or ['']
        rows.append(('field/' + kind, '  ' + wrapped[0]))
        rows.extend((kind, '  ' + row) for row in wrapped[1:])
    return rows


def field_text(text, kind, colored):
    label, separator, value = text.partition(': ')
    return paint(label + separator, 'data', colored) + paint(value, kind, colored)


def discord_rows(line):
    """Render every recorded field; decode message newlines for human reading."""
    try:
        record = json.loads(line)
    except (ValueError, TypeError):
        # Event lines have a timestamp, description, and an optional JSON object.
        prefix, separator, payload = line.partition(' {')
        try:
            fields = json.loads('{' + payload) if separator else {}
        except ValueError:
            return [('data', safe(line.rstrip('\n')))]
        timestamp, _, title = prefix.rstrip('\n').partition(' ')
        rows = [('muted', '\n' + timestamp), (severity(title), title)]
        rows.extend(metadata_rows(fields, severity(title)))
        return rows
    if not isinstance(record, dict) or 'role' not in record or 'content' not in record:
        return [('data', safe(line.rstrip('\n')))]
    kind = {'user': 'input', 'assistant': 'reply'}.get(record['role'], 'data')
    rows = [('muted', '\n' + safe(record.get('time', ''))),
            ('answer_heading' if record['role'] == 'assistant' else 'meta',
             f"{safe(record['role']).upper()} · Discord")]
    metadata = {}
    for key, value in record.items():
        if key not in ('role', 'content', 'time'):
            label = f'incoming {key}' if record['role'] == 'assistant' and key in ('sender_id', 'message_id') else key
            metadata[label] = value
    rows.extend(metadata_rows(metadata))
    rows.append(('data', ''))
    rows.append((kind, safe(record['content'])))
    rows.append(('data', ''))
    return rows


class DiagnosticView:
    """Color each row without buffering, removing, or changing saved event text."""
    def __init__(self):
        self.kind = 'data'
        self.role = None

    def row(self, line):
        if line.startswith('[event '):
            self.kind, self.role = 'data', None
            return 'muted'
        text = line.removeprefix('    | ').lstrip()
        if re.match(r'\d[\d.]*\s+E\s', text) or text.startswith(('Client: Request failed:',
                'Client: Discord local request failed:', 'Client: Client error:')):
            self.kind = 'error'
        elif re.match(r'\d[\d.]*\s+W\s', text):
            self.kind = 'warning'
        elif re.match(r'\d[\d.]*\s+[IDT]\s+.*(?:print_timing|print_timings|timings:)', text):
            self.kind = 'timing'
        elif re.match(r'\d[\d.]*\s+[IDT]\s+.*\b(?:n_ctx|n_ctx_seq|n_tokens|n_predict)\s*[=:]', text):
            self.kind = 'tokens'
        elif text.startswith('Client: Discord input'):
            self.kind = 'input'
        elif text.startswith('Client: Discord answer:'):
            self.kind = 'reply'
        elif text.startswith('Client: Reasoning:'):
            self.kind = 'data'
        elif re.match(r'"role"\s*:\s*"(user|assistant)"', text):
            self.role = 'input' if '"user"' in text else 'reply'
            self.kind = 'meta'
        elif re.match(r'"reasoning_content"\s*:', text):
            self.kind = 'data'
        elif re.match(r'"content"\s*:', text):
            self.kind = self.role or 'reply'
        elif re.match(r'"[^"\n]+"\s*:', text):
            key = text.split('"', 2)[1]
            self.kind = field_kind(key, 'data')
        elif text.startswith(('Client: Prompt budget:', 'Client: Context policy:', 'Client: Runtime usage:')):
            self.kind = 'tokens'
        elif text.startswith('Client: Rollover preparation'):
            self.kind = severity(text)
        elif text.startswith(('Session started:', 'Session ended:', 'Client: Local server started:',
                              'Client: Local server stopped.', 'Client: Chat history cleared.')):
            self.kind = 'meta'
        elif text.startswith(('Client: Prepared cache timings:', 'Client: Preparation wait after input:')):
            self.kind = 'timing'
        elif text.startswith(('Client: Reply completed:', 'Client: Local server started:')):
            self.kind = 'success'
        return self.kind


def numeric_fields(text, colored):
    """Highlight values in known diagnostic rows, never in message prose."""
    pattern = r'(?P<key>[a-z_]+)=(?P<value>\d+(?:\.\d+)?)|(?P<amount>\d+(?:\.\d+)?\s*(?:ms|tokens)\b)'
    pieces, end = [], 0
    for value in re.finditer(pattern, text):
        pieces.append(paint(text[end:value.start()], 'data', colored))
        if value['key']:
            pieces.append(paint(value['key'] + '=', 'data', colored))
            pieces.append(paint(value['value'], field_kind(value['key'], 'tokens'), colored))
        else:
            pieces.append(paint(value[0], 'timing' if value[0].endswith('ms') else 'tokens', colored))
        end = value.end()
    pieces.append(paint(text[end:], 'data', colored))
    return ''.join(pieces)


def diagnostic_row(line, kind, colored):
    # Split headings from content without changing any saved character.
    text = line.rstrip('\n')
    match = re.match(r'(    \| Client: Discord input \[)([0-9]+)(\]: )(.*)', text)
    if match:
        return (paint(match[1], 'meta', colored) + paint(match[2], 'ids', colored)
                + paint(match[3], 'meta', colored) + paint(match[4], 'input', colored))
    match = re.match(r'(    \| (?:Client: Discord answer: |"content"\s*:))(.*)', text)
    if match and kind == 'reply':
        return paint(match[1], 'answer_heading', colored) + paint(match[2], 'reply', colored)
    match = re.match(r'(    \| (?:Client: Reasoning: |"reasoning_content"\s*:))(.*)', text)
    if match:
        return paint(match[1], 'thinking_heading', colored) + paint(match[2], 'data', colored)
    match = re.match(r'(    \|\s*"[^"\n]+"\s*:)(.*)', text)
    if match and kind in ('timing', 'tokens', 'ids', 'error', 'success', 'warning'):
        return paint(match[1], 'data', colored) + paint(match[2], kind, colored)
    if 'Client: Rollover preparation' in text:
        heading = re.match(r'    \| Client: Rollover preparation [^:;.]+[:;.]', text)
        if heading:
            return paint(heading[0], kind, colored) + numeric_fields(text[heading.end():], colored)
    if kind in ('timing', 'tokens'):
        return numeric_fields(text, colored)
    return paint(text, kind, colored)


def render(source, output, mode, colored):
    view = DiagnosticView()
    for line in source:
        if mode == 'discord':
            for kind, text in discord_rows(line):
                rendered = field_text(text, kind[6:], colored) if kind.startswith('field/') else paint(text, kind, colored)
                output.write(rendered + '\n')
        else:
            kind = view.row(line)
            if line.startswith(('    | Session started:', '    | Session ended:',
                                '    | Client: Chat history cleared.', '    | Client: Rollover preparation')):
                output.write('\n')
            output.write(diagnostic_row(line, kind, colored) + '\n')
        output.flush()


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('discord', 'diagnostic'):
        raise SystemExit('Usage: log_view.py discord|diagnostic < SAVED_LOG')
    try:
        render(sys.stdin, sys.stdout, sys.argv[1], enabled())
    finally:
        if enabled():
            sys.stdout.write('\033[0m')
            sys.stdout.flush()
