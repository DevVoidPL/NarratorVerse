"""Adapter runtime probes; controlled results, not real native load evidence."""
import subprocess
from types import SimpleNamespace
from unittest.mock import patch
from narratorverse.runtime_checks import native_runtimes, tesseract_runtime


def test_native_imports_fail_closed_and_parse_last_line():
    with patch('narratorverse.runtime_checks.subprocess.run',return_value=SimpleNamespace(stdout='library log\n{"piper":true,"rapidocr":false,"translation":true}\n')):
        assert native_runtimes()=={'piper':True,'rapidocr':False,'translation':True}
    for error in (OSError('missing'),subprocess.TimeoutExpired('probe',25)):
        with patch('narratorverse.runtime_checks.subprocess.run',side_effect=error):
            assert not any(native_runtimes().values())


def test_native_executable_must_actually_run():
    with patch('narratorverse.runtime_checks.subprocess.run',return_value=SimpleNamespace(returncode=0)):
        assert tesseract_runtime('/verified/tesseract')
    with patch('narratorverse.runtime_checks.subprocess.run',side_effect=OSError('bad shared library')):
        assert not tesseract_runtime('/broken/tesseract')