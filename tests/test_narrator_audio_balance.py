"""Mixer tests use fake streams only; never access or modify host audio."""
from array import array
from dataclasses import replace
import json
import os
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from game_optimization_linux.models.narrator import NarratorGameSettings, PcmAudio
from narratorverse.audio_balance import (AudioBalance, BalanceEngine, Pactl, Stream,
                                        normalize_speech, validate_target)
from narratorverse.audio_balance_worker import validated_message, write_journal
from narratorverse.main import AudioGate, Backend
from narratorverse.profiles import Profiles


TARGET = validate_target(json.dumps({'application.name': 'Test application',
                                    'application.process.binary': 'fictional-game',
                                    'application.id': ''}))
OTHER = validate_target(json.dumps({'application.name': 'Other application',
                                   'application.process.binary': 'other',
                                   'application.id': ''}))
SERVER_INFO = {'server_name': 'PulseAudio (on PipeWire 1.6.10)', 'is_local': 'yes',
               'cookie': '1234:5678', 'host_name': 'test', 'user_name': 'test'}


@pytest.mark.parametrize('targets', [[], [{'target': TARGET, 'label': 'Test application', 'ambiguous': False}]])
def test_audio_targets_request_schedules_read_only_discovery(monkeypatch, targets):
    discovery = Mock(return_value=targets)
    monkeypatch.setattr('narratorverse.main.list_targets', discovery)
    backend = SimpleNamespace(quick=SimpleNamespace(busy=False), async_job=Mock(), writer=Mock())
    Backend.handle(backend, {'id': 42, 'method': 'audio_targets', 'params': {}})
    backend.async_job.assert_called_once_with(42, discovery)
    backend.writer.send.assert_not_called()
    discovery.assert_not_called()
    # Run only the injected read-only job, never the actual pactl implementation.
    assert backend.async_job.call_args.args[1]() == targets


class Mixer:
    def __init__(self):
        self.items = [Stream(1, 'serial-1', TARGET, '111', 'Test', (60000, 30000), False),
                      Stream(2, 'serial-2', OTHER, '222', 'Other', (40000, 40000), False)]
        self.writes = []

    def streams(self):
        return list(self.items)

    def set_volume(self, stream, values):
        self.writes.append((stream.index, tuple(values)))
        self.items = [replace(item, volumes=tuple(values)) if item.identity == stream.identity else item
                      for item in self.items]


def engine():
    mixer = Mixer()
    policy = BalanceEngine(mixer)
    policy.configure(TARGET, -12, mixer.streams())
    return mixer, policy


def tick(mixer, policy, now, active=True):
    policy.step(mixer.streams(), active=active, now=now)


def test_attack_hold_release_and_stereo_without_touching_other_application():
    mixer, policy = engine()
    original = mixer.streams()
    for i in range(5):
        tick(mixer, policy, i * .05)
    raw_gain = 10 ** (-12 / 60)
    assert mixer.items[0].volumes == tuple(round(v * raw_gain) for v in original[0].volumes)
    assert mixer.items[1] == original[1]
    reduced = mixer.items[0].volumes
    tick(mixer, policy, .4, False)
    assert mixer.items[0].volumes == reduced
    for i in range(10, 40):
        tick(mixer, policy, i * .05, False)
    assert mixer.items == original
    assert not policy.entries
    assert policy.state == 'ready'


def test_repeated_speech_does_not_compound_or_replace_baseline():
    mixer, policy = engine()
    for i in range(100):
        tick(mixer, policy, i * .05)
    assert next(iter(policy.entries.values()))['base'] == [60000, 30000]
    assert mixer.items[0].volumes[0] == round(60000 * 10 ** (-12 / 60))
    policy.configure('', -12, mixer.streams())
    assert mixer.items[0].volumes == (60000, 30000)


def test_manual_mixer_edit_is_never_overwritten_or_restored_to_old_value():
    mixer, policy = engine()
    tick(mixer, policy, 1)
    mixer.items[0] = replace(mixer.items[0], volumes=(17000, 9000))
    tick(mixer, policy, 1.1)
    assert policy.state == 'manual'
    assert not policy.entries
    tick(mixer, policy, 2, False)
    policy.restore(mixer.streams())
    assert mixer.items[0].volumes == (17000, 9000)


def test_ambiguous_processes_and_unknown_source_do_not_change_volume():
    mixer, policy = engine()
    mixer.items.append(replace(mixer.items[0], index=3, identity='new', pid='333'))
    tick(mixer, policy, 1)
    assert policy.state == 'ambiguous'
    assert not mixer.writes
    policy.configure(OTHER + ' ', -12, mixer.streams())
    tick(mixer, policy, 2)
    assert policy.state == 'missing'
    assert not mixer.writes


def test_disappeared_stream_baseline_is_not_applied_to_recycled_index():
    mixer, policy = engine()
    tick(mixer, policy, 1)
    mixer.items[0] = replace(mixer.items[0], identity='different-serial', target=OTHER,
                             volumes=(14000, 11000))
    policy.restore(mixer.streams())
    assert mixer.items[0].volumes == (14000, 11000)


def test_replacement_during_ducking_suspends_instead_of_compounding():
    mixer, policy = engine()
    tick(mixer, policy, 1)
    inherited = mixer.items[0].volumes
    mixer.items[0] = replace(mixer.items[0], identity='new-stream')
    tick(mixer, policy, 1.1)
    assert policy.state == 'changed'
    assert mixer.items[0].volumes == inherited
    assert not policy.entries
    tick(mixer, policy, 2)
    assert mixer.items[0].volumes == inherited


def test_game_stream_added_during_ducking_releases_known_streams():
    mixer, policy = engine()
    tick(mixer, policy, 1)
    mixer.items.append(replace(mixer.items[0], index=3, identity='additional', volumes=(15000, 7000)))
    tick(mixer, policy, 1.1)
    assert policy.state == 'changed'
    assert mixer.items[0].volumes == (60000, 30000)
    assert mixer.items[2].volumes == (15000, 7000)


def test_muted_and_zero_volume_sources_are_not_raised():
    mixer, policy = engine()
    mixer.items[0] = replace(mixer.items[0], muted=True)
    tick(mixer, policy, 1)
    assert not mixer.writes
    mixer.items[0] = replace(mixer.items[0], muted=False, volumes=(0, 0))
    tick(mixer, policy, 2)
    assert not mixer.writes


def test_mute_during_ducking_does_not_strand_baseline():
    mixer, policy = engine()
    tick(mixer, policy, 1)
    mixer.items[0] = replace(mixer.items[0], muted=True)
    policy.restore(mixer.streams())
    assert mixer.items[0].muted
    assert mixer.items[0].volumes == (60000, 30000)


def test_failed_command_keeps_original_baseline_for_recovery(tmp_path):
    mixer, policy = engine()
    journal = tmp_path / 'recovery.json'
    policy.save = lambda entries: write_journal(journal, entries)
    mixer.set_volume = Mock(side_effect=RuntimeError('server unavailable'))
    with pytest.raises(RuntimeError):
        tick(mixer, policy, 1)
    saved = json.loads(journal.read_text())
    assert saved['serial-1']['base'] == [60000, 30000]
    assert saved['serial-1']['before'] == [60000, 30000]
    assert saved['serial-1']['last'] != saved['serial-1']['base']


@pytest.mark.parametrize('field,value', [('audio_balance_enabled', 1), ('normalize_narrator', 'yes'),
    ('audio_balance_db', float('nan')), ('audio_balance_db', -100), ('audio_balance_target', '\n')])
def test_settings_reject_invalid_balance_values(field, value):
    with pytest.raises(ValueError):
        NarratorGameSettings.default('local-test').__class__(game_key='local-test', **{field: value})


def test_profile_persistence_isolation_reset_and_legacy_defaults(tmp_path):
    profiles = Profiles(tmp_path / 'profiles.json')
    assert not profiles.settings().audio_balance_enabled
    first = profiles.selected()['id']
    profiles.update({'audio_balance_enabled': True, 'audio_balance_target': TARGET,
                     'audio_balance_db': -6, 'normalize_narrator': True})
    profiles.create('Second')
    assert not profiles.settings().normalize_narrator
    profiles.select(first)
    assert profiles.settings().audio_balance_target == TARGET
    profiles.reset('audio')
    assert not profiles.settings().audio_balance_enabled
    assert not profiles.settings().audio_balance_target
    assert not profiles.settings().normalize_narrator
    assert Profiles(profiles.path).settings().audio_balance_db == -12


