#!/usr/bin/env python3
"""Install pinned, verified local runtime and model. No services or root access."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads(Path(__file__).with_name("downloads.json").read_text())


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(spec, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and digest(target) == spec["sha256"]:
        print(f"Verified existing {target.name}", flush=True)
        return
    partial = target.with_name(target.name + ".part")
    print(f"Downloading {target.name}", flush=True)
    with urllib.request.urlopen(spec["url"], timeout=60) as source, partial.open("wb") as out:
        shutil.copyfileobj(source, out, 1024 * 1024)
    if digest(partial) != spec["sha256"]:
        partial.unlink()
        raise RuntimeError(f"Checksum mismatch: {target.name}")
    partial.replace(target)
    print(f"Verified {target.name}", flush=True)


def main():
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("This pinned runtime requires x86_64 Linux.")
    required = ("bash", "script", "xdg-terminal-exec", "tail", "mktemp", "date")
    missing = [command for command in required if shutil.which(command) is None]
    if missing:
        raise SystemExit("Install required system commands first: " + ", ".join(missing))
    spec = MANIFEST["runtime"]
    archive = ROOT / "data/downloads" / spec["url"].rsplit("/", 1)[-1]
    download(spec, archive)
    destination = ROOT / "runtime/llama.cpp" / spec["version"]
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as bundle:
        bundle.extractall(destination, filter="data")
    executable = destination / spec["executable"]
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise SystemExit(f"Runtime executable missing or not executable: {executable}")
    download(MANIFEST["model"], ROOT / "data/models" / MANIFEST["model"]["filename"])
    print("Setup complete. Run ./scripts/native-linux/chat.sh", flush=True)


if __name__ == "__main__":
    main()
