#!/usr/bin/env python3
"""Human-readable, colored views of saved diagnostics; never rewrite evidence."""
import json
import re
import sys
import textwrap

from style import enabled, paint, safe


def severity(text):
    if re.search(r'\b(?:failed|failure|error)\b', text, re.I):
        return 'error'
    if re.search(r'\b(?:disconnect|disconnected|warning|ignored|retry|retrying)\b', text, re.I):
        return 'warning'
    if re.search(r'\b(?:connected|ready|resumed|delivered|sent|completed)\b', text, re.I):
        return 'success'
    return 'data'


def field_kind(key, default='data'):
    if key.endswith('_id'):
        return 'ids'
    if key.endswith('_at') or key in ('time', 'timestamp'):
        return 'muted'
    if key.endswith('_ms') or 'timing' in key or 'latency' in key:
        return 'timing'
    if 'token' in key or 'context' in key or key in ('capacity', 'reply_budget'):
        return 'tokens'
    return default


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
        for key, value in fields.items():
            kind = field_kind(key, severity(title))
            text = f'{key}: {json.dumps(value, ensure_ascii=False)}'
            rows.extend((kind, '  ' + row) for row in textwrap.wrap(safe(text), 116,
                         replace_whitespace=False, drop_whitespace=False) or [''])
        return rows
    if not isinstance(record, dict) or 'role' not in record or 'content' not in record:
        return [('data', safe(line.rstrip('\n')))]
    kind = {'user': 'input', 'assistant': 'reply'}.get(record['role'], 'data')
    rows = [('muted', '\n' + safe(record.get('time', ''))),
            ('answer_heading' if record['role'] == 'assistant' else 'meta',
             f"{safe(record['role']).upper()} · Discord")]
    for key, value in record.items():
        if key not in ('role', 'content', 'time'):
            label = f'incoming {key}' if record['role'] == 'assistant' and key in ('sender_id', 'message_id') else key
            rows.append((field_kind(key, 'meta'), f'  {safe(label)}: {safe(json.dumps(value, ensure_ascii=False))}'))
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
        elif text.startswith(('Client: Prepared cache timings:', 'Client: Preparation wait after input:',
                              'Client: Rollover preparation completed:')):
            self.kind = 'timing'
        elif text.startswith(('Client: Reply completed:', 'Client: Local server started:')):
            self.kind = 'success'
        return self.kind


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
    return paint(text, kind, colored)


def render(source, output, mode, colored):
    view = DiagnosticView()
    for line in source:
        if mode == 'discord':
            for kind, text in discord_rows(line):
                output.write(paint(text, kind, colored) + '\n')
        else:
            kind = view.row(line)
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
