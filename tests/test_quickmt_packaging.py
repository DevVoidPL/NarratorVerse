"""Standard packaging includes SentencePiece and excludes downloaded weights."""
import importlib.util
from pathlib import Path
import subprocess
import os

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _stage():
    spec = importlib.util.spec_from_file_location('nv_stage', ROOT / 'scripts/stage-flatpak.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _dependency(root):
    package = root / '.tools/quickmt-python/sentencepiece'
    package.mkdir(parents=True)
    (package / '__init__.py').write_text('')
    (package / '_sentencepiece.cpython-313-x86_64-linux-gnu.so').write_bytes(b'test-native')
    metadata = package.parent / 'sentencepiece-0.2.1.dist-info'
    metadata.mkdir()
    (metadata / 'METADATA').write_text('Name: sentencepiece\nVersion: 0.2.1\n')
    license_dir = root / 'licenses'
    license_dir.mkdir(exist_ok=True)
    (license_dir / 'sentencepiece-LICENSE.txt').write_text('Apache License\nVersion 2.0\n')
    return package.parent


def test_only_sentencepiece_is_staged_not_other_tools_or_weights(tmp_path, monkeypatch):
    module = _stage()
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    tools = _dependency(tmp_path)
    (tools / 'model.bin').write_bytes(b'never ship')
    destination = tmp_path / 'output'
    destination.mkdir()
    module.stage_quickmt_runtime(destination)
    assert (destination / 'sentencepiece/__init__.py').is_file()
    assert (destination / 'sentencepiece-0.2.1.dist-info/METADATA').is_file()
    assert not (destination / 'model.bin').exists()


def test_missing_dependency_fails_with_preparation_command(tmp_path, monkeypatch):
    module = _stage()
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    with pytest.raises(RuntimeError, match='prepare-quickmt-runtime.sh'):
        module.stage_quickmt_runtime(tmp_path / 'output')


def test_cannot_overwrite_existing_sentencepiece(tmp_path, monkeypatch):
    module = _stage()
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    _dependency(tmp_path)
    destination = tmp_path / 'output'
    (destination / 'sentencepiece').mkdir(parents=True)
    with pytest.raises(RuntimeError, match='overwrite|existing'):
        module.stage_quickmt_runtime(destination)


def test_standard_bundle_has_no_model_path_or_experimental_launch_switches():
    text = (ROOT / 'scripts/build-flatpak.sh').read_text()
    assert 'NARRATORVERSE_EXPERIMENT_' not in text
    assert '--quickmt' not in text
    assert 'narratorverse.quickmt_runtime' in text


def test_reinstall_script_has_valid_shebang():
    assert (ROOT / 'scripts/reinstall.sh').read_text().startswith('#!/bin/sh\n')