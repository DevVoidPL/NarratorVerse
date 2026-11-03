"""Episode, pending reservation and playback history form one dialogue guard."""
from concurrent.futures import Future

import pytest

from game_optimization_linux.services.narrator_pipeline import PhraseDeduplicator

A = 'Jedziemy teraz do starego banku.'
B = 'Zostań tutaj i pilnuj samochodu.'
C = 'Porozmawiam jutro z twoim bratem.'


def accept(dedup, text, now=1):
    return dedup.accept(text, now=now, cooldown_seconds=4.5)


def test_default_history_blocks_return_until_exact_playback_boundary():
    d = PhraseDeduplicator()
    assert accept(d, A)
    d.mark_spoken(A, now=10)
    assert accept(d, B, 11)
    assert accept(d, A, 14.499) is None
    assert accept(d, A, 14.5) == A


def test_reservation_blocks_pending_return_without_starting_history():
    d = PhraseDeduplicator()
    assert accept(d, A)
    d.reserve(7, A)
    assert accept(d, B, 2)
    assert accept(d, A, 100) is None  # It is still in FIFO, not expired speech.
    assert not d._spoken_at
    d.mark_spoken(A, now=100, request_id=7)
    assert not d._reserved
    assert accept(d, A, 104.499) is None
    assert accept(d, A, 104.5) == A


@pytest.mark.parametrize('candidate', [A, 'teraz do starego banku'])
def test_reservation_blocks_exact_and_safe_fragment(candidate):
    d = PhraseDeduplicator()
    assert accept(d, A)
    d.reserve(1, A)
    assert accept(d, B)
    assert accept(d, candidate) is None


@pytest.mark.parametrize('first,second', [
    ('Oddaj mi 50 dolarów.', 'Oddaj mi 500 dolarów.'),
    ('Musisz teraz otworzyć drzwi.', 'Nie musisz teraz otworzyć drzwi.'),
    ('CJ: Musimy teraz uciekać.', 'Ryder: Musimy teraz uciekać.'),
    (A, B),
])
def test_reservation_keeps_real_dialogue_changes(first, second):
    d = PhraseDeduplicator()
    assert accept(d, first)
    d.reserve(1, first)
    assert accept(d, second) == second


def test_release_failed_current_phrase_allows_retry_not_permanent_episode_lock():
    d = PhraseDeduplicator()
    assert accept(d, A)
    d.reserve(1, A)
    d.release(1)
    assert accept(d, A) == A
    assert not d._spoken_at


def test_release_other_phrase_does_not_clear_current_episode():
    d = PhraseDeduplicator()
    assert accept(d, A)
    d.reserve(1, A)
    assert accept(d, B)
    d.release(1)
    assert accept(d, B) is None


def test_clear_pending_keeps_started_history_but_releases_unsaid_episode():
    d = PhraseDeduplicator()
    d.mark_spoken(A, now=1)
    assert accept(d, B)
    d.reserve(2, B)
    d.clear_pending()
    assert accept(d, B) == B
    assert accept(d, A, 2) is None


def test_new_session_has_no_history_or_reservations(tmp_path):
    from test_narrator_foundation import _pipeline, _ManualExecutor, _settings
    p, *_ = _pipeline(tmp_path, _ManualExecutor())
    p.start(_settings())
    p._deduplicator.mark_spoken(A, now=1)
    p._deduplicator.reserve(99, B)
    p.stop()
    p.start(_settings())
    assert not p._deduplicator._reserved
    assert accept(p._deduplicator, A) == A
    p.shutdown()


def setup_pipeline(tmp_path):
    from test_narrator_foundation import _pipeline, _ManualExecutor, _settings, _AlwaysStable
    ex = _ManualExecutor()
    p, _, _, _, translator, tts, audio = _pipeline(tmp_path, ex)
    p._tts_executor = ex
    p._clock = lambda: 10.0
    p.start(_settings())
    p._stabilizer = _AlwaysStable()
    return p, ex, translator, tts, audio


def observe(p, text, request):
    """Exercise real OCR completion, gate, dedup and FIFO without capture timing."""
    from game_optimization_linux.models.narrator import OcrResult
    future = Future()
    p._request_id = request
    p._request_active = True
    p._text_gate.observe(text, .99, now=9.9)
    future.set_result(OcrResult(text=text, raw_text=text, filtered_text=text,
                               confidence=.99, provider_id='test-ocr'))
    p._ocr_finished(future, generation=p._generation, request_id=request,
                    frame_timestamp=10, stabilization_ms=0, visual_decision='test')


def test_pending_duplicate_preserves_abc_fifo_and_starts_without_timer(tmp_path):
    p, ex, translator, tts, audio = setup_pipeline(tmp_path)
    for i, line in enumerate((A, B, C, B), 1):
        observe(p, line, i)
    assert [item[0] for item in p._narration_queue] == [B, C]
    while ex.jobs:
        ex.run_next()
    assert translator.values == [A, B, C]
    assert len(audio.played) == 3
    assert all(e == 10 for e in p._deduplicator._spoken_at.values())
    assert not p._deduplicator._reserved
    p.shutdown()


