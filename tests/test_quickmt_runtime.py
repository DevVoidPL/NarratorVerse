"""Native runtime diagnostics without installing dependencies in unit tests."""
from types import SimpleNamespace

import pytest


def test_runtime_reports_exact_missing_dependency_not_generic_pair():
    from narratorverse.quickmt_runtime import inspect_runtime
    def importer(name):
        if name == 'sentencepiece':
            raise ModuleNotFoundError("No module named 'sentencepiece'")
        return SimpleNamespace(__version__='4.8.1', __file__='/local/ctranslate2/__init__.py',
                               Translator=object, get_supported_compute_types=lambda device: {'float32'})
    report = inspect_runtime(importer=importer)
    assert not report['ok']
    assert report['modules']['ctranslate2']['ok']
    assert report['modules']['sentencepiece']['ok'] is False
    assert 'sentencepiece' in report['modules']['sentencepiece']['error']


def test_runtime_checks_native_api_not_just_python_package():
    from narratorverse.quickmt_runtime import inspect_runtime
    def importer(name):
        if name == 'ctranslate2':
            return SimpleNamespace(__version__='4.8.1')  # missing _ext silently swallowed upstream
        return SimpleNamespace(SentencePieceProcessor=object)
    report = inspect_runtime(importer=importer)
    assert not report['ok']
    assert 'Translator' in report['modules']['ctranslate2']['error']


def test_runtime_preserves_shared_library_loader_error():
    from narratorverse.quickmt_runtime import inspect_runtime
    def importer(name):
        raise OSError('libexample.so: cannot open shared object file')
    report = inspect_runtime(importer=importer)
    assert not report['ok']
    assert 'libexample.so' in report['modules']['ctranslate2']['error']
    assert 'executable' in report and 'pythonpath' in report


def test_runtime_probes_cpu_support_and_sentencepiece_constructor():
    from narratorverse.quickmt_runtime import inspect_runtime
    calls = []
    modules = {
        'ctranslate2': SimpleNamespace(Translator=object, get_supported_compute_types=lambda d: calls.append(d) or {'float32'}),
        'sentencepiece': SimpleNamespace(SentencePieceProcessor=lambda: calls.append('processor')),
    }
    report = inspect_runtime(importer=modules.__getitem__)
    assert report['ok']
    assert calls == ['cpu', 'processor']
    assert report['modules']['ctranslate2']['cpu_compute_types'] == ['float32']


def test_runtime_diagnosis_exit_code_and_output(monkeypatch, capsys):
    from narratorverse import quickmt_runtime
    monkeypatch.setattr(quickmt_runtime, 'inspect_runtime', lambda: {'ok': False, 'error': 'sentencepiece'})
    assert quickmt_runtime.main() == 1
    assert 'sentencepiece' in capsys.readouterr().out


def test_smoke_cli_stops_before_model_loading_on_runtime_error(monkeypatch, capsys):
    from narratorverse import quickmt_runtime, quickmt_smoke
    monkeypatch.setattr(quickmt_runtime, 'inspect_runtime', lambda: {'ok': False, 'missing': 'sentencepiece'})
    def forbidden(*args, **kwargs): pytest.fail('Model should not be loaded with broken runtime')
    monkeypatch.setattr(quickmt_smoke, 'smoke_test', forbidden)
    assert quickmt_smoke.main([]) == 1
    assert 'sentencepiece' in capsys.readouterr().out


def test_prepare_runtime_script_is_opt_in_and_does_not_modify_shared_runtime():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    script = (root / 'scripts/prepare-quickmt-runtime.sh').read_text()
    assert 'scripts/build-fresh.sh' in script
    manifest = (root / 'flatpak/io.github.DevVoidPL.NarratorVerse.json').read_text()
    assert '--require-hashes' in manifest
    assert '--no-deps' in manifest
    assert '--only-binary=:all:' in manifest
    assert '--upgrade' not in script
    requirements = (root / 'flatpak/python-requirements.lock').read_text()
    assert 'sentencepiece' in requirements
    assert 'c7f0fd2f2693309e6628aeeb2e2faf6edd221134dfccac3308ca0de01f8dab47' in requirements
    assert 'ctranslate2 @' not in requirements