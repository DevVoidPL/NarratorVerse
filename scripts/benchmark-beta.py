#!/usr/bin/env python3
"""Explicit offline CPU probe: real MT/Piper, no capture or audible playback.

Run inside GNOME SDK with the backend/runtime on PYTHONPATH. Results are local
measurements, NOT an end-to-end gameplay or weak-CPU performance guarantee.
"""
import argparse
import json
import math
import os
from pathlib import Path
import platform
import statistics
from threading import Event, Thread
import time


def summarize(values):
    if not values:
        return {'count': 0}
    ordered = sorted(values)
    return dict(count=len(values), min=ordered[0], median=statistics.median(ordered),
                p95=ordered[max(0, math.ceil(len(ordered)*.95)-1)], max=ordered[-1])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, required=True, help='Developer-only read-only fixture')
    parser.add_argument('--components', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=180)
    parser.add_argument('--profile', choices=('fast', 'balanced'), default='balanced')
    args = parser.parse_args(argv)
    if args.seconds <= 0:
        parser.error('--seconds must be positive')
    import psutil
    from narratorverse.quickmt import QuickMTTranslationProvider
    from narratorverse.translation_compare import runtime_versions
    from game_optimization_linux.services.narrator_tts import PiperPolishTtsProvider
    provider = QuickMTTranslationProvider(args.model_dir)
    tts = PiperPolishTtsProvider(args.components)
    if not provider.available or not tts.voice_available('voidek-pl-e991'):
        raise RuntimeError('Verified local QuickMT and Voidek CPU runtime required')
    stop = Event()
    samples = []
    process = psutil.Process()
    def sample():
        while not stop.is_set():
            rss, cpu, mt_rss = 0, 0, 0
            for proc in [process, *process.children(recursive=True)]:
                try:
                    value = proc.memory_info().rss
                    rss += value
                    times = proc.cpu_times()
                    cpu += times.user + times.system
                    if 'narratorverse.quickmt_worker' in ' '.join(proc.cmdline()):
                        mt_rss += value
                except psutil.Error:
                    continue
            samples.append(dict(monotonic=time.monotonic(), rss_bytes=rss,
                                quickmt_rss_bytes=mt_rss, cpu_seconds=cpu))
            stop.wait(.1)
    sampler = Thread(target=sample, daemon=True)
    sampler.start()
    texts = (
        'Do not open the door. Wait for me!',
        'There are three guards by the entrance. Take the other way.',
        'We need to return to the old bank before sunset.',
        'Anna: I did not say that we should leave without him.',
        'The room number is 101, not 102. Remember it.',
    )
    rows = []
    started = time.monotonic()
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        while not rows or time.monotonic() - started < args.seconds:
            text = texts[len(rows) % len(texts)]
            begin = time.monotonic()
            translated = provider.translate(text, source_language='en', target_language='pl', profile_id=args.profile)
            mt_end = time.monotonic()
            audio = tts.synthesize(translated.translated_text, language='pl', voice_id='voidek-pl-e991', speech_rate=1.0)
            end = time.monotonic()
            rows.append(dict(mt_ms=(mt_end-begin)*1000, tts_ms=(end-mt_end)*1000,
                             text_to_pcm_ready_ms=(end-begin)*1000,
                             pcm_seconds=len(audio.samples)/(audio.sample_rate*audio.channels*2)))
    finally:
        stop.set()
        sampler.join(timeout=2)
        provider.close()
        tts.close()
        elapsed = time.monotonic() - started
        cpu_seconds = max((s['cpu_seconds'] for s in samples), default=0) - min((s['cpu_seconds'] for s in samples), default=0)
        cpu_model = next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')), platform.processor())
        report = dict(measured_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'), cpu=cpu_model,
            logical_cpus=os.cpu_count(), affinity=sorted(os.sched_getaffinity(0)), runtime=runtime_versions(),
            device='cpu', profile=args.profile, elapsed_seconds=elapsed,
            completed=len(rows), cache='bypassed in provider-only benchmark',
            limitations=['No OCR/capture or actual audio start measured',
                         'Sequential provider probe, not a FIFO backlog measurement',
                         'Not a long gameplay soak or weak-CPU guarantee',
                         'RSS sums shared mappings, not unique memory'],
            mt_ms=summarize([r['mt_ms'] for r in rows]),
            warm_mt_ms=summarize([r['mt_ms'] for r in rows[1:]]),
            tts_ms=summarize([r['tts_ms'] for r in rows]),
            warm_tts_ms=summarize([r['tts_ms'] for r in rows[1:]]),
            text_to_pcm_ready_ms=summarize([r['text_to_pcm_ready_ms'] for r in rows]),
            peak_rss_bytes=max((s['rss_bytes'] for s in samples), default=0),
            quickmt_peak_rss_bytes=max((s['quickmt_rss_bytes'] for s in samples), default=0),
            cpu_one_core_percent=cpu_seconds/max(.001, elapsed)*100,
            resource_samples=samples, requests=rows)
        with os.fdopen(descriptor, 'w') as output:
            json.dump(report, output, indent=2)
        print(json.dumps({k:v for k,v in report.items() if k not in ('resource_samples','requests')},indent=2),flush=True)


if __name__ == '__main__':
    main()