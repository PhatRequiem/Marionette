"""Move legacy personal-data paths without rewriting their contents.

Call only while the checkout's chat lock is held and Discord is stopped.
Conflicting destinations and symbolic links require operator review.
"""
from pathlib import Path


def migrate_personal_paths(root):
    root = Path(root)
    moves = [('identities', 'contacts'), ('characters', 'contact_notes'), ('self', 'soul')]
    active = []
    for old, new in moves:
        source, target = root / old, root / new
        for path in (source, target):
            if path.is_symlink() or (path.exists() and any(p.is_symlink() for p in path.rglob('*'))):
                raise ValueError('Personal-data migration refuses symbolic links.')
        # Reset preserves empty directory trees. They contain nothing to migrate.
        if not source.exists() or (source.is_dir() and all(p.is_dir() for p in source.rglob('*'))):
            continue
        active.append((old, new))
        if target.exists():
            raise ValueError(f'Both {old} and {new} exist; review before migrating.')
    soul = root / ('self' if ('self', 'soul') in active else 'soul')
    if (soul / 'identity.json').exists() and (soul / 'profile.json').exists():
        raise ValueError('Both legacy and current soul files exist; review before migrating.')
    for old, new in active:
        (root / old).rename(root / new)
    old = root / 'soul/identity.json'
    if old.exists():
        old.rename(root / 'soul/profile.json')
