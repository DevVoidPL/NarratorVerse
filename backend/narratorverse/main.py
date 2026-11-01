from __future__ import annotations
import json
import logging
import os
from pathlib import Path
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from threading import Thread, Event
import time

from PySide6.QtCore import QObject, QTimer, Signal, Qt
from PySide6.QtGui import QGuiApplication
from game_optimization_linux import config
from game_optimization_linux.models.narrator import NormalizedRect
from game_optimization_linux.services.narrator_audio import QtNarratorAudioOutput
from game_optimization_linux.services.narrator_capture import PortalScreenCaptureProvider
from game_optimization_linux.services.narrator_portal import QtPortalScreenCastBackend
from game_optimization_linux.services.narrator_ocr import TesseractOcrProvider
from game_optimization_linux.services.narrator_rapidocr import RapidOcrProvider
from game_optimization_linux.services.narrator_translation import ArgosCTranslate2TranslationProvider
from game_optimization_linux.services.narrator_tts import PiperPolishTtsProvider, validate_piper_voice_config
from .pipeline import StandalonePipeline
from game_optimization_linux.services.narrator_persistence import CaptureGrantRepository
from game_optimization_linux.services.narrator_region import encode_region_preview
from .profiles import Profiles
from .protocol import Writer, decode, MAX_FRAME
from .components import ComponentManager
from .seed import seed
from .quick_read import QuickRead
from .filechooser import import_from_chooser
from .runtime_checks import native_runtimes, tesseract_runtime
from .audio_balance import AudioBalance, list_targets, normalize_speech

class NoGameRequirement:
    def is_active(self, _profile_id): return True

class CaptureGate:
    """Keep portal open while editing/paused; never expose uncropped web capture."""
    def __init__(self, provider):
        self.provider, self.reading, self.frame = provider, False, None
        self.epoch = 0
    def __getattr__(self, name): return getattr(self.provider, name)
    def start(self, request, *, frame_callback, state_callback):
        self.frame = None
        self.epoch += 1
        epoch = self.epoch
        def receive(frame):
            if epoch != self.epoch: return
            self.frame = frame
            if self.reading: frame_callback(frame)
        def state_changed(state, message):
            if epoch == self.epoch: state_callback(state, message)
        self.provider.start(request, frame_callback=receive, state_callback=state_changed)
    def stop(self):
        self.epoch += 1
        self.reading = False
        self.frame = None
        self.provider.stop()

class AudioGate:
    def __init__(self, audio, capture, balance=None):
        self.audio, self.capture, self.balance = audio, capture, balance
        self.normalize = False
    def __getattr__(self, name): return getattr(self.audio, name)
    def play(self, pcm, **kwargs):
        if not self.capture.reading:
            return
        if self.normalize:
            pcm = normalize_speech(pcm)
        if self.balance is not None:
            epoch, request = self.balance.epoch, kwargs['request_id']
            started, completed, failed = kwargs['started_callback'], kwargs['completed_callback'], kwargs['error_callback']
            def on_start(elapsed):
                if (self.capture.reading and kwargs['volume'] > 0
                        and any(pcm.samples)):
                    self.balance.started(epoch, request)
                    self.balance.tick(self.capture.reading)
                started(elapsed)
            def on_terminal():
                self.balance.finished(epoch, request)
                self.balance.tick(self.capture.reading)
            def on_complete():
                self.balance.finished(epoch, request)
                completed()
            def on_error(message):
                self.balance.finished(epoch, request)
                failed(message)
            kwargs = {**kwargs, 'started_callback': on_start,
                      'completed_callback': on_complete, 'error_callback': on_error,
                      'terminal_callback': on_terminal}
        self.audio.play(pcm, **kwargs)
    def stop(self):
        if self.balance is not None: self.balance.reset()
        self.audio.stop()

