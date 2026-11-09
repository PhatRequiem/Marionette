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
    if re.search(r'\b(?:disconnect|disconnected|warning|ignored)\b', text, re.I):
        return 'warning'
    return 'data'


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
            kind = 'meta' if key.endswith('_id') else severity(title)
            text = f'{key}: {json.dumps(value, ensure_ascii=False)}'
            rows.extend((kind, '  ' + row) for row in textwrap.wrap(safe(text), 116,
                         replace_whitespace=False, drop_whitespace=False) or [''])
        return rows
    if not isinstance(record, dict) or 'role' not in record or 'content' not in record:
        return [('data', safe(line.rstrip('\n')))]
    kind = {'user': 'input', 'assistant': 'reply'}.get(record['role'], 'data')
    rows = [('muted', '\n' + safe(record.get('time', ''))),
            ('meta', f"{safe(record['role']).upper()} · Discord")]
    for key, value in record.items():
        if key not in ('role', 'content', 'time'):
            label = f'incoming {key}' if record['role'] == 'assistant' and key in ('sender_id', 'message_id') else key
            rows.append(('meta', f'  {safe(label)}: {safe(json.dumps(value, ensure_ascii=False))}'))
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
        return self.kind


def render(source, output, mode, colored):
    view = DiagnosticView()
    for line in source:
        if mode == 'discord':
            for kind, text in discord_rows(line):
                output.write(paint(text, kind, colored) + '\n')
        else:
            kind = view.row(line)
            # Sender metadata is cyan, while the actual input stays green.
            if 'Client: Discord input [' in line:
                prefix, separator, body = line.partition(']: ')
                output.write(paint(prefix + separator, 'meta', colored)
                             + paint(body.rstrip('\n'), 'input', colored) + '\n')
            else:
                output.write(paint(line.rstrip('\n'), kind, colored) + '\n')
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
