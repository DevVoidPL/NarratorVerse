"""Release defaults use exactly one pinned, GUI-managed local translator."""
import hashlib
import json
from pathlib import Path

from game_optimization_linux import config
from game_optimization_linux.models.narrator import NarratorGameSettings, NarratorComponentKind
from game_optimization_linux.services.narrator_components import DEFAULT_NARRATOR_COMPONENTS
from narratorverse.quickmt import QUICKMT_FILES, QUICKMT_REVISION, QuickMTTranslationProvider
from narratorverse.components import ComponentManager

ROOT = Path(__file__).resolve().parents[1]


def test_only_quickmt_is_advertised_and_default_provider_matches():
    definitions = [d for d in DEFAULT_NARRATOR_COMPONENTS if d.kind == NarratorComponentKind.TRANSLATION]
    assert len(definitions) == 1
    definition = definitions[0]
    assert definition.component_id == 'translation.quickmt-en-pl'
    assert definition.version == QUICKMT_REVISION
    assert definition.license_id == 'CC-BY-4.0'
    assert definition.install_ready
    assert len(definition.resolved_artifacts()) >= 6
    for artifact in definition.resolved_artifacts():
        assert QUICKMT_REVISION in artifact.source_url
        assert len(artifact.sha256) == 64
    assert NarratorGameSettings.default('480').translation_provider_id == QuickMTTranslationProvider.provider_id


def test_all_six_model_files_are_pinned_by_sha256():
    assert len(QUICKMT_FILES) == 6
    assert all(kind == 'sha256' and len(digest) == 64 for _, kind, digest in QUICKMT_FILES.values())


def test_one_xdg_component_location_without_manual_model_path():
    from narratorverse.quickmt_download import default_model_dir
    provider = QuickMTTranslationProvider(runtime_available=lambda: False)
    assert provider.component_id == 'translation.quickmt-en-pl'
    assert provider._component_path == config.NARRATOR_COMPONENTS_DIR / provider.component_id
    assert default_model_dir() == provider._component_path


def test_application_has_no_experimental_translator_or_dedup_switch():
    text = (ROOT / 'backend/narratorverse/main.py').read_text()
    assert 'ExperimentOptions' not in text
    assert 'ArgosCTranslate2TranslationProvider' not in text
    assert 'QuickMTTranslationProvider()' in text
    assert 'session_settings' not in text
    assert 'sacremoses' not in (ROOT / 'backend/narratorverse/runtime_checks.py').read_text()


def test_component_download_progress_is_aggregate_and_failed_install_atomic(tmp_path, monkeypatch):
    from io import BytesIO
    import narratorverse.components as module
    from game_optimization_linux.services.narrator_components import NarratorComponentArtifact, NarratorComponentDefinition
    files = {'one': b'a'*200000, 'two': b'b'*100000}
    artifacts = tuple(NarratorComponentArtifact('https://huggingface.co/test/'+name,
                      hashlib.sha256(data).hexdigest(), len(data), name) for name, data in files.items())
    definition = NarratorComponentDefinition(component_id='translation.fixture',
        kind=NarratorComponentKind.TRANSLATION, name='fixture', license_id='CC-BY-4.0',
        version='1', install_ready=True, download_size_bytes=300000, artifacts=artifacts)
    class Response(BytesIO):
        def geturl(self): return 'https://huggingface.co/test'
    monkeypatch.setattr(module, 'urlopen', lambda url, **kw: Response(files[url.rsplit('/',1)[-1]]))
    progress = []
    manager = ComponentManager(tmp_path, definitions=(definition,), progress=lambda n,t: progress.append((n,t)))
    manager.install('translation.fixture')
    assert progress[-1] == (300000, 300000)
    assert [n for n,t in progress] == sorted(n for n,t in progress)
    assert all(t == 300000 for n,t in progress)
    assert manager.verify_installed('translation.fixture')[0]
    manager.cancelled.set()
    import pytest
    with pytest.raises(RuntimeError, match='anulowane'):
        manager.install('translation.fixture')
    assert manager.verify_installed('translation.fixture')[0]


def test_old_profile_provider_migrates_without_changing_other_fields(tmp_path):
    from narratorverse.profiles import Profiles
    profiles = Profiles(tmp_path / 'profiles.json')
    data = json.loads(profiles.path.read_text())
    data['profiles'][0]['settings']['translation_provider_id'] = 'argos-ctranslate2-en-pl-1.9'
    data['profiles'][0]['settings']['speech_rate'] = 1.2
    profiles.path.write_text(json.dumps(data))
    migrated = Profiles(profiles.path)
    assert migrated.settings().translation_provider_id == QuickMTTranslationProvider.provider_id
    assert migrated.settings().speech_rate == 1.2
    assert json.loads(profiles.path.read_text())['profiles'][0]['settings']['translation_provider_id'] == QuickMTTranslationProvider.provider_id