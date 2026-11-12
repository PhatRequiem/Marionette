"""Refresh one bounded operator-only Markdown section from startup evidence."""
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import tempfile

START = '<!-- startup-observations:start -->'
END = '<!-- startup-observations:end -->'
PATTERNS = {
    'Model name': r'\bgeneral\.name\s+(?:str\s+)?=\s*(.+)',
    'GGUF file type': r'\bfile type\s*=\s*(.+)',
    'Runtime build': r'\bbuild\s*=\s*(\d+\s*\([0-9a-fA-F]+\))',
    'Loaded device': r'\busing device\s+([^\r\n]+?)\s+-\s+\d+ MiB free',
    'GPU layers': r'\boffloaded\s+(\d+/\d+) layers to GPU',
    'Context per sequence': r'\bllama_context: n_ctx_seq\s*=\s*(\d+)\s*$',
    'Parallel sequences': r'\bllama_context: n_seq_max\s*=\s*(\d+)\s*$',
}
SAMPLING = ('temp', 'top_p', 'top_k', 'min_p', 'presence_penalty',
            'repeat_penalty', 'repeat_last_n', 'frequency_penalty')


def observe(line, facts):
    # Only startup output is passed here, never conversation records.
    if len(line) > 4096:
        return
    for name, pattern in PATTERNS.items():
        match = re.search(pattern, line)
        if match:
            facts.setdefault(name, set()).add(match[1].strip())
    for name in SAMPLING:
        match = re.search(r'\b' + name + r'\s*=\s*(-?\d+(?:\.\d+)?)\b', line)
        if match:
            facts.setdefault('Sampling ' + name, set()).add(match[1])


def cell(value):
    # Runtime text is data, not Markdown/HTML or instructions.
    text = str(value)[:240]
    return ''.join(c if c.isprintable() else ' ' for c in text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '&#124;').replace('`', '&#96;').replace('[', '&#91;').replace(']', '&#93;').replace('\\', '&#92;')


def render(status, facts, *, capacity=None):
    stamp = datetime.now(timezone.utc).isoformat()
    rows = [START, '## Latest startup observations', '',
            f'Updated (UTC): {stamp}', '', f'Startup status: **{status}**.', '',
            'This section describes the last startup attempt, not current server health. '
            'It is not supplied to the model. Missing observations never inherit prior values.', '',
            '| Fact | Observed value | Evidence |', '|---|---|---|']
    for name in (*PATTERNS, *('Sampling ' + k for k in SAMPLING)):
        values = facts.get(name, set()) if status == 'ready' else set()
        if not values:
            value, source = 'Unverified', 'No confirmed startup observation'
        elif len(values) > 1 and name != 'Loaded device':
            value, source = 'Unverified', 'Conflicting startup observations'
        else:
            value, source = '; '.join(sorted(values)), 'Runtime startup output'
        rows.append(f'| {name} | {cell(value)} | {source} |')
    if status == 'ready' and capacity is not None:
        rows += [f'| Effective context capacity | {capacity} tokens | Runtime output agrees with `/props` |',
                 f'| Reply allowance | {min(32768, capacity // 2)} tokens | Application policy at this capacity |',
                 f'| Next-input reserve | {min(2048, capacity // 8)} tokens | Application policy at this capacity |',
                 '| Local server startup health | Passed | `/health` returned status `ok` before chat |']
    else:
        rows.append('| Effective context / startup health | Unverified | Startup verification not completed |')
    rows += ['', 'Runtime-reported model/device strings do not verify file checksums. '
             'Thinking is requested by application code; its effective template behavior is not independently verified here. '
             'Discord status, personal data, paths, credentials, PIDs and conversation/session IDs are not copied into this file.', END]
    return '\n'.join(rows)


def update(path, status, facts, *, capacity=None):
    """Replace only the marked section atomically, without keeping old copies."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Datasheet must be a regular file, not a symlink.')
    if status not in ('starting', 'ready', 'failed'):
        raise ValueError('Invalid startup status.')
    original = path.read_text()
    if len(original.encode()) > 128 * 1024:
        raise ValueError('Datasheet exceeds the update size limit.')
    if original.count(START) != 1 or original.count(END) != 1:
        raise ValueError('Datasheet needs exactly one startup-observations marker pair.')
    start, end = original.index(START), original.index(END)
    if end < start:
        raise ValueError('Datasheet markers are out of order.')
    revised = original[:start] + render(status, facts, capacity=capacity) + original[end + len(END):]
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.setup-datasheet-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(revised)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(path.stat().st_mode & 0o777)
        # Avoid overwriting an operator edit noticed during report generation.
        if path.is_symlink() or path.read_text() != original:
            raise ValueError('Datasheet changed during startup update.')
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
