"""Refresh one bounded operator-only Markdown section from startup evidence."""
from datetime import datetime, timezone
import os
import math
from importlib.metadata import version, PackageNotFoundError
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


def render(status, facts, *, capacity=None, details=None):
    stamp = datetime.now(timezone.utc).isoformat()
    rows = [START, '## Latest startup observations', '',
            f'Updated (UTC): {stamp}', '', f'Startup status: **{status}**.', '',
            'This section describes the last startup attempt, not current server health. '
            'It is not supplied to the model. Missing observations never inherit prior values.', '',
            '| Fact | Observed value | Evidence |', '|---|---|---|']
    for name in (*PATTERNS, *('Sampling ' + k for k in SAMPLING)):
        values = facts.get(name, set()) if status == 'ready' else set()
        if status == 'ready' and name in (details or {}) and (not values or not details[name][1].startswith('Configured:')):
            value, source = details[name]
        elif not values:
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
    if status == 'ready':
        for name, (value, source) in (details or {}).items():
            if name not in PATTERNS and not name.startswith('Sampling '):
                rows.append(f'| {cell(name)} | {cell(value)} | {cell(source)} |')
    rows += ['', 'Runtime-reported model/device strings do not verify file checksums. '
             'Thinking is requested by application code; its effective template behavior is not independently verified here. '
             'Discord is recorded at the initial main-chat boundary only. Personal data, paths, credentials, PIDs and conversation/session IDs are not copied into this file.', END]
    return '\n'.join(rows)


def update(path, status, facts, *, capacity=None, details=None):
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
    revised = original[:start] + render(status, facts, capacity=capacity, details=details) + original[end + len(END):]
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


def configuration(command, props, runtime_output=''):
    """Allowlisted runtime defaults plus explicitly labeled requested settings."""
    details = {}
    settings = props.get('default_generation_settings', {})
    if not isinstance(settings, dict):
        settings = {}
    params = settings.get('params', settings)
    if not isinstance(params, dict):
        params = {}
    flags = {'temp': '--temp', 'top_p': '--top-p', 'top_k': '--top-k',
             'min_p': '--min-p', 'presence_penalty': '--presence-penalty',
             'repeat_penalty': '--repeat-penalty', 'repeat_last_n': '--repeat-last-n',
             'frequency_penalty': '--frequency-penalty',
             'Prompt cache budget (MiB)': '--cache-ram',
             'Reasoning mode requested': '--reasoning',
             'Reasoning format requested': '--reasoning-format',
             'Separate reasoning budget requested': '--reasoning-budget'}
    for name, flag in flags.items():
        requested = None
        for i, arg in enumerate(command):
            if arg == flag and i + 1 < len(command): requested = command[i + 1]
            elif arg.startswith(flag + '='): requested = arg.split('=', 1)[1]
        label = 'Sampling ' + name if name in SAMPLING else name
        value = params.get(name)
        if name in SAMPLING and type(value) in (int, float) and math.isfinite(value):
            details[label] = (str(value), 'Observed server defaults: /props')
        elif requested is not None:
            details[label] = (requested, 'Configured: effective launch arguments; not independently observed')
        elif name not in SAMPLING:
            details[label] = ('Unverified', 'No explicit launch setting')
    # The launcher already invokes this exact executable with --version.
    for line in runtime_output[:16384].splitlines():
        if line.startswith('version: '):
            details['Runtime build'] = (line[len('version: '):], 'Executable --version output from this launch')
            break
    return details


def application(api, conversation, store, bridge_bound):
    """Inspect initialized components before accepting any external request."""
    tools = tuple(api.tools)
    names = sorted(tool.name for tool in tools)
    try:
        framework = version('qwen-agent')
    except PackageNotFoundError:
        framework = 'Unverified'
    result = {
        'Application startup': ('Initialized before accepting input', 'Observed components after profile selection'),
        'Terminal interface': ('Initialized', 'Observed: profile selected; conversation constructed'),
        'Local inference': ('Loopback HTTP server', 'Observed listener and startup health check'),
        'Discord interface': ('Offline at main-chat startup', 'Startup boundary before the new chat bridge begins serving; not a later connectivity probe'),
        'Discord local bridge': ('Bound; starts serving after this capture' if bridge_bound else 'Not enabled', 'Observed: LocalConnection constructed' if bridge_bound else 'No local connection configured'),
        'Tool coordinator': ('Qwen-Agent ' + framework, 'Installed Python package metadata'),
        'Registered tools at capture': (', '.join(names) or 'None', 'Observed: api.tools'),
        'Contact-note memory': ('Enabled; current-contact tool binds on ordinary turns' if conversation.contact_notes is not None else 'Disabled', 'Initialized conversation components'),
        'Soul memory': ('Enabled; shared persistent profile' if conversation.soul is not None else 'Disabled', 'Initialized conversation components'),
        'Conversation history': ('Separate per terminal profile / Discord sender; fresh on restart', 'Application design'),
        'Conversation storage': ('SQLite open; schema ' + str(store.db.execute('PRAGMA user_version').fetchone()[0]) if store is not None else 'Not attached', 'Observed store connection; not a write durability test'),
        'Thinking template request': ('enable_thinking=true', 'Configured by inference adapter; not independent template verification'),
    }
    purposes = {'update_soul': 'Edit persistent self name and description',
                'update_contact_notes': 'Edit notes for the current contact'}
    for tool in tools:
        result['Tool: ' + tool.name] = (purposes.get(tool.name, 'Registered; purpose not catalogued'), 'Observed registration; purpose from application design')
    if conversation.contact_notes is not None and 'update_contact_notes' not in names:
        result['Tool: update_contact_notes'] = ('Available on ordinary identified-contact turns; not yet bound at capture', 'Observed contact-note component; conversation turn binding policy')
    # No enabled external read tools exist in the current production registry.
    known = set(names) <= set(purposes)
    result['Log lookup / vault access'] = ('Not connected' if known else 'Unverified: additional tools registered', 'Observed startup tools; no external reader configured by this startup')
    if store is not None:
        policy = store.db.execute('SELECT * FROM retention_state WHERE id=1').fetchone()
        result['Diagnostic raw-event budget'] = (str(policy['budget_bytes']) + ' bytes', 'Configured recorder policy in SQLite; live occupancy not probed')
        result['Diagnostic batch size'] = (str(policy['part_bytes']) + ' bytes', 'Configured recorder policy in SQLite')
        result['Protected error windows'] = (str(policy['error_limit']) + ' windows; ' + str(policy['window_events']) + ' events before/after', 'Configured recorder policy in SQLite')
    result['Diagnostic persistence'] = ('RAM rolling buffer; saved on orderly recorder shutdown', 'Application design; abrupt recorder loss can lose unsaved diagnostics')
    return result
