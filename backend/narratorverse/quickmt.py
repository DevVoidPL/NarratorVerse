"""Local QuickMT provider; verified SHA-256, lazy CPU worker, no cloud fallback."""
from __future__ import annotations

from functools import partial
import hashlib
import importlib.util
from pathlib import Path
from game_optimization_linux.config import NARRATOR_COMPONENTS_DIR
from .quickmt_model import (QUICKMT_REVISION, QUICKMT_FILES,
                           QUICKMT_COMPONENT_ID, QUICKMT_PROVIDER_ID)

from game_optimization_linux.services.narrator_translation import (
    LocalCTranslate2TranslationProvider, _SubprocessTranslationWorker,
)

def quickmt_layout(root: Path) -> tuple[Path, Path, str] | None:
    root = Path(root)
    try:
        for name, (size, kind, expected) in QUICKMT_FILES.items():
            path = root / name
            if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
                return None
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                return None
    except OSError:
        return None
    return root, root / 'src.spm.model', ''


def quickmt_runtime_available() -> bool:
    try:
        return all(importlib.util.find_spec(name) is not None
                   for name in ('ctranslate2', 'sentencepiece'))
    except (ImportError, ValueError):
        return False


class QuickMTTranslationProvider(LocalCTranslate2TranslationProvider):
    provider_id = QUICKMT_PROVIDER_ID
    component_id = QUICKMT_COMPONENT_ID
    model_version = QUICKMT_REVISION

    def __init__(self, model_dir: Path | None = None, *, runtime_available=quickmt_runtime_available,
                 worker_factory=None, **kwargs):
        self._checked_signature = None
        self._checked_layout = None
        super().__init__(component_path=model_dir or NARRATOR_COMPONENTS_DIR / self.component_id, runtime_available=runtime_available,
                         worker_factory=worker_factory or partial(
                             _SubprocessTranslationWorker,
                             worker_module='narratorverse.quickmt_worker'), **kwargs)

    def _layout(self):
        try:
            signature = tuple((name, path.stat().st_size, path.stat().st_mtime_ns,
                               path.stat().st_ctime_ns, path.stat().st_ino, path.is_symlink())
                              for name in QUICKMT_FILES
                              for path in (self._component_path / name,))
        except OSError:
            return None
        with self._worker_lock:
            if signature != self._checked_signature:
                self._checked_layout = quickmt_layout(self._component_path)
                self._checked_signature = signature
            return self._checked_layout

    @property
    def status_message(self):
        if not self._runtime_available():
            return 'QuickMT requires local CTranslate2 and SentencePiece in the backend runtime'
        if self._layout() is None:
            return 'QuickMT files are missing or do not match pinned revision ' + QUICKMT_REVISION
        return 'QuickMT EN→PL is ready (local CPU)'

    def translate(self, text, **kwargs):
        if not self.available:
            raise RuntimeError(self.status_message)
        return super().translate(text, **kwargs)