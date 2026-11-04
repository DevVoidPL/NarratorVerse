#!/usr/bin/env python3
"""Summarize hash-only P0 traces. Never infer physical audibility from callbacks."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path


def summarize(records):
    footers = [r for r in records if r.get('event') == 'trace_closed']
    groups = defaultdict(list)
    for record in records:
        if record.get('phrase_id', 0) > 0:
            key = tuple(record.get(k) for k in ('run_id', 'pid', 'session_id', 'generation', 'phrase_id'))
            groups[key].append(record)
    rows = []
    for key, events in groups.items():
        accepted = [e for e in events if e['event'] == 'ocr_decision' and e.get('decision') == 'accepted']
        if not accepted:
            continue
        names = Counter(e['event'] for e in events)
        decision = accepted[0]
        dedup = next((e for e in events if e['event'] == 'dedup_checked'), {})
        terminals = [e for e in events if e['event'] == 'sink_terminal']
        counts = dict(accepted=len(accepted), reserved=names['phrase_reserved'],
            fifo_admitted=names['dialogue_queued'] or names['dialogue_started'],
            fifo_dispatched=names['fifo_dequeued'], tts=names['tts_provider_input'],
            audio_submitted=names['audio_submitted'], sink_submitted=names['sink_submitted'],
            sink_started=names['sink_started'], playback_started=names['playback_started'],
            sink_terminal=len(terminals), completed=names['playback_completed'])
        rows.append(dict(zip(('run_id', 'pid', 'session_id', 'generation', 'phrase_id'), key),
            text_sha256=decision.get('accepted_text_sha256'),
            identity_sha256=dedup.get('identity_text_sha256'), counts=counts,
            stage_times={name: [e['monotonic'] for e in events if e['event'] == name]
                         for name in ('ocr_decision', 'tts_provider_input', 'audio_submitted',
                                      'sink_started', 'sink_terminal')},
            terminal_results=[{k: e.get(k) for k in ('result', 'processed_ms', 'expected_ms',
                                                   'backend_error', 'terminal_state')} for e in terminals],
            one_to_one=all(value == 1 for value in counts.values())))
    by_hash = defaultdict(Counter)
    for row in rows:
        # Aggregate for discovery, not a time-window verdict: a legitimate line
        # may recur in later scenes/sessions. Inspect per-request timestamps.
        by_hash[row['identity_sha256'] or row['text_sha256']].update(row['counts'])
    return dict(trace_complete=bool(footers) and all(r.get('dropped_events') == 0 for r in footers),
                footer_count=len(footers), accepted_requests=rows,
                totals_by_identity_hash={key: dict(value) for key, value in by_hash.items()},
                physical_playback='NOT_TESTED_BY_ANALYZER',
                note='Correlate hashes via request IDs. Auxiliary voice/QuickRead must be disabled. '
                     'Human listening/PipeWire evidence and scenario timing are required for P0 closure.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    args = parser.parse_args()
    records = [json.loads(line) for line in args.trace.read_text().splitlines() if line.strip()]
    print(json.dumps(summarize(records), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()