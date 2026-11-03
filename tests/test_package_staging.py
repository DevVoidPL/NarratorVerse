"""Package allowlist tests on fake files; no native dependency installation."""
import importlib.util
import hashlib
import json
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('stage_flatpak', Path(__file__).resolve().parents[1] / 'scripts/stage-flatpak.py')
staging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(staging)


def fake_source(root):
    for name in ('backend','bin','.runtime/lib','.runtime/bin','.runtime/share','licenses'):
        p = root / name / 'fixture'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('fixture')
    for name in staging.COMPONENTS + ('tts.custom-voices',):
        p = root / 'components' / name / 'model'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('not a real model')
    for name in ('LICENSE','src-tauri/target/release/narratorverse',f'data/{staging.APP_ID}.desktop',f'data/{staging.APP_ID}.metainfo.xml',f'data/{staging.APP_ID}.png'):
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('fixture')
    for size in (16,24,32,48,64,128,256,512):
        p = root / f'data/icons/{size}x{size}.png'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f'icon-{size}')


def test_staged_allowlist_includes_voidek_but_excludes_private_data(tmp_path, monkeypatch):
    source, dest = tmp_path / 'source', tmp_path / 'dest'
    fake_source(source)
    monkeypatch.setattr(staging, 'ROOT', source)
    from test_quickmt_packaging import _dependency
    _dependency(source)
    staging.stage(dest)
    app = dest / 'share/narratorverse'
    assert (app / 'components/tts.voidek/model').read_text() == 'not a real model'
    assert not (app / 'components/tts.custom-voices').exists()
    inventory = json.loads((app / 'licenses/snapshot-files.json').read_text())
    assert 'bin/narratorverse' in inventory
    voice_entry = inventory['share/narratorverse/components/tts.voidek/model']
    assert voice_entry['sha256'] == hashlib.sha256(b'not a real model').hexdigest()
    assert voice_entry['bytes'] == len(b'not a real model')
    for size in (16,24,32,48,64,128,256,512):
        assert (dest / f'share/icons/hicolor/{size}x{size}/apps/{staging.APP_ID}.png').read_text() == f'icon-{size}'
    for name in staging.COMPONENTS:
        assert (app / 'components' / name / 'model').is_file()
    with pytest.raises(RuntimeError, match='overwrite'): staging.stage(dest)


def test_staging_rejects_symlinks(tmp_path, monkeypatch):
    source, dest = tmp_path / 'source', tmp_path / 'dest'
    fake_source(source)
    (source / 'backend/link').symlink_to(source / 'LICENSE')
    monkeypatch.setattr(staging, 'ROOT', source)
    from test_quickmt_packaging import _dependency
    _dependency(source)
    with pytest.raises(RuntimeError, match='Symlink'): staging.stage(dest)