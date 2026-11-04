"""Every terminal path releases P0 lifetime protection, without changing FIFO."""
import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtMultimedia import QtAudio

from test_narrator_p0_repetition import rig, A, B
from test_narrator_playback_diagnostics import _FakeSink, _Device, _playback
from game_optimization_linux.services.narrator_audio import QtNarratorAudioOutput


@pytest.mark.parametrize('failure', ['null_device', 'factory', 'start'])
def test_start_failure_notifies_terminal_once_and_recovers(failure):
    terminals, errors = [], []
    class Device(_Device):
        def isNull(self):
            return failure == 'null_device'
    class Sink(_FakeSink):
        def start(self, buffer):
            if failure == 'start':
                raise RuntimeError('injected start failure')
    def factory(*args):
        if failure == 'factory':
            raise RuntimeError('injected factory failure')
        return Sink(*args)
    output = QtNarratorAudioOutput(sink_factory=factory, device_provider=Device)
    item = _playback(1, A)
    item.terminal_callback = lambda: terminals.append(1)
    item.error_callback = errors.append
    output._queue_playback(item)
    assert len(errors) == 1
    assert terminals == [1]
    assert output._current is None
    assert output._sink is None and output._buffer is None
    output._device_provider = lambda: _Device()
    output._sink_factory = _FakeSink
    output._queue_playback(_playback(2, B))
    assert output._current.request_id == 2
    output._stop_all()
    assert terminals == [1]


@pytest.mark.parametrize('terminal', ['complete', 'underrun', 'device_error', 'stop', 'pause', 'shutdown'])
def test_pipeline_releases_playing_and_waiting_on_terminal(tmp_path, terminal):
    p, ex, _, _, audio, _, _, sinks, frame, drain = rig(tmp_path)
    try:
        frame(A, 0)
        frame(A, .2)
        frame(B, .4)
        frame(B, .6)
        drain()
        assert len(p._deduplicator._playing) == len(p._deduplicator._reserved) == 1
        if terminal == 'complete':
            sinks[0].finish(1)
            sinks[1].finish(1)
        elif terminal in ('underrun', 'device_error'):
            if terminal == 'device_error':
                sinks[0].error = lambda: QtAudio.Error.IOError
            sinks[0].finish(0)
            sinks[1].finish(1)
        elif terminal == 'stop':
            p.stop()
        elif terminal == 'pause':
            from narratorverse.pipeline import StandalonePipeline
            from game_optimization_linux.services.narrator_pipeline import SubtitleRegionStabilizer
            p.__class__ = StandalonePipeline
            p._stabilizer = SubtitleRegionStabilizer()
            p.pause_processing()
        else:
            p.shutdown()
        QCoreApplication.processEvents()
        assert not p._deduplicator._playing
        assert not p._deduplicator._reserved
        assert audio.queue_depth == 0
    finally:
        if terminal != 'shutdown':
            p.shutdown()


def test_failed_waiter_does_not_strand_later_fifo_items():
    terminals = []
    calls = []
    def factory(*args):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError('second device creation fails')
        return _FakeSink(*args)
    output = QtNarratorAudioOutput(sink_factory=factory, device_provider=lambda: _Device())
    for request in range(1, 4):
        item = _playback(request, str(request), seconds=1)
        item.terminal_callback = lambda request=request: terminals.append(request)
        output._queue_playback(item)
    output._sink.finish(1)
    assert terminals == [1, 2]
    assert output._current.request_id == 3
    output._sink.finish(1)
    assert terminals == [1, 2, 3]
    assert output.queue_depth == 0


def test_concurrent_delivery_consumes_future_once(tmp_path):
    from concurrent.futures import Future, ThreadPoolExecutor
    from threading import Barrier
    p, *_ = rig(tmp_path)
    future = Future()
    future.set_result(None)
    barrier = Barrier(8)
    def consume(_):
        barrier.wait(timeout=10)
        return p._consume_completion(future, 'tts', 1)
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            assert sum(pool.map(consume, range(8))) == 1
    finally:
        p.shutdown()


def test_terminal_observer_runs_even_if_error_observer_raises():
    terminals = []
    output = QtNarratorAudioOutput()
    item = _playback(1, A)
    item.terminal_callback = lambda: terminals.append(1)
    def fail(_):
        raise RuntimeError('observer failed')
    item.error_callback = fail
    output._notify_failure(item, 'device error')
    assert terminals == [1]