@pytest.mark.parametrize('value', ['[]', '{}', 'not-json', '', '{"application.name":"x"}'])
def test_target_validation(value):
    if value == '':
        assert validate_target(value) == ''
    else:
        with pytest.raises(ValueError):
            validate_target(value)


def pcm(values):
    samples = array('h', values)
    if sys.byteorder != 'little':
        samples.byteswap()
    return PcmAudio(samples=samples.tobytes(), sample_rate=24000, channels=1)


def decoded(audio):
    values = array('h')
    values.frombytes(audio.samples)
    if sys.byteorder != 'little':
        values.byteswap()
    return values


def test_leveling_bounds_gain_peak_and_does_not_amplify_silence():
    silent = pcm([0] * 100)
    assert normalize_speech(silent) is silent
    noise = pcm([5, -5] * 100)
    assert normalize_speech(noise) is noise
    quiet = pcm([1000, -1000] * 100)
    assert max(decoded(normalize_speech(quiet))) == 2000
    loud = normalize_speech(pcm([32000, -32000] * 100))
    assert max(abs(v) for v in decoded(loud)) <= 32768 * .89
    assert len(loud.samples) == 400
    unsupported = replace(quiet, sample_format='f32le')
    assert normalize_speech(unsupported) is unsupported


def test_gate_uses_playback_callbacks_only_and_invalidates_late_callbacks(tmp_path):
    balance = AudioBalance(tmp_path)
    output, capture = Mock(), SimpleNamespace(reading=True)
    gate = AudioGate(output, capture, balance)
    gate.play(pcm([500]), volume=.85, request_id=5, started_callback=Mock(),
              completed_callback=Mock(), error_callback=Mock())
    callbacks = output.play.call_args.kwargs
    assert not balance.playing
    callbacks['started_callback'](0)
    assert balance.playing == {5}
    callbacks['completed_callback']()
    assert not balance.playing
    gate.stop()
    callbacks['started_callback'](0)
    assert not balance.playing
    capture.reading = False
    output.reset_mock()
    gate.play(pcm([0]), request_id=6)
    output.play.assert_not_called()


def test_protocol_validation_and_json_pactl_parser():
    with pytest.raises(ValueError):
        validated_message({'enabled': 'yes', 'active': True, 'reading': True, 'db': -12, 'target': TARGET})
    payload = [{'index': 5, 'client': 7, 'mute': False,
                'properties': {**json.loads(TARGET), 'application.process.id': '99999999', 'object.serial': '55'},
                'volume': {'front-left': {'value': 60000}, 'front-right': {'value': 30000}}}]
    def run(args, **kwargs):
        return SimpleNamespace(stdout=json.dumps(SERVER_INFO if 'info' in args else payload))
    runner = Mock(side_effect=run)
    result = Pactl(runner).streams()
    assert result[0].target == TARGET
    assert result[0].volumes == (60000, 30000)
    assert runner.call_args.kwargs['timeout'] == 2
    assert not runner.call_args.kwargs.get('shell')


def test_multiple_streams_from_same_process_are_balanced_individually():
    mixer, policy = engine()
    mixer.items.append(replace(mixer.items[0], index=3, identity='serial-3', volumes=(20000, 10000)))
    for i in range(5):
        tick(mixer, policy, i * .05)
    assert len(policy.entries) == 2
    assert mixer.items[2].volumes == tuple(round(v * 10 ** (-12 / 60)) for v in (20000, 10000))
    policy.restore(mixer.streams())
    assert mixer.items[2].volumes == (20000, 10000)


def test_silent_gameplay_and_direct_quickread_output_do_not_duck(tmp_path):
    balance = AudioBalance(tmp_path)
    output, capture = Mock(), SimpleNamespace(reading=True)
    gate = AudioGate(output, capture, balance)
    gate.play(pcm([0] * 32), volume=.85, request_id=1, started_callback=Mock(),
              completed_callback=Mock(), error_callback=Mock())
    output.play.call_args.kwargs['started_callback'](0)
    assert not balance.playing
    output.play(pcm([500]), volume=.85, request_id=2, started_callback=Mock(),
                completed_callback=Mock(), error_callback=Mock())
    assert not balance.playing


