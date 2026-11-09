"""Small, portable profile registry; identification is not authentication."""
import json
import os
from pathlib import Path
import tempfile
import uuid


def valid_name(name):
    return isinstance(name, str) and 0 < len(name.strip()) <= 80 and all(c.isprintable() for c in name)


class Profiles:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
            self.validate()
        else:
            owner = str(uuid.uuid4())
            self.data = {'version': 1, 'owner_uuid': owner, 'profiles': [
                {'uuid': owner, 'name': 'Phat', 'discord_id': None}]}
            self.save()

    @property
    def profiles(self):
        return self.data['profiles']

    def validate(self):
        def require(condition):
            if not condition:
                raise ValueError

        try:
            require(self.data['version'] == 1)
            ids, names, accounts = set(), set(), set()
            for profile in self.profiles:
                uid, name, account = profile['uuid'], profile['name'], profile['discord_id']
                require(str(uuid.UUID(uid)) == uid and uid not in ids)
                require(valid_name(name) and name.casefold() not in names)
                if account is not None:
                    require(isinstance(account, str) and account.isascii() and account.isdecimal())
                    require(0 < int(account) < 2**64 and account not in accounts)
                    accounts.add(account)
                ids.add(uid)
                names.add(name.casefold())
            require(self.data['owner_uuid'] in ids)
        except (KeyError, TypeError, ValueError, AttributeError):
            raise ValueError('Invalid profiles file; restore or repair it rather than resetting identities.') from None

    def save(self):
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
        if owner['discord_id'] == account:
            return
        if owner['discord_id'] is not None or any(p['discord_id'] == account for p in self.profiles):
            raise ValueError('Discord account differs from saved identity; review profiles.json before relinking.')
        owner['discord_id'] = account
        self.save()

    def add(self, name):
        name = name.strip()
        if not valid_name(name) or any(p['name'].casefold() == name.casefold() for p in self.profiles):
            raise ValueError('Use a unique, printable profile name of 1–80 characters.')
        profile = {'uuid': str(uuid.uuid4()), 'name': name, 'discord_id': None}
        self.profiles.append(profile)
        try:
            self.save()
        except OSError:
            self.profiles.pop()
            raise
        return profile

    def select(self):
        while True:
            print('\nWho is chatting?', flush=True)
            for number, profile in enumerate(self.profiles, 1):
                print(f'{number}. {profile["name"]}')
            print(f'{len(self.profiles) + 1}. Add new profile', flush=True)
            choice = input('Profile: ').strip()
            if choice.isascii() and choice.isdecimal():
                number = int(choice)
                if 1 <= number <= len(self.profiles):
                    return self.profiles[number - 1]
                if number == len(self.profiles) + 1:
                    try:
                        return self.add(input('Name: '))
                    except ValueError as error:
                        print(error)
                        continue
            print('Choose a listed number.')

    def resolve(self, source, sender_id):
        key = 'uuid' if source == 'terminal' else 'discord_id'
        if source not in ('terminal', 'discord'):
            raise ValueError('Unknown message source.')
        profile = next((p for p in self.profiles if p[key] == sender_id), None)
        if profile is None:
            raise ValueError('Sender has no linked profile.')
        return {'source': source, 'sender_id': sender_id,
                'display_name': profile['name'], 'person_uuid': profile['uuid']}


def message_with_identity(message, identity):
    return ('Sender metadata (provided by Marionette):\n' + json.dumps(identity, ensure_ascii=False)
            + '\n\nMessage:\n' + message)
