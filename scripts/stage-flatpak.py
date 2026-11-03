#!/usr/bin/env python3
"""Assemble a local snapshot with owner-authorized Voidek, never user data."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
APP_ID = 'io.github.DevVoidPL.NarratorVerse'
COMPONENTS = ('ocr.english-local', 'ocr.polish-local', 'ocr.rapidocr-local', 'tts.voidek')


def copy_tree(source, destination):
    if not source.is_dir(): raise RuntimeError(f'Missing input directory: {source}')
    for path in source.rglob('*'):
        if path.is_symlink(): raise RuntimeError(f'Symlink not allowed in snapshot: {path}')
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.pytest_cache'))


def stage_quickmt_runtime(destination):
    source = ROOT / '.tools/quickmt-python'
    metadata = source / 'sentencepiece-0.2.1.dist-info'
    license_file = ROOT / 'licenses/sentencepiece-LICENSE.txt'
    if not (metadata / 'METADATA').is_file() or not (source / 'sentencepiece').is_dir():
        raise RuntimeError('Missing SentencePiece; run scripts/prepare-quickmt-runtime.sh first')
    if not license_file.is_file() or license_file.is_symlink():
        raise RuntimeError('Missing SentencePiece license: licenses/sentencepiece-LICENSE.txt')
    details = importlib.metadata.PathDistribution(metadata)
    if details.metadata['Name'] != 'sentencepiece' or details.version != '0.2.1':
        raise RuntimeError('Expected pinned SentencePiece 0.2.1')
    if not (source / 'sentencepiece/_sentencepiece.cpython-313-x86_64-linux-gnu.so').is_file():
        raise RuntimeError('Missing CPython 3.13 / x86_64 SentencePiece native extension')
    for name in ('sentencepiece', 'sentencepiece-0.2.1.dist-info'):
        if (destination / name).exists():
            raise RuntimeError(f'Refusing to overwrite existing runtime package: {name}')
    for name in ('sentencepiece', 'sentencepiece-0.2.1.dist-info'):
        copy_tree(source / name, destination / name)


def stage(destination):
    binary = ROOT / 'src-tauri/target/release/narratorverse'
    if not binary.is_file(): raise RuntimeError('Build the release binary first')
    app = destination / 'share/narratorverse'
    if app.exists(): raise RuntimeError(f'Refusing to overwrite staged application: {app}')
    app.mkdir(parents=True)
    copy_tree(ROOT / 'backend', app / 'backend')
    copy_tree(ROOT / 'bin', app / 'bin')
    # .runtime/python is an obsolete duplicate; Python imports from lib only.
    for name in ('lib', 'lib64', 'bin', 'share', 'libexec'):
        source = ROOT / '.runtime' / name
        if source.exists(): copy_tree(source, app / '.runtime' / name)
    stage_quickmt_runtime(app / '.runtime/lib/python3.13/site-packages')
    for component in COMPONENTS:
        copy_tree(ROOT / 'components' / component, app / 'components' / component)
    copy_tree(ROOT / 'licenses', app / 'licenses')
    shutil.copy2(ROOT / 'LICENSE', app / 'LICENSE')
    (destination / 'bin').mkdir(exist_ok=True)
    shutil.copy2(binary, destination / 'bin/narratorverse')
    for source, target in (
        (ROOT / f'data/{APP_ID}.desktop', destination / f'share/applications/{APP_ID}.desktop'),
        (ROOT / f'data/{APP_ID}.metainfo.xml', destination / f'share/metainfo/{APP_ID}.metainfo.xml'),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        target = destination / f'share/icons/hicolor/{size}x{size}/apps/{APP_ID}.png'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f'data/icons/{size}x{size}.png', target)
    packages = []
    for dist in importlib.metadata.distributions(path=[str(app / '.runtime/lib/python3.13/site-packages')]):
        packages.append({'name': dist.metadata.get('Name'), 'version': dist.version,
                         'license': dist.metadata.get('License-Expression') or dist.metadata.get('License'),
                         'classifiers': dist.metadata.get_all('Classifier', [])})
    (app / 'licenses/python-packages.json').write_text(json.dumps(packages, indent=2))
    inventory = {}
    for path in sorted(destination.rglob('*')):
        if path.is_symlink(): raise RuntimeError(f'Unexpected staged symlink: {path}')
        if path.is_file():
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            inventory[str(path.relative_to(destination))] = {'bytes': path.stat().st_size, 'sha256': digest}
    (app / 'licenses/snapshot-files.json').write_text(json.dumps(inventory, indent=2))
    forbidden = ('tts.custom-voices', '.private', 'reference', 'profiles.json', 'quick-read.json',
                 'audio-balance-recovery.json', 'capture-grants.json', 'translation.opus-en-pl',
                 'translation-cache.sqlite3', 'quickmt-en-pl', 'src.spm.model', 'tgt.spm.model')
    for path in destination.rglob('*'):
        if any(part in forbidden for part in path.relative_to(destination).parts):
            raise RuntimeError(f'Forbidden package input: {path}')
    print(f'Staged {len(inventory)} files; owner-authorized Voidek included; user data and custom voices excluded.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dest', required=True, type=Path)
    args = parser.parse_args()
    stage(args.dest.resolve())