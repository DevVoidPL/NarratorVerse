"""Import native runtimes in a disposable process, not just find_spec()."""
import json
import subprocess
import sys

SCRIPT = '''
import importlib, json
groups = {'piper': ('piper.voice', 'onnxruntime'),
          'rapidocr': ('rapidocr', 'onnxruntime'),
          'translation': ('ctranslate2', 'sentencepiece')}
results = {}
for name, modules in groups.items():
    try:
        for module in modules: importlib.import_module(module)
        results[name] = True
    except Exception:
        results[name] = False
print(json.dumps(results))
'''


def native_runtimes():
    try:
        result = subprocess.run([sys.executable, '-c', SCRIPT], capture_output=True, text=True, timeout=25, check=True)
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return {'piper': False, 'rapidocr': False, 'translation': False}


def tesseract_runtime(executable):
    try:
        return subprocess.run([str(executable), '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False).returncode == 0
    except (OSError, subprocess.SubprocessError): return False