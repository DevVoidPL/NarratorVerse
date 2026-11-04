#!/usr/bin/env python3
"""Prepare verified fresh inputs. Never read an installed runtime or build output."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import urllib.error
import urllib.request
import zipfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from packaging_policy import copy_files, policy, validate

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fetch(artifact, directory):
    name = artifact['filename']
    if Path(name).name != name:
        raise ValueError('Unsafe artifact filename')
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    if target.exists():
        if target.is_symlink() or digest(target) != artifact['sha256']:
            raise ValueError('SHA-256 mismatch: ' + str(target))
        return target
    url = artifact['url']
    if not url.startswith('https://'):
        raise ValueError('HTTPS source required: ' + url)
    for attempt in range(3):
        with tempfile.NamedTemporaryFile(prefix=name + '.', suffix='.pending', dir=directory, delete=False) as output:
            pending = Path(output.name)
        try:
            with urllib.request.urlopen(url, timeout=120) as source, pending.open('wb') as output:
                if not source.url.startswith('https://'):
                    raise ValueError('Non-HTTPS redirect')
                shutil.copyfileobj(source, output)
            break
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise
    if digest(pending) != artifact['sha256']:
        raise ValueError('SHA-256 mismatch: ' + str(pending))
    pending.rename(target)
    return target


def unpack_wheel(archive, destination):
    with zipfile.ZipFile(archive) as wheel:
        for entry in wheel.infolist():
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or '..' in path.parts or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError('Unsafe wheel member: ' + entry.filename)
        destination.mkdir(parents=True, exist_ok=True)
        wheel.extractall(destination)


def component_manifest(directory, metadata):
    files = []
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlink in model component')
        if path.is_file() and path.name != 'component.json':
            files.append({'path': path.relative_to(directory).as_posix(),
                          'size': path.stat().st_size, 'sha256': digest(path)})
    # Existing component reader requires this stable schema identity.
    manifest = dict(metadata, schema_version=1, managed_by='game-optimization-linux', files=files)
    (directory / 'component.json').write_text(json.dumps(manifest, indent=2) + '\n')


def source_snapshot(source, destination):
    if destination.exists():
        raise ValueError('Refusing to replace source snapshot')
    rules = policy(ROOT)
    validate(source, rules['build'], rules['source_roots'], rules['excluded_source'])
    destination.mkdir(parents=True)
    copy_files(source, destination, rules['build'])


def prepare(work, voidek, wheel_cache=None):
    lock = json.loads((ROOT / 'flatpak/python-lock.json').read_text())
    wheelhouse = work / 'wheelhouse'
    for artifact in lock['artifacts']:
        if wheel_cache is not None:
            cached = wheel_cache / artifact['filename']
            if cached.exists():
                if cached.is_symlink() or digest(cached) != artifact['sha256']:
                    raise ValueError('SHA-256 mismatch in wheel cache: ' + str(cached))
                wheelhouse.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cached, wheelhouse / cached.name)
        fetch(artifact, wheelhouse)
    shutil.copy2(ROOT / 'flatpak/python-requirements.lock', work / 'python-requirements.lock')
    components = work / 'components'
    if components.exists():
        raise ValueError('Refusing to merge components; use a new work directory')
    components.mkdir()
    models = json.loads((ROOT / 'flatpak/components-lock.json').read_text())
    for model in models:
        directory = components / model['component_id']
        directory.mkdir()
        if model.get('archive'):
            artifact = model['archive']
            archive = fetch(artifact, work / 'downloads')
            unpack_wheel(archive, directory)
        for artifact in model.get('files', []):
            if artifact.get('owner_input'):
                if voidek is None:
                    raise ValueError('Voidek owner-supplied original required: --voidek-input DIR (not an installed component)')
                source = voidek / artifact['filename']
                if source.is_symlink() or not source.is_file() or digest(source) != artifact['sha256']:
                    raise ValueError('Voidek SHA-256 mismatch or missing original: ' + str(source))
            else:
                source = fetch(artifact, work / 'downloads')
            target = directory / artifact.get('target', artifact['filename'])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for name in model.get('project_notices', []):
            shutil.copy2(ROOT / 'licenses' / name, directory / name)
        component_manifest(directory, {k: v for k, v in model.items()
                                      if k not in ('files', 'archive', 'project_notices')})
    source_snapshot(ROOT, work / 'source')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--voidek-input', type=Path)
    parser.add_argument('--wheel-cache', type=Path, help='Optional verified wheel archive cache, not installed packages')
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    prepare(args.work.resolve(), args.voidek_input.resolve() if args.voidek_input else None,
            args.wheel_cache.resolve() if args.wheel_cache else None)