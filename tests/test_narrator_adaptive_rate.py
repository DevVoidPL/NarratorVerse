"""Deterministic rate policy and live-pipeline wiring, not an audio quality test."""
from concurrent.futures import Future
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from game_optimization_linux.models.narrator import NarratorGameSettings, NarratorSubtitleLanguageMode, PcmAudio, TranslationResult
from game_optimization_linux.services.narrator_adaptive_rate import AdaptiveSpeechRate
from narratorverse.pipeline import StandalonePipeline
from narratorverse.profiles import Profiles
from test_narrator_behavior_contract import ContractReplay
from test_narrator_foundation import _ManualExecutor, _pipeline, _settings


def select(policy, index, *, base=1.0, enabled=True, now=None, backlog=False):
    return policy.select(base_rate=base, enabled=enabled,
                         accepted_at=float(index) if now is None else now,
                         text='Musimy natychmiast wrócić do miasta i ostrzec mieszkańców.',
                         backlog=backlog, phrase_id=index)


def test_rise_requires_sustained_pressure_and_has_small_steps():
    policy = AdaptiveSpeechRate()
    rates = [select(policy, i) for i in range(10)]
    assert rates[:4] == pytest.approx([1.0, 1.0, 1.10, 1.20])
    assert rates[-1] == pytest.approx(1.5)
    assert all(0 <= right - left <= .100001 for left, right in zip(rates, rates[1:]))


def test_single_fast_exchange_does_not_cause_acceleration():
    policy = AdaptiveSpeechRate()
    assert select(policy, 0) == 1
    assert select(policy, 1) == 1
    assert select(policy, 2, now=8) == 1


@pytest.mark.parametrize('base', [.5, .85, 1.3, 1.95, 2.0])
def test_boost_is_relative_to_base_and_never_exceeds_piper_limit(base):
    policy = AdaptiveSpeechRate()
    for i in range(12):
        rate = select(policy, i, base=base, now=i * .1, backlog=True)
        assert base <= rate <= min(2.0, base * 1.5)
    assert rate == pytest.approx(min(2.0, base * 1.5))


def test_backlog_can_trigger_boost_even_without_fast_dialogue():
    policy = AdaptiveSpeechRate()
    select(policy, 0, backlog=True)
    assert select(policy, 1, now=5.0, backlog=True) == pytest.approx(1.10)


def test_backlog_is_not_mistaken_for_silence_between_subtitles():
    policy = AdaptiveSpeechRate()
    rates = [select(policy, i, now=i * 30.0, backlog=True) for i in range(8)]
    assert rates[:3] == pytest.approx([1, 1.10, 1.20])
    assert rates[-1] == pytest.approx(1.5)


def test_short_fast_replies_that_fit_are_not_accelerated():
    policy = AdaptiveSpeechRate()
    for i in range(5):
        assert select(policy, i) == 1
        policy.synthesized(i, .5)


def test_slower_dialogue_gradually_returns_to_base():
    policy = AdaptiveSpeechRate()
    for i in range(8):
        select(policy, i)
    policy.synthesized(7, .5)
    rate = select(policy, 8, now=8.0)
    assert rate == pytest.approx(1.45)
    for i in range(9, 20):
        policy.synthesized(i - 1, .5)
        rate = select(policy, i)
    assert rate == 1.0


def test_long_silence_clears_previous_boost():
    policy = AdaptiveSpeechRate()
    for i in range(8):
        select(policy, i)
    assert select(policy, 8, now=60) == 1


def test_disabled_and_reset_clear_all_pressure():
    policy = AdaptiveSpeechRate()
    for i in range(8):
        select(policy, i)
    assert select(policy, 8, base=1.3, enabled=False) == 1.3
    assert select(policy, 9) == 1
    policy.reset()
    assert select(policy, 10, backlog=True) == 1


def test_stale_duration_cannot_overwrite_newer_estimate():
    policy = AdaptiveSpeechRate()
    select(policy, 0)
    select(policy, 1)
    policy.synthesized(0, .5)
    assert select(policy, 2) == pytest.approx(1.10)


def test_clock_moving_backwards_discards_previous_pressure():
    policy = AdaptiveSpeechRate()
    for i in range(8):
        select(policy, i)
    assert select(policy, 8, now=1.0) == 1


@pytest.mark.parametrize('duration', [0, -.5, float('nan'), float('inf'), 121])
def test_invalid_duration_does_not_replace_estimate(duration):
    policy = AdaptiveSpeechRate()
    select(policy, 0)
    policy.synthesized(0, duration)
    select(policy, 1)
    assert select(policy, 2) == pytest.approx(1.10)


