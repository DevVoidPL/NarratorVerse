# P0 repetition investigation — 2026-11-04 — RELEASE HOLD

Public-safe historical report/procedure: `<private-...>` paths are descriptive
placeholders, not supplied evidence or runnable paths. Raw logs, JSONL, WAV and
packages are intentionally not published. Test counts below are historical.
Source publication does not authorize binary release or close P0.

## Reproduced defect, not yet attribution of the Arch incident

`PhraseDeduplicator.mark_spoken()` removed a request from `_reserved` at audio
start. History was correctly written using the monotonic clock, but was the only
remaining protection once three blank OCR observations cleared the visible
episode. At 4.5 seconds after audio start, history expired even when the original
PCM was **still playing**. The next recognition of the same text passed the gate
and deduplicator, created another synthesis and waited in the existing FIFO.
It could start immediately after the first PCM finished: an audible gap under
3 seconds does not imply recognition/start timestamps were under 4.5 seconds.

Minimal fix: move the pending reservation into `_playing` on audio start; check
both pending and playing reservations; release playing protection only on a
terminal event (also completion), explicit cancellation or session stop. Keep
4500 ms history semantics and the existing visible episode, FIFO and limits.
Releasing started audio must not clear its visible episode latch as failed,
unsaid work would. History itself is not removed by terminal release.

An independent injected-event reproduction exposed non-idempotent completion
handlers: delivering one translation Future twice submitted two TTS jobs;
delivering one TTS Future twice queued its PCM twice. OCR completion could also
count the same observation twice. A locked weak set consumes each Future once,
without retaining results/PCM. There is **no evidence yet that production
concurrent.futures delivers duplicates**; do not present this injection as proof
of the Arch incident.

## Trace and correlation

Use the existing opt-in `NARRATORVERSE_DIAGNOSTIC_TRACE` with an absolute,
new file path. `DialogueTrace` writes mode 0600, refuses existing files/symlinks,
records monotonic timestamps, PID/run/session/generation and dropped-event footer.
Text-bearing fields and freeform error messages are SHA-256 hashes with lengths,
not dialogue. Existing ordinary application logs predate this hash-only JSONL;
they can still contain dialogue. Collect the JSONL rather than forwarding those
logs unredacted.

Trace stages:

1. `capture_frame`: capture timestamp/session/generation/source and pixel hash.
2. `ocr_submitted` / `ocr_completion`: request ID bridges frame and OCR result.
3. `ocr_decision`: raw/filtered/accepted hashes; `dedup_checked` additionally
   carries normalized identity hash, reason, cooldown, history ages, pending and
   playing request IDs. Different OCR request IDs may share one text hash.
4. `phrase_reserved`, `dialogue_queued` (FIFO append when busy),
   `fifo_dequeued` / `dialogue_started` (including immediate dispatch).
5. Translation input/output, `tts_provider_input` immediately before synthesis,
   `tts_completion`, `audio_submitted` with PCM hash.
6. `sink_submitted`, `sink_started`, `playback_started`, `history_written`,
   `sink_terminal` (processed/expected duration), `playback_completed`,
   `reservation_released`.

All phrase-stage events carry the accepted OCR request ID, session/generation,
pipeline/deduplicator IDs. Sink events additionally identify audio output and
playback objects. Cross-process comparison requires PID/run identity: Python
object IDs alone are not global identifiers. `*_completion_ignored` proves an
attempted duplicate callback was ignored. Capture events preceding OCR use
frame timestamp/hash rather than inventing a phrase ID before text exists.

Classify a reported repeat from the earliest branching point: two accepted OCR
IDs with one identity hash; two FIFO appends for one accepted ID; two provider
inputs for one accepted ID; or two sink starts for one synthesis/PCM hash. Check
session and instance IDs before concluding that two events share guard state.

## Tests and limits

Evidence root: `<private-evidence>/p0-20261104`.
Final full suite: **899 passed, 9 skipped in 20.25s**, recorded in
`<private-evidence>/p0-20261104/final.log`.
Skips concern unavailable local legacy Tesseract fixtures, not physical audio.
The real-time controlled run lasted 6.300343 seconds: 12 OCR completions,
one accepted phrase, one TTS provider call, one sink submission/start/terminal
and one playback completion. Both controlled traces report zero dropped events
and were checked for absence of the sample dialogue.
`red2.log` records injected repeated translation/TTS callbacks creating duplicate
work. `active-red.log` records the unmodified active-reservation defect creating
two synthesis calls for the same line. The normal short-duration repeated-frame
test already passed before the fix; that is why a deduplicator-only test missed
this lifecycle defect.

New pipeline tests use actual gate, deduplicator, serialized narration FIFO,
translation dispatch, TTS dispatch, Qt queued audio submission, playback FIFO,
and terminal callbacks. Capture/OCR/inference and the physical sink are injected.
The active-PCM scenario runs with both controlled time and real monotonic elapsed
time, observations 0.2–1.0 seconds apart, three blank frames, and six-second PCM.
One accepted line must give one TTS call, one audio submission, one sink start,
and one completion. Reports and hash-only JSONL are in pytest basetemp directories.

The existing ContractReplay fixture now emits completion for its tiny synthetic
PCM before the next observation; previously it silently left every utterance
playing forever. Tests of long active playback use the new explicit sink harness.
The unit boundary test now explicitly terminates the reservation before checking
history expiry. Different lines remain FIFO and are not suppressed.

Static lifecycle review: one deduplicator is created per pipeline session;
`submit_frame` checks session/generation under the shared lock and serializes OCR;
portal capture uses an attempt guard and one callback, and audio connects its
queued play signal once per output instance. This review does not rule out two
running application processes or an environment-specific capture lifecycle bug.

## Required closure — not completed here

- Reproduce on the reported Arch desktop with hash-only trace, exact installed
  executable/bundle identity, active profile cooldown, PCM duration and pause/
  resume/profile/capture lifecycle recorded. Confirm the earliest duplicate stage.
- Repeat the same controlled subtitle sequence using real capture, OCR, Piper
  and physical/PipeWire output. Confirm one synthesis and one audible playback;
  injected sink completion is not physical playback acceptance.
- If corrected payload is needed, build it in a new directory, never overwrite
  `full-attempt-2`, then rerun payload, QuickMT and graphical acceptance checks.
- Release remains blocked by this Arch acceptance and the previously documented
  compliance/interactive gates. No push, publication or full rebuild was done.