def test_terminal_observer_releases_underrun_without_false_completion(tmp_path):
    from game_optimization_linux.services.narrator_audio import QtNarratorAudioOutput
    from test_narrator_playback_completion import _FakeSink, _Device
    sinks = []
    def factory(*args):
        sink = _FakeSink(*args)
        sinks.append(sink)
        return sink
    balance = AudioBalance(tmp_path)
    output = QtNarratorAudioOutput(sink_factory=factory, device_provider=_Device)
    gate = AudioGate(output, SimpleNamespace(reading=True), balance)
    completed = Mock()
    gate.play(pcm([500] * 24000), volume=.85, request_id=1, started_callback=Mock(),
              completed_callback=completed, error_callback=Mock())
    # Run the queued payload synchronously for deterministic fake-sink feedback.
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.processEvents()
    assert balance.playing == {1}
    sinks[0].finish(.2)
    assert not balance.playing
    completed.assert_not_called()
    assert output.interrupted_count == 1


def test_write_revalidates_identity_and_manual_edits_before_command():
    mixer = Pactl(Mock())
    stream = Mixer().items[0]
    mixer.streams = Mock(return_value=[replace(stream, identity='recycled')])
    with pytest.raises(RuntimeError, match='disappeared'):
        mixer.set_volume(stream, (10000, 5000))
    mixer.command = Mock()
    mixer.streams = Mock(return_value=[replace(stream, volumes=(20000, 20000))])
    with pytest.raises(RuntimeError, match='externally'):
        mixer.set_volume(stream, (10000, 5000))
    mixer.command.assert_not_called()


@pytest.mark.parametrize('disconnect', [True, False], ids=['backend-eof', 'expired-heartbeat'])
def test_worker_eof_restores_after_parent_disconnect(tmp_path, disconnect):
    """Real subprocess/pipe/journal lifecycle against a fake pactl executable."""
    data = tmp_path / 'mixer.json'
    state = tmp_path / 'state'
    payload = [{'index': 5, 'client': 7, 'mute': False,
                'properties': {**json.loads(TARGET), 'application.process.id': '99999999', 'object.serial': '55'},
                'volume': {'front-left': {'value': 60000}, 'front-right': {'value': 30000}}}]
    data.write_text(json.dumps(payload))
    tool = tmp_path / 'pactl'
    tool.write_text('#!' + sys.executable + '\n'
        'import json, os, sys\nfrom pathlib import Path\n'
        'p=Path(os.environ["FAKE_MIXER"])\ndata=json.loads(p.read_text())\n'
        'if "info" in sys.argv: print(' + repr(json.dumps(SERVER_INFO)) + ')\n'
        'elif "list" in sys.argv: print(json.dumps(data))\n'
        'else:\n'
        ' for channel, value in zip(data[0]["volume"].values(),sys.argv[3:]): channel["value"]=int(value)\n'
        ' temp=p.with_suffix(".tmp"); temp.write_text(json.dumps(data)); temp.replace(p)\n')
    tool.chmod(0o700)
    env = {**os.environ, 'FAKE_MIXER': str(data), 'PATH': str(tmp_path) + os.pathsep + os.environ['PATH']}
    process = subprocess.Popen([sys.executable, '-m', 'narratorverse.audio_balance_worker', str(state)],
                               stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                               text=True, env=env)
    try:
        command = {'enabled': True, 'active': True, 'reading': True, 'db': -12, 'target': TARGET}
        process.stdin.write(json.dumps(command) + '\n')
        process.stdin.flush()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if json.loads(data.read_text())[0]['volume']['front-left']['value'] < 60000:
                break
            if process.poll() is not None:
                pytest.fail(process.stderr.read())
            time.sleep(.02)
        assert json.loads(data.read_text())[0]['volume']['front-left']['value'] < 60000
        if not disconnect:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                current = json.loads(data.read_text())[0]['volume']
                if [v['value'] for v in current.values()] == [60000, 30000]:
                    break
                if process.poll() is not None:
                    pytest.fail(process.stderr.read())
                time.sleep(.02)
            current = json.loads(data.read_text())[0]['volume']
            assert [v['value'] for v in current.values()] == [60000, 30000]
        process.stdin.close()
        process.wait(timeout=8)
        assert process.returncode == 0, process.stderr.read()
        restored = json.loads(data.read_text())[0]['volume']
        assert [v['value'] for v in restored.values()] == [60000, 30000]
        assert json.loads((state / 'audio-balance-recovery.json').read_text()) == {}
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)