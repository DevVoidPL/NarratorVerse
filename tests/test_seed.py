"""Seeding only touches independent temporary storage; never owner models."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import pytest
import narratorverse.seed as seeding


def source_component(root):
    source = root / 'ocr.english-local'
    source.mkdir(parents=True)
    payload = b'local model fixture'
    (source / 'fixture').write_bytes(payload)
    (source / 'component.json').write_text(json.dumps({'files': [{'path': 'fixture', 'sha256': hashlib.sha256(payload).hexdigest()}]}))
    return source


def test_seed_copies_without_writable_sharing_and_respects_removal(tmp_path):
    bundle, target = tmp_path / 'bundled', tmp_path / 'data'
    source = source_component(bundle)
    with patch.object(seeding, 'BUNDLED_NARRATOR_COMPONENTS_DIR', bundle), patch.object(seeding, 'NARRATOR_COMPONENTS_DIR', target), patch.object(seeding.NarratorComponentManager, 'verify_installed', return_value=(True, '')):
        seeding.seed()
        installed = target / source.name / 'fixture'
        assert installed.read_bytes() == (source / 'fixture').read_bytes()
        assert installed.stat().st_ino != (source / 'fixture').stat().st_ino
        installed.unlink()
        seeding.seed()
        assert not installed.exists(), 'Startup must not undo an explicit removal'


def test_failed_seed_has_no_marker_or_partial_component(tmp_path):
    bundle, target = tmp_path / 'bundled', tmp_path / 'data'
    source_component(bundle)
    with patch.object(seeding, 'BUNDLED_NARRATOR_COMPONENTS_DIR', bundle), patch.object(seeding, 'NARRATOR_COMPONENTS_DIR', target), patch.object(seeding.NarratorComponentManager, 'verify_installed', return_value=(False, 'bad hash')):
        with pytest.raises(RuntimeError, match='bad hash'): seeding.seed()
    assert not (target / '.seeded').exists()
    assert not (target / 'ocr.english-local').exists()


def test_seed_verifies_destination_before_publication(tmp_path):
    bundle, target = tmp_path / 'bundled', tmp_path / 'data'
    source = source_component(bundle)
    (source / 'fixture').write_bytes(b'corrupt')
    with patch.object(seeding, 'BUNDLED_NARRATOR_COMPONENTS_DIR', bundle), patch.object(seeding, 'NARRATOR_COMPONENTS_DIR', target), patch.object(seeding.NarratorComponentManager, 'verify_installed', return_value=(True, '')):
        with pytest.raises(RuntimeError, match='copied component failed'): seeding.seed()
    assert not (target / source.name).exists()
    assert not (target / ('.' + source.name + '-seed')).exists()