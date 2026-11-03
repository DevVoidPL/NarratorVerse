"""Explicit installer tests: tiny local payloads, no model/network/native imports."""
import hashlib
from io import BytesIO
import json
from types import SimpleNamespace

import pytest


def _installer():
    from narratorverse import quickmt_download
    return quickmt_download


@pytest.fixture
def model(monkeypatch):
    module = _installer()
    payloads = {'model.bin': b'weights', 'config.json': b'{}',
                'README.md': b'license: cc-by-4.0\nQuickMT\n'}
    manifest = {}
    for name, content in payloads.items():
        manifest[name] = (len(content), 'sha256', hashlib.sha256(content).hexdigest())
    monkeypatch.setattr(module, 'FILES', manifest)
    calls = []
    def opener(url, timeout):
        calls.append(url)
        assert timeout > 0
        assert url.startswith(module.BASE_URL + '/')
        return BytesIO(payloads[url.rsplit('/', 1)[-1]])
    return module, payloads, calls, opener


def test_installer_entrypoint_is_available():
    from importlib.util import find_spec
    assert find_spec('narratorverse.quickmt_download') is not None


def test_install_checks_every_sha256_and_preserves_attribution(tmp_path, model):
    module, payloads, calls, opener = model
    root = tmp_path / 'model'
    module.install(root, opener=opener)
    receipt = json.loads((root / 'SHA256SUMS.json').read_text())
    assert receipt['revision'] == module.QUICKMT_REVISION
    assert receipt['files'] == {name: hashlib.sha256(data).hexdigest()
                                for name, data in payloads.items()}
    for name, data in payloads.items():
        assert (root / name).read_bytes() == data
    assert 'CC BY 4.0' in (root / 'ATTRIBUTION.txt').read_text()
    assert 'QuickMT' in (root / 'ATTRIBUTION.txt').read_text()
    assert 'https://creativecommons.org/licenses/by/4.0/' in (root / 'ATTRIBUTION.txt').read_text()
    assert len(calls) == len(payloads)
    module.verify_installation(root)


def test_offline_verification_opens_existing_lock_readonly(tmp_path, model, monkeypatch):
    import os
    module, _, _, opener = model
    root = tmp_path / 'model'
    module.install(root, opener=opener)
    original = os.open
    flags_seen = []
    def spy(path, flags, *args, **kwargs):
        if str(path).endswith('.download.lock'):
            flags_seen.append(flags)
        return original(path, flags, *args, **kwargs)
    monkeypatch.setattr(module.os, 'open', spy)
    module.verify_installation(root)
    assert flags_seen
    assert flags_seen[0] & os.O_ACCMODE == os.O_RDONLY
    assert not flags_seen[0] & os.O_CREAT


def test_rerun_reuses_weights_but_repairs_corrupted_files(tmp_path, model):
    module, payloads, calls, opener = model
    root = tmp_path / 'model'
    module.install(root, opener=opener)
    calls.clear()
    (root / 'config.json').write_bytes(b'xx')
    module.install(root, opener=opener)
    assert not any(url.endswith('/model.bin') for url in calls)
    assert (root / 'config.json').read_bytes() == payloads['config.json']
    module.verify_installation(root)


def test_bad_payload_is_not_promoted_and_rerun_recovers(tmp_path, model):
    module, _, _, opener = model
    root = tmp_path / 'model'
    def corrupt(url, timeout):
        if url.endswith('/model.bin'):
            return BytesIO(b'corrupt')
        return opener(url, timeout)
    with pytest.raises(ValueError, match='model.bin'):
        module.install(root, opener=corrupt)
    assert not (root / 'model.bin').exists()
    assert not (root / 'SHA256SUMS.json').exists()
    module.install(root, opener=opener)
    module.verify_installation(root)


def test_interrupted_download_can_be_retried(tmp_path, model):
    module, _, _, opener = model
    root = tmp_path / 'model'
    def offline(url, timeout):
        raise OSError('network disconnected')
    with pytest.raises(OSError, match='disconnected'):
        module.install(root, opener=offline)
    assert not (root / 'SHA256SUMS.json').exists()
    module.install(root, opener=opener)
    module.verify_installation(root)