class Backend(QObject):
    request = Signal(object)
    completed = Signal(object)
    def __init__(self, app, writer):
        super().__init__()
        self.app, self.writer = app, writer
        self.pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix='narratorverse-adapter')
        seed()
        self.profiles = Profiles()
        self.capture = CaptureGate(PortalScreenCaptureProvider(QtPortalScreenCastBackend()))
        self.ocr = TesseractOcrProvider()
        self.rapid = RapidOcrProvider()
        self.translator = ArgosCTranslate2TranslationProvider()
        self.tts = PiperPolishTtsProvider()
        self.balance = AudioBalance(config.STATE_DIR)
        self.audio = AudioGate(QtNarratorAudioOutput(), self.capture, self.balance)
        self.quick = QuickRead(PiperPolishTtsProvider(), self.audio.audio, self.emit)
        self.voice_job = False
        self.voice_cancelled = Event()
        self.components_refreshing = False
        self.region_confirmed = False
        self.region_required = False
        self.pipeline = StandalonePipeline(self.capture, self.ocr, self.translator, self.tts, self.audio, NoGameRequirement(), ocr_providers=(self.rapid,))
        self.manager = ComponentManager(progress=lambda size,total: self.emit('download', {'bytes': size, 'total': total, 'component': self.component_job}))
        self.component_job = ''
        self.component_list = []
        self.preview_pending = False
        self.preview_future = None
        self.closed = False
        self.voice_generation = 0
        self.preview_generation = 0
        self.request.connect(self.handle, Qt.ConnectionType.QueuedConnection)
        self.completed.connect(self.finish_job, Qt.ConnectionType.QueuedConnection)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(150)
        self.apply_ocr()
        self.refresh_components()

    def emit(self, event, data):
        self.writer.send({'event': event, 'data': data})

    def async_job(self, request_id, fn, after=None, generation=None):
        future = self.pool.submit(fn)
        def done(f):
            try: result = {'id': request_id, 'result': f.result(), 'after': after}
            except Exception as error:
                logging.exception('Background operation failed')
                result = {'id': request_id, 'error': str(error), 'after': after}
            result['generation'] = generation
            self.completed.emit(result)
        future.add_done_callback(done)

    def finish_job(self, result):
        after = result.pop('after', None)
        generation = result.pop('generation', None)
        stale = self.closed or (after == 'voice' and generation != self.voice_generation) or (after == 'preview' and generation != self.preview_generation)
        if stale:
            if result.get('id') is not None:
                self.writer.send({'id': result['id'], 'error': 'Operacja anulowana'})
            return
        if after == 'components':
            component = self.component_job
            self.component_job = ''
            if 'error' in result: self.manager.failures[component] = result['error']
            else: self.manager.failures.pop(component, None)
            self.refresh_components()
        if after == 'component_status':
            self.components_refreshing = False
            if 'result' in result:
                self.component_list = result['result']
                self.emit('components', self.component_list)
                self.emit('profiles', self.view())
        if after == 'preview': self.preview_future = None
        if after == 'voice' and 'result' in result:
            pcm = result.pop('result')
            self.audio.audio.play(pcm, volume=self.profiles.settings().volume, request_id=0,
                started_callback=lambda *_: self.emit('voice_preview', {'state': 'playing'}),
                completed_callback=lambda: self.emit('voice_preview', {'state': 'finished'}),
                error_callback=lambda message: self.emit('error', {'message': message}))
            result['result'] = True
        if after == 'voices':
            self.voice_job = False
            self.emit('profiles', self.view())
        if after == 'preview' and 'result' in result:
            self.emit('preview', result['result'])
        elif result.get('id') is not None: self.writer.send(result)
        elif 'error' in result: self.emit('error', {'message': result['error']})

    def view(self):
        def installed(voice):
            if not self.tts.voice_available(voice.voice_id): return False
            try:
                model, configuration = self.tts._voice_paths(voice)
                validate_piper_voice_config(configuration)
                if not model.stat().st_size: return False
                if not voice.custom:
                    component = next((c for c in self.component_list if c['component_id'] == voice.component_id), None)
                    return bool(component and component.get('installed'))
                return True
            except (OSError, ValueError): return False
        return {**self.profiles.data, 'voices': [asdict(v) | {'installed': installed(v)} for v in self.tts.voices], 'paths': {'config': str(config.CONFIG_DIR), 'data': str(config.DATA_DIR), 'cache': str(config.CACHE_DIR), 'state': str(config.STATE_DIR)}}

    def refresh_components(self):
        if self.components_refreshing or self.component_job: return
        self.components_refreshing = True
        def refresh():
            native = native_runtimes()
            tesseract = tesseract_runtime(self.ocr.executable)
            runtime = {'capture.portal-pipewire': self.capture.capabilities().available,
                       'audio.qt-pcm': self.audio.available,
                       'ocr.english-local': tesseract and self.ocr.language_available('en'),
                       'ocr.polish-local': tesseract and self.ocr.language_available('pl'),
                       'ocr.rapidocr-local': native['rapidocr'] and self.rapid.available,
                       'translation.opus-en-pl': native['translation'] and self.translator.available,
                       'tts.voidek': native['piper'] and self.tts.voice_available('voidek-pl-e991')}
            return [self.manager.verified_status(c.component_id, runtime.get(c.component_id, False)) for c in self.manager.list_components()]
        self.async_job(None, refresh, 'component_status')

    def apply_ocr(self):
        options = self.profiles.selected()['ocr']
        mode = options.get('mode', 'automatic')
        if mode not in ('automatic', 'classic'): raise ValueError('Unknown OCR mode')
        self.ocr.set_settings_mode(mode)

    def stop(self):
        self.voice_generation += 1
        self.preview_generation += 1
        self.preview_future = None
        self.capture.reading = False
        self.preview_pending = False
        self.pipeline.stop()
        self.capture.stop()
        self.audio.stop()
        self.region_confirmed = False
        self.region_required = False

    def handle(self, request):
        request_id = request.get('id')
        try:
            method, p = request['method'], request.get('params', {})
            if self.quick.busy and method in ('start','change_source','read','pause','stop','preview','region','profile_create','profile_select','profile_delete'):
                raise RuntimeError('Najpierw zatrzymaj Szybki odczyt. Sesja przechwytywania pozostaje bez zmian.')
            result = True
            if method == 'status':
                result = {'profiles': self.view(), 'components': self.component_list, 'session': self.session(), 'quick_read': self.quick.snapshot()}
            elif method == 'quick_settings': result = self.quick.save(p['values'])
            elif method == 'audio_targets':
                self.async_job(request_id, list_targets); return
            elif method == 'quick_read':
                if self.voice_job: raise RuntimeError('Poczekaj na zakończenie importu głosu')
                result = self.quick.start(p.get('text'), p.get('options', {}), live_reading=self.capture.reading, component_job=bool(self.component_job))
            elif method == 'quick_stop': result = self.quick.stop()
            elif method == 'profile_create':
                self.stop(); result = self.profiles.create(p['name']); self.apply_ocr()
            elif method == 'profile_select':
                self.stop(); self.profiles.select(p['id']); self.apply_ocr()
            elif method == 'profile_rename':
                self.profiles.rename(p['name'])
            elif method == 'profile_delete':
                if len(self.profiles.data['profiles']) <= 1: raise ValueError('Zachowaj przynajmniej jeden profil')
                self.stop()
                key = self.profiles.selected()['id']
                self.profiles.delete()
                CaptureGrantRepository().save_token(key, '')
                self.apply_ocr()
            elif method == 'settings':
                if self.pipeline.active: raise RuntimeError('Zatrzymaj sesję przed zmianą ustawień')
                mode = p.get('ocr_mode', self.profiles.selected()['ocr'].get('mode', 'automatic'))
                if mode not in ('automatic', 'classic'): raise ValueError('Unknown OCR mode')
                self.profiles.update(p['values'], ocr_mode=mode)
                self.apply_ocr()
            elif method == 'ocr_options':
                if self.pipeline.active: raise RuntimeError('Zatrzymaj sesję przed zmianą OCR')
                mode = p['mode']
                if mode not in ('automatic','classic'): raise ValueError('Unknown OCR mode')
                self.profiles.update({}, ocr_mode=mode); self.apply_ocr()
            elif method == 'reset':
                if self.pipeline.active: raise RuntimeError('Zatrzymaj sesję przed resetem')
                self.profiles.reset(p['section']); self.apply_ocr()
            elif method in ('start', 'change_source'):
                if self.quick.busy: raise RuntimeError('Najpierw zatrzymaj Szybki odczyt')
                if self.component_job: raise RuntimeError('Zaczekaj na zakończenie operacji komponentu')
                self.stop()
                self.region_required = True
                if method == 'change_source': CaptureGrantRepository().save_token(self.profiles.selected()['id'], '')
                self.pipeline.start(self.profiles.settings())
                self.preview_pending = True
            elif method == 'read':
                if self.quick.busy: raise RuntimeError('Najpierw zatrzymaj Szybki odczyt')
                if not self.pipeline.active or self.capture.frame is None: raise RuntimeError('Najpierw wybierz źródło i zaczekaj na klatkę')
                if not self.region_confirmed: raise RuntimeError('Najpierw potwierdź obszar napisów w podglądzie')
                audio_settings = self.profiles.settings()
                self.balance.configure(audio_settings)
                self.audio.normalize = audio_settings.normalize_narrator
                self.capture.reading = True
            elif method == 'pause':
                self.voice_generation += 1
                self.capture.reading = False
                self.pipeline.pause_processing()
            elif method == 'stop': self.stop()
            elif method == 'preview':
                self.capture.reading = False
                self.pipeline.pause_processing()
                self.preview_generation += 1
                self.preview_future = None
                self.preview_pending = True
            elif method == 'region':
                rect = NormalizedRect(**p['rect'])
                self.capture.reading = False
                self.pipeline.pause_processing()
                self.preview_generation += 1
                self.preview_future = None
                self.profiles.update({'subtitle_region': rect.to_dict()})
                self.region_confirmed = True
                self.region_required = False
                if self.pipeline.active:
                    # Region is immutable in settings; replace atomically without restarting portal/models.
                    with self.pipeline._lock:
                        self.pipeline._settings = replace(self.pipeline._settings, subtitle_region=rect, subtitle_region_source='saved')
                        self.pipeline._stabilizer.reset()
                self.preview_pending = False
            elif method == 'components_refresh': self.refresh_components()
            elif method == 'component_cancel': self.manager.cancelled.set()
            elif method == 'component':
                if self.quick.busy or self.voice_job or self.components_refreshing: raise RuntimeError('Poczekaj na zakończenie odczytu, importu lub sprawdzania komponentów')
                if self.component_job: raise RuntimeError('Inna operacja komponentu jest w toku')
                if self.pipeline.active: raise RuntimeError('Zatrzymaj lektora przed zmianą komponentów')
                component, action = p['component'], p['action']
                self.component_job = component
                self.manager.cancelled.clear()
                def work():
                    if action in ('install','repair'):
                        bundled = config.BUNDLED_NARRATOR_COMPONENTS_DIR
                        definition = self.manager._definition(component)
                        if definition.pinned_files:
                            self.manager.install_local(component, {item.target_relative_path: bundled / component / item.target_relative_path for item in definition.pinned_files})
                            (self.manager.root / component / '.narratorverse-origin').write_text('bundled\n')
                            return True
                        self.manager.install(component)
                        (self.manager.root / component / '.narratorverse-origin').write_text('downloaded\n')
                        return True
                    if action == 'verify': return self.manager.verify_installed(component)
                    if action == 'remove': return self.manager.remove(component)
                    raise ValueError('Unknown component action')
                self.async_job(request_id, work, 'components'); return
            elif method == 'voice_import':
                if self.pipeline.active or self.component_job or self.quick.busy or self.voice_job: raise RuntimeError('Zatrzymaj lektora, Szybki odczyt i operacje komponentów')
                self.voice_job = True
                self.voice_cancelled.clear()
                self.async_job(request_id, lambda: import_from_chooser(self.tts, self.voice_cancelled), 'voices'); return
            elif method == 'voice_remove':
                if self.pipeline.active or self.component_job or self.quick.busy or self.voice_job: raise RuntimeError('Zatrzymaj lektora, Szybki odczyt i operacje komponentów')
                self.voice_job = True
                self.async_job(request_id, lambda: self.tts.remove_custom_voice(p['id']), 'voices'); return
            elif method == 'voice_preview':
                s = self.profiles.settings()
                result = self.quick.start(p.get('text') or 'Cześć! Jestem Voidek.', {'voice_id': s.voice_id, 'speech_rate': s.speech_rate, 'volume': s.volume}, live_reading=self.capture.reading, component_job=bool(self.component_job))
            elif method == 'shutdown':
                self.shutdown(); return
            else: raise ValueError('Unknown method: ' + method)
            self.writer.send({'id': request_id, 'result': result})
            if method.startswith('profile_') or method in ('settings','reset','ocr_options','region'):
                self.emit('profiles', self.view())
        except Exception as error:
            logging.exception('Request failed')
            self.writer.send({'id': request_id, 'error': str(error)})

    def session(self):
        snap = asdict(self.pipeline.snapshot)
        snap['audio_balance'] = self.balance.snapshot()
        state = snap.get('capture_state')
        failed = state in ('error', 'source_lost', 'permission_denied', 'restore_failed', 'unavailable', 'cancelled') or snap.get('status') == 'error'
        if failed: ui_state = 'failed'
        elif not self.pipeline.active: ui_state = 'empty'
        elif not self.capture.frame: ui_state = 'selecting_source' if state in ('permission_required', 'selecting_source') else 'starting'
        elif self.capture.reading: ui_state = 'reading'
        elif not self.region_confirmed: ui_state = 'selecting_region'
        else: ui_state = 'paused'
        return {'snapshot': snap, 'ui_state': ui_state, 'region_confirmed': self.region_confirmed, 'reading': self.capture.reading and not failed, 'active': self.pipeline.active, 'has_frame': self.capture.frame is not None and not failed, 'source': self.profiles.settings().capture_source, 'frames': self.capture.frames_received, 'variant': self.capture.negotiated_variant, 'restarts': self.capture.restarts, 'component_job': self.component_job, 'components_refreshing': self.components_refreshing, 'voice_job': self.voice_job}

    def tick(self):
        if (self.pipeline.snapshot.capture_state in ('source_lost', 'error', 'permission_denied', 'cancelled', 'restore_failed', 'unavailable')
                or self.pipeline.snapshot.status == 'error'):
            if self.capture.reading:
                self.capture.reading = False
                self.pipeline.pause_processing()
            self.region_confirmed = False
        self.balance.tick(self.capture.reading)
        for event in self.pipeline.drain_events(): self.emit('narrator', asdict(event))
        self.emit('session', self.session())
        self.emit('components', self.component_list)
        if self.preview_pending and self.capture.frame and not self.preview_future:
            self.preview_pending = False
            frame = self.capture.frame
            self.preview_future = True
            self.async_job(None, lambda: encode_region_preview(frame).to_dict(), 'preview', self.preview_generation)

    def shutdown(self):
        if self.closed: return
        self.closed = True
        self.timer.stop()
        self.manager.cancelled.set()
        self.voice_cancelled.set()
        self.stop()
        self.balance.close()
        self.quick.shutdown()
        self.pipeline.shutdown()
        for provider in (self.ocr, self.rapid, self.translator, self.tts): provider.close()
        self.capture.close()
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.app.quit()

