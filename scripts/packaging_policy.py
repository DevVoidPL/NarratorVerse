"""Reviewed packaging boundaries, independent of Git and ignore rules."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil


def policy(root):
    return json.loads((root / 'flatpak/publication-files.json').read_text())


def safe_file(root, name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('Unsafe policy path: ' + name)
    target = root
    for part in path.parts:
        target = target / part
        if target.is_symlink():
            raise ValueError('Symlink input: ' + name)
    if not target.is_file():
        raise ValueError('Missing input: ' + name)
    return target


def validate(root, names, roots, excluded=()):
    allowed = set(names) | set(excluded)
    for base in roots:
        directory = root / base
        if directory.is_symlink():
            raise ValueError('Symlink input: ' + base)
        for path in directory.rglob('*'):
            relative = path.relative_to(root)
            if any(part in ('target', 'node_modules', '__pycache__', '.pytest_cache')
                   for part in relative.parts):
                continue
            if path.is_symlink():
                raise ValueError('Symlink input: ' + relative.as_posix())
            if path.is_file() and relative.as_posix() not in allowed:
                raise ValueError('Unexpected input: ' + relative.as_posix())
    for name in names:
        safe_file(root, name)


def copy_files(root, destination, names):
    for name in names:
        source = safe_file(root, name)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def validate_components(root, entries):
    validate(root, entries, ['components'])
    for name, expected in entries.items():
        with safe_file(root, name).open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != expected:
            raise ValueError('SHA-256 mismatch: ' + name)


def normalize_manifest(path, work):
    """Builder writes its expanded manifest into /app after installation."""
    text = path.read_text()
    # Structural JSON roundtrip ensures unusual path characters stay valid.
    def replace(value):
        if isinstance(value, str):
            return value.replace(str(work), '@WORK@')
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        return value
    import os
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as output:
        output.write(json.dumps(replace(json.loads(text)), indent=2) + '\n')
        temporary = Path(output.name)
    temporary.chmod(path.stat().st_mode & 0o777)
    os.replace(temporary, path)


if __name__ == '__main__':
    import sys
    from pathlib import Path
    if len(sys.argv) != 3:
        raise SystemExit('Usage: packaging_policy.py APP_MANIFEST WORK_DIRECTORY')
    normalize_manifest(Path(sys.argv[1]), Path(sys.argv[2]))
