#!/usr/bin/env python3
"""Install pinned, verified local runtime and model. No services or root access."""
import hashlib
import fcntl
import json
import os
from pathlib import Path
import platform
import shutil
import tarfile
import tempfile
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
    print(f"Downloading {target.name}", flush=True)
    partial = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".part", delete=False) as out:
            partial = Path(out.name)
            with urllib.request.urlopen(spec["url"], timeout=60) as source:
                shutil.copyfileobj(source, out, 1024 * 1024)
        if digest(partial) != spec["sha256"]:
            raise RuntimeError(f"Checksum mismatch: {target.name}")
        partial.replace(target)
    finally:
        if partial is not None:
            partial.unlink(missing_ok=True)
    print(f"Verified {target.name}", flush=True)


def install_runtime(archive, destination, executable_name):
    """Validate existing files without overwriting a runtime that may be in use."""
    with tarfile.open(archive) as bundle:
        if destination.exists():
            for member in bundle.getmembers():
                path = destination / member.name
                valid = True
                if member.isfile():
                    valid = path.is_file() and digest(path) == hashlib.file_digest(bundle.extractfile(member), "sha256").hexdigest()
                elif member.issym():
                    valid = path.is_symlink() and os.readlink(path) == member.linkname
                elif member.isdir():
                    valid = path.is_dir()
                if not valid:
                    raise RuntimeError(f"Runtime differs from verified archive: {path}. Close chats, move {destination} aside, then rerun setup.")
            print("Verified installed runtime; files left untouched.", flush=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=destination.parent, prefix=".install-") as stage:
                bundle.extractall(stage, filter="data")
                executable = Path(stage) / executable_name
                if not executable.is_file() or not os.access(executable, os.X_OK):
                    raise RuntimeError(f"Archive lacks executable: {executable_name}")
                Path(stage).rename(destination)
    executable = destination / executable_name
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise RuntimeError(f"Runtime executable missing or not executable: {executable}")


def main():
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("This pinned runtime requires x86_64 Linux.")
    required = ("bash", "script", "xdg-terminal-exec", "tail", "mktemp", "date")
    missing = [command for command in required if shutil.which(command) is None]
    if missing:
        raise SystemExit("Install required system commands first: " + ", ".join(missing))
    if not hasattr(tarfile, "data_filter"):
        raise SystemExit("Python with tarfile data extraction filters is required (Python 3.12+ recommended).")
    (ROOT / "data").mkdir(exist_ok=True)
    with (ROOT / "data/.setup.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Another setup is already running in this checkout.")
        install()


def install():
    spec = MANIFEST["runtime"]
    archive = ROOT / "data/downloads" / spec["url"].rsplit("/", 1)[-1]
    download(spec, archive)
    destination = ROOT / "runtime/llama.cpp" / spec["version"]
    install_runtime(archive, destination, spec["executable"])
    download(MANIFEST["model"], ROOT / "data/models" / MANIFEST["model"]["filename"])
    print("Setup complete. Run ./scripts/native-linux/chat.sh", flush=True)


if __name__ == "__main__":
    main()
