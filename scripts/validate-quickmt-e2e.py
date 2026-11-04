#!/usr/bin/env python3
"""Opt-in validation of the built backend; isolated XDG dirs required.

Run inside `flatpak build --runtime`; never tests GUI, portals or audible audio.
The install phase uses Backend.handle, not a separate model downloader.
"""
import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import wave

sys.path[:0] = ['/app/share/narratorverse/backend', '/app/lib/python3.13/site-packages']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('install', 'offline'))
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    if not work.is_dir() or not (work / '.isolated-validation').is_file():
        parser.error('Create a dedicated directory with .isolated-validation first')
    if (work / (args.phase + '-report.json')).exists() or (
            args.phase == 'offline' and any(work.glob('quickmt-*.wav'))):
        parser.error('Refusing to overwrite validation evidence')
    for name, directory in [('XDG_DATA_HOME', 'data'), ('XDG_CONFIG_HOME', 'config'),
                            ('XDG_CACHE_HOME', 'cache'), ('XDG_STATE_HOME', 'state')]:
        os.environ[name] = str(work / directory)
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    # Match /app/share/narratorverse/bin/backend for subprocess workers too.
    os.environ['PYTHONPATH'] = '/app/share/narratorverse/backend:/app/lib/python3.13/site-packages'
    from PySide6.QtGui import QGuiApplication
    from narratorverse.main import Backend
    from narratorverse.quickmt_model import QUICKMT_COMPONENT_ID, QUICKMT_DOWNLOAD_FILES
    from game_optimization_linux.models.narrator import NarratorSubtitleLanguageMode
    from game_optimization_linux.services.narrator_pipeline import _AcceptedSubtitleTiming

    class Writer:
        def __init__(self):
            self.messages = []

        def send(self, value):
            self.messages.append(value)

    app = QGuiApplication(['NarratorVerse-QuickMT-validation'])
    writer = Writer()
    backend = Backend(app, writer)

    def wait(predicate, timeout):
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() >= deadline:
                raise TimeoutError('Backend operation timed out')
            app.processEvents()
            time.sleep(0.02)

    report = {'phase': args.phase, 'gui_portal_audio': 'NOT_TESTED'}
    try:
        wait(lambda: not backend.components_refreshing, 120)
        model = backend.manager.root / QUICKMT_COMPONENT_ID
        if args.phase == 'install':
            if model.exists():
                raise RuntimeError('Installation must begin without an existing model')
            backend.handle({'id': 100, 'method': 'component', 'params': {
                'component': QUICKMT_COMPONENT_ID, 'action': 'install'}})
            wait(lambda: any(m.get('id') == 100 for m in writer.messages), 1200)
            response = next(m for m in writer.messages if m.get('id') == 100)
            if response.get('error') or response.get('result') is not True:
                raise RuntimeError(str(response))
            assert (model / '.narratorverse-origin').read_text().strip() == 'downloaded'
            report['application_component_install'] = 'PASS'
        good, message = backend.manager.verify_installed(QUICKMT_COMPONENT_ID)
        if not good:
            raise RuntimeError(message)
        report['pinned_files'] = {}
        for name, (size, _, digest) in QUICKMT_DOWNLOAD_FILES.items():
            path = model / name
            with path.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            assert path.stat().st_size == size and actual == digest, name
            report['pinned_files'][name] = {'bytes': size, 'sha256': actual}
        # Same-size corruption: verification must reject bytes, not just length.
        config = model / 'config.json'
        original = config.read_bytes()
        try:
            config.write_bytes(bytes([original[0] ^ 1]) + original[1:])
            assert not backend.manager.verify_installed(QUICKMT_COMPONENT_ID)[0]
            assert not backend.translator.available
        finally:
            config.write_bytes(original)
        assert backend.manager.verify_installed(QUICKMT_COMPONENT_ID)[0]
        assert backend.translator.available
        report['same_size_corruption_rejected_and_restored'] = 'PASS'
        if args.phase == 'offline':
            texts = ['Do not open the door. Wait for me!',
                     'We need to find a safe place before nightfall.']
            traces, played = [], []
            pipeline = backend.pipeline
            pipeline._diagnostic = lambda event, **fields: traces.append(dict(event=event, **fields))

            class FileAudio:
                """Only the output device is replaced; synthesis is real."""
                available = True
                provider_id = 'validation-wave-file-no-playback'

                def play(self, pcm, **kwargs):
                    assert pcm.samples
                    path = work / ('quickmt-%d.wav' % (len(played) + 1))
                    with wave.open(str(path), 'wb') as output:
                        output.setnchannels(pcm.channels)
                        assert pcm.sample_format == 's16le'
                        output.setsampwidth(2)
                        output.setframerate(pcm.sample_rate)
                        output.writeframes(pcm.samples)
                    played.append({'text': kwargs['text'], 'wav': str(path),
                                   'pcm_bytes': len(pcm.samples)})
                    kwargs['started_callback'](0.0)
                    kwargs['completed_callback']()
                    if kwargs.get('terminal_callback'):
                        kwargs['terminal_callback']()

                def stop(self):
                    pass

            pipeline.audio = FileAudio()
            pipeline._settings = replace(backend.profiles.settings(), enabled=True,
                subtitle_language_mode=NarratorSubtitleLanguageMode.ENGLISH_TO_POLISH,
                adaptive_speech_rate=False, translation_profile_id='balanced')
            pipeline._session_id = 'isolated-quickmt-validation'
            # Enter exactly at the accepted-subtitle queue boundary. No claim of
            # capture/OCR coverage; those are separate tests.
            now = time.monotonic()
            timing = _AcceptedSubtitleTiming(now, now, now, 0, 0, 0, 0, 0, now)
            for index, text in enumerate(texts, 1):
                pipeline._deduplicator.reserve(index, text)
                pipeline._narration_queue.append((text, timing, index))
            pipeline._drain_narration_queue()
            wait(lambda: len(played) == len(texts) or
                 pipeline._snapshot.translation_status == 'error' or
                 pipeline._snapshot.tts_status == 'error', 300)
            translations = [e for e in traces if e['event'] == 'translation_output']
            assert len(played) == len(texts) and len(translations) == len(texts), traces
            assert [e['source_text'] for e in translations] == texts
            assert all(not e['cached'] and e['text'].strip() and e['text'] != e['source_text']
                       for e in translations)
            assert [p['text'] for p in played] == [e['text'] for e in translations]
            assert not pipeline._narration_queue
            report.update(offline_translation_queue_piper='PASS', translations=translations,
                          synthesized=played, trace=traces)
        output = work / (args.phase + '-report.json')
        if output.exists():
            raise RuntimeError('Refusing to overwrite previous report')
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    finally:
        backend.shutdown()


if __name__ == '__main__':
    main()