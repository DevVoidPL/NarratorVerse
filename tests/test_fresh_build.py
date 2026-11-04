"""Fresh build input contracts, runnable without Qt or installed application."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch
import io

ROOT = Path(__file__).resolve().parents[1]


class FreshBuildTests(unittest.TestCase):
    def helper(self):
        path = ROOT / 'scripts/fresh-inputs.py'
        self.assertTrue(path.is_file(), 'Fresh input preparation is not implemented')
        spec = importlib.util.spec_from_file_location('fresh_inputs', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_verified_download_rejects_changed_cached_bytes(self):
        helper = self.helper()
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / 'artifact.whl'
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                helper.fetch({'filename': path.name, 'sha256': '0' * 64,
                              'url': 'https://files.pythonhosted.org/not-used'}, Path(work))
            self.assertEqual(path.read_bytes(), b'changed')

    def test_zip_slip_and_symlinks_rejected(self):
        helper = self.helper()
        with tempfile.TemporaryDirectory() as work:
            archive = Path(work) / 'bad.whl'
            with zipfile.ZipFile(archive, 'w') as output:
                output.writestr('../escaped', 'bad')
            with self.assertRaises(ValueError):
                helper.unpack_wheel(archive, Path(work) / 'output')
            self.assertFalse((Path(work) / 'escaped').exists())
            with zipfile.ZipFile(archive, 'w') as output:
                link = zipfile.ZipInfo('link')
                link.external_attr = 0o120777 << 16
                output.writestr(link, '/etc/passwd')
            with self.assertRaises(ValueError):
                helper.unpack_wheel(archive, Path(work) / 'output')

    def test_download_retries_transient_network_error_without_replacing_failed_evidence(self):
        helper = self.helper()
        class Response(io.BytesIO):
            url = 'https://files.pythonhosted.org/test'
        with tempfile.TemporaryDirectory() as work:
            with patch.object(helper.urllib.request, 'urlopen', side_effect=[
                    TimeoutError('test timeout'), Response(b'wheel')]) as request:
                path = helper.fetch({'filename': 'test.whl', 'url': Response.url,
                    'sha256': hashlib.sha256(b'wheel').hexdigest()}, Path(work))
                self.assertEqual(path.read_bytes(), b'wheel')
                self.assertEqual(request.call_count, 2)
                self.assertTrue(list(Path(work).glob('*.pending')))

    def test_component_manifest_hashes_real_output_and_keeps_license(self):
        helper = self.helper()
        with tempfile.TemporaryDirectory() as work:
            component = Path(work)
            (component / 'model').write_bytes(b'model')
            (component / 'LICENSE').write_text('test license')
            helper.component_manifest(component, {'component_id': 'ocr.test',
                'version': 'pinned', 'license_id': 'Apache-2.0', 'kind': 'ocr'})
            manifest = json.loads((component / 'component.json').read_text())
            entries = {e['path']: e for e in manifest['files']}
            self.assertEqual(entries['model']['sha256'], hashlib.sha256(b'model').hexdigest())
            self.assertIn('LICENSE', entries)
            self.assertEqual(manifest['managed_by'], 'game-optimization-linux')
            self.assertEqual(entries['model']['size'], 5)

    def test_source_snapshot_excludes_old_artifacts_and_user_data(self):
        helper = self.helper()
        with tempfile.TemporaryDirectory() as work:
            source = Path(work) / 'source'
            source.mkdir()
            for path in ['src/App.svelte', 'src-tauri/src/main.rs', 'svelte.config.js',
                         'src-tauri/target/old', '.runtime/old', 'components/old',
                         'backend/__pycache__/bad.pyc']:
                p = source / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('test')
            dest = Path(work) / 'snapshot'
            helper.source_snapshot(source, dest)
            self.assertTrue((dest / 'src-tauri/src/main.rs').is_file())
            self.assertTrue((dest / 'src/App.svelte').is_file())
            self.assertTrue((dest / 'svelte.config.js').is_file())
            for path in ['src-tauri/target', '.runtime', 'components', 'backend/__pycache__']:
                self.assertFalse((dest / path).exists(), path)

    def test_manifest_builds_source_not_historical_payload(self):
        manifest = json.loads((ROOT / 'flatpak/io.github.DevVoidPL.NarratorVerse.json').read_text())
        text = json.dumps(manifest)
        self.assertNotIn('local-snapshot', text)
        for source in [s for module in manifest['modules'] for s in module.get('sources', [])]:
            self.assertNotIn('.runtime', source.get('path', ''))
            self.assertNotIn('target/release', source.get('path', ''))
        self.assertIn('--frozen', text)
        self.assertIn('npm ci', text)
        self.assertIn('--require-hashes', text)
        self.assertIn('--ignore-installed', text)

    def test_default_build_entries_never_use_snapshot(self):
        for name in ('build.sh', 'build-flatpak.sh', 'prepare-quickmt-runtime.sh'):
            text = (ROOT / 'scripts' / name).read_text()
            self.assertNotIn('.runtime', text, name)
            self.assertNotIn('npm install', text, name)
            self.assertNotIn('stage-flatpak.py', text, name)
            self.assertIn('build-fresh.sh', text, name)

    def test_inventory_tracks_files_symlinks_and_model_versions(self):
        spec = importlib.util.spec_from_file_location('payload_inventory', ROOT / 'scripts/payload-inventory.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            (root / 'file').write_bytes(b'payload')
            (root / 'link').symlink_to('file')
            result = module.inventory(root)
            files = {entry['path']: entry for entry in result['files']}
            self.assertEqual(files['file']['sha256'], hashlib.sha256(b'payload').hexdigest())
            self.assertEqual(files['link']['symlink'], 'file')
            self.assertTrue(result['redistribution_review'].startswith('OPEN'))


if __name__ == '__main__':
    unittest.main()