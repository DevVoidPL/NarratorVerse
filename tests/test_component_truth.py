"""Actual file verification against small pinned fixtures, no network."""
import hashlib
import json
from pathlib import Path
from narratorverse.components import ComponentManager
from game_optimization_linux.services.narrator_components import NarratorComponentDefinition, NarratorPinnedFile
from game_optimization_linux.models.narrator import NarratorComponentKind


def manager(tmp_path):
    data = b'pinned fixture'
    pin = NarratorPinnedFile(target_relative_path='model', size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    definition = NarratorComponentDefinition(component_id='tts.fixture',kind=NarratorComponentKind.TTS,name='Fixture',license_id='test',version='verified-version',pinned_files=(pin,))
    instance = ComponentManager(tmp_path/'installed',definitions=(definition,))
    source = tmp_path/'source'; source.write_bytes(data)
    return instance, source


def test_catalog_is_not_installed_and_corruption_is_error(tmp_path):
    m, source = manager(tmp_path)
    row = m.verified_status('tts.fixture', True, tmp_path/'bundle')
    assert row['state']=='not_installed' and not row['installed'] and not row['version']
    m.install_local('tts.fixture', {'model':source})
    row = m.verified_status('tts.fixture', True, tmp_path/'bundle')
    assert row['state']=='available' and row['verified'] and row['installed']
    assert row['version']=='verified-version' and row['origin']=='local'
    assert row['installed_size_bytes'] == sum(p.stat().st_size for p in (m.root/'tts.fixture').rglob('*') if p.is_file())
    (m.root/'tts.fixture/model').write_bytes(b'corrupt')
    row = m.verified_status('tts.fixture', True, tmp_path/'bundle')
    assert row['state']=='error' and not row['installed']


def test_runtime_required_and_bundled_identity(tmp_path):
    m, source = manager(tmp_path)
    m.install_local('tts.fixture', {'model':source})
    row = m.verified_status('tts.fixture', False, tmp_path/'bundle')
    assert row['state']=='error' and not row['installed']
    bundle = tmp_path/'bundle/tts.fixture'; bundle.mkdir(parents=True)
    (bundle/'component.json').write_bytes((m.root/'tts.fixture/component.json').read_bytes())
    row = m.verified_status('tts.fixture', True, tmp_path/'bundle')
    assert row['origin']=='bundled'
    (m.root/'tts.fixture/model').unlink()
    assert m.verified_status('tts.fixture', True, tmp_path/'bundle')['state']=='error'


def test_explicit_download_origin_overrides_equal_bundle_files(tmp_path):
    m, source = manager(tmp_path)
    m.install_local('tts.fixture', {'model':source})
    bundle = tmp_path/'bundle/tts.fixture'; bundle.mkdir(parents=True)
    (bundle/'component.json').write_bytes((m.root/'tts.fixture/component.json').read_bytes())
    (m.root/'tts.fixture/.narratorverse-origin').write_text('downloaded\n')
    assert m.verified_status('tts.fixture',True,tmp_path/'bundle')['origin']=='downloaded'


def test_self_authored_manifest_cannot_remove_expected_file(tmp_path):
    m, source = manager(tmp_path)
    m.install_local('tts.fixture', {'model':source})
    bundle = tmp_path/'bundle/tts.fixture'; bundle.mkdir(parents=True)
    original=json.loads((m.root/'tts.fixture/component.json').read_text())
    original['files'].append({'path':'required-extra','size':1,'sha256':hashlib.sha256(b'x').hexdigest()})
    (bundle/'component.json').write_text(json.dumps(original))
    row=m.verified_status('tts.fixture',True,tmp_path/'bundle')
    assert row['state']=='error' and not row['installed']