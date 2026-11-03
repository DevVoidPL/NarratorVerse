"""Explicit first-run copying of already verified components, never original data."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from game_optimization_linux.config import NARRATOR_COMPONENTS_DIR, BUNDLED_NARRATOR_COMPONENTS_DIR
from game_optimization_linux.services.narrator_components import NarratorComponentManager
import shutil

manager = NarratorComponentManager()
source = NarratorComponentManager(BUNDLED_NARRATOR_COMPONENTS_DIR)
for directory in BUNDLED_NARRATOR_COMPONENTS_DIR.iterdir():
    if not directory.is_dir() or directory.name.startswith('.') or directory.name == 'tts.custom-voices': continue
    target = NARRATOR_COMPONENTS_DIR / directory.name
    if target.exists(): continue
    good, message = source.verify_installed(directory.name)
    if not good: raise RuntimeError(f'{directory.name}: {message}')
    shutil.copytree(directory, target, symlinks=False)
    print(f'Copied verified component {directory.name} to independent directory')