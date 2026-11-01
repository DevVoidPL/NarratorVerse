from __future__ import annotations
from concurrent.futures import Future
from dataclasses import replace
import json
from pathlib import Path
import stat
from threading import Event
import time
from typing import Any, Callable
import pytest
from PySide6.QtCore import QCoreApplication
from game_optimization_linux.models.narrator import CaptureFrame, CaptureSourceType, CaptureState, NarratorComponentKind, NarratorGameSettings, NarratorSessionStatus, NarratorSourceMode, NarratorSubtitleLanguageMode, NormalizedRect, OcrDecisionObservation, OcrResult, PcmAudio, TranslationResult
from game_optimization_linux.services.narrator_capture import CaptureCapabilities, CaptureRequest, CaptureSessionInfo, PortalScreenCaptureProvider
from game_optimization_linux.services.narrator_components import NarratorComponentDefinition, NarratorComponentManager
from game_optimization_linux.services.narrator_audio import QtNarratorAudioOutput
from game_optimization_linux.services.narrator_persistence import CaptureGrantRepository, NarratorSettingsRepository, TranslationCache
from game_optimization_linux.services.narrator_pipeline import NarratorPipeline, PhraseDeduplicator, SubtitleRegionStabilizer, UnavailableAudioOutput, UnavailableOcrProvider, UnavailableTranslationProvider, UnavailableTtsProvider, crop_frame
_APPLICATION = QCoreApplication.instance() or QCoreApplication([])

class _PortalBackend:

    def __init__(self, capabilities: CaptureCapabilities) -> None:
        self._capabilities = capabilities
        self.requests: list[CaptureRequest] = []
        self.started_callbacks: list[Callable[[CaptureSessionInfo], None]] = []
        self.state_callbacks: list[Callable[[CaptureState, str], None]] = []
        self.stop_calls = 0

    def capabilities(self) -> CaptureCapabilities:
        return self._capabilities

    def start(self, request: CaptureRequest, *, frame_callback: Callable[[CaptureFrame], None], started_callback: Callable[[CaptureSessionInfo], None], state_callback: Callable[[CaptureState, str], None]) -> None:
        del frame_callback
        self.requests.append(request)
        self.started_callbacks.append(started_callback)
        self.state_callbacks.append(state_callback)

    def stop(self) -> None:
        self.stop_calls += 1

class _Capture:
    provider_id = 'test-capture'

    def __init__(self) -> None:
        self.requests: list[CaptureRequest] = []
        self.frame_callback: Callable[[CaptureFrame], None] | None = None
        self.state_callback: Callable[[CaptureState, str], None] | None = None
        self.stop_calls = 0

    def capabilities(self) -> CaptureCapabilities:
        return CaptureCapabilities(available=True, portal_version=6, source_types=frozenset({CaptureSourceType.WINDOW}), persistence_supported=True)

    def start(self, request: CaptureRequest, *, frame_callback: Callable[[CaptureFrame], None], state_callback: Callable[[CaptureState, str], None]) -> None:
        self.requests.append(request)
        self.frame_callback = frame_callback
        self.state_callback = state_callback
        state_callback(CaptureState.ACTIVE, '')

    def stop(self) -> None:
        self.stop_calls += 1

class _Activity:

    def __init__(self, active: bool=True) -> None:
        self.active = active

    def is_active(self, game_key: str) -> bool:
        del game_key
        return self.active

class _Ocr:
    provider_id = 'test-ocr'
    available = True

    def __init__(self) -> None:
        self.values: list[int] = []

    def recognize(self, frame: CaptureFrame, *, language: str) -> OcrResult:
        assert language == 'en'
        value = frame.pixels[0]
        self.values.append(value)
        return OcrResult(text=f'phrase {value}', confidence=0.95, provider_id=self.provider_id, elapsed_ms=4.0)

class _Translator:
    provider_id = 'test-translator'
    available = True

    def __init__(self) -> None:
        self.values: list[str] = []
        self.cancel_calls = 0

    def translate(self, text: str, *, source_language: str, target_language: str, profile_id: str) -> TranslationResult:
        assert (source_language, target_language, profile_id) == ('en', 'pl', 'small')
        self.values.append(text)
        return TranslationResult(source_text=text, translated_text=f'polski {text}', provider_id=self.provider_id, elapsed_ms=8.0)

    def cancel(self) -> None:
        self.cancel_calls += 1

