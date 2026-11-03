"""GTA OCR text regressions; synthetic confidence/timing, not a model benchmark."""
from __future__ import annotations

from pathlib import Path

import pytest

from game_optimization_linux.services.narrator_pipeline import (
    PhraseDeduplicator,
    _same_episode_variant,
)
from test_narrator_behavior_contract import ContractReplay


# Raw OCR text from gta-cooldown-02, phrases 2237..2243 and 2446..2451.
# ContractReplay supplies deterministic clocks and fake inference providers.
_GTA_SEQUENCES = (
    (
        'Są sposoby, by się tak nam nie dtużyło.',
        'Sa sposoby, by się tak nam nie dłuzyło..',
        'Sa sposoby, by się tak narn nte dtużyto',
        'Są sposoby by się tak nar nie dłużyto.',
        'Sa sposoby, by się tak narn nie dlużyto.',
        'Są sposoby, by się tak nam nie dłużyło.',
    ),
    (
        'Dobra, teraz wyjada na otwarty teren. Mozna tam zwinać furgonetki, ale to\n'
        'musiałby być szybki numer.',
        'Dobra, teraz wyjada na otwarty teren. Można tam zwinać furgonetki, ale to\n'
        'musiatby być szybki numer.',
        'Dobra teraz wyjada na otwarty teren. Można tam zwinąć furgonetki, ale to\n'
        'musiatbybyćszybkinumer.',
        'Dobral teraz wyjada na otwarty teren. Możn tarn winać furgoneti ale to '
        'musiałby być szybki numer.',
        'Dobra, teraz wjada na otwarty teren. Można tarn zwinać furgonetki, ale to\n'
        'musiałby być szybki nurner.',
        'Dobra, teraz wyjada na otwarty teren. Można tarn zwinąć furgonetki, ale to\n'
        'musiałby być szybki numer.',
    ),
)

_ACCEPTED_PAIRS = (
    (
        'Są sposoby, by się tak nam nie dłuzyło..',
        'Są sposoby, by się tak narn nie dłużyto.',
    ),
    (
        'Dobra, teraz wyjada na otwarty teren. Można tam zwinać furgonetki, ale to '
        'musiatby być szybki numer.',
        'Dobral, teraz wjada na otwarty teren. Można tarn zwinać furgonetki, ale to '
        'musiałby być szybki nurner.',
    ),
)


@pytest.mark.parametrize('first,second', _ACCEPTED_PAIRS, ids=['nam-narn', 'tam-tarn'])
def test_gta_accepted_ocr_variants_match_in_both_directions(first: str, second: str) -> None:
    assert _same_episode_variant(first, second) is True
    assert _same_episode_variant(second, first) is True


@pytest.mark.parametrize('sequence', _GTA_SEQUENCES, ids=['ways', 'vans'])
def test_gta_visible_subtitle_enqueues_speech_only_once(
    tmp_path: Path, sequence: tuple[str, ...]
) -> None:
    replay = ContractReplay(tmp_path)
    events: list[dict[str, object]] = []
    replay.pipeline._diagnostic = lambda event, **fields: events.append(
        dict(event=event, **fields)
    )
    replay.pipeline._deduplicator = PhraseDeduplicator()
    try:
        decisions = [replay.observe(text) for text in sequence[:2]]
        assert sum(decision.accepted for decision in decisions) == 1
        assert len(replay.tts.values) == 1
        for text in (*sequence[2:], sequence[1], sequence[1]):
            decisions.append(replay.observe(text))
        assert sum(decision.accepted for decision in decisions) == 1
        assert len({decision.episode_id for decision in decisions if decision.accepted}) == 1
        assert len(replay.tts.values) == 1
        assert sum(event['event'] == 'tts_provider_input' for event in events) == 1
        assert sum(event['event'] == 'playback_started' for event in events) == 1
    finally:
        replay.close()


@pytest.mark.parametrize('first,second', _ACCEPTED_PAIRS, ids=['nam-narn', 'tam-tarn'])
def test_beta_spoken_history_blocks_gta_variant_without_active_episode(
    first: str, second: str
) -> None:
    # Isolate the cooldown path: there is no active accepted episode here.
    dedup = PhraseDeduplicator()
    dedup.mark_spoken(first, now=10.0)
    assert dedup.accept(second, now=11.0, cooldown_seconds=4.5) is None
    assert dedup.last_rejection_reason == 'cooldown_variant'


@pytest.mark.parametrize('first,second', [
    ('Idź do pokoju 101.', 'Idź do pokoju 102.'),
    ('Jedź teraz do salonu.', 'Nie jedź teraz do salonu.'),
    ('Please lock the door.', 'Please unlock the door.'),
    ('Anna: Tak.', 'Marek: Tak.'),
    ('Musimy teraz jechać do banku po pieniądze.',
     'Musimy teraz jechać do portu po pieniądze.'),
    ('Idź do sklepu i kup chleb, mleko oraz masło na jutro.',
     'Idź do sklepu i kup chleb, mleko oraz masło na dziś.'),
])
def test_gta_variant_matching_keeps_meaning_and_speaker_changes_distinct(
    tmp_path: Path, first: str, second: str
) -> None:
    assert _same_episode_variant(first, second) is False
    assert _same_episode_variant(second, first) is False
    replay = ContractReplay(tmp_path)
    try:
        decisions = [replay.observe(text) for text in (first, first, second, second)]
        assert sum(decision.accepted for decision in decisions) == 2
        assert len(replay.tts.values) == 2
    finally:
        replay.close()