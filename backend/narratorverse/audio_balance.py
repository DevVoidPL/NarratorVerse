"""Per-application ducking. No master-volume, routing or microphone access."""
from __future__ import annotations

from array import array
from dataclasses import dataclass, replace
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from threading import Lock, Thread
import time


TARGET_KEYS = ('application.name', 'application.process.binary', 'application.id')


def validate_target(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError('Invalid audio application')
    if not value:
        return ''
    data = json.loads(value)
    if (not isinstance(data, dict) or set(data) != set(TARGET_KEYS)
            or not all(isinstance(v, str) and len(v) <= 500
                       and not any(c in v for c in '\r\n\0') for v in data.values())
            or not data['application.name'] or not data['application.process.binary']):
        raise ValueError('Invalid audio application')
    return json.dumps(data, sort_keys=True, ensure_ascii=False)


@dataclass(frozen=True)
class Stream:
    index: int
    identity: str
    target: str
    pid: str
    label: str
    volumes: tuple[int, ...]
    muted: bool


class Pactl:
    def __init__(self, runner=subprocess.run):
        self.runner = runner
        self.executable = shutil.which('pactl') or 'pactl'

    def command(self, *args):
        result = self.runner([self.executable, *args], capture_output=True, text=True,
                             timeout=2, check=True, env={**os.environ, 'LC_ALL': 'C'})
        if len(result.stdout) > 4 * 1024 * 1024:
            raise RuntimeError('Audio server response is too large')
        return result.stdout

    def server_identity(self):
        info = json.loads(self.command('--format=json', 'info'))
        # This implementation is deliberately limited to the diagnosed PipeWire
        # backend. Native PulseAudio flat-volume semantics need separate testing.
        if (not isinstance(info, dict) or not str(info.get('server_name', '')).startswith('PulseAudio (on PipeWire ')
                or info.get('is_local') != 'yes' or not info.get('cookie')):
            raise RuntimeError('Audio balance requires a local PipeWire PulseAudio server')
        return (info['cookie'], info.get('host_name', ''), info.get('user_name', ''))

    def streams(self):
        server = self.server_identity()
        data = json.loads(self.command('--format=json', 'list', 'sink-inputs'))
        if self.server_identity() != server:
            raise RuntimeError('Audio server restarted while reading streams')
        if not isinstance(data, list):
            raise ValueError('Invalid audio server response')
        result = []
        for item in data:
            props = item.get('properties', {})
            name = props.get('application.name', '')
            binary = props.get('application.process.binary', '')
            pid = str(props.get('application.process.id', ''))
            # Never offer our output as a target. Missing identity is not guessed.
            if (not name or not binary or not pid.isdigit() or pid == str(os.getpid())
                    or 'narratorverse' in (name + ' ' + binary).casefold()
                    or props.get('application.id') == 'io.github.DevVoidPL.NarratorVerse'):
                continue
            target = validate_target(json.dumps({key: props.get(key, '') for key in TARGET_KEYS}))
            volume = item.get('volume', {})
            values = tuple(channel['value'] for channel in volume.values())
            if (not values or len(values) > 32
                    or any(type(v) is not int or not 0 <= v <= 65536 * 4 for v in values)):
                continue
            index = item['index']
            if type(index) is not int or index < 0:
                continue
            serial = props.get('object.serial')
            if serial is None:
                # PipeWire exposes a stable serial. Without it do not write to
                # potentially recycled indices after a server reconnection.
                continue
            identity = json.dumps([server, index, str(serial), str(item.get('client')), pid,
                                   props.get('application.process.machine_id', ''),
                                   list(volume), target])
            result.append(Stream(index, identity, target, pid, f'{name} · {binary}',
                                 values, bool(item.get('mute'))))
        return result

    def set_volume(self, stream, values):
        current = next((item for item in self.streams() if item.identity == stream.identity), None)
        if current is None:
            raise RuntimeError('Audio stream disappeared before volume update')
        if current.volumes != stream.volumes:
            raise RuntimeError('Audio volume changed externally; control released')
        # Raw per-channel values preserve stereo balance. PulseAudio's raw
        # volume is cubic: the engine converts linear gain before reaching here.
        self.command('set-sink-input-volume', str(stream.index), *(str(v) for v in values))


def list_targets():
    streams = Pactl().streams()
    groups = {}
    for stream in streams:
        group = groups.setdefault(stream.target, {'target': stream.target, 'label': stream.label,
                                                  'processes': set()})
        group['processes'].add(stream.pid)
    return [{'target': item['target'], 'label': item['label'],
             'ambiguous': len(item['processes']) != 1} for item in groups.values()]


def normalize_speech(pcm):
    """Bounded s16le phrase gain, not a LUFS meter or game-signal analysis."""
    if (pcm.sample_format.casefold() != 's16le' or len(pcm.samples) % 2
            or not pcm.samples or len(pcm.samples) > 1024 * 1024):
        return pcm
    samples = array('h')
    samples.frombytes(pcm.samples)
    if sys.byteorder != 'little':
        samples.byteswap()
    peak = max(abs(value) for value in samples)
    # Ignore padding for the RMS estimate, but never turn near-silence into speech.
    active = [value for value in samples if abs(value) >= 32768 * .003]
    if not active or peak < 32768 * .01:
        return pcm
    rms = math.sqrt(sum(value * value for value in active) / len(active)) / 32768
    gain = min(2.0, int(.89 * 32768) / peak, max(.5, .125 / rms))
    if abs(gain - 1) < .01:
        return pcm
    adjusted = array('h', (max(-32768, min(32767, round(value * gain))) for value in samples))
    if sys.byteorder != 'little':
        adjusted.byteswap()
    return replace(pcm, samples=adjusted.tobytes())


class BalanceEngine:
    """Single-owner, time-based envelope with injectable mixer and journal.

    User mixer edits win: stop writing that stream until the next configuration.
    A disappearance is not permission to raise another stream with a reused ID.
    """
    def __init__(self, mixer, save=lambda entries: None):
        self.mixer, self.save = mixer, save
        self.entries = {}
        self.known = set()
        self.target = ''
        self.db = -12.0
        self.factor = 1.0
        self.until = 0.0
        self.previous = None
        self.yielded = set()
        self.source_lost = False
        self.state = 'off'

    @staticmethod
    def matches(values, expected):
        return len(values) == len(expected) and all(abs(a - b) <= 2 for a, b in zip(values, expected))

    def restore(self, streams):
        visible = {stream.identity: stream for stream in streams}
        for key, entry in list(self.entries.items()):
            stream = visible.get(key)
            if stream is not None and (self.matches(stream.volumes, entry['last'])
                                       or self.matches(stream.volumes, entry.get('before', entry['last']))):
                self.mixer.set_volume(stream, entry['base'])
            del self.entries[key]
            self.save(self.entries)
        self.factor = 1.0
        self.until = 0.0

    def configure(self, target, db, streams):
        self.restore(streams)
        self.target, self.db = target, db
        self.yielded.clear()
        self.source_lost = False
        self.until = 0
        self.previous = None
        self.known = {stream.identity for stream in streams if stream.target == target}

    def step(self, streams, *, active, now):
        elapsed = min(.2, max(0, now - self.previous)) if self.previous is not None else .05
        self.previous = now
        selected = [stream for stream in streams if stream.target == self.target]
        if not self.target:
            self.state = 'off'
            return
        visible = {stream.identity for stream in streams}
        selected_ids = {stream.identity for stream in selected}
        if self.entries and (set(self.entries) - visible or selected_ids - self.known):
            # A replacement may inherit a persisted ducked volume. We cannot
            # safely raise an unidentified new stream, nor duck it a second time.
            self.source_lost = True
        if self.source_lost:
            self.restore(streams)
            self.state = 'changed'
            return
        if len({stream.pid for stream in selected}) > 1:
            self.restore(streams)
            self.state = 'ambiguous'
            return
        self.known = selected_ids
        if active:
            self.until = now + .45
        held = active or now < self.until
        goal = 10 ** (self.db / 20) if held else 1.0
        speed = (1 - 10 ** (self.db / 20)) / (.12 if held else .85)
        self.factor += max(-speed * elapsed, min(speed * elapsed, goal - self.factor))
        self.state = ('ducking' if held else 'restoring') if self.factor < .99999 else 'ready'
        if not selected:
            self.state = 'missing'
        for stream in selected:
            if stream.identity in self.yielded:
                self.state = 'manual'
                continue
            entry = self.entries.get(stream.identity)
            if entry and not self.matches(stream.volumes, entry['last']):
                self.yielded.add(stream.identity)
                del self.entries[stream.identity]
                self.save(self.entries)
                self.state = 'manual'
                continue
            if entry is None and (stream.muted or not any(stream.volumes)):
                continue
            if entry is None:
                if self.factor >= .99999:
                    continue
                entry = {'base': list(stream.volumes), 'last': list(stream.volumes)}
                self.entries[stream.identity] = entry
            # Raw PA volume is the cube root of linear amplitude.
            values = tuple(round(v * self.factor ** (1 / 3)) for v in entry['base'])
            if (stream.volumes != values if self.factor >= .99999
                    else not self.matches(stream.volumes, values)):
                # Journal BEFORE the command: a backend crash cannot erase the
                # original baseline. Keep both sides of an in-flight write.
                entry['before'] = entry['last']
                entry['last'] = list(values)
                self.save(self.entries)
                self.mixer.set_volume(stream, values)
            if self.factor >= .99999:
                del self.entries[stream.identity]
                self.save(self.entries)


class AudioBalance:
    """Non-blocking backend adapter; a separate process owns mixer restoration."""
    def __init__(self, state_directory):
        self.directory = str(state_directory)
        journal = Path(state_directory) / 'audio-balance-recovery.json'
        self.recovery_pending = journal.exists() and journal.stat().st_size > 2
        self.lock = Lock()
        self.process = None
        self.settings = {'enabled': False, 'target': '', 'db': -12.0}
        self.playing = set()
        self.epoch = 0
        self.status = {'state': 'off', 'error': ''}
        self.closed = False

    def configure(self, settings):
        if self.process is not None and self.process.poll() is not None:
            self.process.stdin.close()
            self.process.stdout.close()
            self.process = None
        with self.lock:
            self.settings = {'enabled': settings.audio_balance_enabled,
                             'target': settings.audio_balance_target,
                             'db': settings.audio_balance_db}

    def started(self, epoch, request_id):
        with self.lock:
            if epoch == self.epoch and not self.closed:
                self.playing.add(request_id)

    def finished(self, epoch, request_id):
        with self.lock:
            if epoch == self.epoch:
                self.playing.discard(request_id)

    def reset(self):
        with self.lock:
            self.epoch += 1
            self.playing.clear()

    def snapshot(self):
        with self.lock:
            return dict(self.status)

    def _read(self, process):
        try:
            for line in process.stdout:
                result = json.loads(line)
                with self.lock:
                    if self.process is process:
                        self.status = result
        except (OSError, ValueError):
            pass

    def tick(self, reading):
        with self.lock:
            options = dict(self.settings)
            active = bool(self.playing) and reading
            epoch = self.epoch
        if self.closed:
            return
        if self.process is not None and self.process.poll() is not None:
            with self.lock:
                self.status = {'state': 'error', 'error': 'Audio balance worker stopped; pause and resume reading to retry.'}
            if options['enabled']:
                return
            self.process = None
        if self.process is None:
            if (not options['enabled'] or not options['target'] or not reading) and not self.recovery_pending:
                with self.lock:
                    self.status = {'state': 'choose' if options['enabled'] else 'off', 'error': ''}
                return
            try:
                self.process = subprocess.Popen(
                    [sys.executable, '-m', 'narratorverse.audio_balance_worker', self.directory],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
                os.set_blocking(self.process.stdin.fileno(), False)
                self.recovery_pending = False
                Thread(target=self._read, args=(self.process,), daemon=True,
                       name='narratorverse-audio-status').start()
            except OSError as error:
                with self.lock:
                    self.status = {'state': 'error', 'error': str(error)}
                return
        try:
            payload = (json.dumps({**options, 'active': active, 'reading': bool(reading), 'epoch': epoch},
                                  ensure_ascii=False) + '\n').encode()
            # Each bounded message fits PIPE_BUF. Never block Qt on a stalled
            # worker or another instance holding the recovery lock.
            if len(payload) > 4096:
                raise ValueError('Audio balance command too large')
            if os.write(self.process.stdin.fileno(), payload) != len(payload):
                raise OSError('Incomplete audio balance command')
        except (OSError, ValueError):
            with self.lock:
                self.status = {'state': 'error', 'error': 'Audio balance connection lost'}

    def close(self):
        self.reset()
        self.closed = True
        if self.process is not None:
            try:
                self.process.stdin.close()
                # Do not kill the independent restorer if the server is slow.
                self.process.wait(timeout=3)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass