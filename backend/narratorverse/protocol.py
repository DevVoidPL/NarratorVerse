"""Bounded, newline-framed UTF-8 JSON; stdout is protocol-only."""
import dataclasses
import datetime
import enum
import json
from pathlib import Path
from threading import Lock

MAX_FRAME = 16 * 1024 * 1024

def serial(value):
    if dataclasses.is_dataclass(value): return dataclasses.asdict(value)
    if isinstance(value, (datetime.datetime, Path)): return str(value)
    if isinstance(value, enum.Enum): return value.value
    if isinstance(value, (set, frozenset, tuple)): return list(value)
    raise TypeError(type(value).__name__)

class Writer:
    def __init__(self, stream):
        self.stream, self.lock = stream, Lock()

    def send(self, value):
        payload = json.dumps(value, ensure_ascii=False, default=serial, allow_nan=False) + '\n'
        if len(payload.encode()) > MAX_FRAME: raise ValueError('IPC frame too large')
        with self.lock:
            self.stream.write(payload)
            self.stream.flush()

def decode(line):
    if len(line) > MAX_FRAME: raise ValueError('IPC frame too large')
    value = json.loads(line)
    if not isinstance(value, dict) or not isinstance(value.get('method'), str):
        raise ValueError('Invalid request envelope')
    if not isinstance(value.get('params', {}), dict): raise ValueError('Invalid params')
    return value