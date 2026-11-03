"""Synthetic, hermetic tests. Not evidence of portal consent, audio or gameplay."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from narratorverse.profiles import Profiles
from narratorverse.protocol import Writer, decode, MAX_FRAME
from narratorverse.components import ComponentManager
from game_optimization_linux.models.narrator import NormalizedRect
from game_optimization_linux.services.narrator_persistence import CaptureGrantRepository
from game_optimization_linux import config

class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'profiles.json'
        self.profiles = Profiles(self.path)

    def test_identity_is_stable_after_rename_and_restart(self):
        p=self.profiles
        key=p.selected()['id']
        p.selected()['name']='Firefox — film'
        p.persist()
        self.assertEqual(Profiles(self.path).selected()['id'],key)
        self.assertEqual(Profiles(self.path).selected()['name'],'Firefox — film')

    def test_profile_isolation_and_region_restore(self):
        p=self.profiles
        key=p.selected()['id']
        rect={'x':.1,'y':.7,'width':.8,'height':.2}
        p.update({'subtitle_region':rect,'speech_rate':1.2,'ocr_provider_id':'rapidocr-local','subtitle_language_mode':'polish','capture_sampling_hz':8})
        other=p.create('GTA V')
        self.assertNotEqual(key,other)
        self.assertEqual(p.settings().speech_rate,1.0)
        p.select(key)
        loaded=Profiles(self.path).settings()
        self.assertEqual(loaded.subtitle_region.to_dict(),rect)
        self.assertEqual(loaded.speech_rate,1.2)
        self.assertEqual(loaded.capture_sampling_hz,8)
        self.assertEqual(loaded.ocr_provider_id,'rapidocr-local')
        self.assertEqual(loaded.subtitle_language_mode,'polish')

    def test_grants_never_cross_profiles(self):
        grants=CaptureGrantRepository(Path(self.tmp.name)/'grants.json')
        a=self.profiles.selected()['id']; b=self.profiles.create('Firefox')
        grants.save_token(a,'synthetic-test-token')
        self.assertEqual(grants.load_token(b),'')
        self.assertEqual(grants.load_token(a),'synthetic-test-token')

    def test_invalid_settings_do_not_change_saved_data(self):
        before=self.path.read_bytes()
        with self.assertRaises(ValueError): self.profiles.update({'stabilization_ms':-1})
        with self.assertRaises(ValueError): self.profiles.update({'subtitle_region':{'x':.9,'y':0,'width':.5,'height':.2}})
        self.assertEqual(self.path.read_bytes(),before)

    def test_reset_section_preserves_other_settings(self):
        p=self.profiles
        p.update({'speech_rate':1.5,'capture_sampling_hz':9})
        p.reset('recognition')
        self.assertEqual(p.settings().speech_rate,1.5)
        self.assertEqual(p.settings().capture_sampling_hz,6)

    def test_atomic_ui_settings_include_ocr_mode(self):
        self.profiles.update({'ocr_provider_id':'rapidocr-local','speech_rate':1.2},ocr_mode='classic')
        loaded=Profiles(self.path)
        self.assertEqual(loaded.selected()['ocr']['mode'],'classic')
        self.assertEqual(loaded.settings().speech_rate,1.2)
        before=self.path.read_bytes()
        with self.assertRaises(ValueError): self.profiles.update({'speech_rate':1.8},ocr_mode='invalid')
        self.assertEqual(self.path.read_bytes(),before)

    def test_no_silent_new_delay(self):
        s=self.profiles.settings()
        self.assertEqual((s.capture_sampling_hz,s.stabilization_ms,s.duplicate_cooldown_ms),(6,240,4500))

    def test_name_validation_and_private_permissions(self):
        for name in ('','\n','bad\0name','x'*101):
            with self.assertRaises(ValueError): self.profiles.create(name)
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)

class ProtocolTests(unittest.TestCase):
    def test_roundtrip_polish_and_frame(self):
        stream=io.StringIO()
        Writer(stream).send({'method':'test','params':{'text':'Zażółć gęślą jaźń'}})
        self.assertEqual(decode(stream.getvalue())['params']['text'],'Zażółć gęślą jaźń')
        self.assertEqual(stream.getvalue().count('\n'),1)

    def test_reject_bad_envelopes(self):
        for data in ('[]','{}','{"method":2}','{"method":"start","params":[]}','x'*(MAX_FRAME+1)):
            with self.assertRaises(ValueError): decode(data)

    def test_nonfinite_output_rejected(self):
        with self.assertRaises(ValueError): Writer(io.StringIO()).send({'x':float('nan')})

class ComponentTests(unittest.TestCase):
    def test_cancel_does_not_open_network(self):
        from game_optimization_linux.services.narrator_components import DEFAULT_NARRATOR_COMPONENTS
        definition=next(x for x in DEFAULT_NARRATOR_COMPONENTS if x.component_id=='ocr.english-local')
        with tempfile.TemporaryDirectory() as d:
            manager=ComponentManager(Path(d))
            manager.cancelled.set()
            with patch('narratorverse.components.urlopen') as network:
                with self.assertRaisesRegex(RuntimeError,'anulowane'): manager.install(definition.component_id)
                network.assert_not_called()
            self.assertEqual(list(Path(d).iterdir()),[])

    def test_missing_models_error_not_engine_fallback(self):
        from game_optimization_linux.services.narrator_rapidocr import RapidOcrProvider
        with tempfile.TemporaryDirectory() as d:
            rapid=RapidOcrProvider(Path(d))
            self.assertFalse(rapid.available)
            with self.assertRaises(RuntimeError): rapid.prepare('pl')
            rapid.close()

    def test_independent_paths(self):
        for p in (config.CONFIG_DIR,config.CACHE_DIR,config.STATE_DIR,config.DATA_DIR,config.NARRATOR_COMPONENTS_DIR):
            self.assertNotIn('game-optimization-linux',str(p))
            self.assertNotIn('GameOptimizationLinux',str(p))
            self.assertTrue(p.is_absolute())

if __name__=='__main__': unittest.main()