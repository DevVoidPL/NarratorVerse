#!/usr/bin/env python3
"""Install only freshly built outputs, preserving wheel/model license files."""
import json
from pathlib import Path
import shutil
import subprocess

root = Path.cwd()
app = Path('/app/share/narratorverse')
app.mkdir(parents=True, exist_ok=False)
for name in ('backend', 'bin', 'licenses'):
    shutil.copytree(root / name, app / name,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
shutil.copytree(root / 'components', app / 'components')
shutil.copy2(root / 'LICENSE', app / 'LICENSE')
subprocess.run(['install', '-Dm755', 'src-tauri/target/release/narratorverse',
                '/app/bin/narratorverse'], check=True)
app_id = 'io.github.DevVoidPL.NarratorVerse'
for source, target in [
    (f'data/{app_id}.desktop', f'/app/share/applications/{app_id}.desktop'),
    (f'data/{app_id}.metainfo.xml', f'/app/share/metainfo/{app_id}.metainfo.xml'),
]:
    subprocess.run(['install', '-Dm644', source, target], check=True)
for size in (16, 24, 32, 48, 64, 128, 256, 512):
    subprocess.run(['install', '-Dm644', f'data/icons/{size}x{size}.png',
        f'/app/share/icons/hicolor/{size}x{size}/apps/{app_id}.png'], check=True)
for name in ('python-lock.json', 'components-lock.json', 'build-tools-lock.json', 'sdk-lock.json'):
    shutil.copy2(root / 'build-locks' / name, app / 'licenses' / name)
# Preserve source-lock provenance and available dependency notice texts, including
# frontend code embedded into the Rust executable. Missing notices remain visible
# in payload inventory/review; metadata is never substituted for license texts.
third_party = app / 'licenses/third-party'
for kind, base in [('cargo', root / 'vendor'), ('npm', root / 'node_modules')]:
    for source in base.rglob('*'):
        if source.is_file() and not source.is_symlink() and any(
                word in source.name.lower() for word in ('license', 'notice', 'copying', 'copyright')):
            target = third_party / kind / source.relative_to(base)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
shutil.copy2(root / 'src-tauri/Cargo.lock', app / 'licenses/Cargo.lock')
shutil.copy2(root / 'package-lock.json', app / 'licenses/package-lock.json')