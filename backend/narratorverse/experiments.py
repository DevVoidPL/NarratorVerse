"""Developer-only opt-in private dialogue JSONL traces; no behavior switches."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from queue import Queue, Full, Empty
from threading import Thread, Lock, Event
import time
from uuid import uuid4


class DialogueTrace:
    """Nonblocking producer; bounded writer queue, never on the inference path.

    Full text is intentional and opt-in. Existing files/symlinks are refused.
    Trace loss is counted and reported, never silently labelled a complete run.
    """
    def __init__(self, path, *, run_id='', clock=time.monotonic):
        if not Path(path).is_absolute():
            raise ValueError("Diagnostic trace must be an absolute path")
        self.run_id = run_id or uuid4().hex
        self.clock = clock
        self.dropped = 0
        self.error = ''
        self._queue = Queue(maxsize=4096)
        self._closed = False
        self._producer_lock = Lock()
        self._stop = Event()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self._stream = os.fdopen(fd, 'w', encoding='utf-8')
        self._thread = Thread(target=self._write, daemon=True, name='narratorverse-trace')
        self._thread.start()

    def emit(self, event, **fields):
        record = dict(fields, event=event, monotonic=self.clock(), run_id=self.run_id)
        # Serialize only enqueue/close, never file I/O. Nothing may be enqueued
        # after shutdown has established the end of this run.
        with self._producer_lock:
            if self._closed:
                return
            try:
                self._queue.put_nowait(record)
            except Full:
                self.dropped += 1

    def _write(self):
        try:
            while True:
                try:
                    record = self._queue.get(timeout=0.1)
                except Empty:
                    # A producer may enqueue between get() timing out and
                    # close() setting stop. After stop no producer can enqueue.
                    if self._stop.is_set() and self._queue.empty():
                        break
                    continue
                self._stream.write(json.dumps(record, ensure_ascii=False) + '\n')
                self._stream.flush()
            self._stream.write(json.dumps(dict(event='trace_closed', run_id=self.run_id,
                                   dropped_events=self.dropped, monotonic=self.clock())) + '\n')
        except (OSError, ValueError, TypeError) as error:
            self.error = str(error)
            logging.getLogger(__name__).error('Experimental trace failed: %s', error)
        finally:
            self._stream.close()

    def close(self):
        with self._producer_lock:
            self._closed = True
            self._stop.set()
        # A full queue must not prevent shutdown signalling. The writer drains
        # it even when this bounded wait expires; no sentinel can be lost.
        self._thread.join(timeout=2)
        if self._thread.is_alive() or self.dropped or self.error:
            logging.getLogger(__name__).warning(
                'Experimental trace incomplete: dropped=%d error=%s writer_alive=%s',
                self.dropped, self.error, self._thread.is_alive())