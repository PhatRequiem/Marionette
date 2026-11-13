#!/usr/bin/env python3
"""Install pinned local Obsidian integration; never modifies conversation content."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).parent / 'obsidian'

def private_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    path.chmod(0o600)

def main():
    os.umask(0o077)
    node_major = int(subprocess.check_output(['node', '--version'], text=True).strip().lstrip('v').split('.')[0])
    if node_major < 24:
        raise SystemExit('Cyanheads 3.9.0 requires Node.js 24 or newer.')
    runtime = ROOT / 'runtime/obsidian-mcp'
    runtime.mkdir(parents=True, exist_ok=True)
    for name in ('package.json', 'package-lock.json'):
        shutil.copyfile(SPEC / name, runtime / name)
    subprocess.run(['npm', 'ci', '--prefix', str(runtime), '--ignore-scripts', '--no-audit', '--no-fund'], check=True)
    vault = ROOT / 'data/conversations/obsidian-vault'
    if not (vault / 'Welcome.md').is_file():
        raise SystemExit('Refresh the conversation vault before setup.')
    plugin = vault / '.obsidian/plugins/obsidian-local-rest-api'
    if any(p.is_symlink() for p in (plugin, *plugin.parents)) or (plugin.exists() and any(p.is_symlink() for p in plugin.rglob('*'))):
        raise SystemExit('Plugin installation refuses symbolic links.')
    plugin.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((SPEC / 'downloads.json').read_text())
    for asset in manifest['assets']:
        cache = ROOT / 'data/downloads/obsidian-local-rest-api' / manifest['plugin_version'] / asset['name']
        expected = asset['digest'].removeprefix('sha256:')
        content = cache.read_bytes() if cache.exists() else urllib.request.urlopen(asset['browser_download_url'], timeout=60).read()
        if hashlib.sha256(content).hexdigest() != expected:
            raise SystemExit('Plugin checksum mismatch: ' + asset['name'])
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(content)
        (plugin / asset['name']).write_bytes(content)
    settings_path = plugin / 'data.json'
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    settings.update(bindingHost='127.0.0.1', enableInsecureServer=True, insecurePort=27123,
                    enableSecureServer=True, enableSignedUrls=False, enableConfigDirAccess=False, enableVerboseLogging=False)
    settings.setdefault('apiKey', secrets.token_hex(32))
    private_json(settings_path, settings)
    enabled_path = vault / '.obsidian/community-plugins.json'
    enabled = json.loads(enabled_path.read_text()) if enabled_path.exists() else []
    if 'obsidian-local-rest-api' not in enabled:
        enabled.append('obsidian-local-rest-api')
    private_json(enabled_path, enabled)
    private_json(ROOT / 'data/obsidian/connection.json', {'enabled': True, 'api_key': settings['apiKey'],
                 'base_url': 'http://127.0.0.1:27123', 'vault': str(vault)})
    print('Installed pinned Cyanheads and Obsidian API plugin. Open/reload the Marionette vault to activate the plugin. Read-only access is enforced by Marionette and Cyanheads.')

if __name__ == '__main__':
    main()
