"""Direct text-to-speech adapter. No capture, OCR, translation or profile writes."""
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, Signal, Qt
from game_optimization_linux.config import CONFIG_DIR
from game_optimization_linux.services.narrator_persistence import _atomic_json_write

EXAMPLE = 'Cześć! Jestem Voidek. Wklej tekst, a przeczytam go na głos.'
DEFAULTS = {'voice_id': 'voidek-pl-e991', 'speech_rate': 1.0, 'volume': .85}
MAX_TEXT = 10000


def validate_options(values):
    result = {**DEFAULTS, **values}
    for key, low, high in (('speech_rate', .5, 2), ('volume', 0, 1)):
        value = result[key]
        if isinstance(value, bool): raise ValueError('Nieprawidłowe tempo lub głośność')
        value = float(value)
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError('Tempo: 0,5–2; głośność: 0–1')
        result[key] = value
    if not isinstance(result['voice_id'], str): raise ValueError('Wybierz głos')
    return {key: result[key] for key in DEFAULTS}


def chunks(text):
    if not isinstance(text, str) or not text.strip(): raise ValueError('Wpisz tekst do przeczytania')
    if len(text) > MAX_TEXT: raise ValueError('Tekst może mieć najwyżej 10 000 znaków')
    words = re.findall(r'\S+', text)
    parts, current = [], ''
    for word in words:
        # Bound even a single enormous word; do not allocate minutes of PCM at once.
        for offset in range(0, len(word), 350):
            piece = word[offset:offset + 350]
            if current and len(current) + len(piece) + 1 > 350:
                parts.append(current); current = ''
            current = (current + ' ' + piece).strip()
    if current: parts.append(current)
    return parts


class QuickRead(QObject):
    completed = Signal(object)

    def __init__(self, tts, audio, emit, path=CONFIG_DIR / 'quick-read.json'):
        super().__init__()
        self.tts, self.audio, self.emit, self.path = tts, audio, emit, Path(path)
        self.options = dict(DEFAULTS)
        if self.path.exists(): self.options = validate_options(json.loads(self.path.read_text()))
        self.state, self.error, self.required = 'idle', '', ''
        self.generation, self.index, self.parts = 0, 0, []
        self.cancelled = Event()
        self.closed = False
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='narratorverse-quick')
        self.completed.connect(self._finished, Qt.ConnectionType.QueuedConnection)

    @property
    def busy(self): return self.state in ('synthesizing', 'playing', 'stopping')

    def snapshot(self):
        return {'state': self.state, 'error': self.error, 'required_component': self.required,
                'options': dict(self.options), 'part': min(self.index + 1, len(self.parts)), 'parts': len(self.parts)}

    def notify(self): self.emit('quick_read', self.snapshot())

    def save(self, values):
        if self.busy: raise RuntimeError('Zatrzymaj odczyt przed zmianą ustawień')
        options = validate_options({**self.options, **values})
        _atomic_json_write(self.path, options)
        self.options = options
        self.notify()
        return self.snapshot()

    def start(self, text, options, *, live_reading=False, component_job=False):
        if self.closed: raise RuntimeError('Silnik został zamknięty')
        if self.busy: raise RuntimeError('Trwa odczyt. Najpierw naciśnij Stop.')
        if live_reading: raise RuntimeError('Wstrzymaj czytanie napisów przed Szybkim odczytem. Źródło może pozostać otwarte.')
        if component_job: raise RuntimeError('Poczekaj na zakończenie operacji komponentu')
        parts = chunks(text)
        selected = validate_options({**self.options, **options})
        voice = selected['voice_id'] or DEFAULTS['voice_id']
        if voice not in self.tts.available_voice_ids:
            self.state, self.required = 'error', 'tts.voidek' if voice == DEFAULTS['voice_id'] else 'custom-voice'
            self.error = 'Brak wybranego głosu lub środowiska Piper. Zainstaluj Voidek w Komponentach albo wybierz dostępny własny głos.'
            self.notify()
            raise RuntimeError(self.error)
        if not self.audio.available:
            self.state, self.required, self.error = 'error', 'audio.qt-pcm', 'Brak urządzenia wyjścia dźwięku. Sprawdź ustawienia dźwięku systemu.'
            self.notify(); raise RuntimeError(self.error)
        self.save(selected)
        self.generation += 1
        self.cancelled = Event()
        self.parts, self.index, self.error, self.required = parts, 0, '', ''
        self._synthesize()
        return self.snapshot()

    def _synthesize(self):
        self.state = 'synthesizing'; self.notify()
        generation, cancelled, options = self.generation, self.cancelled, dict(self.options)
        text = self.parts[self.index]
        def work():
            try:
                if cancelled.is_set(): return None
                return self.tts.synthesize(text, language='pl', voice_id=options['voice_id'], speech_rate=options['speech_rate'])
            finally:
                # Stop may race with initial worker construction. Close again after inference.
                if cancelled.is_set(): self.tts.close()
        future = self.pool.submit(work)
        def done(f):
            try: payload = {'generation': generation, 'pcm': f.result(), 'volume': options['volume']}
            except Exception as error: payload = {'generation': generation, 'error': str(error)}
            self.completed.emit(payload)
        future.add_done_callback(done)

    def _finished(self, result):
        if self.closed or result['generation'] != self.generation: return
        if result.get('stopped'):
            self.state = 'stopped'; self.notify(); return
        if result.get('error'):
            self.state, self.error = 'error', result['error']; self.notify(); return
        pcm = result.get('pcm')
        if pcm is None: return
        generation = self.generation
        self.audio.play(pcm, volume=result['volume'], request_id=generation,
                        started_callback=lambda *_: self._playing(generation),
                        completed_callback=lambda: self._next(generation),
                        error_callback=lambda message: self._audio_error(generation, message))

    def _playing(self, generation):
        if generation != self.generation: return
        self.state = 'playing'; self.notify()

    def _next(self, generation):
        if generation != self.generation: return
        self.index += 1
        if self.index < len(self.parts): self._synthesize()
        else:
            self.state = 'finished'; self.notify()
            self.pool.submit(self.tts.close)

    def _audio_error(self, generation, message):
        if generation != self.generation: return
        self.state, self.error = 'error', message; self.notify()
        self.pool.submit(self.tts.close)

    def stop(self):
        if not self.busy: return self.snapshot()
        self.generation += 1; generation = self.generation
        self.cancelled.set()
        self.state = 'stopping'; self.notify()
        self.audio.stop()
        self.tts.cancel()
        future = self.pool.submit(self.tts.close)
        future.add_done_callback(lambda _: self.completed.emit({'generation': generation, 'stopped': True}))
        return self.snapshot()

    def shutdown(self):
        self.stop(); self.closed = True
        self.pool.shutdown(wait=True, cancel_futures=True)
        self.tts.close()