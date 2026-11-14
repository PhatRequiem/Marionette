"""Persistent admission policy shared by main chat and the Discord adapter."""
import json
import os
from pathlib import Path
import tempfile


class DiscordAccess:
    def __init__(self, data):
        self.path = Path(data) / 'discord/access.json'

    def enabled(self):
        try:
            value = json.loads(self.path.read_text())
            return isinstance(value, dict) and value.get('allow_other_dms') is True
        except FileNotFoundError:
            return True  # Preserve existing access until the owner changes it.
        except (OSError, ValueError):
            return False  # Unreadable/invalid policy must not open access.

    def set_enabled(self, enabled):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix='.access-')
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump({'allow_other_dms': bool(enabled)}, stream)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            Path(name).unlink(missing_ok=True)
