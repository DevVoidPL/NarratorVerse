"""Controlled audio/TTS fixtures; these tests do not exercise physical output."""
import json
import time
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QCoreApplication
from narratorverse.quick_read import QuickRead, chunks, validate_options, DEFAULTS
from narratorverse.profiles import Profiles
from narratorverse.filechooser import pair_from_uris
from narratorverse.main import Backend


def spin(predicate):
    app = QCoreApplication.instance() or QCoreApplication([])
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate(): return
        time.sleep(.005)
    assert predicate()


@pytest.fixture
def quick(tmp_path):
    app = QCoreApplication.instance() or QCoreApplication([])
    tts = Mock(available_voice_ids=('voidek-pl-e991', 'custom-owner'))
    tts.synthesize.return_value = object()
    audio = Mock(available=True)
    reader = QuickRead(tts, audio, Mock(), tmp_path / 'quick.json')
    yield reader, tts, audio
    reader.shutdown()
    app.processEvents()


def test_direct_read_and_completion_without_capture(quick):
    reader, tts, audio = quick
    reader.start('Zażółć gęślą jaźń.', {})
    spin(lambda: audio.play.called)
    assert reader.state == 'synthesizing'
    callback = audio.play.call_args.kwargs
    callback['started_callback'](0)
    assert reader.state == 'playing'
    callback['completed_callback']()
    assert reader.state == 'finished'
    tts.synthesize.assert_called_once_with('Zażółć gęślą jaźń.', language='pl', voice_id='voidek-pl-e991', speech_rate=1)


def test_repeated_click_and_live_conflict(quick):
    reader, tts, audio = quick
    with pytest.raises(RuntimeError, match='Wstrzymaj'): reader.start('Test', {}, live_reading=True)
    assert not tts.synthesize.called
    reader.start('Test', {})
    with pytest.raises(RuntimeError, match='Trwa odczyt'): reader.start('Test', {})
    with pytest.raises(RuntimeError): reader.save({'volume': .3})


def test_stop_during_synthesis_discards_pcm_and_closes_worker(quick):
    reader, tts, audio = quick
    started, release = Event(), Event()
    def synthesize(*args, **kwargs):
        started.set(); release.wait(2); return object()
    tts.synthesize.side_effect = synthesize
    reader.start('Test', {})
    assert started.wait(1)
    reader.stop()
    assert reader.state == 'stopping'
    tts.cancel.assert_called_once()
    release.set()
    spin(lambda: reader.state == 'stopped')
    assert not audio.play.called
    assert tts.close.called


def test_long_input_is_sequential_and_stop_ignores_late_audio_callbacks(quick):
    reader, tts, audio = quick
    reader.start('Przykładowy tekst. ' * 60, {})
    assert len(reader.parts) > 1
    spin(lambda: audio.play.call_count == 1)
    first = audio.play.call_args.kwargs
    first['started_callback'](0)
    assert tts.synthesize.call_count == 1
    first['completed_callback']()
    spin(lambda: audio.play.call_count == 2)
    second = audio.play.call_args.kwargs
    reader.stop(); second['started_callback'](0); second['completed_callback']()
    spin(lambda: reader.state == 'stopped')
    assert tts.synthesize.call_count == 2


def test_options_persist_independently_and_custom_voice(quick, tmp_path):
    reader, tts, audio = quick
    profiles = Profiles(tmp_path / 'profiles.json')
    before = profiles.path.read_bytes()
    reader.start('Test', {'voice_id': 'custom-owner', 'speech_rate': 1.3, 'volume': .2})
    spin(lambda: audio.play.called)
    assert audio.play.call_args.kwargs['volume'] == .2
    assert tts.synthesize.call_args.kwargs['voice_id'] == 'custom-owner'
    assert profiles.path.read_bytes() == before
    assert json.loads(reader.path.read_text())['speech_rate'] == 1.3


def test_missing_speech_only_and_audio_error(quick):
    reader, tts, audio = quick
    tts.available_voice_ids = ()
    with pytest.raises(RuntimeError): reader.start('Test', {})
    assert reader.required == 'tts.voidek'
    assert 'OCR' not in reader.error
    tts.available_voice_ids = ('voidek-pl-e991',)
    audio.available = False
    with pytest.raises(RuntimeError): reader.start('Test', {})
    assert reader.required == 'audio.qt-pcm'


