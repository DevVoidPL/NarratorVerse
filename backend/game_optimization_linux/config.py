"""Independent NarratorVerse paths. No import of the original application's config."""
import os
from pathlib import Path

APP_ID = 'io.github.DevVoidPL.NarratorVerse'
APP_NAME = 'NarratorVerse'
APP_VERSION = '0.1.0'

def xdg(name, fallback):
    value = Path(os.environ.get(name, str(Path.home() / fallback))).expanduser()
    return value if value.is_absolute() else Path.home() / fallback

CONFIG_DIR = xdg('XDG_CONFIG_HOME', '.config') / 'narratorverse'
STATE_DIR = xdg('XDG_STATE_HOME', '.local/state') / 'narratorverse'
CACHE_DIR = xdg('XDG_CACHE_HOME', '.cache') / 'narratorverse'
DATA_DIR = xdg('XDG_DATA_HOME', '.local/share') / 'narratorverse'
GAMES_CONFIG_DIR = CONFIG_DIR / 'profiles'
NARRATOR_COMPONENTS_DIR = DATA_DIR / 'narrator/components'
NARRATOR_CAPTURE_GRANTS_FILE = CONFIG_DIR / 'capture-grants.json'
NARRATOR_TRANSLATION_CACHE_FILE = CACHE_DIR / 'translation-cache.sqlite3'
BUNDLED_NARRATOR_COMPONENTS_DIR = Path(__file__).resolve().parents[2] / 'components'