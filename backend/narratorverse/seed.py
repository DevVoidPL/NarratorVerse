"""Seed independent storage from local, hash-verified model copies (no network)."""
import shutil
import fcntl
import hashlib
import json
from game_optimization_linux.config import NARRATOR_COMPONENTS_DIR, BUNDLED_NARRATOR_COMPONENTS_DIR
from game_optimization_linux.services.narrator_components import NarratorComponentManager

def seed():
    NARRATOR_COMPONENTS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (NARRATOR_COMPONENTS_DIR / '.seed.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if (NARRATOR_COMPONENTS_DIR / '.seeded').exists(): return
        _seed_locked()
        if BUNDLED_NARRATOR_COMPONENTS_DIR.is_dir():
            (NARRATOR_COMPONENTS_DIR / '.seeded').touch(mode=0o600)

def _seed_locked():
    root = BUNDLED_NARRATOR_COMPONENTS_DIR
    if not root.is_dir(): return
    source = NarratorComponentManager(root)
    for directory in root.iterdir():
        if not directory.is_dir() or directory.name.startswith('.') or directory.name == 'tts.custom-voices': continue
        target = NARRATOR_COMPONENTS_DIR / directory.name
        if target.exists(): continue
        good, message = source.verify_installed(directory.name)
        if not good: raise RuntimeError(f'{directory.name}: {message}')
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        staging = target.with_name('.' + target.name + '-seed')
        if staging.exists(): shutil.rmtree(staging)
        try:
            shutil.copytree(directory, staging, symlinks=False)
            manifest = json.loads((staging / 'component.json').read_text())
            for entry in manifest['files']:
                copied = staging / entry['path']
                if hashlib.sha256(copied.read_bytes()).hexdigest() != entry['sha256']:
                    raise RuntimeError(f'{directory.name}: copied component failed verification')
            (staging / '.narratorverse-origin').write_text('bundled\n')
            staging.rename(target)
        finally:
            if staging.exists(): shutil.rmtree(staging)