"""Opt-in experiments: unchanged defaults, Beta timer, correlated local traces."""
import json

import pytest

from game_optimization_linux.services.narrator_pipeline import PhraseDeduplicator
from narratorverse.experiments import DialogueTrace


def test_trace_rejects_relative_path():
    with pytest.raises(ValueError, match="absolute"):
        DialogueTrace("relative.jsonl")


def test_default_dedup_retains_recent_speech_across_distinct_dialogue():
    dedup = PhraseDeduplicator()
    assert dedup.accept('Siema!', now=10, cooldown_seconds=4.5)
    dedup.mark_spoken('Siema!', now=10)
    assert dedup.accept('Ruszamy do banku.', now=11, cooldown_seconds=4.5)
    assert dedup.accept('Siema!', now=12, cooldown_seconds=4.5) is None
    assert dedup.accept('Siema!', now=14.5, cooldown_seconds=4.5)


def test_beta_timer_starts_at_playback_not_acceptance_and_expires_at_boundary():
    dedup = PhraseDeduplicator()
    assert dedup.accept('Siema!', now=1, cooldown_seconds=4.5)
    assert dedup.accept('Ruszamy do banku.', now=2, cooldown_seconds=4.5)
    # Not spoken yet: the original mechanism did not reserve pending text.
    assert dedup.accept('Siema!', now=3, cooldown_seconds=4.5)
    dedup.mark_spoken('Siema!', now=10)
    assert dedup.accept('Idziemy inną drogą.', now=11, cooldown_seconds=4.5)
    assert dedup.accept('Siema!', now=14.499, cooldown_seconds=4.5) is None
    assert dedup.last_rejection_reason == 'cooldown_exact'
    assert dedup.accept('Siema!', now=14.5, cooldown_seconds=4.5)


def test_beta_disappearance_does_not_erase_spoken_history():
    dedup = PhraseDeduplicator()
    assert dedup.accept('Siema!', now=10, cooldown_seconds=4.5)
    dedup.mark_spoken('Siema!', now=10)
    for now in (11, 12, 13):
        dedup.accept('', now=now, cooldown_seconds=4.5, frame_had_text=False)
    assert dedup.accept('Siema!', now=14, cooldown_seconds=4.5) is None
    assert dedup.last_rejection_reason == 'cooldown_exact'
    assert dedup.accept('Siema!', now=15, cooldown_seconds=4.5)


def test_beta_blocks_variant_and_contained_fragment():
    for candidate, expected in [('Musimy rusza ć', 'cooldown_variant'),
                                ('teraz do starego banku', 'cooldown_fragment')]:
        dedup = PhraseDeduplicator()
        dedup.mark_spoken('Musimy ruszać.' if expected.endswith('variant')
                          else 'Jedziemy teraz do starego banku.', now=10)
        assert dedup.accept(candidate, now=11, cooldown_seconds=4.5) is None
        assert dedup.last_rejection_reason == expected


def test_trace_is_private_jsonl_with_text_hash_and_clock(tmp_path):
    path = tmp_path / 'run.jsonl'
    trace = DialogueTrace(path, run_id='gta-A', clock=lambda: 12.5)
    trace.emit('ocr', session_id='s', generation=2, phrase_id=7,
               raw_text='Długi tekst\nz polskimi znakami: ąę')
    trace.close()
    event = json.loads(path.read_text().splitlines()[0])
    assert event['monotonic'] == 12.5
    assert event['run_id'] == 'gta-A'
    assert event['phrase_id'] == 7
    import hashlib
    assert event['raw_text_sha256'] == hashlib.sha256(
        'Długi tekst\nz polskimi znakami: ąę'.encode()).hexdigest()
    assert 'raw_text' not in event
    assert path.stat().st_mode & 0o777 == 0o600
    # Do not overwrite, mix runs or follow a symlink by accident.
    with pytest.raises(FileExistsError):
        DialogueTrace(path)


