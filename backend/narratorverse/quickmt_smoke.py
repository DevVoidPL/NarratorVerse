"""Offline CPU inference smoke test through the application's QuickMT provider."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

from .quickmt import QUICKMT_REVISION, QuickMTTranslationProvider
from .quickmt_download import default_model_dir, verify_installation
from .translation_compare import runtime_versions


def smoke_test(root, text, profile):
    if not text.strip() or len(text) > 8000:
        raise ValueError('Tekst testu musi mieć od 1 do 8000 znaków')
    if profile not in ('balanced', 'fast'):
        raise ValueError('Nieprawidłowy profil tłumaczenia')
    verify_installation(root)
    provider = QuickMTTranslationProvider(root)
    try:
        started = time.monotonic()
        result = provider.translate(text, source_language='en', target_language='pl', profile_id=profile)
        if not result.translated_text.strip():
            raise RuntimeError('QuickMT zwrócił pusty tekst')
        return dict(event='quickmt_cpu_smoke_passed', revision=QUICKMT_REVISION,
                    provider_id=provider.provider_id, device='cpu', profile=profile,
                    text=text, translated_text=result.translated_text,
                    first_request_wall_ms=max(0.0, (time.monotonic() - started) * 1000),
                    runtime=runtime_versions())
    finally:
        provider.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, default=default_model_dir())
    parser.add_argument('--text', default='Do not open the door. Wait for me!')
    parser.add_argument('--profile', choices=('balanced', 'fast'), default='balanced')
    arguments = parser.parse_args(argv)
    from .quickmt_runtime import inspect_runtime
    diagnostic = inspect_runtime()
    print(json.dumps(dict(event='quickmt_native_runtime', **diagnostic), ensure_ascii=False, indent=2), flush=True)
    if not diagnostic['ok']:
        print('QuickMT: runtime nie przeszedł diagnostyki. Model nie był ładowany. '
              'Dla brakującego SentencePiece uruchom jawnie '
              'scripts/prepare-quickmt-runtime.sh przez sh, '
              'następnie ponów diagnostykę modułem narratorverse.quickmt_smoke.', file=sys.stderr)
        return 1
    try:
        report = smoke_test(arguments.model_dir, arguments.text, arguments.profile)
    except Exception as error:
        print(f'QuickMT — test CPU NIEUDANY: {error}\n'
              'Sprawdź lokalny runtime CTranslate2/SentencePiece i kompletność modelu. '
              'Po naprawie ponów diagnostykę. Nie użyto translatora zastępczego.', file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print('OK: model załadowany, wykonano tłumaczenie na CPU i zamknięto provider. '
          'To test zgodności, nie ocena jakości ani benchmark RAM/CPU.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())