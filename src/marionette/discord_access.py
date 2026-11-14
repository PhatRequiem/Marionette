"""Persistent admission policy shared by main chat and the Discord adapter."""
import json
import os
from pathlib import Path
import tempfile


class DiscordAccess:
    def __init__(self, data):
        self.path = Path(data) / 'discord/access.json'

    def policy(self):
        try:
            value = json.loads(self.path.read_text())
            if not isinstance(value, dict) or type(value.get('allow_other_dms')) is not bool:
                raise ValueError('Invalid policy')
            for key in ('allowed', 'blocked'):
                if not isinstance(value.get(key, []), list) or any(not isinstance(x, str) or not x.isdecimal() for x in value.get(key, [])):
                    raise ValueError('Invalid policy')
            return value
        except FileNotFoundError:
            return {'allow_other_dms': True}
        except (OSError, ValueError):
            return {'allow_other_dms': False}

    def enabled(self):
        return self.policy()['allow_other_dms']

    def admits(self, sender):
        value = self.policy()
        sender = str(sender)
        return sender not in value.get('blocked', []) and (value['allow_other_dms'] or sender in value.get('allowed', []))

    def set_rule(self, sender, allow):
        value = self.policy()
        for key in ('allowed', 'blocked'):
            value[key] = [x for x in value.get(key, []) if x != sender]
        value['allowed' if allow else 'blocked'].append(sender)
        self.write(value)

    def set_enabled(self, enabled):
        value = self.policy()
        value['allow_other_dms'] = bool(enabled)
        self.write(value)

    def write(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix='.access-')
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(value, stream)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            Path(name).unlink(missing_ok=True)