def test_duration_feedback_prevents_false_pressure():
    policy = AdaptiveSpeechRate()
    select(policy, 0)
    policy.synthesized(0, .5)
    assert select(policy, 1) == 1
    policy.synthesized(1, .5)
    assert select(policy, 2) == 1


def test_rate_setting_round_trip_and_legacy_default():
    legacy = NarratorGameSettings.from_dict({'game_key': '480'}, expected_game_key='480')
    assert legacy.adaptive_speech_rate is True
    disabled = replace(legacy, adaptive_speech_rate=False)
    restored = NarratorGameSettings.from_dict(disabled.to_dict(), expected_game_key='480')
    assert restored.adaptive_speech_rate is False


@pytest.mark.parametrize('invalid', [None, 0, 1, 'false', [], {}])
def test_adaptive_setting_requires_real_boolean(invalid):
    with pytest.raises(ValueError, match='adaptive_speech_rate'):
        NarratorGameSettings.from_dict({'adaptive_speech_rate': invalid}, expected_game_key='480')


def test_profile_save_isolation_reset_and_invalid_update(tmp_path):
    path = tmp_path / 'profiles.json'
    profiles = Profiles(path)
    first = profiles.selected()['id']
    profiles.update({'adaptive_speech_rate': False, 'speech_rate': 1.3})
    before = path.read_bytes()
    with pytest.raises(ValueError):
        profiles.update({'adaptive_speech_rate': 'false'})
    assert path.read_bytes() == before
    profiles = Profiles(path)
    assert profiles.settings().adaptive_speech_rate is False
    profiles.create('Drugi')
    assert profiles.settings().adaptive_speech_rate is True
    profiles.select(first)
    assert profiles.settings().adaptive_speech_rate is False
    profiles.reset('recognition')
    assert profiles.settings().adaptive_speech_rate is False
    profiles.reset('voice')
    assert profiles.settings().adaptive_speech_rate is True
    assert profiles.settings().speech_rate == 1.0


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('translated', [False, True])
def test_live_ocr_pipeline_forwards_rate_without_stopping_audio(tmp_path, enabled, translated):
    replay = ContractReplay(tmp_path)
    rates = []

    def synthesize(text, *, language, voice_id, speech_rate):
        assert (language, voice_id) == ('pl', 'voice-pl')
        rates.append(speech_rate)
        replay.tts.values.append(text)
        # Tiny synthetic PCM keeps the existing fake audio contract. Policy
        # ignores sub-300 ms feedback and retains its text-length fallback.
        return PcmAudio(samples=b'\x00\x00', sample_rate=24000, channels=1,
                        provider_id='test-tts', elapsed_ms=12.0)

    replay.tts.synthesize = synthesize
    replay.pipeline._settings = replace(replay.pipeline._settings, adaptive_speech_rate=enabled)
    if translated:
        replay.pipeline._settings = replace(
            replay.pipeline._settings,
            subtitle_language_mode=NarratorSubtitleLanguageMode.ENGLISH_TO_POLISH,
        )

        def recognize(frame, *, language):
            assert language == 'en'
            return replay.current

        def translate(text, *, source_language, target_language, profile_id):
            assert (source_language, target_language, profile_id) == ('en', 'pl', 'small')
            return TranslationResult(source_text=text, translated_text=text,
                                     provider_id='test-translator')

        # Identity translation tests routing and cadence only, not translation
        # quality; the same Polish output can then be compared in both modes.
        replay.pipeline.ocr.recognize = recognize
        replay.pipeline.translator.translate = translate
    lines = ['Musimy natychmiast ostrzec mieszkańców pobliskiego miasta.',
             'Strażnicy zamknęli wszystkie bramy, nie ma stąd wyjścia.',
             'Zabierz dokumenty ze stołu i biegnij prosto do portu.']
    try:
        for line in lines:
            replay.observe(line)
            replay.observe(line)
        assert replay.tts.values == lines
        assert rates == pytest.approx([1, 1, 1.10] if enabled else [1, 1, 1])
        assert replay.pipeline.snapshot.effective_speech_rate == pytest.approx(rates[-1])
        assert replay.pipeline.audio.stop_calls == 0
        # Duplicate OCR and filtered-empty stage directions must not advance
        # the policy or synthesize an extra utterance.
        replay.observe(lines[-1])
        replay.observe('(ciężkie oddychanie)')
        replay.observe('(ciężkie oddychanie)')
        assert len(rates) == 3
        assert replay.pipeline.snapshot.effective_speech_rate == pytest.approx(rates[-1])
    finally:
        replay.close()


