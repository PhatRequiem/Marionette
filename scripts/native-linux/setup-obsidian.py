#!/usr/bin/env python3
"""Install the pinned optional Obsidian plugin into this checkout's docs vault."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def main():
    spec = json.loads(Path(__file__).with_name('obsidian-downloads.json').read_text())
    plugin = ROOT / 'docs/.obsidian/plugins/obsidian-local-rest-api'
    plugin.mkdir(parents=True, exist_ok=True)
    for name, source in spec['files'].items():
        target = plugin / name
        if target.exists():
            data = target.read_bytes()
            if hashlib.sha256(data).hexdigest() != source['sha256']:
                raise SystemExit(f'Existing plugin file differs: {name}; inspect before replacing.')
        else:
            data = urllib.request.urlopen(source['url'], timeout=30).read()
            if hashlib.sha256(data).hexdigest() != source['sha256']:
                raise SystemExit(f'Checksum mismatch: {name}')
            target.write_bytes(data)
    settings = plugin / 'data.json'
    if not settings.exists():
        with settings.open('w', opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
            stream.write(json.dumps({'apiKey': secrets.token_hex(32), 'bindingHost': '127.0.0.1',
            'port': 27134, 'insecurePort': 27133, 'enableInsecureServer': True,
            'enableSecureServer': False, 'enableSignedUrls': False, 'enableConfigDirAccess': False}, indent=2)+'\n')
    settings.chmod(0o600)
    enabled = ROOT / 'docs/.obsidian/community-plugins.json'
    names = json.loads(enabled.read_text()) if enabled.exists() else []
    if 'obsidian-local-rest-api' not in names:
        names.append('obsidian-local-rest-api')
        enabled.write_text(json.dumps(names, indent=2)+'\n')
    print('Plugin verified. Open docs as an Obsidian vault and enable community plugins if prompted.')


if __name__ == '__main__':
    main()
