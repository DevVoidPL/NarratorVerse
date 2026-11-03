"""Offline corpus comparison, without native models or network access."""
import json
from types import SimpleNamespace

import pytest

from narratorverse.translation_compare import compare, load_corpus


def test_corpus_preserves_occurrences_and_rejects_empty_input(tmp_path):
    path = tmp_path / 'corpus.jsonl'
    path.write_text('{"text":"Go!"}\n{"text":"Go!"}\n', encoding='utf-8')
    assert load_corpus(path) == ['Go!', 'Go!']
    path.write_text('{"text":" "}\n', encoding='utf-8')
    with pytest.raises(ValueError, match='line 1'):
        load_corpus(path)


def test_compare_uses_identical_corpus_without_cache_and_closes_each_provider(tmp_path):
    calls, closed = [], []
    class Provider:
        available = True
        def __init__(self, name): self.provider_id = name
        def translate(self, text, **kwargs):
            calls.append((self.provider_id, text, kwargs))
            return SimpleNamespace(translated_text=self.provider_id + ': ' + text)
        def close(self): closed.append(self.provider_id)
    output = tmp_path / 'report.jsonl'
    assert compare(['Go!', 'Go!'], output, profile='fast', passes=2,
                   provider_factory=Provider) == 0
    assert closed == ['quickmt']
    assert [text for name, text, _ in calls if name == 'quickmt'] == ['Go!'] * 4
    assert all(kwargs == dict(source_language='en', target_language='pl', profile_id='fast')
               for _, _, kwargs in calls)
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    results = [row for row in rows if row['event'] == 'translation']
    assert len(results) == 4
    assert rows[-1]['event'] == 'comparison_closed'
    assert rows[-1]['errors'] == 0
    assert output.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        compare(['Go!'], output, provider_factory=Provider)


def test_compare_records_failure_without_silent_fallback(tmp_path):
    closed = []
    class Provider:
        available = False
        status_message = 'Model missing'
        def close(self): closed.append(True)
    output = tmp_path / 'failed.jsonl'
    assert compare(['Go!'], output, provider_factory=lambda _: Provider()) == 1
    assert len(closed) == 1
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert rows[-1]['errors'] == 1
    assert not any(row['event'] == 'translation' for row in rows)


def test_close_failure_does_not_load_another_model(tmp_path):
    created = []
    class Provider:
        available = False
        def close(self): raise RuntimeError('Worker still alive')
    def factory(name):
        created.append(name)
        return Provider()
    assert compare(['Go!'], tmp_path / 'failed-close.jsonl', provider_factory=factory) == 1
    assert created == ['quickmt']