def test_pause_and_new_session_reset_adaptation_without_closing_portal_on_pause(tmp_path):
    executor = _ManualExecutor()
    original, capture, activity, ocr, translator, tts, audio = _pipeline(tmp_path, executor)
    pipeline = StandalonePipeline(capture, ocr, translator, tts, audio, activity,
                                  original.cache, executor=executor)
    try:
        pipeline.start(_settings())
        pipeline._settings = replace(pipeline._settings, speech_rate=1.3)
        pipeline._snapshot = replace(pipeline._snapshot, effective_speech_rate=1.56)
        for i in range(8):
            select(pipeline._adaptive_rate, i)
        pipeline.pause_processing()
        assert pipeline._adaptive_rate.boost == 0
        assert pipeline.snapshot.effective_speech_rate == 1.3
        assert capture.stop_calls == 0
        for i in range(8):
            select(pipeline._adaptive_rate, i)
        pipeline.stop()
        assert pipeline._adaptive_rate.boost == 0
        assert pipeline.snapshot.effective_speech_rate == 1.3
        pipeline.start(_settings())
        assert select(pipeline._adaptive_rate, 0) == 1
        assert pipeline.snapshot.effective_speech_rate == 1.0
    finally:
        pipeline.shutdown()
        original.shutdown()


@pytest.mark.parametrize('transition', ['pause', 'restart'])
def test_late_tts_result_after_pause_or_restart_does_not_affect_adaptation(tmp_path, transition):
    executor = _ManualExecutor()
    original, capture, activity, ocr, translator, tts, audio = _pipeline(tmp_path, executor)
    pipeline = StandalonePipeline(capture, ocr, translator, tts, audio, activity,
                                  original.cache, executor=executor)
    try:
        pipeline.start(_settings())
        generation, work_id = pipeline._generation, pipeline._work_id
        if transition == 'pause':
            pipeline.pause_processing()
        else:
            pipeline.stop()
            pipeline.start(_settings())
        synthesized = Mock()
        pipeline._adaptive_rate.synthesized = synthesized
        future = Future()
        future.set_result(SimpleNamespace(
            audio=PcmAudio(samples=b'\x00\x00' * 24000, sample_rate=24000,
                           channels=1, provider_id='test-tts'),
            started_at=10.0, finished_at=10.1,
        ))
        pipeline._tts_finished(future, translated='Stary wynik.', source_text='Old result.',
                               translation_bypassed=False, generation=generation,
                               work_id=work_id, timing=None)
        synthesized.assert_not_called()
        assert pipeline._adaptive_rate.boost == 0
        assert audio.played == []
        assert pipeline.snapshot.effective_speech_rate == 1.0
    finally:
        pipeline.shutdown()
        original.shutdown()


def test_fatal_capture_error_resets_adaptation_and_reported_rate(tmp_path):
    executor = _ManualExecutor()
    pipeline, *_ = _pipeline(tmp_path, executor)
    try:
        pipeline.start(replace(_settings(), speech_rate=1.3))
        for i in range(8):
            select(pipeline._adaptive_rate, i)
        pipeline._snapshot = replace(pipeline._snapshot, effective_speech_rate=1.56)
        with pipeline._lock:
            pipeline._fail('Synthetic capture failure')
        assert pipeline._adaptive_rate.boost == 0
        assert pipeline.snapshot.effective_speech_rate == 1.3
        assert not pipeline.active
    finally:
        pipeline.shutdown()


@pytest.mark.parametrize(('sample_format', 'width'), [('u8', 1), ('s16le', 2), ('s32le', 4), ('f32le', 4)])
def test_pipeline_uses_actual_pcm_duration_for_rate_feedback(tmp_path, sample_format, width):
    executor = _ManualExecutor()
    pipeline, _, _, _, _, tts, audio = _pipeline(tmp_path, executor)
    tts.synthesize = Mock(return_value=PcmAudio(
        samples=b'\x00' * (24000 * 2 * width), sample_rate=24000,
        channels=2, sample_format=sample_format, provider_id='test-tts',
        # Deliberately inconsistent metadata: PCM itself is one second long.
        audio_duration_ms=9999.0,
    ))
    audio.play = Mock()
    try:
        pipeline.start(replace(_settings(), adaptive_speech_rate=True))
        feedback = Mock(wraps=pipeline._adaptive_rate.synthesized)
        pipeline._adaptive_rate.synthesized = feedback
        with pipeline._lock:
            pipeline._start_tts(
                'Musimy natychmiast wrócić do miasta i ostrzec mieszkańców.',
                source_text='Synthetic subtitle.', generation=pipeline._generation,
                work_id=pipeline._work_id, timing=SimpleNamespace(accepted_at=10.0),
                translation_status='bypassed', translation_ms=None, last_translation='',
            )
        executor.run_next()
        feedback.assert_called_once_with(pipeline._work_id, 1.0)
        audio.play.assert_called_once()
        assert audio.stop_calls == 0
        assert select(pipeline._adaptive_rate, 1, now=12.0) == 1.0
    finally:
        pipeline.shutdown()