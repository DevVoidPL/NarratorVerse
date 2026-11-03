"""Occurrence identity, short replies and bounded rapid-dialogue queues."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtMultimedia import QtAudio

from game_optimization_linux.models.narrator import OcrResult, PcmAudio
from game_optimization_linux.services.narrator_audio import QtNarratorAudioOutput, _Playback
from game_optimization_linux.services.narrator_ocr import TesseractOcrProvider
from game_optimization_linux.services.narrator_pipeline import PhraseDeduplicator, SubtitleRegionStabilizer, SubtitleTextGate
from narratorverse.pipeline import StandalonePipeline
from test_narrator_behavior_contract import ContractReplay
from test_narrator_foundation import _ManualExecutor, _frame


@pytest.mark.parametrize('text', ['Nie', 'Nie.', 'Siema', 'Siema.', 'OK', 'OK.', 'Tak!', 'No?'])
def test_single_word_has_strong_ocr_evidence_and_can_be_accepted_once(text):
    header = 'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'
    tsv = header + f'5\t1\t1\t1\t1\t1\t40\t20\t80\t20\t97\t{text}\n'
    _, filtered, confidence, _, tokens = TesseractOcrProvider._analyze_tsv(tsv)
    evidence = TesseractOcrProvider._quality_evidence(filtered, confidence, tokens, image_width=800, image_height=200)
    assert evidence['clean_short_phrase_evidence'] is True
    gate = SubtitleTextGate()
    first = gate.observe(filtered, confidence, now=1, strong_short_phrase_evidence=True)
    assert first.accepted_text == text
    assert gate.observe(filtered, confidence, now=1.2, strong_short_phrase_evidence=True).accepted_text == ''


def test_weak_single_word_still_requires_confirmation():
    gate = SubtitleTextGate()
    assert gate.observe('OK', .70, now=1).accepted_text == ''
    assert gate.observe('OK', .70, now=1.2).accepted_text == 'OK'
    assert SubtitleTextGate().observe('OK', .20, now=1).rejection_reason == 'low_confidence'


def test_edge_cleanup_does_not_erase_entire_short_reply():
    gate = SubtitleTextGate()
    gate.observe('OK', .70, now=1, leading_low_quality_tokens=('OK',))
    assert gate.observe('OK', .70, now=1.2, leading_low_quality_tokens=('OK',)).accepted_text == 'OK'


def test_clean_reply_replaces_unconfirmed_noise_immediately():
    gate = SubtitleTextGate()
    gate.observe('Niepewny odczyt', .70, now=1)
    assert gate.observe('Siema.', .97, now=1.2, strong_short_phrase_evidence=True).accepted_text == 'Siema.'


@pytest.mark.parametrize('text', ['Nie.', 'Siema.', 'OK'])
def test_persistent_short_display_is_spoken_once_beyond_cooldown(tmp_path, text):
    replay = ContractReplay(tmp_path)
    try:
        for _ in range(25):
            replay.observe(text)
        assert replay.tts.values == [text]
    finally:
        replay.close()


def test_same_text_after_real_disappearance_is_another_occurrence(tmp_path):
    replay = ContractReplay(tmp_path)
    try:
        for _ in range(2):
            replay.now += 4.5
            replay.observe('Siema.', frame_value=180)
            replay.observe('Siema.', frame_value=180)
            for _ in range(3):
                replay.observe('', confidence=None, frame_value=0)
        assert replay.tts.values == ['Siema.', 'Siema.']
    finally:
        replay.close()


def test_one_transient_blank_does_not_rearm_reply(tmp_path):
    replay = ContractReplay(tmp_path)
    try:
        for text in ['Siema.', 'Siema.', '', 'Siema.', 'Siema.']:
            replay.observe(text)
        assert replay.tts.values == ['Siema.']
    finally:
        replay.close()


def test_repeated_empty_ocr_on_identical_pixels_is_not_disappearance(tmp_path):
    replay = ContractReplay(tmp_path)
    try:
        for text in ['Siema.', 'Siema.', '', '', '', '', 'Siema.', 'Siema.']:
            replay.observe(text, frame_value=180)
        assert replay.tts.values == ['Siema.']
        assert replay.pipeline.snapshot.ocr_execution_count == 8
        assert not any(item.reason_code == 'confirmed_disappearance'
                       for item in replay.pipeline.snapshot.ocr_decision_history)
    finally:
        replay.close()


def test_returning_reply_after_distinct_dialogue_waits_for_history_expiry(tmp_path):
    replay = ContractReplay(tmp_path)
    try:
        for text in ['Siema.', 'Nie.', 'Siema.']:
            replay.observe(text)
            replay.observe(text)
        assert replay.tts.values == ['Siema.', 'Nie.']
        replay.now += 4.5
        replay.observe('Siema.')
        replay.observe('Siema.')
        assert replay.tts.values == ['Siema.', 'Nie.', 'Siema.']
    finally:
        replay.close()


def test_different_explicit_speakers_with_identical_dialogue_are_distinct():
    first = 'Profesor Fig: Musimy natychmiast wrócić do zamku i ostrzec mieszkańców.'
    second = 'Profesor Black: Musimy natychmiast wrócić do zamku i ostrzec mieszkańców.'
    gate = SubtitleTextGate()
    dedup = PhraseDeduplicator()
    for index, text in enumerate((first, second)):
        gate.observe(text, .95, now=index + 1)
        accepted = gate.observe(text, .95, now=index + 1.2).accepted_text
        assert accepted == text
        assert dedup.accept(accepted, now=index + 1.2, cooldown_seconds=10) == text


@pytest.mark.parametrize(('first_label', 'second_label'), [
    ('Bluszcz', 'Trujący Bluszcz'),
    ('Trujący Bluszcz', 'Bluszcz'),
    ('Profesor.Fig Fig', 'Profesor Fig'),
    ('Profesor Fig', 'Profesor.Fig Fig'),
])
def test_recovered_or_duplicated_speaker_label_is_not_a_new_occurrence(first_label, second_label):
    speech = 'Musimy natychmiast wrócić do zamku i ostrzec mieszkańców.'
    first, second = f'{first_label}: {speech}', f'{second_label}: {speech}'
    gate = SubtitleTextGate()
    dedup = PhraseDeduplicator()
    gate.observe(first, .95, now=1)
    assert gate.observe(first, .95, now=1.2).accepted_text == first
    assert dedup.accept(first, now=1.2, cooldown_seconds=10) == first
    assert gate.observe(second, .95, now=1.4).accepted_text == ''
    assert gate.observe(second, .95, now=1.6).accepted_text == ''
    assert dedup.accept(second, now=1.6, cooldown_seconds=10) is None


def test_static_visual_gate_periodically_probes_small_replies():
    stabilizer = SubtitleRegionStabilizer()
    first = _frame(session_id='session', generation=1, value=100, timestamp=1)
    assert stabilizer.consider_for_ocr(first, threshold=.1) is first
    assert stabilizer.consider_for_ocr(replace(first, timestamp_monotonic=1.2), threshold=.1) is None
    tiny_reply = replace(first, timestamp_monotonic=1.6, pixels=bytes([101] * 4))
    assert stabilizer.consider_for_ocr(tiny_reply, threshold=.1) is tiny_reply
    assert stabilizer.last_decision == 'periodic_probe'


def test_pipeline_strong_single_word_path_reaches_tts_on_first_frame(tmp_path):
    replay = ContractReplay(tmp_path)
    try:
        replay.current = OcrResult('OK', confidence=.97, clean_short_phrase_evidence=True)
        replay.pipeline._stabilizer = SubtitleRegionStabilizer()
        snapshot = replay.snapshot
        replay.pipeline.submit_frame(_frame(session_id=snapshot.session_id, generation=snapshot.generation, value=180, timestamp=11))
        while replay.executor.jobs:
            replay.executor.run_next()
        assert replay.tts.values == ['OK']
    finally:
        replay.close()


def test_rapid_accepted_dialogue_waits_for_synthesis_instead_of_cancelling_it(tmp_path):
    replay = ContractReplay(tmp_path)
    synthesis = _ManualExecutor()
    replay.pipeline._tts_executor = synthesis
    lines = ['Musimy wrócić do miasta.', 'Nie.', 'Siema.', 'OK']
    try:
        for text in lines:
            replay.observe(text)
            replay.observe(text)
        assert len(synthesis.jobs) == 1
        assert not synthesis.jobs[0][0].cancelled()
        assert len(replay.pipeline._narration_queue) == len(lines) - 1
        while synthesis.jobs:
            synthesis.run_next()
        assert replay.tts.values == lines
        assert replay.pipeline.audio.spoken_texts == lines
        assert replay.pipeline._narration_busy is False
        assert not replay.pipeline._narration_queue
    finally:
        replay.close()


def test_stop_discards_queued_dialogue_and_prevents_late_playback(tmp_path):
    replay = ContractReplay(tmp_path)
    synthesis = _ManualExecutor()
    replay.pipeline._tts_executor = synthesis
    try:
        for text in ['Pierwsza kwestia.', 'Następna kwestia.']:
            replay.observe(text)
            replay.observe(text)
        assert replay.pipeline._narration_queue
        synthesis.mark_first_running()
        replay.pipeline.stop()
        synthesis.run_next()
        assert not replay.pipeline._narration_queue
        assert replay.pipeline.audio.played == []
    finally:
        replay.close()


def test_audio_fifo_preserves_three_waiting_replies_and_stop_clears_it():
    output = QtNarratorAudioOutput()
    started = []
    audio = PcmAudio(samples=b'\x00\x00' * 24000, sample_rate=24000, channels=1, provider_id='test')

    def start(playback):
        output._current = playback
        output._sink = SimpleNamespace(
            processedUSecs=lambda: 1_000_000,
            error=lambda: QtAudio.Error.NoError,
            state=lambda: QtAudio.State.IdleState,
            stateChanged=Mock(), stop=Mock(), deleteLater=Mock(),
        )
        started.append(playback.request_id)

    output._start = start
    for index in range(4):
        output._queue_playback(_Playback(audio=audio, volume=1, request_id=index,
                                        started_callback=Mock(), completed_callback=Mock(),
                                        error_callback=Mock(), queued_at=0, text='Siema.'))
    assert output.queue_depth == 4
    for _ in range(4):
        output._state_changed()
    assert started == [0, 1, 2, 3]
    assert output.completed_count == 4
    assert output.queue_depth == 0
    assert output.superseded_count == 0
    for index in range(3):
        output._queue_playback(_Playback(audio=audio, volume=1, request_id=index,
                                        started_callback=Mock(), completed_callback=Mock(),
                                        error_callback=Mock(), queued_at=0))
    output._stop_all()
    assert output.queue_depth == 0


def test_sustained_overload_is_bounded_and_explicitly_counted(tmp_path):
    replay = ContractReplay(tmp_path)
    synthesis = _ManualExecutor()
    replay.pipeline._tts_executor = synthesis
    try:
        for index in range(12):
            text = f'Pokój {index + 100}'
            replay.observe(text)
            replay.observe(text)
        assert len(replay.pipeline._narration_queue) == 8
        assert replay.pipeline._funnel['dialogue_queue_overflow'] == 3
        assert not synthesis.jobs[0][0].cancelled()
    finally:
        replay.close()


def test_failed_synthesis_does_not_block_next_accepted_reply(tmp_path):
    replay = ContractReplay(tmp_path)
    synthesis = _ManualExecutor()
    replay.pipeline._tts_executor = synthesis
    original = replay.tts.synthesize

    def synthesize(text, **kwargs):
        if text == 'Pierwsza kwestia.':
            raise RuntimeError('Synthetic provider failure')
        return original(text, **kwargs)

    replay.tts.synthesize = synthesize
    try:
        for text in ['Pierwsza kwestia.', 'OK']:
            replay.observe(text)
            replay.observe(text)
        while synthesis.jobs:
            synthesis.run_next()
        assert replay.pipeline.audio.spoken_texts == ['OK']
        assert replay.pipeline._narration_busy is False
    finally:
        replay.close()


def test_pause_clears_narration_fifo_without_closing_capture(tmp_path):
    replay = ContractReplay(tmp_path)
    synthesis = _ManualExecutor()
    replay.pipeline._tts_executor = synthesis
    try:
        for text in ['Pierwsza kwestia.', 'Następna kwestia.']:
            replay.observe(text)
            replay.observe(text)
        synthesis.mark_first_running()
        replay.pipeline._stabilizer = SubtitleRegionStabilizer()
        StandalonePipeline.pause_processing(replay.pipeline)
        synthesis.run_next()
        assert not replay.pipeline._narration_queue
        assert not replay.pipeline._narration_busy
        assert replay.pipeline.capture.stop_calls == 0
        assert replay.pipeline.audio.played == []
    finally:
        replay.close()


def test_backlog_uses_remaining_pcm_time_not_only_number_of_items(tmp_path):
    replay = ContractReplay(tmp_path)
    try:
        replay.pipeline.audio = SimpleNamespace(available=True, queued_seconds=2.0, queue_depth=1, stop=Mock(), superseded_count=0)
        assert replay.pipeline._speech_backlog() is True
        replay.pipeline.audio.queued_seconds = .1
        assert replay.pipeline._speech_backlog() is False
    finally:
        replay.close()