def test_text_overflow_keeps_existing_victim_and_releases_reservation(tmp_path):
    from game_optimization_linux.services.narrator_pipeline import NARRATION_QUEUE_LIMIT
    p, ex, translator, _, _ = setup_pipeline(tmp_path)
    lines = [f'Oddaj mi teraz {n} dolarów.' for n in range(NARRATION_QUEUE_LIMIT + 2)]
    for i, line in enumerate(lines, 1):
        observe(p, line, i)
    assert [item[0] for item in p._narration_queue] == lines[2:]
    assert 2 not in p._deduplicator._reserved
    while ex.jobs:
        ex.run_next()
    assert translator.values == [lines[0], *lines[2:]]
    assert not p._deduplicator._reserved
    p.shutdown()


@pytest.mark.parametrize('stage', ['translation', 'tts', 'cancel'])
def test_failed_processing_releases_only_failed_reservation(tmp_path, stage):
    p, ex, translator, tts, _ = setup_pipeline(tmp_path)
    observe(p, A, 1)
    observe(p, B, 2)
    if stage == 'tts':
        ex.run_next()
        tts.synthesize = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('test TTS'))
    elif stage == 'translation':
        ex.jobs[0][0].set_exception(RuntimeError('test translation'))
        ex.jobs.pop(0)
    if stage == 'cancel':
        ex.jobs[0][0].cancel()
    elif stage != 'translation':
        ex.run_next()
    assert 1 not in p._deduplicator._reserved
    assert 2 in p._deduplicator._reserved
    p.shutdown()


def test_audio_waiting_reservation_moves_to_history_only_on_start(tmp_path):
    p, ex, _, _, audio = setup_pipeline(tmp_path)
    audio.auto_start = False
    for i, line in enumerate((A, B), 1):
        observe(p, line, i)
    while ex.jobs:
        ex.run_next()
    assert set(p._deduplicator._reserved) == {1, 2}
    assert not p._deduplicator._spoken_at
    audio.started_callbacks[0](0)
    assert set(p._deduplicator._reserved) == {2}
    audio.error_callbacks[1]('Device unavailable')
    assert not p._deduplicator._reserved
    assert list(p._deduplicator._spoken_at.values()) == [10]
    p.shutdown()


def test_audio_overflow_and_stop_notify_dropped_waiters():
    from test_narrator_playback_diagnostics import _playback, _Device, _FakeSink
    from game_optimization_linux.services.narrator_audio import QtNarratorAudioOutput
    output = QtNarratorAudioOutput(sink_factory=_FakeSink, device_provider=lambda: _Device())
    terminals = []
    for i in range(1, 11):
        item = _playback(i, str(i))
        item.terminal_callback = lambda i=i: terminals.append(i)
        output._queue_playback(item)
    assert terminals == [2]
    assert output._current.request_id == 1
    assert output._pending.request_id == 3
    output._stop_all()
    assert sorted(terminals) == list(range(1, 11))


def test_pause_cancels_without_starting_next_accepted_job(tmp_path):
    from narratorverse.pipeline import StandalonePipeline
    p, ex, translator, _, _ = setup_pipeline(tmp_path)
    p.__class__ = StandalonePipeline
    observe(p, A, 1)
    observe(p, B, 2)
    from game_optimization_linux.services.narrator_pipeline import SubtitleRegionStabilizer
    p._stabilizer = SubtitleRegionStabilizer()
    p.pause_processing()
    assert not p._deduplicator._reserved
    assert not p._narration_queue
    assert not p._narration_busy
    assert p._work_id >= p._audio_request_floor
    while ex.jobs:
        ex.run_next()
    assert translator.values == []
    p.shutdown()


@pytest.mark.parametrize('stage', ['translation', 'tts'])
def test_executor_submission_failure_is_terminal_and_retryable(tmp_path, stage):
    p, ex, _, _, _ = setup_pipeline(tmp_path)
    class Refusing:
        def submit(self, *args, **kwargs):
            raise RuntimeError('Executor shut down')
    if stage == 'translation':
        p._executor = Refusing()
        observe(p, A, 1)
    else:
        observe(p, A, 1)
        p._tts_executor = Refusing()
        ex.run_next()
    assert not p._deduplicator._reserved
    assert not p._narration_busy
    assert accept(p._deduplicator, A) == A
    p.shutdown()


def test_history_spelling_retains_explicit_speaker_boundaries():
    d = PhraseDeduplicator()
    d.mark_spoken('CJ: Musimy teraz uciekać.', now=1)
    assert accept(d, 'Ryder: Musimy teraz uciekać.', 2)