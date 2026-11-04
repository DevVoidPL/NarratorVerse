# P0 terminal/lifetime review — 2026-11-04

Public-safe historical report/procedure: `<private-...>` paths are descriptive
placeholders, not supplied evidence or runnable paths. Raw logs, JSONL, WAV and
packages are intentionally not published. Test counts below are historical.
Source publication does not authorize binary release or close P0.

Scope: dirty `release/0.2.0-beta.1`, private Arch candidate, no publication.
No independent reviewer/subagent execution was available in this environment;
this is an explicit source review plus executable regression validation.

## Findings addressed before build

`QtNarratorAudioOutput._notify_failure` previously called only the error observer.
The production pipeline error observer released its reservation, but an observer
exception or a different caller could skip terminal cleanup. It now invokes the
single-use terminal observer in `finally`.

More importantly, the queued Qt `_start` path did not catch device/sink factory
or start exceptions. Those exceptions occur after `pipeline.audio.play` returns,
so the pipeline submission try/except cannot release the request. `_start` now
cleans up partial sink/buffer state, reports failure and terminates the request.
FIFO draining continues past failed waiters. Tests before the fix: 3 failed,
6 passed, preserved in the audit `terminal-red.log`.

## Path coverage

| Path | Cleanup |
| --- | --- |
| Successful PCM completion | `_record` → single-use terminal, then completion; both release idempotently |
| Underrun / unexpected stop | `_record` → terminal; never reported as successful completion |
| Backend device error | `_record` terminal + failure observer; duplicate cleanup harmless |
| No device / unsupported format / buffer open failure | failure observer and terminal in finally |
| Exception constructing/starting sink | `_start` cleanup + failure + terminal; next FIFO item proceeds |
| FIFO audio overflow | dropped waiter terminal; existing queue limit/order unchanged |
| Explicit audio stop | current `_record`, all pending/waiting terminal callbacks, clear sink/buffer |
| AudioGate refuses because reading stopped | calls terminal without submitting audio |
| Pause | under pipeline RLock clear pending/playing/text FIFO, invalidate IDs, cancel Futures, then audio stop |
| Stop/profile/source restart | clear reservations before generation changes/cancellation; audio stop |
| Application shutdown | Backend stop and pipeline shutdown; all reservation state cleared |
| Translation/TTS error/cancel/submit refusal | release request and drain serialized narration queue |
| Late old-session completion | rejected by generation/work/floor; old reservations already cleared |

There is no timer releasing a still-playing phrase. Pending and playing state is
bounded by actual accepted work and removed by terminal/lifecycle events, not
history expiry. A hung external backend that never signals any terminal state
cannot be proven absent by source review: pause/stop/shutdown explicitly clear
its guard state. A process kill destroys in-memory state rather than leaving a
persistent reservation. No new watchdog or duration-based drop was introduced.

## Concurrency, history and queue contract

Pipeline OCR acceptance/reservation, history writes, terminal callbacks and
lifecycle mutations execute under the same RLock. The deduplicator is not an
independently thread-safe API; callers must use pipeline locking. Future delivery
consumption uses the same lock and a WeakSet, preventing duplicate delivery from
retaining PCM indefinitely. An eight-thread barrier regression confirms exactly
one successful consumption. Existing generation/work-ID checks remain in place.

Qt audio mutation runs on its QObject thread through queued play/stop signals;
stateChanged is handled there. Diagnostic queue writing has its own producer
lock and a bounded queue; footer reports dropped events. Repeated error/terminal
notifications cannot consume the terminal callback twice.

History still uses injected monotonic time, is written at audio start, survives
terminal release, and retains the original 4500ms expiry. `_playing` protects
active PCM independently of that expiry. No FIFO algorithm/limit or Latest Wins
change: narration limit remains 8; audio pending limit remains 8; existing
overflow selection is unchanged. Different-line FIFO tests remain passing.

## Verification and remaining gate

Full source suite: **913 passed, 9 skipped** (legacy local Tesseract unavailable).
Targeted P0/terminal/FIFO/analyzer suite using the **new built /app backend and
Platform**, network disabled: **44 passed in 7.83s**. Physical sink still injected
in these regressions; they are NOT Arch audible acceptance.

A broader full-suite attempt on the same built Platform produced **920 passed,
1 xfailed, 1 failed**: the source-archive packaging test invokes `git`, which is
not installed in Platform. The expected xfail is the documented Tesseract
pixel-font mismatch. This run is retained as `payload-full-tests.log`; it is not
reported as a full Platform-suite PASS. The source suite in SDK includes git
and its archive test passed. No git dependency was added to the shipped app.
The explicit app/Platform rerun excluding only that source-archive test passed:
**920 passed, 1 deselected, 1 xfailed in 23.21s** (`platform-app-tests.log`).

New attempt:
`<private-work>/p0-attempt-1`.
Initial source-download DNS failure retained; retry and fresh compilation passed.
Existing debugedit absolute-path warning remains; no new source-lookup claim.
The actual Python P0 modules match working tree/snapshot/payload SHA-256.
Rust launcher was rebuilt but is not where the Python fix resides.

Evidence root: `<private-evidence>/p0-arch-20261104`.
See `P0_ARCH_ACCEPTANCE.md` in this docs directory for the mandatory real
capture/OCR/Piper/Voidek/PipeWire procedure. **P0 and release remain OPEN.**