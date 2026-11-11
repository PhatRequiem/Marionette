"""Small, portable profile registry; identification is not authentication."""
import copy
from datetime import datetime, timezone
import json
import re
import os
from pathlib import Path
import tempfile
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def valid_name(name):
    return isinstance(name, str) and 0 < len(name.strip()) <= 80 and all(c.isprintable() for c in name)


class Profiles:
    def __init__(self, path):
        self.path = Path(path)
        self._saved = None
        if self.path.exists():
            original = self.path.read_bytes()
            self.data = json.loads(original)
            legacy = (isinstance(self.data, dict) and type(self.data.get('version')) is int
                      and self.data['version'] == 1 and 'schema_version' not in self.data)
            if legacy:
                try:
                    self.data['schema_version'] = 2
                    del self.data['version']
                    for profile in self.data['profiles']:
                        account = profile.pop('discord_id')
                        profile.update(created_at=None, updated_at=None, preferred_name=None,
                                       timezone=None, linked_accounts=[])
                        if account is not None:
                            profile['linked_accounts'].append({'service': 'discord', 'account_id': account})
                except (KeyError, TypeError, AttributeError):
                    raise ValueError('Invalid legacy profiles file; original left untouched.') from None
            self.validate()
            if legacy:
                # Preserve the exact old bytes before replacing the registry.
                backup = self.path.with_name('profiles.v1.backup.json')
                if backup.exists():
                    if backup.read_bytes() != original:
                        raise ValueError('Existing migration backup differs; review it before migrating.')
                else:
                    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, 'wb') as output:
                        output.write(original)
                        output.flush()
                        os.fsync(output.fileno())
                self.save()
            else:
                self._saved = copy.deepcopy(self.data)
        else:
            owner = self.new_profile('Phat')
            self.data = {'schema_version': 2, 'owner_uuid': owner['uuid'], 'profiles': [owner]}
            self.save()

    @staticmethod
    def new_profile(name):
        now = datetime.now(timezone.utc).isoformat()
        return {'uuid': str(uuid.uuid4()), 'name': name, 'preferred_name': None,
                'timezone': None, 'created_at': now, 'updated_at': now,
                'linked_accounts': []}

    @property
    def profiles(self):
        return self.data['profiles']

    def validate(self):
        def require(condition):
            if not condition:
                raise ValueError

        try:
            require(type(self.data['schema_version']) is int and self.data['schema_version'] == 2)
            require(isinstance(self.profiles, list))
            ids, names, accounts = set(), set(), set()
            for profile in self.profiles:
                uid, name = profile['uuid'], profile['name']
                require(str(uuid.UUID(uid)) == uid and uid not in ids)
                require(valid_name(name) and name.casefold() not in names)
                require(profile['preferred_name'] is None or valid_name(profile['preferred_name']))
                if profile['timezone'] is not None:
                    require(isinstance(profile['timezone'], str))
                    ZoneInfo(profile['timezone'])
                for field in ('created_at', 'updated_at'):
                    if profile[field] is not None:
                        require(isinstance(profile[field], str))
                        require(datetime.fromisoformat(profile[field]).utcoffset() is not None)
                require(isinstance(profile['linked_accounts'], list))
                for link in profile['linked_accounts']:
                    service, account = link['service'], link['account_id']
                    require(isinstance(service, str) and re.fullmatch(r'[a-z][a-z0-9_-]{0,39}', service))
                    require(service != 'terminal')  # Terminal identity is the person UUID.
                    require(isinstance(account, str) and 0 < len(account) <= 256
                            and account == account.strip() and all(c.isprintable() for c in account))
                    if service == 'discord':
                        require(account.isascii() and account.isdecimal() and 0 < int(account) < 2**64)
                        account = str(int(account))
                    require((service, account) not in accounts)
                    accounts.add((service, account))
                ids.add(uid)
                names.add(name.casefold())
            require(self.data['owner_uuid'] in ids)
        except (KeyError, TypeError, ValueError, AttributeError, ZoneInfoNotFoundError):
            raise ValueError('Invalid profiles file; restore or repair it rather than resetting identities.') from None

    def save(self):
        self.validate()
        previous = {p['uuid']: p for p in self._saved['profiles']} if self._saved else {}
        for profile in self.profiles:
            if profile != previous.get(profile['uuid']):
                profile['updated_at'] = datetime.now(timezone.utc).isoformat()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Only the main chat writes profiles; its launcher lock excludes another writer.
        fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix='.profiles-')
        try:
            with os.fdopen(fd, 'w') as output:
                json.dump(self.data, output, ensure_ascii=False, indent=2)
                output.write('\n')
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
            self._saved = copy.deepcopy(self.data)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def link_owner(self, config):
        """Read only the configured account ID; never retain or log the bot token."""
        if not config.exists():
            return
        account = ''
        for line in config.read_text().splitlines():
            key, _, value = line.strip().partition('=')
            if key == 'DISCORD_ALLOWED_USER_ID':
                account = value.strip()
        if not account:
            return
        if not account.isascii() or not account.isdecimal() or not 0 < int(account) < 2**64:
            raise ValueError('Invalid DISCORD_ALLOWED_USER_ID in Discord configuration.')
        account = str(int(account))
        owner = next(p for p in self.profiles if p['uuid'] == self.data['owner_uuid'])
        links = [link for p in self.profiles for link in p['linked_accounts']
                 if link['service'] == 'discord']
        owner_links = [link for link in owner['linked_accounts'] if link['service'] == 'discord']
        if any(str(int(link['account_id'])) == account for link in owner_links):
            return
        if owner_links or any(str(int(link['account_id'])) == account for link in links):
            raise ValueError('Discord account differs from saved identity; review profiles.json before relinking.')
        old = copy.deepcopy(owner)
        owner['linked_accounts'].append({'service': 'discord', 'account_id': account})
        try:
            self.save()
        except (OSError, ValueError):
            owner.clear()
            owner.update(old)
            raise

    def add(self, name):
        name = name.strip()
        if not valid_name(name) or any(p['name'].casefold() == name.casefold() for p in self.profiles):
            raise ValueError('Use a unique, printable profile name of 1–80 characters.')
        profile = self.new_profile(name)
        self.profiles.append(profile)
        try:
            self.save()
        except OSError:
            self.profiles.pop()
            raise
        return profile

    def resolve(self, source, sender_id):
        if source not in ('terminal', 'discord'):
            raise ValueError('Unknown message source.')
        profile = next((p for p in self.profiles if
            (p['uuid'] == sender_id if source == 'terminal' else
             any(link['service'] == source and str(int(link['account_id'])) == sender_id
                 for link in p['linked_accounts'] if link['service'] == 'discord'))), None)
        if profile is None:
            raise ValueError('Sender has no linked profile.')
        return {'source': source, 'sender_id': sender_id,
                'display_name': profile['name'], 'person_uuid': profile['uuid'],
                'preferred_name': profile['preferred_name'] or profile['name'],
                'timezone': profile['timezone']}


def message_with_identity(message, identity):
    return ('Sender metadata (provided by Marionette):\n' + json.dumps(identity, ensure_ascii=False)
            + '\n\nMessage:\n' + message)
