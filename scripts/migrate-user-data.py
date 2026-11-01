#!/usr/bin/env python3
"""Copy user data from LektorPL to NarratorVerse without removing the originals.

The old identity appears here only to locate existing data, never as a runtime
alias. Portal grants are application-ID scoped and intentionally not imported.
Run with the old and new applications closed, before first NarratorVerse launch.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

OLD_ID = 'io.github.DevVoidPL.LektorPL'
NEW_ID = 'io.github.DevVoidPL.NarratorVerse'
OLD_SLUG = 'lektorpl'
NEW_SLUG = 'narratorverse'


def migrate(source, destination):
    source, destination = Path(source), Path(destination)
    marker = destination / '.narratorverse-migration.json'
    if marker.exists(): return json.loads(marker.read_text())
    if not source.is_dir(): return {'status': 'no_previous_data', 'files': []}
    if source.resolve() == destination.resolve(): raise ValueError('Source and destination must differ')
    mappings = [('config', 'config'), ('data', 'data'), ('cache', 'cache'),
                ('.local/state', '.local/state')]
    planned = []
    for old, new in mappings:
        base = source / old / OLD_SLUG
        if not base.is_dir(): continue
        for p in base.rglob('*'):
            if p.is_symlink(): raise ValueError(f'Refusing symlink in previous data: {p}')
            if not p.is_file() or p.name in ('capture-grants.json', '.seed.lock'): continue
            relative = p.relative_to(base)
            relative = Path(*(part.replace('.lektorpl-origin', '.narratorverse-origin') for part in relative.parts))
            target = destination / new / NEW_SLUG / relative
            if target.exists(): raise FileExistsError(f'Refusing to overwrite new data: {target}')
            planned.append((p, target))
    report = {'status': 'migrated', 'source_identity': OLD_ID, 'identity': NEW_ID,
              'portal_grants': 'not_copied_application_scoped', 'files': []}
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    for old, new in planned:
        new.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Exclusive creation, no clobber even if another process starts meanwhile.
        with old.open('rb') as src, new.open('xb') as dest: shutil.copyfileobj(src, dest)
        shutil.copystat(old, new)
        digest = hashlib.sha256(new.read_bytes()).hexdigest()
        if digest != hashlib.sha256(old.read_bytes()).hexdigest(): raise RuntimeError(f'Copy verification failed: {old}')
        report['files'].append({'path': str(new.relative_to(destination)), 'sha256': digest})
    temporary = marker.with_suffix('.tmp')
    with temporary.open('x') as stream: json.dump(report, stream, indent=2)
    os.chmod(temporary, 0o600)
    temporary.replace(marker)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path.home()/'.var/app'/OLD_ID)
    parser.add_argument('--destination', type=Path, default=Path.home()/'.var/app'/NEW_ID)
    args = parser.parse_args()
    report = migrate(args.source, args.destination)
    print(json.dumps({'status': report['status'], 'files': len(report['files'])}))