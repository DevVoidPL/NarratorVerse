import importlib.util
from pathlib import Path


def test_summary_correlates_changed_tts_hash_through_request_id():
    path = Path(__file__).resolve().parents[1] / 'scripts/analyze-p0-trace.py'
    spec = importlib.util.spec_from_file_location('p0_analysis', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base = dict(run_id='r', pid=1, session_id='s', generation=1, phrase_id=2, monotonic=1)
    records = [dict(base, event=name) for name in ('phrase_reserved', 'dialogue_started',
        'fifo_dequeued', 'tts_provider_input', 'audio_submitted', 'sink_submitted',
        'sink_started', 'playback_started', 'sink_terminal', 'playback_completed')]
    records += [dict(base, event='ocr_decision', decision='accepted', accepted_text_sha256='source'),
                dict(base, event='dedup_checked', identity_text_sha256='identity'),
                dict(event='trace_closed', dropped_events=0)]
    result = module.summarize(records)
    assert result['trace_complete']
    assert result['accepted_requests'][0]['one_to_one']
    assert result['totals_by_identity_hash']['identity']['tts'] == 1
    assert result['physical_playback'] == 'NOT_TESTED_BY_ANALYZER'
    records.append(dict(base, event='tts_provider_input', text_sha256='translated'))
    assert not module.summarize(records)['accepted_requests'][0]['one_to_one']


def test_missing_or_lossy_footer_is_incomplete():
    path = Path(__file__).resolve().parents[1] / 'scripts/analyze-p0-trace.py'
    spec = importlib.util.spec_from_file_location('p0_analysis', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert not module.summarize([])['trace_complete']
    assert not module.summarize([dict(event='trace_closed', dropped_events=1)])['trace_complete']