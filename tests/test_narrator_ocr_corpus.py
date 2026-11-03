"""Measurements over the committed OCR corpus. Measurement only, no behaviour.

See tests/fixtures/ocr-corpus/README.md for the provenance of each fixture.
"""
from __future__ import annotations
from pathlib import Path
import pytest
from game_optimization_linux.services.narrator_ocr import TesseractOcrProvider
CORPUS = Path(__file__).parent / 'fixtures' / 'ocr-corpus'
_SUBTITLE = '„W obliczu śmierci nie ma się już czego bać. Twoja zemsta nadejdzie”.'

def _payload(name: str) -> str:
    return (CORPUS / f'{name}.tsv').read_text(encoding='utf-8')

def _lines(text: str) -> list[str]:
    return [line for line in text.split('\n') if line.strip()]

def test_corpus_is_committed() -> None:
    assert (CORPUS / 'observation-01.tsv').is_file()
    assert (CORPUS / 'observation-03.tsv').is_file()
    assert (CORPUS / 'observation-12.tsv').is_file()

def test_clean_single_line_subtitle_scores_high() -> None:
    text, confidence, _tokens = TesseractOcrProvider._parse_tsv_detailed(_payload('observation-03'))
    assert text == _SUBTITLE
    assert confidence is not None and confidence > 0.95
    assert len(_lines(text)) == 1

def test_background_lines_dilute_a_correctly_read_subtitle() -> None:
    """The measured core finding.

    The subtitle itself is read at 0.967, but five background lines drag the
    character-weighted phrase confidence to 0.347 - below the 0.62 gate.
    """
    raw, filtered, confidence, raw_confidence, tokens = TesseractOcrProvider._analyze_tsv(_payload('observation-01'))
    assert len(_lines(raw)) == 6
    assert raw_confidence is not None and raw_confidence == pytest.approx(0.347, abs=0.01)
    groups: dict[tuple, list] = {}
    for token in tokens:
        key = (token['page'], token['block'], token['paragraph'], token['line'])
        groups.setdefault(key, []).append(token)
    line_confidences = [TesseractOcrProvider._token_confidence(values) for values in groups.values()]
    strongest = max((value for value in line_confidences if value is not None))
    assert strongest > 0.95
    assert filtered == _SUBTITLE
    assert len(_lines(filtered)) == 1
    assert confidence is not None and confidence > 0.95
    assert raw != filtered

def test_weak_line_rule_cannot_fire_when_every_line_is_weak() -> None:
    """A background-only frame: nothing is filtered, so raw == filtered.

    The rule needs another line at >= 0.80. Here the strongest line is ~0.66, so
    no line qualifies as the strong reference and nothing is removed. The frame
    is then rejected on confidence, which is the correct outcome - there is no
    subtitle in it.
    """
    raw, filtered, confidence, raw_confidence, tokens = TesseractOcrProvider._analyze_tsv(_payload('observation-12'))
    assert not any((token.get('filter_reason') == 'weak_isolated_line' for token in tokens))
    assert raw != '' and filtered != ''
    assert confidence is not None and confidence < 0.62
    groups: dict[tuple, list] = {}
    for token in tokens:
        key = (token['page'], token['block'], token['paragraph'], token['line'])
        groups.setdefault(key, []).append(token)
    confidences = [TesseractOcrProvider._token_confidence(values) for values in groups.values()]
    assert max((value for value in confidences if value is not None)) < 0.8

@pytest.mark.parametrize('name', ('observation-01', 'observation-03', 'observation-12'))
def test_no_tsv_metadata_leaks_into_parsed_text(name: str) -> None:
    """Regression check for the historical quote-absorption parsing bug."""
    text, _confidence, tokens = TesseractOcrProvider._parse_tsv_detailed(_payload(name))
    assert '\t' not in text
    for token in tokens:
        assert '\t' not in str(token['text'])
        assert '\n' not in str(token['text'])
    assert '61.909798' not in text
    assert '96.983337' not in text

@pytest.mark.parametrize(('name', 'expected_lines'), (('observation-03', 1), ('observation-01', 6), ('observation-12', 7)))
def test_returned_line_counts_are_measured(name: str, expected_lines: int) -> None:
    """Pin the observed structure so a preprocessing change is visible."""
    text, _confidence, _tokens = TesseractOcrProvider._parse_tsv_detailed(_payload(name))
    assert len(_lines(text)) == expected_lines

