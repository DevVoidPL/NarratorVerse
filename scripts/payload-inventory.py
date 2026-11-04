#!/usr/bin/env python3
"""Inventory final /app bytes and installed metadata; unknown licensing fails review, not hidden."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess


def inventory(root):
    files = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            files.append({'path': path.relative_to(root).as_posix(), 'symlink': str(path.readlink())})
        elif path.is_file():
            with path.open('rb') as stream:
                prefix = stream.read(4)
                stream.seek(0)
                sha = hashlib.file_digest(stream, 'sha256').hexdigest()
            row = {'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha}
            if prefix == b'\x7fELF':
                result = subprocess.run(['readelf', '-d', str(path)], capture_output=True, text=True, check=True)
                row['elf_dynamic'] = result.stdout
            files.append(row)
    packages = []
    owners = {}
    for dist in importlib.metadata.distributions(path=[str(root / 'lib/python3.13/site-packages')]):
        packages.append({'name': dist.metadata['Name'], 'version': dist.version,
                         'license': dist.metadata.get('License-Expression') or dist.metadata.get('License'),
                         'notices': [str(p) for p in dist.files or [] if any(
                             word in str(p).lower() for word in ('license', 'notice', 'copying'))]})
        for member in dist.files or []:
            located = Path(dist.locate_file(member)).resolve()
            if located.is_relative_to(root.resolve()):
                owners[located.relative_to(root.resolve()).as_posix()] = {
                    'name': dist.metadata['Name'], 'version': dist.version,
                    'license': packages[-1]['license'], 'notice_review':
                    'REQUIRED' if not packages[-1]['notices'] else 'texts-present-review-required'}
    models = [json.loads(p.read_text()) for p in (root / 'share/narratorverse/components').glob('*/component.json')]
    for entry in files:
        if entry['path'] in owners:
            entry['distribution'] = owners[entry['path']]
        elif 'elf_dynamic' in entry:
            entry['license_mapping'] = 'REVIEW_REQUIRED: native, debug or bundled library'
    return {'files': files, 'python': packages, 'components': models,
            'redistribution_review': 'OPEN: metadata is not a license/source compliance declaration'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Refusing to overwrite inventory')
    args.output.write_text(json.dumps(inventory(args.root), indent=2) + '\n')