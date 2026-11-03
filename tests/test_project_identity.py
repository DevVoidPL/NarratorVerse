"""Current identity and explicit, non-destructive legacy data migration."""
import importlib.util
import json
import re
import tomllib
import xml.etree.ElementTree as ET
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


def test_beta_version_is_consistent_across_source_metadata():
    version = '0.2.0-beta.1'
    package = json.loads((ROOT/'package.json').read_text())
    lock = json.loads((ROOT/'package-lock.json').read_text())
    cargo = tomllib.loads((ROOT/'src-tauri/Cargo.toml').read_text())
    cargo_lock = tomllib.loads((ROOT/'src-tauri/Cargo.lock').read_text())
    rust_package = next(p for p in cargo_lock['package'] if p['name'] == 'narratorverse')
    tauri = json.loads((ROOT/'src-tauri/tauri.conf.json').read_text())
    release = ET.parse(ROOT/'data/io.github.DevVoidPL.NarratorVerse.metainfo.xml').find('releases/release')
    versions = [package['version'], lock['version'], lock['packages']['']['version'],
                cargo['package']['version'], rust_package['version'], tauri['version'],
                config.APP_VERSION, release.attrib['version']]
    assert versions == [version] * len(versions)
    assert release.attrib['type'] == 'development'
    assert re.fullmatch(r'\d+\.\d+\.\d+-beta\.\d+', version)


def test_bundle_filename_uses_the_declared_version_without_another_beta_suffix():
    script = (ROOT/'scripts/build-flatpak.sh').read_text()
    assert 'NarratorVerse-${VERSION}-x86_64.flatpak' in script
    assert '${VERSION}-beta-integration' not in script


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