@pytest.mark.parametrize('name', ('observation-01', 'observation-03', 'observation-12'))
def test_line_count_against_geometric_capacity(name: str) -> None:
    """Report whether the returned line count is geometrically plausible.

    The processed image is 540 px tall. Capacity uses the median glyph height
    times 1.4 as the minimum line pitch. On this corpus every count fits, so a
    line count alone does not prove hallucination at this ROI height.
    """
    _text, _confidence, tokens = TesseractOcrProvider._parse_tsv_detailed(_payload(name))
    heights = sorted((int(t['height']) for t in tokens if int(t['height']) > 0))
    median = heights[len(heights) // 2]
    capacity = 540 // max(1, int(median * 1.4))
    groups = {(t['page'], t['block'], t['paragraph'], t['line']) for t in tokens}
    assert len(groups) <= capacity, f'{name}: {len(groups)} lines exceeds capacity {capacity} for median glyph height {median}px'

def _summary(funnel: dict[str, int]) -> dict[str, int]:
    from game_optimization_linux.models.narrator import NarratorSessionSnapshot
    return NarratorSessionSnapshot(session_id='s1', game_key='292030', narration_funnel=funnel).narration_funnel_summary()

def test_strongest_line_uses_the_weak_line_rule_threshold() -> None:
    """The split must reuse the rule's own 0.80, not a second tunable."""
    from game_optimization_linux.services.narrator_ocr import OCR_STRONG_LINE_CONFIDENCE
    assert OCR_STRONG_LINE_CONFIDENCE == 0.8

def test_background_only_frame_has_no_strong_line() -> None:
    """observation-12: every line weak, so it is a probable no-subtitle frame."""
    _text, _confidence, tokens = TesseractOcrProvider._parse_tsv_detailed(_payload('observation-12'))
    from game_optimization_linux.services.narrator_ocr import OCR_STRONG_LINE_CONFIDENCE
    strongest, text = TesseractOcrProvider._strongest_line(tokens)
    assert strongest is not None
    assert strongest < OCR_STRONG_LINE_CONFIDENCE
    assert text

def test_subtitle_frame_has_a_strong_line_and_is_not_rejected() -> None:
    """observation-01 is accepted after filtering, so it counts as neither."""
    from game_optimization_linux.services.narrator_ocr import OCR_STRONG_LINE_CONFIDENCE
    _raw, filtered, confidence, _raw_conf, tokens = TesseractOcrProvider._analyze_tsv(_payload('observation-01'))
    strongest, text = TesseractOcrProvider._strongest_line(tokens)
    assert strongest is not None and strongest >= OCR_STRONG_LINE_CONFIDENCE
    assert text.strip().startswith('„W obliczu')
    assert confidence is not None and confidence > 0.62
    assert filtered == _SUBTITLE

def test_split_counters_are_reported_separately() -> None:
    summary = _summary({'observations': 20, 'rejected_low_confidence': 12, 'rejected_no_strong_line': 9, 'rejected_despite_strong_line': 3})
    assert summary['rejectedNoStrongLine'] == 9
    assert summary['rejectedDespiteStrongLine'] == 3

def test_split_counters_sum_to_the_previous_single_total() -> None:
    """The split must account for every low-confidence rejection."""
    summary = _summary({'observations': 526, 'rejected_low_confidence': 374, 'rejected_no_strong_line': 351, 'rejected_despite_strong_line': 23})
    assert summary['rejectedNoStrongLine'] + summary['rejectedDespiteStrongLine'] == summary['rejectedLowConfidence']

def test_split_counters_default_to_zero() -> None:
    summary = _summary({'observations': 3})
    assert summary['rejectedNoStrongLine'] == 0
    assert summary['rejectedDespiteStrongLine'] == 0

def test_lost_strong_line_history_is_bounded_and_carries_text() -> None:
    from game_optimization_linux.models.narrator import NarratorSessionSnapshot
    entries = tuple(({'observation': index, 'confidence': 0.9, 'text': f'line {index}'} for index in range(10)))
    payload = NarratorSessionSnapshot(session_id='s1', game_key='292030', lost_strong_lines=entries).to_dict()
    assert len(payload['lostStrongLines']) == 10
    assert payload['lostStrongLines'][0]['text'] == 'line 0'
    assert payload['lostStrongLines'][-1]['confidence'] == 0.9
