"""Developer-only offline QuickMT corpus timing, preserving repeated occurrences.

No OCR, TTS, cache, downloads or application profile writes. Run separately
from gameplay: only one translation provider is resident at a time.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4


def load_corpus(path):
    texts = []
    with Path(path).open(encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            try:
                record = json.loads(line)
                text = record['text'] if isinstance(record, dict) else None
                if not isinstance(text, str) or not text.strip() or len(text) > 8000:
                    raise ValueError('expected nonempty text, at most 8000 characters')
            except (ValueError, KeyError) as error:
                raise ValueError(f'Invalid corpus line {number}: {error}') from error
            texts.append(text)
    if not texts:
        raise ValueError('Corpus must contain at least one occurrence')
    return texts


def runtime_versions():
    versions = {'python': sys.version.split()[0]}
    for package in ('ctranslate2', 'sentencepiece'):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = 'not installed'
    return versions


def compare(texts, output, *, profile='balanced', passes=2,
            order=('quickmt',), provider_factory=None):
    if profile not in ('balanced', 'fast') or passes < 1:
        raise ValueError('Expected balanced/fast and at least one pass')
    if tuple(order) != ('quickmt',):
        raise ValueError('Only the installed QuickMT provider is supported')
    if not texts or any(not isinstance(text, str) or not text.strip() or len(text) > 8000
                        for text in texts):
        raise ValueError('Expected nonempty corpus of texts up to 8000 characters')
    if provider_factory is None:
        raise ValueError('An explicit local provider factory is required')
    from .quickmt import QUICKMT_REVISION
    corpus_hash = hashlib.sha256(json.dumps(texts, ensure_ascii=False).encode('utf-8')).hexdigest()
    run_id, errors = uuid4().hex, 0
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        def emit(event, **fields):
            stream.write(json.dumps(dict(event=event, run_id=run_id, **fields),
                                    ensure_ascii=False) + '\n')
            stream.flush()
        emit('comparison_started', corpus_sha256=corpus_hash, occurrences=len(texts),
             profile=profile, passes=passes, order=list(order), cache='bypass',
             device='cpu', quickmt_revision=QUICKMT_REVISION, runtime=runtime_versions())
        for name in order:
            provider = None
            close_failed = False
            try:
                provider = provider_factory(name)
                if not provider.available:
                    raise RuntimeError(getattr(provider, 'status_message', 'Model unavailable'))
                for pass_index in range(passes):
                    for occurrence, text in enumerate(texts, 1):
                        started = time.monotonic()
                        try:
                            result = provider.translate(text, source_language='en',
                                                        target_language='pl', profile_id=profile)
                        except Exception as error:
                            errors += 1
                            emit('translation_error', provider=name, occurrence=occurrence,
                                 pass_index=pass_index, text=text, message=str(error))
                            continue
                        emit('translation', provider=name, provider_id=provider.provider_id,
                             occurrence=occurrence, pass_index=pass_index, text=text,
                             translated_text=result.translated_text,
                             first_request=pass_index == 0 and occurrence == 1,
                             wall_ms=max(0.0, (time.monotonic() - started) * 1000))
            except Exception as error:
                errors += 1
                emit('provider_error', provider=name, message=str(error))
            finally:
                if provider is not None:
                    try:
                        provider.close()
                    except Exception as error:
                        errors += 1
                        close_failed = True
                        emit('provider_close_error', provider=name, message=str(error))
            if close_failed:
                # Never load a second model if the first may still be resident.
                break
        emit('comparison_closed', errors=errors)
    return 1 if errors else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', choices=('balanced', 'fast'), default='balanced')
    parser.add_argument('--passes', type=int, default=2)
    arguments = parser.parse_args(argv)
    from .quickmt import QuickMTTranslationProvider
    def provider_factory(name):
        return QuickMTTranslationProvider()
    order = ('quickmt',)
    try:
        return compare(load_corpus(arguments.corpus), arguments.output,
                       profile=arguments.profile, passes=arguments.passes,
                       order=order, provider_factory=provider_factory)
    except (OSError, ValueError) as error:
        print(f'Comparison failed: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())