def test_stale_partial_is_removed_only_by_explicit_install(tmp_path, model):
    module, _, _, opener = model
    root = tmp_path / 'model'
    module.install(root, opener=opener)
    partial = root / '.quickmt-interrupted'
    partial.write_bytes(b'partial')
    with pytest.raises(ValueError, match='częściowy'):
        module.verify_installation(root)
    assert partial.exists()
    module.install(root, opener=opener)
    assert not partial.exists()
    module.verify_installation(root)


def test_modified_receipt_cannot_authenticate_modified_payload(tmp_path, model):
    module, _, _, opener = model
    root = tmp_path / 'model'
    module.install(root, opener=opener)
    changed = b'changed'
    (root / 'model.bin').write_bytes(changed)
    receipt_path = root / 'SHA256SUMS.json'
    receipt = json.loads(receipt_path.read_text())
    receipt['files']['model.bin'] = hashlib.sha256(changed).hexdigest()
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match='model.bin'):
        module.verify_installation(root)


def test_sha256_of_disk_payload_is_checked_before_promotion(tmp_path, model, monkeypatch):
    module, _, _, opener = model
    monkeypatch.setattr(module, '_sha256', lambda path: '0' * 64)
    root = tmp_path / 'model'
    with pytest.raises(ValueError, match='SHA-256'):
        module.install(root, opener=opener)
    assert not (root / 'model.bin').exists()


def test_offline_check_catches_manifest_digest_mismatch(tmp_path, model):
    module, _, _, opener = model
    root = tmp_path / 'model'
    module.install(root, opener=opener)
    path = root / 'SHA256SUMS.json'
    receipt = json.loads(path.read_text())
    receipt['files']['config.json'] = '0' * 64
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match='config.json.*SHA-256'):
        module.verify_installation(root)


def test_redirect_handler_refuses_untrusted_redirect():
    from urllib.request import Request
    module = _installer()
    with pytest.raises(ValueError, match='przekierowanie'):
        module._OfficialRedirect().redirect_request(Request(module.BASE_URL), None, 302,
                                                    'Found', {}, 'https://example.org/model')


def test_model_is_never_installed_inside_source_tree():
    module = _installer()
    from pathlib import Path
    root = Path(module.__file__).resolve().parents[2] / 'components/quickmt-test'
    with pytest.raises(ValueError, match='repozytorium'):
        module.install(root)


def test_default_directory_is_shared_with_application_component_root(monkeypatch):
    from pathlib import Path
    from game_optimization_linux import config
    monkeypatch.setattr(config, 'NARRATOR_COMPONENTS_DIR', Path('/tmp/user-data/narratorverse/narrator/components'))
    assert _installer().default_model_dir() == config.NARRATOR_COMPONENTS_DIR / 'translation.quickmt-en-pl'


def test_check_is_offline_and_rejects_corruption_and_missing_license(tmp_path, model):
    module, _, _, opener = model
    root = tmp_path / 'model'
    module.install(root, opener=opener)
    (root / 'model.bin').write_bytes(b'changed')
    with pytest.raises(ValueError, match='model.bin'):
        module.verify_installation(root)
    module.install(root, opener=opener)
    (root / 'README.md').unlink()
    with pytest.raises((ValueError, OSError), match='README.md'):
        module.verify_installation(root)


@pytest.mark.parametrize('entry', ['model.bin', 'SHA256SUMS.json', 'ATTRIBUTION.txt'])
def test_rejects_symlink_targets_without_modifying_them(tmp_path, model, entry):
    module, _, _, opener = model
    root = tmp_path / 'model'
    root.mkdir()
    external = tmp_path / 'external'
    external.write_text('untouched')
    (root / entry).symlink_to(external)
    with pytest.raises(ValueError, match='symlink|dowiąza'):
        module.install(root, opener=opener)
    assert external.read_text() == 'untouched'


def test_rejects_unknown_files_and_symlink_directory(tmp_path, model):
    module, _, _, opener = model
    root = tmp_path / 'model'
    root.mkdir()
    (root / 'unexpected.bin').write_text('not part of model')
    with pytest.raises(ValueError, match='unexpected.bin'):
        module.install(root, opener=opener)
    link = tmp_path / 'link'
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink|dowiąza'):
        module.install(link, opener=opener)