def test_pipeline_trace_covers_tts_provider_input_and_latencies(tmp_path):
    from test_narrator_foundation import _pipeline, _ManualExecutor, _settings, _confirm_phrase
    executor = _ManualExecutor()
    pipeline, _, _, _, _, tts, audio = _pipeline(tmp_path, executor)
    events = []
    pipeline._diagnostic = lambda event, **fields: events.append({'event': event, **fields})
    pipeline._clock = lambda: 20.0
    snapshot = pipeline.start(_settings())
    _confirm_phrase(pipeline, executor, session_id=snapshot.session_id,
                    generation=snapshot.generation, value=1, timestamp=19.0)
    executor.run_next()  # local translation
    executor.run_next()  # actual TTS submission, audio start
    audio.completed_callbacks[0]()
    by_name = {e['event']: e for e in events}
    for name in ('ocr_decision', 'dialogue_started', 'translation_input',
                 'translation_output', 'tts_provider_input', 'playback_started', 'playback_completed'):
        assert name in by_name
    assert by_name['tts_provider_input']['text'] == tts.values[0]
    assert by_name['playback_started']['accepted_to_speech_ms'] == pytest.approx(0)
    assert by_name['playback_started']['recognized_to_speech_ms'] >= 0
    assert by_name['playback_started']['audio_queue_wait_ms'] == 2.5
    ids = {by_name[name]['phrase_id'] for name in ('dialogue_started', 'translation_input',
           'translation_output', 'tts_provider_input', 'playback_started', 'playback_completed')}
    assert len(ids) == 1
    pipeline.shutdown()


def test_tts_trace_retains_submission_context_after_session_change(tmp_path):
    from test_narrator_foundation import _pipeline, _ManualExecutor
    pipeline, _, _, _, _, _, _ = _pipeline(tmp_path, _ManualExecutor())
    events = []
    pipeline._diagnostic = lambda event, **fields: events.append(dict(event=event, **fields))
    pipeline._session_id, pipeline._generation = 'new', 9
    pipeline._synthesize_timed('Idź!', 'voice-pl', 1.0,
                               session_id='old', phrase_id=7, generation=3)
    event = next(e for e in events if e['event'] == 'tts_provider_input')
    assert (event['session_id'], event['generation'], event['phrase_id']) == ('old', 3, 7)
    assert all(event['session_id'] == 'old' and event['generation'] == 3 for event in events)
    pipeline.shutdown()


def test_recognition_acceptance_and_capture_latencies_are_distinct(tmp_path):
    from game_optimization_linux.services.narrator_pipeline import _AcceptedSubtitleTiming
    from test_narrator_foundation import _pipeline, _ManualExecutor, _settings
    pipeline, _, _, _, _, _, _ = _pipeline(tmp_path, _ManualExecutor())
    pipeline._clock = lambda: 20.0
    snapshot = pipeline.start(_settings())
    events = []
    pipeline._diagnostic = lambda event, **fields: events.append(dict(event=event, **fields))
    timing = _AcceptedSubtitleTiming(4.0, 5.0, 12.0, 0, 0, 0, 0, 0, recognized_at=10.0)
    pipeline._audio_started(2.5, source_text='Hello!', translated='Cześć!',
                            translation_bypassed=False, timing=timing,
                            generation=snapshot.generation, request_id=1, model='warm')
    event = next(e for e in events if e['event'] == 'playback_started')
    assert event['accepted_to_speech_ms'] == 8000
    assert event['recognized_to_speech_ms'] == 10000
    assert event['frame_to_speech_ms'] == 15000
    pipeline.shutdown()


def test_trace_close_drains_concurrent_producers_without_records_after_footer(tmp_path):
    from threading import Thread
    path = tmp_path / 'concurrent.jsonl'
    trace = DialogueTrace(path)
    producers = [Thread(target=lambda: [trace.emit('ocr', index=i) for i in range(1000)])
                 for _ in range(4)]
    for producer in producers: producer.start()
    trace.close()
    for producer in producers: producer.join(timeout=2)
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert records[-1]['event'] == 'trace_closed'
    assert sum(record['event'] == 'trace_closed' for record in records) == 1
    assert not trace._thread.is_alive()


