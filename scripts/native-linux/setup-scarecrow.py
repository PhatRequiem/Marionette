#!/usr/bin/env python3
"""Install the local, dependency-free Scarecrow plugin; preserve vault notes."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import uuid

ROOT = Path(__file__).resolve().parents[2]


def safe(path):
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise SystemExit('Setup refuses symlinked installation/configuration paths.')


def private_json(path, value):
    safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    safe(temporary)
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)



def bundle():
    """Assemble our three fixed CommonJS modules for Obsidian's single-file loader."""
    source = ROOT / 'plugins/scarecrow'
    modules = []
    for name in ('operations', 'server', 'main'):
        modules.append(json.dumps('./' + name) + ': function(module, exports, require) {\n' +
                       (source / (name + '.js')).read_text() + '\n}')
    return ("// Scarecrow 0.1.1: generated from versioned project source.\n" +
            "const nativeRequire = require;\nconst factories = {" + ',\n'.join(modules) + "};\n" +
            "const cache = {};\nfunction load(name) {\n" +
            "  if (!Object.hasOwn(factories, name)) return nativeRequire(name);\n" +
            "  if (!cache[name]) { const m = {exports:{}}; cache[name]=m; factories[name](m,m.exports,load); }\n" +
            "  return cache[name].exports;\n}\nmodule.exports = load('./main');\n")


def install(vault, data, port=27124):
    os.umask(0o077)
    vault, data = Path(vault).absolute(), Path(data).absolute()
    safe(vault); safe(data)
    if not 1024 <= port <= 65535:
        raise SystemExit('Port must be 1024–65535.')
    if not (vault / 'Generated/.marionette-managed').is_file():
        raise SystemExit('Refresh the Marionette mirror before installing Scarecrow.')
    plugin = vault / '.obsidian/plugins/scarecrow'
    safe(plugin)
    settings_path = plugin / 'data.json'
    safe(settings_path)
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    settings.update(port=port)
    settings.setdefault('token', secrets.token_hex(32))
    settings.setdefault('vault_id', str(uuid.uuid4()))
    plugin.mkdir(parents=True, exist_ok=True)
    safe(plugin / 'main.js')
    (plugin / 'main.js').write_text(bundle())
    for name in ('operations.js', 'server.js'):
        stale = plugin / name
        safe(stale)
        if stale.exists():
            stale.unlink()
    for name in ('manifest.json', 'LICENSE'):
        target = plugin / name
        safe(target)
        shutil.copyfile(ROOT / 'plugins/scarecrow' / name, target)
    private_json(settings_path, settings)
    enabled_path = vault / '.obsidian/community-plugins.json'
    safe(enabled_path)
    enabled = json.loads(enabled_path.read_text()) if enabled_path.exists() else []
    if not isinstance(enabled, list):
        raise SystemExit('Unexpected Obsidian community plugin configuration.')
    if 'scarecrow' not in enabled:
        enabled.append('scarecrow')
    private_json(enabled_path, enabled)
    private_json(data / 'scarecrow/connection.json', dict(settings, enabled=True, vault=str(vault)))
    print('Scarecrow 0.1.1 installed. Open/reload this vault in Obsidian; restart Marionette to register read_vault.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, help='Explicit vault; otherwise use the selected log/data directory.')
    parser.add_argument('--data', type=Path, default=Path(os.environ.get('MARIONETTE_DATA_DIR', ROOT / 'data')))
    parser.add_argument('--port', type=int, default=27124)
    args = parser.parse_args()
    logs = Path(os.environ.get('MARIONETTE_LOG_DIR') or args.data / 'conversations')
    vault = args.vault if args.vault is not None else logs / 'obsidian-vault'
    install(vault, args.data, args.port)
