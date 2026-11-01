"""Standalone lifecycle controls; inference and recognition remain upstream."""
from dataclasses import replace
from game_optimization_linux.services.narrator_pipeline import NarratorPipeline, SubtitleTextGate


class StandalonePipeline(NarratorPipeline):
    def pause_processing(self):
        """Discard pending work without closing the user's portal session."""
        with self._lock:
            self._adaptive_rate.reset()
            self._narration_queue.clear()
            self._narration_busy = False
            self._last_text_frame_digest = None
            self._snapshot = replace(
                self._snapshot,
                effective_speech_rate=self._settings.speech_rate if self._settings else 1.0,
            )
            self._request_id = max(self._request_id, self._work_id) + 1
            self._work_id = self._request_id
            self._audio_request_floor = self._request_id
            self._latest_audio_request_id = 0
            ocr = self._ocr_future
            self._ocr_future = None
            if ocr is not None: ocr.cancel()
            for future in tuple(self._stage_futures): future.cancel()
            self._stage_futures.clear()
            self._stage_kinds.clear()
            self._request_active = False
            self._pending_frame = None
            self._pending_frame_stabilization_ms = 0.0
            self._pending_frame_visual_decision = ''
            self._first_visible_frame_timestamp = None
            self._last_sampled_at = None
            self._roi_diagnostic = None
            self._roi_diagnostic_logged = False
            self._stabilizer.reset()
            self._text_gate = SubtitleTextGate(min_confidence=self._settings.ocr_min_confidence) if self._settings else SubtitleTextGate()
            self._cancel_provider_work()
        self.audio.stop()

    def _ocr_finished(self, future, **kwargs):
        # Upstream generation stays unchanged because the portal stays open.
        # Future identity rejects a pre-pause ROI even after reading resumes.
        with self._lock:
            if future is not self._ocr_future: return
            super()._ocr_finished(future, **kwargs)