@pytest.mark.parametrize('bypass', [False, True])
def test_translation_trace_distinguishes_cache_hit_and_full_bypass(tmp_path, bypass):
    from game_optimization_linux.services.narrator_pipeline import _AcceptedSubtitleTiming
    from test_narrator_foundation import _pipeline, _ManualExecutor, _settings
    executor = _ManualExecutor()
    pipeline, _, _, _, translator, _, _ = _pipeline(tmp_path, executor)
    pipeline._bypass_translation_cache = bypass
    pipeline.cache.put('Go!', 'Z pamięci.', provider_id=translator.provider_id, profile_id='small')
    if bypass:
        def forbidden(*args, **kwargs):
            pytest.fail('Cache bypass must skip reads and writes')
        pipeline.cache.get = forbidden
        pipeline.cache.put = forbidden
    events = []
    pipeline._diagnostic = lambda event, **fields: events.append(dict(event=event, **fields))
    pipeline.start(_settings())
    timing = _AcceptedSubtitleTiming(1, 1, 1, 0, 0, 0, 0, 0)
    try:
        pipeline._narrate_phrase('Go!', timing, 1)
        if bypass:
            executor.run_next()  # translation, not a cache hit
        executor.run_next()  # TTS
        result = next(e for e in events if e['event'] == 'translation_output')
        assert result['cached'] is (not bypass)
        assert translator.values == (['Go!'] if bypass else [])
        assert result['text'] == ('polski Go!' if bypass else 'Z pamięci.')
    finally:
        pipeline.shutdown()


def test_polish_mode_traces_bypass_without_invoking_translation(tmp_path):
    from dataclasses import replace
    from game_optimization_linux.models.narrator import NarratorSubtitleLanguageMode
    from game_optimization_linux.services.narrator_pipeline import _AcceptedSubtitleTiming
    from test_narrator_foundation import _pipeline, _ManualExecutor, _settings
    executor = _ManualExecutor()
    pipeline, _, _, _, translator, tts, _ = _pipeline(tmp_path, executor)
    events = []
    pipeline._diagnostic = lambda event, **fields: events.append(dict(event=event, **fields))
    pipeline.start(replace(_settings(), subtitle_language_mode=NarratorSubtitleLanguageMode.POLISH))
    try:
        pipeline._narrate_phrase('Idziemy do domu.', _AcceptedSubtitleTiming(1, 1, 1, 0, 0, 0, 0, 0), 1)
        executor.run_next()
        assert translator.values == []
        assert tts.values == ['Idziemy do domu.']
        assert any(e['event'] == 'translation_bypassed' for e in events)
        assert not any(e['event'] in ('translation_input', 'translation_output') for e in events)
    finally:
        pipeline.shutdown()


def test_trace_writer_is_bounded_and_reports_dropped_events(tmp_path):
    path = tmp_path / 'bounded.jsonl'
    trace = DialogueTrace(path)
    trace.close()
    footer = json.loads(path.read_text().splitlines()[-1])
    assert footer['event'] == 'trace_closed'
    assert footer['dropped_events'] == 0
    assert trace._queue.maxsize == 4096


def test_audio_trace_captures_context_before_session_changes():
    from test_narrator_playback_completion import _FakeSink, _Device, _audio
    from game_optimization_linux.services.narrator_audio import QtNarratorAudioOutput, _Playback
    events = []
    context = {'session_id': 'old', 'generation': 1}
    output = QtNarratorAudioOutput(sink_factory=_FakeSink, device_provider=_Device,
                                  clock=lambda: 5.0,
                                  diagnostic=lambda event, **fields: events.append(dict(event=event, **fields)),
                                  diagnostic_context=lambda: dict(context))
    playback = _Playback(audio=_audio(1), volume=1, request_id=9,
                         started_callback=lambda _: None, completed_callback=lambda: None,
                         error_callback=lambda _: None, queued_at=4.0,
                         diagnostic_context=dict(context))
    context['session_id'] = 'new'
    output._queue_playback(playback)
    output._sink.finish(0.5)
    started = next(e for e in events if e['event'] == 'sink_started')
    terminal = next(e for e in events if e['event'] == 'sink_terminal')
    assert started['session_id'] == terminal['session_id'] == 'old'
    assert started['audio_queue_wait_ms'] == 1000
    assert terminal['result'] == 'interrupted'
    assert terminal['processed_ms'] == pytest.approx(500)
    assert terminal['expected_ms'] == pytest.approx(1000)