"""Current identity and explicit, non-destructive legacy data migration."""
import importlib.util
import json
from pathlib import Path
import pytest
from game_optimization_linux import config

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('migrate_user_data', ROOT/'scripts/migrate-user-data.py')
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def test_current_identity_is_consistent():
    app = 'io.github.DevVoidPL.NarratorVerse'
    assert config.APP_ID == app and config.APP_NAME == 'NarratorVerse'
    assert all(p.name == 'narratorverse' for p in (config.CONFIG_DIR,config.DATA_DIR,config.CACHE_DIR,config.STATE_DIR))
    assert json.loads((ROOT/'src-tauri/tauri.conf.json').read_text())['identifier'] == app
    assert json.loads((ROOT/f'flatpak/{app}.json').read_text())['app-id'] == app
    desktop = (ROOT/f'data/{app}.desktop').read_text()
    assert f'Name=NarratorVerse' in desktop and f'Icon={app}' in desktop
    assert 'Exec=narratorverse' in desktop
    assert (ROOT/'backend/narratorverse').is_dir()


def test_migration_preserves_profiles_voices_and_originals_but_not_grants(tmp_path):
    old, new = tmp_path/'old', tmp_path/'new'
    files={'config/lektorpl/profiles.json':b'{"selected":"user-profile"}',
           'config/lektorpl/quick-read.json':b'{"volume":0.6}',
           'config/lektorpl/capture-grants.json':b'old-application-token',
           'data/lektorpl/narrator/components/tts.custom-voices/custom.onnx':b'unchanged-model',
           'data/lektorpl/narrator/components/tts.fixture/.lektorpl-origin':b'downloaded\n'}
    for name, content in files.items():
        p=old/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)
    result=migration.migrate(old,new)
    assert result['status']=='migrated'
    assert (new/'config/narratorverse/profiles.json').read_bytes()==files['config/lektorpl/profiles.json']
    assert (new/'config/narratorverse/quick-read.json').read_bytes()==files['config/lektorpl/quick-read.json']
    assert not (new/'config/narratorverse/capture-grants.json').exists()
    assert (new/'data/narratorverse/narrator/components/tts.custom-voices/custom.onnx').read_bytes()==b'unchanged-model'
    assert (new/'data/narratorverse/narrator/components/tts.fixture/.narratorverse-origin').read_bytes()==b'downloaded\n'
    assert all((old/p).read_bytes()==content for p,content in files.items())
    assert migration.migrate(old,new)==result


def test_migration_refuses_to_overwrite_existing_new_data(tmp_path):
    old,new=tmp_path/'old',tmp_path/'new'
    for root,slug,data in ((old,'lektorpl',b'old'),(new,'narratorverse',b'new')):
        p=root/'config'/slug/'profiles.json';p.parent.mkdir(parents=True);p.write_bytes(data)
    with pytest.raises(FileExistsError):migration.migrate(old,new)
    assert (new/'config/narratorverse/profiles.json').read_bytes()==b'new'
    assert not (new/'.narratorverse-migration.json').exists()