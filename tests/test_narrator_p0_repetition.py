"""P0: repeat delivery must not multiply work; preserve real FIFO/sink code."""
from dataclasses import replace
import time

import pytest

from PySide6.QtCore import QCoreApplication

from game_optimization_linux.models.narrator import OcrResult
from game_optimization_linux.services.narrator_audio import QtNarratorAudioOutput
from game_optimization_linux.services.narrator_pipeline import subtitle_identity
from test_narrator_foundation import _pipeline, _ManualExecutor, _settings, _frame, _AlwaysStable
from test_narrator_playback_diagnostics import _Device, _FakeSink


A = 'We need to find a safe place before nightfall.'
B = 'Do not open the door. Wait for me!'


def rig(tmp_path, *, real_time=False):
    executor = _ManualExecutor()
    pipeline, capture, _, ocr, translator, tts, _ = _pipeline(tmp_path, executor)
    base = time.monotonic() if real_time else 100.0
    now, events, sinks = [base], [], []
    pipeline._clock = lambda: now[0]
    pipeline._diagnostic = lambda event, **fields: events.append(dict(event=event, **fields))

    def factory(*args):
        sink = _FakeSink(*args)
        sinks.append(sink)
        return sink

    audio = QtNarratorAudioOutput(sink_factory=factory, device_provider=lambda: _Device(),
                                 clock=lambda: now[0], diagnostic=pipeline._diagnostic,
                                 diagnostic_context=pipeline.diagnostic_context)
    pipeline.audio = audio
    pipeline._tts_executor = executor
    pipeline.start(replace(_settings(), capture_sampling_hz=10))
    pipeline._stabilizer = _AlwaysStable()

    def frame(text, seconds):
        if real_time:
            time.sleep(max(0, base + seconds - time.monotonic()))
        now[0] = time.monotonic() if real_time else base + seconds
        ocr.recognize = lambda f, **kw: OcrResult(text=text, raw_text=text,
            filtered_text=text, confidence=.99, provider_id=ocr.provider_id)
        before = len(executor.jobs)
        capture.frame_callback(_frame(session_id=pipeline._session_id,
            generation=pipeline._generation, value=int(seconds * 10) % 255,
            timestamp=now[0]))
        if len(executor.jobs) > before:
            executor.run_at(len(executor.jobs) - 1)  # OCR; inference stays queued

    def drain():
        while executor.jobs:
            executor.run_next()
        QCoreApplication.processEvents()

    return pipeline, executor, translator, tts, audio, now, events, sinks, frame, drain


def test_full_pipeline_identical_frames_gap_and_distinct_fifo(tmp_path):
    p, ex, translator, tts, audio, now, events, sinks, frame, drain = rig(tmp_path)
    try:
        for t in (0, .2, .4):
            frame(A, t)
        # Keep inference pending while a different line and the first recur.
        for text, t in [(B, .6), (B, .8), (A, 1), (A, 1.2)]:
            frame(text, t)
        drain()
        assert translator.values == [A, B]
        assert len(tts.values) == 2
        assert len(sinks) == 1  # second audio waits FIFO
        assert subtitle_identity(A) in p._deduplicator._spoken_at
        sinks[0].finish(1)
        assert len(sinks) == 2
        sinks[1].finish(1)
        history = dict(p._deduplicator._spoken_at)
        for text, t in [('', 1.4), ('', 1.6), ('', 1.8), (A, 2), (A, 2.2), (A, 2.4)]:
            frame(text, t)
        drain()
        assert translator.values == [A, B]
        assert len(tts.values) == len(sinks) == audio.completed_count == 2
        assert p._deduplicator._spoken_at == history
        assert not p._deduplicator._reserved
        assert not p._narration_queue
    finally:
        p.shutdown()


def test_duplicate_ocr_completion_is_consumed_once(tmp_path):
    p, ex, _, tts, audio, _, events, sinks, frame, drain = rig(tmp_path)
    try:
        # A duplicate delivery must not count as the second consensus observation.
        p.ocr.recognize = lambda f, **kw: OcrResult(text=A, confidence=.99, provider_id='test-ocr')
        p._clock = lambda: 100.2
        p.submit_frame(_frame(session_id=p._session_id, generation=p._generation,
                              value=2, timestamp=100.2))
        future = ex.jobs[-1][0]
        callbacks = list(future._done_callbacks)
        ex.run_next()
        for callback in callbacks:
            callback(future)
        drain()
        assert len(tts.values) == len(sinks) == 0
        frame(A, .4)
        drain()
        assert len(tts.values) == len(sinks) == 1
        assert any(e['event'] == 'ocr_completion_ignored' for e in events)
    finally:
        p.shutdown()


