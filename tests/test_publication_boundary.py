"""Publication boundaries are independent of Git ignore rules."""
import importlib.util
import shutil
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_fixture(tmp_path):
    source = tmp_path / 'input'
    source.mkdir()
    # Copy only public tracked inputs, never local runtimes or models.
    import subprocess
    for name in subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z']).decode().split('\0'):
        if name and (ROOT / name).is_file():
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
    for name in ('scripts/packaging_policy.py', 'flatpak/publication-files.json',
                 'tests/test_publication_boundary.py'):
        if (ROOT / name).exists():
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
    return source


@pytest.mark.parametrize('name', ['backend/private-session.txt', 'src/private-session.txt',
                                 'scripts/private-session.txt', 'licenses/private-session.txt'])
def test_unreviewed_source_rejected_before_snapshot(tmp_path, name):
    source = source_fixture(tmp_path)
    private = source / name
    private.write_text('PRIVATE-SENTINEL-DO-NOT-SHIP')
    destination = tmp_path / 'snapshot'
    with pytest.raises(ValueError, match='Unexpected'):
        load('fresh-inputs').source_snapshot(source, destination)
    assert not destination.exists()
    assert private.read_text() == 'PRIVATE-SENTINEL-DO-NOT-SHIP'


def test_installer_import_has_no_side_effects_and_private_input_blocks_app(tmp_path):
    installer = load('install-fresh')
    source = source_fixture(tmp_path)
    (source / 'backend/private-session.txt').write_text('PRIVATE-SENTINEL-DO-NOT-SHIP')
    app = tmp_path / 'app'
    with pytest.raises(ValueError, match='Unexpected'):
        installer.install(source, app)
    assert not app.exists()


def test_snapshot_rejects_allowlisted_symlink_and_missing_file(tmp_path):
    helper = load('fresh-inputs')
    source = source_fixture(tmp_path)
    path = source / 'src/App.svelte'
    path.unlink()
    with pytest.raises(ValueError, match='Missing'):
        helper.source_snapshot(source, tmp_path / 'missing')
    path.symlink_to(ROOT / 'src/App.svelte')
    with pytest.raises(ValueError, match='Symlink'):
        helper.source_snapshot(source, tmp_path / 'symlink')


def install_fixture(tmp_path):
    source = source_fixture(tmp_path)
    rules = json.loads((source / 'flatpak/publication-files.json').read_text())
    import hashlib
    rules['components'] = {'components/ocr.test/model': hashlib.sha256(b'model').hexdigest()}
    (source / 'flatpak/publication-files.json').write_text(json.dumps(rules))
    for name, content in [('components/ocr.test/model', b'model'),
                          ('src-tauri/target/release/narratorverse', b'test executable'),
                          ('vendor/test/LICENSE', b'cargo notice'),
                          ('node_modules/test/LICENSE', b'npm notice')]:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    for name in ('python-lock.json', 'components-lock.json', 'build-tools-lock.json', 'sdk-lock.json'):
        path = source / 'build-locks' / name
        path.parent.mkdir(exist_ok=True)
        path.write_text('{}')
    return source


def test_installer_keeps_runtime_and_notices_but_not_tests_or_root_private_file(tmp_path):
    source = install_fixture(tmp_path)
    (source / 'private-session.txt').write_text('PRIVATE-SENTINEL-DO-NOT-SHIP')
    prefix = tmp_path / 'app'
    load('install-fresh').install(source, prefix)
    app = prefix / 'share/narratorverse'
    assert (app / 'backend/narratorverse/main.py').is_file()
    assert (app / 'licenses/third-party/cargo/test/LICENSE').read_bytes() == b'cargo notice'
    assert (app / 'components/ocr.test/model').read_bytes() == b'model'
    assert not (app / 'tests').exists()
    assert not any(b'PRIVATE-SENTINEL' in p.read_bytes() for p in prefix.rglob('*') if p.is_file())


@pytest.mark.parametrize('change', ['extra', 'corrupt', 'symlink'])
def test_component_extra_bytes_or_symlink_blocks_install_before_app(tmp_path, change):
    source = install_fixture(tmp_path)
    model = source / 'components/ocr.test/model'
    if change == 'extra':
        (model.parent / 'private-session.txt').write_text('PRIVATE-SENTINEL')
    elif change == 'corrupt':
        model.write_bytes(b'wrong')
    else:
        model.unlink()
        model.symlink_to(ROOT / 'LICENSE')
    with pytest.raises(ValueError, match='Unexpected|SHA-256|Symlink'):
        load('install-fresh').install(source, tmp_path / 'app')
    assert not (tmp_path / 'app').exists()


def test_legacy_snapshot_cli_cannot_package_unreviewed_runtime(tmp_path):
    import subprocess
    destination = tmp_path / 'legacy'
    result = subprocess.run(['python3', str(ROOT / 'scripts/stage-flatpak.py'),
                             '--dest', str(destination)], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'disabled' in result.stderr
    assert not destination.exists()


def test_builder_manifest_local_paths_are_normalized_without_losing_provenance(tmp_path):
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'sources': [{'path': str(tmp_path / 'source'),
                                               'sha256': 'pinned'}]}))
    load('packaging_policy').normalize_manifest(manifest, tmp_path)
    data = json.loads(manifest.read_text())
    assert data['sources'] == [{'path': '@WORK@/source', 'sha256': 'pinned'}]
    assert str(tmp_path) not in manifest.read_text()


@pytest.mark.skipif(not shutil.which('flatpak') or not shutil.which('ostree'),
                    reason='Flatpak/OSTree export tools unavailable')
def test_private_root_file_absent_from_actual_fixture_bundle(tmp_path):
    """Real export/import, with synthetic runtime bytes, not application acceptance."""
    import subprocess
    source = install_fixture(tmp_path)
    (source / 'private-session.txt').write_text('PRIVATE-SENTINEL-DO-NOT-SHIP')
    build = tmp_path / 'build'
    load('install-fresh').install(source, build / 'files')
    (build / 'metadata').write_text(
        '[Application]\nname=io.github.DevVoidPL.NarratorVerse\n'
        'runtime=org.gnome.Platform/x86_64/49\ncommand=narratorverse\n')
    repository, imported, bundle = tmp_path / 'repo', tmp_path / 'import', tmp_path / 'fixture.flatpak'
    commands = [
        ['flatpak', 'build-finish', str(build)],
        ['flatpak', 'build-export', str(repository), str(build), 'fixture'],
        ['flatpak', 'build-bundle', str(repository), str(bundle),
         'io.github.DevVoidPL.NarratorVerse', 'fixture'],
        ['ostree', '--repo=' + str(imported), 'init', '--mode=archive-z2'],
        ['flatpak', 'build-import-bundle', str(imported), str(bundle)],
        ['ostree', '--repo=' + str(imported), 'checkout', '--user-mode',
         'app/io.github.DevVoidPL.NarratorVerse/x86_64/fixture', str(tmp_path / 'checkout')],
    ]
    for command in commands:
        subprocess.run(command, check=True, capture_output=True, timeout=60)
    payload = tmp_path / 'checkout/files'
    assert not any(b'PRIVATE-SENTINEL' in p.read_bytes() for p in payload.rglob('*') if p.is_file())
    assert (payload / 'share/narratorverse/components/ocr.test/model').read_bytes() == b'model'