def test_synthesis_and_playback_failures_are_real(quick):
    reader, tts, audio = quick
    tts.synthesize.side_effect = RuntimeError('broken model')
    reader.start('Test', {})
    spin(lambda: reader.state == 'error')
    assert reader.error == 'broken model'
    assert not audio.play.called
    tts.synthesize.side_effect = None
    reader.start('Test', {})
    spin(lambda: audio.play.called)
    audio.play.call_args.kwargs['error_callback']('device lost')
    assert reader.state == 'error' and reader.error == 'device lost'


def test_input_validation_and_bounded_chunks():
    for text in ('', '  ', 'x'*10001, None):
        with pytest.raises(ValueError): chunks(text)
    parts = chunks('x'*9999)
    assert all(len(part) <= 350 for part in parts)
    assert ''.join(parts) == 'x'*9999
    for values in ({'volume': float('nan')}, {'speech_rate': 3}, {'volume': True}):
        with pytest.raises(ValueError): validate_options(values)


def test_filechooser_pair_separate_document_directories(tmp_path):
    model, config = tmp_path/'one/voice.onnx', tmp_path/'two/voice.onnx.json'
    model.parent.mkdir(); config.parent.mkdir()
    model.write_bytes(b'fixture-not-onnx')
    config.write_text(json.dumps({'num_symbols': 10, 'num_speakers': 1, 'audio': {'sample_rate':22050}, 'phoneme_id_map':{'a':[1]}, 'espeak':{'voice':'pl'}}))
    assert pair_from_uris([model.as_uri(), config.as_uri()]) == (model, config)
    for uris in ([model.as_uri()], ['https://example.test/voice.onnx'], [model.as_uri(), model.as_uri()]):
        with pytest.raises(ValueError): pair_from_uris(uris)


@pytest.mark.parametrize('capture,status,active,frame,reading,confirmed,expected',[
    ('stopped','idle',False,False,False,False,'empty'),
    ('starting','starting',True,False,False,False,'starting'),
    ('selecting_source','selecting_source',True,False,False,False,'selecting_source'),
    ('active','listening',True,True,False,False,'selecting_region'),
    ('active','speaking',True,True,True,True,'reading'),
    ('active','speaking',True,True,False,True,'paused'),
    ('source_lost','error',True,True,True,True,'failed'),
    ('cancelled','stopped',False,False,False,False,'failed'),
])
@pytest.mark.parametrize('balance_status', [
    {'state': 'off', 'error': ''},
    {'state': 'ducking', 'error': ''},
    {'state': 'error', 'error': 'Audio balance unavailable'},
], ids=['balance-off', 'balance-ducking', 'balance-error'])
def test_truthful_session_state(capture,status,active,frame,reading,confirmed,expected,balance_status):
    from game_optimization_linux.models.narrator import NarratorSessionSnapshot
    from dataclasses import replace
    snap = replace(NarratorSessionSnapshot(), capture_state=capture, status=status)
    balance = Mock(spec=['snapshot'])
    balance.snapshot.return_value = dict(balance_status)
    backend = SimpleNamespace(
        pipeline=SimpleNamespace(snapshot=snap,active=active),
        capture=SimpleNamespace(reading=reading,frame=object() if frame else None,
                                frames_received=1,negotiated_variant='',restarts=0),
        profiles=SimpleNamespace(settings=lambda:SimpleNamespace(capture_source='window')),
        balance=balance,region_confirmed=confirmed,component_job='',
        components_refreshing=False,voice_job=False,
    )
    result = Backend.session(backend)
    balance.snapshot.assert_called_once_with()
    assert result['snapshot']['audio_balance'] == balance_status
    assert result['snapshot']['capture_state'] == capture
    assert result['snapshot']['status'] == status
    assert result['ui_state'] == expected
    assert result['region_confirmed'] == confirmed
    assert result['active'] == active
    assert result['reading'] == (reading and expected != 'failed')
    assert result['has_frame'] == (frame and expected != 'failed')
    if expected=='failed': assert not result['reading'] and not result['has_frame']