def test_duplicate_translation_completion_cannot_submit_tts_twice(tmp_path):
    p, ex, translator, tts, audio, _, events, sinks, frame, drain = rig(tmp_path)
    try:
        frame(A, 0)
        frame(A, .2)
        translation = ex.jobs[0][0]
        translation_callbacks = list(translation._done_callbacks)
        ex.run_next()
        for callback in translation_callbacks:
            callback(translation)
        assert len(ex.jobs) == 1, 'one translation result submitted TTS twice'
        drain()
        assert len(translator.values) == len(tts.values) == len(sinks) == 1
    finally:
        p.shutdown()


def test_duplicate_tts_completion_cannot_replay_audio(tmp_path):
    p, ex, translator, tts, audio, _, events, sinks, frame, drain = rig(tmp_path)
    try:
        frame(A, 0)
        frame(A, .2)
        ex.run_next()
        synthesis = ex.jobs[0][0]
        synthesis_callbacks = list(synthesis._done_callbacks)
        ex.run_next()
        for callback in synthesis_callbacks:
            callback(synthesis)
        QCoreApplication.processEvents()
        assert len(translator.values) == len(tts.values) == len(sinks) == 1
        assert audio.queue_depth == 1, 'same generated PCM was enqueued twice'
        sinks[0].finish(1)
        assert audio.completed_count == 1
        assert len(sinks) == 1
    finally:
        p.shutdown()


def test_diagnostic_file_hashes_dialogue_but_keeps_correlation(tmp_path):
    import hashlib
    import json
    from narratorverse.experiments import DialogueTrace
    path = tmp_path / 'trace.jsonl'
    trace = DialogueTrace(path, clock=lambda: 12.5)
    trace.emit('ocr_decision', phrase_id=7, raw_text=A, accepted_text=A,
               message='backend echoed ' + A)
    trace.close()
    line = path.read_text()
    event = json.loads(line.splitlines()[0])
    assert A not in line
    assert 'raw_text' not in event and 'message' not in event
    assert event['raw_text_sha256'] == hashlib.sha256(A.encode()).hexdigest()
    assert event['raw_text_sha256'] == event['accepted_text_sha256']
    assert event['phrase_id'] == 7 and event['monotonic'] == 12.5


@pytest.mark.parametrize('real_time', [False, True])
def test_spoken_history_must_not_expire_protection_during_active_pcm(tmp_path, real_time):
    """OCR every 200 ms, short disappearance, long playing PCM: no replay.

    A 4.5s history measured from start cannot protect a 6s utterance alone.
    The still-playing request must retain its reservation until terminal.
    """
    p, ex, translator, tts, audio, now, events, sinks, frame, drain = rig(tmp_path, real_time=real_time)
    from game_optimization_linux.models.narrator import PcmAudio
    from narratorverse.experiments import DialogueTrace
    import json
    trace = DialogueTrace(tmp_path / 'controlled-trace.jsonl', clock=lambda: now[0])

    def diagnostic(event, **fields):
        events.append(dict(event=event, **fields))
        trace.emit(event, **fields)

    p._diagnostic = audio._diagnostic = diagnostic
    base = now[0]
    calls = []

    def synthesize(text, **kwargs):
        calls.append(text)
        return PcmAudio(samples=b'\x00\x01' * (22050 * 6), sample_rate=22050, channels=1)

    tts.synthesize = synthesize
    try:
        frame(A, 0)
        frame(A, .2)
        drain()
        # Same text repeatedly observed with <3 s between observations.
        for text, t in [(A, 1), ('', 1.2), ('', 1.4), ('', 1.6),
                        (A, 2), (A, 2.2), (A, 3), (A, 4), (A, 4.8), (A, 5)]:
            frame(text, t)
        drain()
        assert len(calls) == 1, 'active audio lost its pending protection at audio start'
        if real_time:
            time.sleep(max(0, base + 6.3 - time.monotonic()))
        now[0] = time.monotonic() if real_time else base + 6.3
        sinks[0].finish(6)
        assert len(sinks) == audio.completed_count == 1
        assert not p._deduplicator._reserved
        assert not p._deduplicator._playing
        names = [e['event'] for e in events]
        for stage in ('phrase_reserved', 'fifo_dequeued', 'tts_provider_input',
                      'audio_submitted', 'sink_submitted', 'sink_started',
                      'playback_started', 'history_written', 'sink_terminal', 'playback_completed'):
            assert names.count(stage) == 1, stage
        (tmp_path / 'controlled-report.json').write_text(json.dumps(dict(
            real_time=real_time, duration_seconds=now[0] - base,
            tts_tasks=len(calls), sink_starts=len(sinks), completed=audio.completed_count,
            device='injected fake sink; production Qt FIFO and callbacks',
            capture_ocr='injected frames and OCR; real gate/deduplicator/queue',
            event_counts={name: names.count(name) for name in set(names)}), indent=2))
    finally:
        p.shutdown()
        trace.close()