from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import sys
from types import ModuleType
import pytest
from narratorverse.quickmt import QuickMTTranslationProvider, QUICKMT_REVISION
from narratorverse.quickmt_worker import QuickMTEngine as _TranslationEngine

@pytest.fixture(autouse=True)
def verified_fixture_layout(monkeypatch):
    import narratorverse.quickmt as module
    def layout(root):
        return (root, root / "src.spm.model", "") if (root / "src.spm.model").is_file() else None
    monkeypatch.setattr(module, "quickmt_layout", layout)

def _model_tree(root, *, nested=False):
    root.mkdir(parents=True, exist_ok=True)
    for name in ("model.bin", "config.json", "src.spm.model", "tgt.spm.model", "source_vocabulary.json", "target_vocabulary.json"):
        (root / name).write_bytes(b"fixture")
    return root

class _Worker:

    def __init__(self, model_dir: Path, tokenizer: Path, target_prefix: str='') -> None:
        self.model_dir = model_dir
        self.tokenizer = tokenizer
        self.target_prefix = target_prefix
        self.calls: list[tuple[str, int]] = []
        self.cancelled = 0
        self.closed = 0

    def translate(self, text: str, *, beam_size: int) -> str:
        self.calls.append((text, beam_size))
        return 'Musimy się stąd wydostać.'

    def cancel(self) -> None:
        self.cancelled += 1

    def close(self) -> None:
        self.closed += 1

def test_provider_reports_missing_runtime_and_model(tmp_path: Path) -> None:
    provider = QuickMTTranslationProvider(tmp_path, runtime_available=lambda: False)
    assert provider.available is False
    assert 'runtime' in provider.status_message.casefold()
    provider = QuickMTTranslationProvider(tmp_path, runtime_available=lambda: True)
    assert provider.available is False
    assert 'missing' in provider.status_message.casefold()

def test_provider_requires_direct_pinned_component_layout(tmp_path):
    provider = QuickMTTranslationProvider(tmp_path, runtime_available=lambda: True)
    assert not provider.available
    _model_tree(tmp_path)
    assert provider.available

def test_provider_translates_on_cpu_worker_and_namespaces_cache_version(tmp_path: Path) -> None:
    package = _model_tree(tmp_path)
    workers: list[_Worker] = []

    def factory(model_dir: Path, tokenizer: Path, target_prefix: str) -> _Worker:
        worker = _Worker(model_dir, tokenizer, target_prefix)
        workers.append(worker)
        return worker
    times = iter((10.0, 10.125))
    provider = QuickMTTranslationProvider(tmp_path, runtime_available=lambda: True, worker_factory=factory, clock=lambda: next(times))
    result = provider.translate('  We   need to get out of here. ', source_language='en', target_language='pl', profile_id='')
    assert provider.available is True
    assert provider.provider_id == QuickMTTranslationProvider.provider_id
    assert QUICKMT_REVISION in provider.provider_id
    assert result.source_text == 'We need to get out of here.'
    assert result.translated_text == 'Musimy się stąd wydostać.'
    assert result.provider_id == provider.provider_id
    assert result.elapsed_ms == pytest.approx(125.0)
    assert workers[0].model_dir == package
    assert workers[0].tokenizer == package / 'src.spm.model'
    assert workers[0].calls == [('We need to get out of here.', 4)]

def test_fast_profile_uses_greedy_translation_and_worker_is_reused(tmp_path: Path) -> None:
    _model_tree(tmp_path)
    workers: list[_Worker] = []

    def factory(model_dir: Path, tokenizer: Path, target_prefix: str) -> _Worker:
        worker = _Worker(model_dir, tokenizer, target_prefix)
        workers.append(worker)
        return worker
    provider = QuickMTTranslationProvider(tmp_path, runtime_available=lambda: True, worker_factory=factory)
    for text in ('First line', 'Second line'):
        provider.translate(text, source_language='en', target_language='pl', profile_id='fast')
    assert len(workers) == 1
    assert workers[0].calls == [('First line', 1), ('Second line', 1)]

