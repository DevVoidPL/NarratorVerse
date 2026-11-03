"""Deterministic adapter lifecycle checks; not portal or device evidence."""
import io
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

from narratorverse.main import Backend, CaptureGate, AudioGate
from narratorverse.pipeline import StandalonePipeline
from narratorverse.protocol import Writer
from game_optimization_linux.models.narrator import NormalizedRect, OcrResult
from test_narrator_foundation import _pipeline, _ManualExecutor, _settings, _frame


def make_pipeline(tmp_path):
    executor = _ManualExecutor()
    pipeline, capture, activity, ocr, translator, tts, audio = _pipeline(tmp_path, executor)
    pipeline.__class__ = StandalonePipeline
    pipeline.start(_settings())
    return pipeline, executor


def test_capture_ignores_old_session_callbacks():
    provider = Mock()
    gate = CaptureGate(provider)
    frames, states = [], []
    gate.start(None, frame_callback=frames.append, state_callback=lambda *s: states.append(s))
    first = provider.start.call_args.kwargs
    gate.stop()
    gate.start(None, frame_callback=frames.append, state_callback=lambda *s: states.append(s))
    gate.reading = True
    first['frame_callback']('stale')
    first['state_callback']('error', 'old')
    assert gate.frame is None
    assert not frames and not states
    provider.start.call_args.kwargs['frame_callback']('current')
    assert frames == ['current']
    gate.stop()
    assert gate.frame is None and not gate.reading


def test_paused_audio_is_not_counted_as_completed():
    audio, completed = Mock(), Mock()
    gate = AudioGate(audio, SimpleNamespace(reading=False))
    gate.play(None, completed_callback=completed)
    audio.play.assert_not_called()
    completed.assert_not_called()


def test_pause_invalidates_running_ocr_but_keeps_portal(tmp_path):
    pipeline, executor = make_pipeline(tmp_path)
    pipeline._start_ocr(_frame(session_id=pipeline._session_id, generation=pipeline._generation, value=1))
    old = pipeline._ocr_future
    old.set_running_or_notify_cancel()
    capture_generation = pipeline._generation
    stops = pipeline.capture.stop_calls
    pipeline.pause_processing()
    old.set_result(OcrResult('Old subtitle must not be spoken', .99))
    assert pipeline.active
    assert pipeline._generation == capture_generation
    assert pipeline.capture.stop_calls == stops
    assert not pipeline._request_active
    assert not pipeline.snapshot.last_detected_text
    pipeline._start_ocr(_frame(session_id=pipeline._session_id, generation=pipeline._generation, value=2))
    current = pipeline._ocr_future
    assert current is not old
    current.set_result(OcrResult('New subtitle', .99))
    assert pipeline.snapshot.ocr_decision_history[-1].raw_text == 'New subtitle'
    assert all(x.raw_text != 'Old subtitle must not be spoken' for x in pipeline.snapshot.ocr_decision_history)
    pipeline.stop()


def test_pause_invalidates_downstream_and_region_state(tmp_path):
    pipeline, executor = make_pipeline(tmp_path)
    old_work = pipeline._work_id
    pipeline._pending_frame = object()
    pipeline._roi_diagnostic = {'old': True}
    pipeline.pause_processing()
    assert pipeline._work_id != old_work
    assert pipeline._pending_frame is None and pipeline._roi_diagnostic is None
    pipeline.stop()


def test_stale_voice_completion_does_not_play():
    writer = Writer(io.StringIO())
    backend = SimpleNamespace(closed=False, voice_generation=2, preview_generation=3, writer=writer, audio=Mock())
    Backend.finish_job(backend, {'id': 7, 'after': 'voice', 'generation': 1, 'result': object()})
    backend.audio.audio.play.assert_not_called()
    assert 'Operacja anulowana' in writer.stream.getvalue()


def test_stale_preview_does_not_open_editor():
    backend = SimpleNamespace(closed=False, voice_generation=2, preview_generation=3, writer=Mock(), emit=Mock())
    Backend.finish_job(backend, {'id': None, 'after': 'preview', 'generation': 1, 'result': {'imageUrl': 'stale'}})
    backend.emit.assert_not_called()