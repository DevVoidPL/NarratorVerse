#!/usr/bin/env python3
"""Install only reviewed project files and SHA-256 pinned model files."""
from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from packaging_policy import copy_files, policy, safe_file, validate, validate_components


def install(root, prefix):
    rules = policy(root)
    validate(root, rules['build'], rules['source_roots'],
             rules['excluded_source'] + ['src-tauri/.cargo/config.toml'])
    validate_components(root, rules['components'])
    binary = safe_file(root, 'src-tauri/target/release/narratorverse')
    locks = ['python-lock.json', 'components-lock.json', 'build-tools-lock.json', 'sdk-lock.json']
    for name in locks:
        safe_file(root, 'build-locks/' + name)
    notices = []
    for kind, base in [('cargo', root / 'vendor'), ('npm', root / 'node_modules')]:
        if not base.is_dir() or base.is_symlink():
            raise ValueError('Missing dependency input: ' + kind)
        for source in sorted(base.rglob('*')):
            if re.fullmatch(r'(?:licen[cs]e|notice|copying|copyright)(?:[-.][A-Za-z0-9_.-]+)?',
                            source.name, re.IGNORECASE) and source.is_file():
                safe_file(base, source.relative_to(base).as_posix())
                notices.append((source, kind, source.relative_to(base)))
    app = prefix / 'share/narratorverse'
    if app.exists() or app.is_symlink():
        raise ValueError('Refusing to overwrite application payload')
    app.mkdir(parents=True)
    copy_files(root, app, rules['app'])
    copy_files(root, app, rules['components'])
    target = prefix / 'bin/narratorverse'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, target)
    target.chmod(0o755)
    for source, relative in rules['desktop'].items():
        target = prefix / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(safe_file(root, source), target)
    for name in locks:
        shutil.copy2(root / 'build-locks' / name, app / 'licenses' / name)
    for source, kind, relative in notices:
        target = app / 'licenses/third-party' / kind / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for source, name in [('src-tauri/Cargo.lock', 'Cargo.lock'), ('package-lock.json', 'package-lock.json'),
                         ('flatpak/publication-files.json', 'publication-files.json')]:
        shutil.copy2(root / source, app / 'licenses' / name)


if __name__ == '__main__':
    install(Path.cwd(), Path('/app'))