def test_provider_rejects_wrong_language_profile_and_empty_text(tmp_path: Path) -> None:
    _model_tree(tmp_path)
    provider = QuickMTTranslationProvider(tmp_path, runtime_available=lambda: True, worker_factory=_Worker)
    with pytest.raises(ValueError, match='English to Polish'):
        provider.translate('Text', source_language='de', target_language='pl', profile_id='')
    with pytest.raises(ValueError, match='empty'):
        provider.translate('  ', source_language='en', target_language='pl', profile_id='')
    with pytest.raises(ValueError, match='Unsupported'):
        provider.translate('Text', source_language='en', target_language='pl', profile_id='unknown')

def test_cancel_and_close_discard_lazy_worker(tmp_path: Path) -> None:
    _model_tree(tmp_path)
    workers: list[_Worker] = []

    def factory(model_dir: Path, tokenizer: Path, target_prefix: str) -> _Worker:
        worker = _Worker(model_dir, tokenizer, target_prefix)
        workers.append(worker)
        return worker
    provider = QuickMTTranslationProvider(tmp_path, runtime_available=lambda: True, worker_factory=factory)
    provider.translate('One', source_language='en', target_language='pl', profile_id='')
    provider.cancel()
    assert workers[0].cancelled == 1
    provider.translate('Two', source_language='en', target_language='pl', profile_id='')
    provider.close()
    assert workers[1].closed == 1

@dataclass
class _Result:
    hypotheses: list[list[str]]

class _Tokenizer:

    def __init__(self, *, model_file: str) -> None:
        self.model_file = model_file

    def encode(self, text: str, *, out_type: type[str]) -> list[str]:
        assert out_type is str
        return text.split()

    def decode(self, tokens: list[str]) -> str:
        return ' '.join(tokens)

class _Translator:

    def __init__(self, model_dir: str, **options) -> None:
        assert model_dir == '/model'
        assert options == {'device': 'cpu', 'compute_type': 'auto', 'inter_threads': 1, 'intra_threads': 0}

    def translate_batch(self, batch, **options):
        assert batch == [['English', 'line']]
        assert options == {'beam_size': 4, 'num_hypotheses': 1, 'length_penalty': 0.2, 'replace_unknowns': True}
        return [_Result([['Polska', 'kwestia']])]

def test_worker_engine_uses_cpu_ctranslate2_and_explicit_tokenizer_boundary() -> None:
    engine = _TranslationEngine(Path('/model'), Path('/tokenizer.model'), translator_factory=_Translator, tokenizer_factory=_Tokenizer)
    assert engine.translate('English line', beam_size=4) == 'Polska kwestia'

def test_shared_worker_uses_and_removes_optional_target_prefix() -> None:

    class PrefixedTranslator(_Translator):

        def translate_batch(self, batch, **options):
            assert options['target_prefix'] == [['<2pl>']]
            return [_Result([['<2pl>', 'Polska', 'kwestia']])]
    engine = _TranslationEngine(Path('/model'), Path('/tokenizer.model'), '<2pl>', translator_factory=PrefixedTranslator, tokenizer_factory=_Tokenizer)
    assert engine.translate('English line', beam_size=4) == 'Polska kwestia'

def test_sentencepiece_rejects_non_string_tokens(monkeypatch):
    from narratorverse.quickmt_worker import QuickMTTokenizer
    module = ModuleType("sentencepiece")
    module.SentencePieceProcessor = lambda **kwargs: object()
    monkeypatch.setitem(sys.modules, "sentencepiece", module)
    tokenizer = QuickMTTokenizer("/model/src.spm.model")
    with pytest.raises(TypeError, match="string tokens"):
        tokenizer.encode("Go!", out_type=int)
