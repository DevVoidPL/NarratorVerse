"""Explicit native import/CPU diagnostics; never downloads or loads model weights."""
from __future__ import annotations

import importlib
import json
import os
import sys


def inspect_runtime(*, importer=importlib.import_module):
    report = dict(ok=True, executable=sys.executable, python=sys.version.split()[0],
                  pythonpath=list(sys.path), ld_library_path=os.environ.get('LD_LIBRARY_PATH', ''),
                  modules={})
    for name, api in (('ctranslate2', 'Translator'), ('sentencepiece', 'SentencePieceProcessor')):
        detail = {}
        try:
            module = importer(name)
            detail.update(version=getattr(module, '__version__', 'unknown'),
                          path=getattr(module, '__file__', 'unknown'))
            if not callable(getattr(module, api, None)):
                raise RuntimeError(f'{name}: brak natywnego API {api}')
            if name == 'ctranslate2':
                types = sorted(module.get_supported_compute_types('cpu'))
                if not types:
                    raise RuntimeError('CTranslate2 nie zgłasza obsługiwanych typów CPU')
                detail['cpu_compute_types'] = types
            else:
                module.SentencePieceProcessor()
            detail['ok'] = True
        except Exception as error:
            detail.update(ok=False, error=f'{type(error).__name__}: {error}')
            report['ok'] = False
        report['modules'][name] = detail
    return report


def main():
    report = inspect_runtime()
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())