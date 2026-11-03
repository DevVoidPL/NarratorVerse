"""Disk reload, profile isolation and failed-write tests; never use real user data."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from narratorverse.main import Backend
from narratorverse.profiles import Profiles


VALUES = {
    'capture_source': 'monitor', 'subtitle_language_mode': 'polish',
    'ocr_provider_id': 'rapidocr-local', 'voice_id': 'custom-fixture',
    'speech_rate': 1.35, 'volume': .6, 'adaptive_speech_rate': False,
    'read_speaker_names': True, 'noise_scale': .4, 'noise_w_scale': .7,
    'capture_sampling_hz': 5, 'visual_change_threshold': .04,
    'stabilization_ms': 300, 'ocr_min_confidence': .7, 'duplicate_cooldown_ms': 5000,
    'translation_profile_id': 'fast', 'audio_balance_enabled': True,
    'audio_balance_db': -18, 'normalize_narrator': True,
    'audio_balance_target': json.dumps({'application.name': 'Fixture',
        'application.process.binary': 'fixture', 'application.id': ''}, sort_keys=True),
    'subtitle_region': {'x': .1, 'y': .7, 'width': .8, 'height': .2},
}


def test_every_ui_setting_survives_reload_and_profile_selection(tmp_path):
    path = tmp_path / 'profiles.json'
    profiles = Profiles(path)
    first = profiles.selected()['id']
    profiles.update(VALUES, ocr_mode='classic')
    assert profiles.path.stat().st_mode & 0o777 == 0o600
    profiles.rename('Pierwszy profil')
    second = profiles.create('Drugi profil')
    profiles.update({'volume': .2, 'speech_rate': .8})
    reloaded = Profiles(path)
    assert reloaded.selected()['id'] == second
    assert reloaded.settings().volume == .2
    reloaded.select(first)
    again = Profiles(path)
    assert again.selected()['id'] == first
    assert again.selected()['name'] == 'Pierwszy profil'
    assert again.selected()['ocr']['mode'] == 'classic'
    settings = again.settings().to_dict()
    for key, value in VALUES.items():
        assert settings[key] == value, key
    again.select(second)
    assert again.settings().speech_rate == .8
    assert again.settings().audio_balance_enabled is False
    assert again.settings().read_speaker_names is False


def test_delete_and_reset_are_durable_and_keep_stable_identity(tmp_path):
    path = tmp_path / 'profiles.json'
    profiles = Profiles(path)
    first = profiles.selected()['id']
    second = profiles.create('Test')
    profiles.delete()
    reloaded = Profiles(path)
    assert reloaded.selected()['id'] == first
    assert all(p['id'] != second for p in reloaded.data['profiles'])
    with pytest.raises(ValueError):
        reloaded.delete()
    reloaded.update(VALUES, ocr_mode='classic')
    reloaded.reset('profile')
    reset = Profiles(path)
    assert reset.selected()['id'] == first
    assert reset.selected()['ocr']['mode'] == 'automatic'
    assert reset.settings().speech_rate == 1
    assert reset.settings().read_speaker_names is False
    assert reset.settings().audio_balance_enabled is False


@pytest.mark.parametrize('operation', ['update', 'create', 'select', 'rename', 'delete', 'reset'])
def test_failed_disk_write_changes_neither_memory_nor_disk(tmp_path, monkeypatch, operation):
    path = tmp_path / 'profiles.json'
    profiles = Profiles(path)
    first = profiles.selected()['id']
    profiles.create('Second')
    profiles.update(VALUES, ocr_mode='classic')
    before, disk = deepcopy(profiles.data), path.read_bytes()
    def fail(*_args):
        raise OSError('fixture: disk write refused')
    monkeypatch.setattr('narratorverse.profiles._atomic_json_write', fail)
    calls = {
        'update': lambda: profiles.update({'volume': .1}, ocr_mode='automatic'),
        'create': lambda: profiles.create('Third'), 'select': lambda: profiles.select(first),
        'rename': lambda: profiles.rename('Changed'), 'delete': profiles.delete,
        'reset': lambda: profiles.reset('recognition'),
    }
    with pytest.raises(OSError):
        calls[operation]()
    assert profiles.data == before
    assert path.read_bytes() == disk
    assert Profiles(path).data == before


def test_quick_read_options_survive_reload_without_changing_profiles(tmp_path):
    from narratorverse.quick_read import QuickRead
    profiles = Profiles(tmp_path / 'profiles.json')
    before = profiles.path.read_bytes()
    path = tmp_path / 'quick-read.json'
    first = QuickRead(Mock(), Mock(), Mock(), path)
    try:
        first.save({'voice_id': 'custom-fixture', 'speech_rate': 1.25, 'volume': .45})
        second = QuickRead(Mock(), Mock(), Mock(), path)
        try:
            assert second.options == {'voice_id': 'custom-fixture', 'speech_rate': 1.25, 'volume': .45}
            assert profiles.path.read_bytes() == before
        finally:
            second.shutdown()
    finally:
        first.shutdown()


@pytest.mark.parametrize('values,mode', [({'speech_rate': 3}, None), ({'volume': .4}, 'bad')])
def test_invalid_edit_leaves_disk_and_memory_unchanged(tmp_path, values, mode):
    profiles = Profiles(tmp_path / 'profiles.json')
    before, disk = deepcopy(profiles.data), profiles.path.read_bytes()
    with pytest.raises(ValueError):
        profiles.update(values, ocr_mode=mode)
    assert profiles.data == before
    assert profiles.path.read_bytes() == disk


def test_settings_rpc_success_and_io_failure_do_not_claim_false_save(tmp_path, monkeypatch):
    profiles = Profiles(tmp_path / 'profiles.json')
    backend = SimpleNamespace(quick=SimpleNamespace(busy=False), pipeline=SimpleNamespace(active=False),
        profiles=profiles, writer=Mock(), apply_ocr=Mock(), emit=Mock(), view=Mock(return_value={}))
    Backend.handle(backend, {'id': 1, 'method': 'settings', 'params': {'values': VALUES, 'ocr_mode': 'classic'}})
    backend.writer.send.assert_called_once_with({'id': 1, 'result': True})
    assert Profiles(profiles.path).settings().speech_rate == 1.35
    before = deepcopy(profiles.data)
    backend.writer.reset_mock(); backend.emit.reset_mock()
    monkeypatch.setattr('narratorverse.profiles._atomic_json_write', Mock(side_effect=OSError('disk full')))
    Backend.handle(backend, {'id': 2, 'method': 'settings', 'params': {'values': {'speech_rate': 1.8}}})
    backend.writer.send.assert_called_once_with({'id': 2, 'error': 'disk full'})
    backend.emit.assert_not_called()
    assert profiles.data == before