def test_exclusive_install_lock_is_released_on_failure(tmp_path, model):
    import fcntl
    module, _, _, opener = model
    root = tmp_path / 'model'
    root.mkdir()
    with (root / '.download.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match='pobieranie|lock'):
            module.install(root, opener=opener)
    module.install(root, opener=opener)


def test_pinned_manifest_has_only_official_required_files():
    module = _installer()
    assert module.BASE_URL == ('https://huggingface.co/quickmt/quickmt-en-pl/resolve/'
                               '6209580ce1fe525214f29fc39725007b73410109')
    assert set(module.FILES) == {'model.bin', 'config.json', 'source_vocabulary.json',
                                 'target_vocabulary.json', 'src.spm.model',
                                 'tgt.spm.model', 'README.md'}


def test_https_redirect_policy_rejects_unofficial_or_insecure_hosts():
    module = _installer()
    assert module.allowed_url('https://huggingface.co/quickmt/a')
    assert module.allowed_url('https://cas-bridge.xethub.hf.co/xet-bridge-us/item')
    assert not module.allowed_url('http://huggingface.co/model')
    assert not module.allowed_url('https://huggingface.co.evil.example/model')
    assert not module.allowed_url('https://example.org/model')


def test_smoke_uses_real_provider_boundary_and_closes_on_failure(tmp_path, monkeypatch):
    from narratorverse import quickmt_smoke
    events = []
    class Provider:
        provider_id = 'test-quickmt'
        def __init__(self, root): assert root == tmp_path
        def translate(self, text, **options):
            events.append((text, options))
            return SimpleNamespace(translated_text='Nie otwieraj drzwi.')
        def close(self): events.append('closed')
    monkeypatch.setattr(quickmt_smoke, 'verify_installation', lambda root: events.append('verified'))
    monkeypatch.setattr(quickmt_smoke, 'QuickMTTranslationProvider', Provider)
    report = quickmt_smoke.smoke_test(tmp_path, 'Do not open the door.', 'balanced')
    assert report['translated_text'] == 'Nie otwieraj drzwi.'
    assert report['device'] == 'cpu'
    assert events == ['verified', ('Do not open the door.', dict(source_language='en',
                       target_language='pl', profile_id='balanced')), 'closed']
    def fail(*args, **kwargs): raise RuntimeError('native model load failed')
    monkeypatch.setattr(Provider, 'translate', fail)
    with pytest.raises(RuntimeError, match='native model load failed'):
        quickmt_smoke.smoke_test(tmp_path, 'Go!', 'fast')
    assert events[-1] == 'closed'


def test_download_cli_errors_explain_retry(tmp_path, monkeypatch, capsys):
    module = _installer()
    def fail(*args, **kwargs): raise OSError('disk full')
    monkeypatch.setattr(module, 'install', fail)
    assert module.main(['--model-dir', str(tmp_path)]) == 1
    message = capsys.readouterr().err
    assert 'disk full' in message
    assert 'ponownie' in message


def test_truncated_http_response_is_a_readable_retryable_error(tmp_path, monkeypatch, capsys):
    from http.client import IncompleteRead
    module = _installer()
    def fail(*args, **kwargs): raise IncompleteRead(b'partial', 100)
    monkeypatch.setattr(module, 'install', fail)
    assert module.main(['--model-dir', str(tmp_path)]) == 1
    assert 'ponownie' in capsys.readouterr().err


def test_developer_downloader_help_needs_no_sdk_or_native_imports():
    import subprocess, sys
    result = subprocess.run([sys.executable, '-m', 'narratorverse.quickmt_download', '--help'], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert '--check-files' in result.stdout
    assert '--model-dir' in result.stdout


def test_smoke_does_not_accept_empty_translation(tmp_path, monkeypatch):
    from narratorverse import quickmt_smoke
    monkeypatch.setattr(quickmt_smoke, 'verify_installation', lambda root: None)
    class Provider:
        provider_id = 'test'
        def __init__(self, root): pass
        def translate(self, *args, **kwargs): return SimpleNamespace(translated_text='')
        def close(self): pass
    monkeypatch.setattr(quickmt_smoke, 'QuickMTTranslationProvider', Provider)
    with pytest.raises(RuntimeError, match='pust|empty'):
        quickmt_smoke.smoke_test(tmp_path, 'Go!', 'fast')