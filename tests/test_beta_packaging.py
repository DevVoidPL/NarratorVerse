"""The normal beta bundle includes one translator runtime, never model weights."""
from pathlib import Path
import importlib.util
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def test_normal_staging_requires_sentencepiece_and_excludes_argos():
    spec = importlib.util.spec_from_file_location('beta_stage', ROOT / 'scripts/stage-flatpak.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert 'translation.opus-en-pl' not in module.COMPONENTS
    assert 'quickmt' not in __import__('inspect').signature(module.stage).parameters
    assert 'stage_quickmt_runtime(' in __import__('inspect').getsource(module.stage)


def test_standard_build_checks_staged_cpu_runtime_offline_without_bytecode():
    text = (ROOT / 'scripts/build-flatpak.sh').read_text()
    assert '--quickmt' not in text
    assert '--unshare=network' in text
    assert 'PYTHONDONTWRITEBYTECODE=1' in text
    assert 'VERSION=' in text


def test_no_experimental_launchers_required_or_packaged():
    for name in ('run-quickmt-flatpak.sh', 'build-quickmt-flatpak.sh', 'quickmt-setup.sh', 'compare-translations.sh'):
        assert not (ROOT / 'scripts' / name).exists()
    text = (ROOT / 'backend/narratorverse/main.py').read_text()
    assert 'NARRATORVERSE_EXPERIMENT_' not in text


def test_manifest_uses_allowlist_not_entire_workspace():
    import json
    manifest = json.loads((ROOT / 'flatpak/io.github.DevVoidPL.NarratorVerse.json').read_text())
    sources = manifest['modules'][0]['sources']
    assert not any(source.get('path') == '..' for source in sources)
    assert any(source.get('dest') == '.tools/quickmt-python' for source in sources)


def test_source_archive_excludes_local_inputs_and_machine_telemetry(tmp_path):
    tree = subprocess.check_output(['git', '-C', str(ROOT), 'write-tree'], text=True).strip()
    archive = tmp_path / 'source.tar'
    subprocess.run(['git', '-C', str(ROOT), 'archive', '--format=tar',
                    f'--output={archive}', tree], check=True)
    with tarfile.open(archive) as source:
        names = source.getnames()
        assert '.gitignore' in names
        assert 'licenses/NOTICE.md' in names
        forbidden = {'.private', '.runtime', '.tools', 'node_modules', 'dist',
                     'target', '__pycache__', '.git', 'reference', 'staging'}
        for name in names:
            assert not forbidden.intersection(Path(name).parts), name
            assert not name.endswith(('.flatpak', '.onnx', '.pyc', '.sqlite3', '.log')), name
        assert 'docs/performance-balanced.json' not in names