def main():
    # Native libraries printing to fd 1 cannot corrupt the protocol.
    protocol_stream = os.fdopen(os.dup(sys.stdout.fileno()), 'w', buffering=1)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    sys.stdout = sys.stderr
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    for p in (config.CONFIG_DIR, config.STATE_DIR, config.CACHE_DIR, config.DATA_DIR):
        p.mkdir(parents=True, exist_ok=True, mode=0o700)
    app = QGuiApplication(['NarratorVerse-backend'])
    app.setApplicationName(config.APP_NAME)
    app.setOrganizationDomain(config.APP_ID)
    app.setDesktopFileName(config.APP_ID)
    backend = Backend(app, Writer(protocol_stream))
    def read():
        try:
            while True:
                line = sys.stdin.buffer.readline(MAX_FRAME + 1)
                if not line: break
                try: backend.request.emit(decode(line))
                except Exception as error: backend.emit('error', {'message': str(error)})
        finally: backend.request.emit({'method': 'shutdown'})
    Thread(target=read, daemon=True, name='narratorverse-ipc').start()
    signal.signal(signal.SIGTERM, lambda *_: backend.request.emit({'method': 'shutdown'}))
    signal.signal(signal.SIGINT, lambda *_: backend.request.emit({'method': 'shutdown'}))
    app.aboutToQuit.connect(backend.shutdown)
    backend.emit('ready', {'version': config.APP_VERSION})
    app.exec()

if __name__ == '__main__': main()