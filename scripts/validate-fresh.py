#!/usr/bin/env python3
"""Offline smoke checks inside a newly built Flatpak; no user configuration writes."""
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, '/app/share/narratorverse/backend')
sys.path.insert(0, '/app/lib/python3.13/site-packages')


def main():
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtMultimedia import QAudioSink
    from PIL import Image, ImageDraw
    from game_optimization_linux.services.narrator_components import NarratorComponentManager
    from game_optimization_linux.services.narrator_ocr_worker import TesseractApiEngine
    from game_optimization_linux.services.narrator_rapidocr_worker import RapidEngine
    from game_optimization_linux.services.narrator_piper_worker import _load_voice, _synthesize
    from narratorverse.quickmt_runtime import inspect_runtime
    app = QGuiApplication.instance() or QGuiApplication(['NarratorVerse-offline-validation'])
    root = Path('/app/share/narratorverse/components')
    manager = NarratorComponentManager(root)
    for component in ('ocr.english-local', 'ocr.polish-local', 'ocr.rapidocr-local', 'tts.voidek'):
        good, message = manager.verify_installed(component)
        if not good:
            raise RuntimeError(component + ': ' + message)
    image = Image.new('RGB', (1000, 100), 'white')
    ImageDraw.Draw(image).text((20, 20), 'NarratorVerse test 123', fill='black', font_size=42)
    output = BytesIO()
    image.save(output, format='PNG')
    for language, component in [('eng', 'ocr.english-local'), ('pol', 'ocr.polish-local')]:
        engine = TesseractApiEngine(root / component / 'tessdata' / (language + '.traineddata'), language)
        try:
            text = engine.recognize_png(output.getvalue(), source_resolution=150)
            if '123' not in text:
                raise RuntimeError('Tesseract smoke text mismatch: ' + language)
        finally:
            engine.close()
    rapid = RapidEngine(root / 'ocr.rapidocr-local/rapidocr/models')
    result = rapid.recognize(output.getvalue())
    if not result['lines']:
        raise RuntimeError('RapidOCR smoke image returned no lines')
    voices = root / 'tts.voidek/voices'
    voice = _load_voice(voices / 'voidek-pl-e991.onnx', voices / 'voidek-pl-e991.onnx.json')
    audio = _synthesize(voice, 'Test nowego pakietu NarratorVerse.', 1.0)
    if not audio.get('samples_base64'):
        raise RuntimeError('Piper returned empty audio')
    runtime = inspect_runtime()
    if not runtime['ok']:
        raise RuntimeError('QuickMT CPU runtime unavailable: ' + str(runtime))
    for element in ('pipewiresrc', 'queue', 'videoconvert', 'videorate', 'pnmenc', 'fdsink',
                    'glupload', 'glcolorconvert', 'gldownload'):
        subprocess.run(['gst-inspect-1.0', element], stdout=subprocess.DEVNULL, check=True)
    subprocess.run(['pactl', '--version'], check=True)
    libraries = subprocess.run(['ldd', '/app/bin/narratorverse'], capture_output=True, text=True, check=True)
    if 'not found' in libraries.stdout:
        raise RuntimeError(libraries.stdout)
    print(json.dumps({'offline_smoke': 'PASS', 'quickmt_runtime': runtime,
                      'interactive_portal_audio_game_session': 'NOT_TESTED'}, indent=2))


if __name__ == '__main__':
    main()