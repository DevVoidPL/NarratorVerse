"""Independent restoration owner. EOF or expired heartbeat releases ducking."""
import fcntl
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
from threading import Thread
import time

from .audio_balance import BalanceEngine, Pactl, validate_target


def write_journal(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.audio-balance-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(entries, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validated_message(data):
    if (not isinstance(data, dict) or type(data.get('enabled')) is not bool
            or type(data.get('active')) is not bool or type(data.get('reading')) is not bool
            or isinstance(data.get('db'), bool)
            or not isinstance(data.get('db'), (int, float))
            or type(data.get('epoch', 0)) is not int or data.get('epoch', 0) < 0
            or not -24 <= data['db'] <= -3):
        raise ValueError('Invalid audio balance command')
    return {**data, 'target': validate_target(data.get('target'))}


def receive(messages):
    try:
        for line in sys.stdin:
            if len(line) > 4096:
                break
            data = validated_message(json.loads(line))
            # Latest state, bounded memory, no queue of obsolete heartbeats.
            try:
                messages.get_nowait()
            except queue.Empty:
                pass
            messages.put_nowait((time.monotonic(), data))
    except (ValueError, OSError, queue.Full):
        pass
    finally:
        # A separate EOF flag cannot be overwritten by a pending heartbeat.
        ended[0] = True


ended = [False]


def main(directory):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / 'audio-balance.lock').open('a') as lock:
        # Only one worker can own a journal or manipulate baselines.
        fcntl.flock(lock, fcntl.LOCK_EX)
        journal = root / 'audio-balance-recovery.json'
        mixer = Pactl()
        engine = BalanceEngine(mixer, lambda entries: write_journal(journal, entries))
        if journal.exists():
            saved = json.loads(journal.read_text())
            if not isinstance(saved, dict):
                raise ValueError('Invalid audio recovery journal')
            engine.entries = saved
        messages = queue.Queue(maxsize=1)
        Thread(target=receive, args=(messages,), daemon=True).start()
        options = {'enabled': False, 'target': '', 'db': -12.0, 'active': False, 'reading': False}
        received = 0
        configured = None
        last_status = None
        failed = False
        recovering = bool(engine.entries)
        while True:
            now = time.monotonic()
            try:
                received, options = messages.get_nowait()
            except queue.Empty:
                pass
            exiting = ended[0]
            expired = now - received > 1.5
            target = options['target'] if options['enabled'] and options['reading'] and not expired and not failed else ''
            try:
                streams = mixer.streams()
                if recovering or exiting or failed:
                    engine.restore(streams)
                    recovering = False
                    streams = mixer.streams()
                if exiting:
                    break
                config = (target, options['db'], options.get('epoch', 0))
                if config != configured:
                    engine.configure(target, options['db'], streams)
                    configured = config
                    # Configuration may restore levels. Never re-capture the
                    # pre-restoration snapshot as the next original baseline.
                    streams = mixer.streams()
                engine.step(streams, active=bool(options['active'] and not expired), now=now)
                state = 'error' if failed else engine.state
                error = 'Audio operation failed; pause and resume reading to retry.' if failed else ''
                if failed:
                    engine.target = ''
                if state == 'changed':
                    error = 'Game audio stream changed. Check its normal mixer volume, then pause and resume reading.'
                status = {'state': state, 'error': error}
            except Exception as error:
                # No more ducking after errors. Keep journal and retry release,
                # including after parent death while the audio server recovers.
                failed = True
                recovering = True
                engine.target = ''
                status = {'state': 'error', 'error': str(error)[:300]}
            if status != last_status:
                try:
                    print(json.dumps(status), flush=True)
                except (BrokenPipeError, OSError):
                    ended[0] = True
                last_status = status
            if failed and not engine.entries:
                break
            time.sleep(.05 if not failed and target else .25 if not failed else .5)


if __name__ == '__main__':
    main(sys.argv[1])