class _Tts:
    provider_id = 'test-tts'
    available = True

    def __init__(self) -> None:
        self.values: list[str] = []
        self.cancel_calls = 0

    def synthesize(self, text: str, *, language: str, voice_id: str, speech_rate: float) -> PcmAudio:
        assert (language, voice_id, speech_rate) == ('pl', 'voice-pl', 1.0)
        self.values.append(text)
        return PcmAudio(samples=b'\x00\x00', sample_rate=24000, channels=1, provider_id=self.provider_id, elapsed_ms=12.0)

    def cancel(self) -> None:
        self.cancel_calls += 1

class _PrewarmingTts(_Tts):

    def __init__(self) -> None:
        super().__init__()
        self.prepared: list[str] = []

    def prepare(self, voice_id: str) -> None:
        self.prepared.append(voice_id)

class _Audio:
    provider_id = 'test-audio'
    available = True

    def __init__(self, *, auto_start: bool=True) -> None:
        self.played: list[tuple[int, float]] = []
        self.spoken_texts: list[str] = []
        self.started_callbacks: list[Callable[[float], None]] = []
        self.completed_callbacks: list[Callable[[], None]] = []
        self.error_callbacks: list[Callable[[str], None]] = []
        self.stop_calls = 0
        self.auto_start = auto_start

    def play(self, audio: PcmAudio, *, volume: float, request_id: int, started_callback: Callable[[float], None], completed_callback: Callable[[], None], error_callback: Callable[[str], None], text: str='') -> None:
        assert audio.samples == b'\x00\x00'
        self.spoken_texts.append(text)
        self.played.append((request_id, volume))
        self.started_callbacks.append(started_callback)
        self.completed_callbacks.append(completed_callback)
        self.error_callbacks.append(error_callback)
        if self.auto_start:
            started_callback(2.5)

    def stop(self) -> None:
        self.stop_calls += 1

class _ManualExecutor:

    def __init__(self) -> None:
        self.jobs: list[tuple[Future[Any], Callable[..., Any], tuple[Any, ...], dict[str, Any]]] = []

    def submit(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Future[Any]:
        future: Future[Any] = Future()
        self.jobs.append((future, function, args, kwargs))
        return future

    def mark_first_running(self) -> None:
        assert self.jobs
        assert self.jobs[0][0].set_running_or_notify_cancel()

    def run_next(self) -> None:
        self.run_at(0)

    def run_at(self, index: int) -> None:
        future, function, args, kwargs = self.jobs.pop(index)
        if future.cancelled():
            return
        if not future.running() and (not future.set_running_or_notify_cancel()):
            return
        try:
            result = function(*args, **kwargs)
        except BaseException as error:
            future.set_exception(error)
        else:
            future.set_result(result)

class _AlwaysStable:

    def consider(self, frame: CaptureFrame, *, threshold: float, stabilization_seconds: float) -> CaptureFrame:
        del threshold, stabilization_seconds
        return frame

def _settings() -> NarratorGameSettings:
    # Recognition/lifecycle contracts use fixed-rate speech. Adaptive behaviour
    # is exercised separately with a rate-recording TTS fake.
    return NarratorGameSettings(game_key='292030', enabled=True, adaptive_speech_rate=False, ocr_provider_id='test-ocr', translation_provider_id='test-translator', translation_profile_id='small', tts_provider_id='test-tts', voice_id='voice-pl', subtitle_region=NormalizedRect(x=0, y=0, width=1, height=1))

def _frame(*, session_id: str, generation: int, value: int, timestamp: float=1.0) -> CaptureFrame:
    return CaptureFrame(session_id=session_id, generation=generation, timestamp_monotonic=timestamp, width=2, height=2, stride=2, pixel_format='gray8', pixels=bytes([value] * 4))

def _pipeline(tmp_path: Path, executor: _ManualExecutor) -> tuple[NarratorPipeline, _Capture, _Activity, _Ocr, _Translator, _Tts, _Audio]:
    capture = _Capture()
    activity = _Activity()
    ocr = _Ocr()
    translator = _Translator()
    tts = _Tts()
    audio = _Audio()
    pipeline = NarratorPipeline(capture, ocr, translator, tts, audio, activity, TranslationCache(tmp_path / 'translations.sqlite3'), executor=executor)
    return (pipeline, capture, activity, ocr, translator, tts, audio)

def _confirm_phrase(pipeline: NarratorPipeline, executor: _ManualExecutor, *, session_id: str, generation: int, value: int, timestamp: float=1.0) -> None:
    pipeline.submit_frame(_frame(session_id=session_id, generation=generation, value=value, timestamp=timestamp))
    executor.run_next()
    pipeline.submit_frame(_frame(session_id=session_id, generation=generation, value=value, timestamp=timestamp + 0.2))
    executor.run_next()
