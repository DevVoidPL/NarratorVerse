"""Bounded, utterance-level catch-up; never alters PCM already playing."""
from __future__ import annotations


class AdaptiveSpeechRate:
    MAX_BOOST = 0.50
    RISE_STEP = 0.10
    FALL_STEP = 0.05

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.boost = 0.0
        self._previous_at: float | None = None
        self._previous_duration = 0.0
        self._pressure_count = 0
        self._phrase_id: int | None = None

    def select(self, *, base_rate: float, enabled: bool, accepted_at: float,
               text: str, backlog: bool, phrase_id: int) -> float:
        if not enabled:
            self.reset()
            return base_rate
        gap = None if self._previous_at is None else accepted_at - self._previous_at
        if gap is not None and gap < 0:
            self.reset()
            gap = None
        # One isolated overlap is normal. Require two successive pressure signals
        # before speeding up; duplicates/empty filtered speech never reach here.
        rapid = gap is not None and gap < self._previous_duration * 0.9
        pressure = backlog or rapid
        self._pressure_count = min(2, self._pressure_count + 1) if pressure else 0
        if gap is not None and not backlog:
            # Silence sheds accumulated boost before the next utterance, rather
            # than leaving the first sentence after a long pause unnaturally fast.
            idle = max(0.0, gap - self._previous_duration - 3.0)
            self.boost = max(0.0, self.boost - idle * 0.025)
        if self._pressure_count >= 2:
            self.boost = min(self.MAX_BOOST, self.boost + self.RISE_STEP)
        elif not pressure:
            self.boost = max(0.0, self.boost - self.FALL_STEP)
        rate = min(2.0, base_rate * (1.0 + self.boost))
        self._previous_at = accepted_at
        # Conservative fallback until actual Piper PCM is available. Character
        # count is a heuristic, not a measurement of the voice's speaking speed.
        self._previous_duration = max(0.5, len(text) / (13.0 * rate))
        self._phrase_id = phrase_id
        return rate

    def synthesized(self, phrase_id: int, duration_seconds: float) -> None:
        # Late/stale inference must not overwrite the newer phrase's estimate.
        if phrase_id == self._phrase_id and 0.3 <= duration_seconds <= 120.0:
            self._previous_duration = duration_seconds