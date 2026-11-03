"""QuickMT boundary tests without downloading weights or importing native code."""
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

import pytest

from narratorverse.quickmt import QuickMTTranslationProvider, quickmt_layout
from narratorverse.quickmt_worker import QuickMTEngine, QuickMTTokenizer


def test_missing_quickmt_is_not_silently_replaced_by_argos(tmp_path):
    provider = QuickMTTranslationProvider(tmp_path, runtime_available=lambda: True)
    assert not provider.available
    with pytest.raises(RuntimeError, match='QuickMT'):
        provider.translate('Go!', source_language='en', target_language='pl', profile_id='fast')


def test_quickmt_requires_both_tokenizers_and_pinned_files(tmp_path):
    assert quickmt_layout(tmp_path) is None
    for name in ('model.bin', 'config.json', 'src.spm.model', 'tgt.spm.model',
                 'source_vocabulary.json', 'target_vocabulary.json'):
        (tmp_path / name).write_text('not the pinned model')
    assert quickmt_layout(tmp_path) is None


def test_sentencepiece_source_eos_and_separate_target_decoder(monkeypatch):
    module = ModuleType('sentencepiece')
    class Processor:
        def __init__(self, *, model_file):
            self.file = model_file
        def encode(self, text, *, out_type):
            assert self.file.endswith('src.spm.model')
            assert out_type is str
            return ['▁Go', '!']
        def decode(self, tokens):
            assert self.file.endswith('tgt.spm.model')
            assert tokens == ['▁Idź', '!']
            return 'Idź!'
    module.SentencePieceProcessor = Processor
    monkeypatch.setitem(sys.modules, 'sentencepiece', module)
    tokenizer = QuickMTTokenizer('/model/src.spm.model')
    assert tokenizer.encode('Go!', out_type=str) == ['▁Go', '!', '</s>']
    assert tokenizer.decode(['▁Idź', '!']) == 'Idź!'


def test_quickmt_cpu_and_shared_decoding_controls():
    class Tokenizer:
        def __init__(self, model_file): pass
        def encode(self, text, *, out_type): return ['▁Go', '</s>']
        def decode(self, tokens): return 'Idź!'
    class Translator:
        def __init__(self, model, **options):
            assert options == dict(device='cpu', compute_type='auto', inter_threads=1, intra_threads=0)
        def translate_batch(self, tokens, **options):
            assert tokens == [['▁Go', '</s>']]
            assert options['beam_size'] == 4
            assert options['length_penalty'] == 0.2
            assert options == dict(beam_size=4, num_hypotheses=1,
                                   length_penalty=0.2, replace_unknowns=True)
            return [SimpleNamespace(hypotheses=[['▁Idź', '!']])]
    engine = QuickMTEngine(Path('/model'), Path('/model/src.spm.model'),
                           translator_factory=Translator, tokenizer_factory=Tokenizer)
    assert engine.translate('Go!', beam_size=4) == 'Idź!'


def test_quickmt_has_distinct_cache_identity():
    assert QuickMTTranslationProvider.provider_id != 'argos-ctranslate2-en-pl-1.9'
    assert '6209580' in QuickMTTranslationProvider.provider_id


def test_verified_layout_is_reused_and_mutation_is_rejected(tmp_path, monkeypatch):
    import hashlib
    import narratorverse.quickmt as module
    manifest = {}
    for name in module.QUICKMT_FILES:
        content = name.encode('utf-8')
        (tmp_path / name).write_bytes(content)
        manifest[name] = (len(content), 'sha256', hashlib.sha256(content).hexdigest())
    monkeypatch.setattr(module, 'QUICKMT_FILES', manifest)
    checked = []
    original = module.quickmt_layout
    def layout(root):
        checked.append(root)
        return original(root)
    monkeypatch.setattr(module, 'quickmt_layout', layout)
    calls = []
    class Worker:
        def translate(self, text, *, beam_size):
            calls.append((text, beam_size))
            return 'Idź!'
        def close(self): pass
    provider = QuickMTTranslationProvider(tmp_path, runtime_available=lambda: True,
                                         worker_factory=lambda *args: Worker())
    try:
        assert provider.available
        assert provider.available
        assert len(checked) == 1
        result = provider.translate('Go!', source_language='en', target_language='pl', profile_id='fast')
        assert result.translated_text == 'Idź!'
        assert calls == [('Go!', 1)]
        (tmp_path / 'config.json').write_bytes(b'broken')
        assert not provider.available
        with pytest.raises(RuntimeError, match='QuickMT'):
            provider.translate('Go!', source_language='en', target_language='pl', profile_id='fast')
    finally:
        provider.close()


def test_worker_uses_quickmt_engine_over_existing_json_protocol(monkeypatch):
    from io import StringIO
    import json
    from narratorverse.quickmt_worker import main
    calls = []
    class Engine:
        def __init__(self, *args): calls.append(args)
        def translate(self, text, *, beam_size):
            assert (text, beam_size) == ('Go!', 1)
            return 'Idź!'
    output = StringIO()
    monkeypatch.setattr(sys, 'stdin', StringIO('{"id":7,"operation":"translate","text":"Go!","beam_size":1}\n'))
    monkeypatch.setattr(sys, 'stdout', output)
    assert main(['--model-dir', '/model', '--tokenizer', '/model/src.spm.model'], engine_factory=Engine) == 0
    messages = [json.loads(line) for line in output.getvalue().splitlines()]
    assert messages[0]['status'] == 'ready'
    assert messages[1]['text'] == 'Idź!'
    assert messages[1]['id'] == 7
    assert calls == [(Path('/model'), Path('/model/src.spm.model'), '')]