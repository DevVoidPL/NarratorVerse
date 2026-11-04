# Private Arch Linux P0 acceptance — 2026-11-04

Public-safe historical report/procedure: `<private-...>` paths are descriptive
placeholders, not supplied evidence or runnable paths. Raw logs, JSONL, WAV and
packages are intentionally not published. Test counts below are historical.
Source publication does not authorize binary release or close P0.

**P0 OPEN. Not a public release. No injected audio sink is an acceptance result.**
Use a disposable graphical Arch user/VM with working game, Wayland/X11 portal,
PipeWire, pipewire-pulse, desktop-appropriate portal backend and audible speakers.
Do not replace a daily-use installation or delete its profiles/model store.

Private delivery directory:
`<private-delivery>/package`.
The packet's `SHA256SUMS`, `PACKAGE-IDENTITY.json`, inventory, build logs and
payload verification report identify the candidate. Its Flatpak application ID
is unchanged; its private branch is `p0-arch-test`. The UI version remains
0.2.0-beta.1, so the UI version alone does **not** prove this is the P0 build.

## Install and identify (test account only)

Copy the private package directory to the test machine. In a terminal, set
`PACKAGE` to its real absolute path, then:

```sh
set -eu
PACKAGE=$(realpath "$PACKAGE")
cd "$PACKAGE"
sha256sum -c SHA256SUMS
# GNOME Platform 49/x86_64 must already be installed from a trusted runtime
# remote. The bundle does not embed it. Use the runtime commit recorded here.
flatpak info --user org.gnome.Platform/x86_64/49
flatpak install --user "$PACKAGE/NarratorVerse-0.2.0-beta.1-P0-x86_64.flatpak"
flatpak info --user --show-commit io.github.DevVoidPL.NarratorVerse/x86_64/p0-arch-test
flatpak info --user --show-runtime io.github.DevVoidPL.NarratorVerse/x86_64/p0-arch-test
flatpak run --user --command=sh io.github.DevVoidPL.NarratorVerse/x86_64/p0-arch-test \
  -c 'cd /app/share/narratorverse; sha256sum backend/game_optimization_linux/services/narrator_pipeline.py backend/game_optimization_linux/services/narrator_audio.py backend/narratorverse/experiments.py; sha256sum /app/bin/narratorverse'
```

Compare the installed commit and all four file hashes with `PACKAGE-IDENTITY.json`
and `payload-verification.json`. Do not accidentally launch the old beta-test
branch from a desktop shortcut. Close all other NarratorVerse processes first;
parallel installations share app data for the same app ID in a user account.

## Start a new private hash-only trace

```sh
umask 077
RUN=$(mktemp -d "$HOME/narratorverse-p0-arch.XXXXXXXX")
export RUN
{
  date --iso-8601=seconds
  uname -a
  printf 'desktop=%s session=%s\n' "${XDG_CURRENT_DESKTOP:-}" "${XDG_SESSION_TYPE:-}"
  flatpak --version
  flatpak info --user io.github.DevVoidPL.NarratorVerse/x86_64/p0-arch-test
  flatpak info --user org.gnome.Platform/x86_64/49
  systemctl --user --no-pager status pipewire pipewire-pulse wireplumber xdg-desktop-portal
  wpctl status
  pactl info
} > "$RUN/environment.txt" 2>&1
# Each launch requires a NEW trace path; existing files are deliberately refused.
# Do not use --command=backend, offscreen GUI overrides or a substitute sink.
flatpak run --user --filesystem="$RUN" \
  --env=NARRATORVERSE_DIAGNOSTIC_TRACE="$RUN/trace.jsonl" \
  io.github.DevVoidPL.NarratorVerse/x86_64/p0-arch-test \
  > "$RUN/console-private.log" 2>&1
```

Keep this terminal open. Use a second terminal for `wpctl status`,
`pactl list sink-inputs` and `pactl list source-outputs` snapshots while capture
and speech are active. Save them in the same `$RUN` directory. Confirm the
narrator output stream and portal capture stream on the real PipeWire graph;
the presence of a service alone is not proof of playback/capture.

The opt-in JSONL hashes dialogue/freeform messages before writing. Ordinary
console logs can contain full dialogue: keep them private and redact before
sharing. Screenshots/recordings may expose game content; use only authorized
evidence. A normal application exit is needed for `trace_closed`; a forced kill
or missing/footer-loss trace cannot establish a complete successful run.

## Configure real production path

- Select a fresh test profile; record/export its actual settings. Keep duplicate
  cooldown **4500 ms**. Do not increase it. Record sampling, OCR provider,
  subtitle language, speech rate/adaptive rate and selected output device.
- Select real Piper and bundled Voidek, audible nonzero volume and the intended
  physical output. Confirm Voidek component verification. Do not use voice
  preview or Quick Read during the measured run: auxiliary playback is not game
  narration and can have overlapping request IDs.
- For English game subtitles install and verify QuickMT via the application's
  component UI, then select translation. For Polish subtitles select Polish
  bypass mode. Record which route was used. No online translation service.
- Start capture through the actual portal; select the game window/monitor and
  set the subtitle ROI. Test dialogue must come from the real game capture,
  not calls to `_ocr_finished`, test frames or replay scripts.

## Measured cases

Record game/save/scene, approximate elapsed actions and actual heard count in
`observations.md`. Prefer a repeatable dialogue scene with a long subtitle and
audio **over 4.5 seconds**. The important case straddles the 4.5s history boundary
while the first PCM is still playing, not just repeated text in its first second.
If the scene cannot exercise this condition, mark it NOT_TESTED and select a
different scene. Do not change code, cooldown or use a fake sink to force PASS.

1. **Persistent/repeated A:** identical text on successive captured frames,
   observations less than 3s apart. Hear A once.
2. **Brief disappearance:** allow at least three sampled empty observations,
   then make A reappear while its first audio still plays. Continue observing
   past 4.5s from first audio start. Hear no queued replay after A ends.
3. **Different lines A → B → C:** rapid distinct dialogue while A plays.
   Each accepted line gets one synthesis and one playback, in FIFO order.
   Stay below queue limits; overflow is not the normal success scenario.
4. **Pause/cancel:** pause while A plays and B waits; verify output stops and
   no old queued B plays on resume. Resume and recognize a new line normally.
5. **Profile/source restart:** change profile and capture source, then repeat
   A/B sequence. No second capture receiver or output stream, no stale results
   from the old session. Record session/generation/instance identities.
6. **Device failure/recovery:** on this disposable test system, temporarily
   disconnect/switch the selected output while reading; record failure and
   stopped stream. Restore output and verify a new line works. Do not restart
   shared production audio services just to execute this case.
7. Stop narration and close the application normally. Confirm capture/output
   streams end and a new launch works without old queued speech.

## Analyze, do not auto-close P0

After closing the app, run with host Python 3:

```sh
python3 "$PACKAGE/analyze-p0-trace.py" "$RUN/trace.jsonl" > "$RUN/trace-summary.json"
```

The summary correlates original OCR/identity hashes with translated/TTS hashes
through `(run, PID, session, generation, phrase_id)`. It reports counts per
accepted request and aggregated identity hash, plus stage timestamps. Legitimate
recurrences in later scenes must not be judged solely by the aggregate.

Required trace chain for A:

| Meaning | Event/count |
| --- | --- |
| Accepted OCR | `ocr_decision`, `decision=accepted`: 1 |
| Reservation | `phrase_reserved`: 1 |
| FIFO admission | `dialogue_queued` when busy, otherwise `dialogue_started`: 1 |
| FIFO dispatch | `fifo_dequeued`: 1 |
| Real provider synthesis | `tts_provider_input`: 1 |
| Audio submitted | `audio_submitted`: 1 |
| Qt output submission | `sink_submitted`: 1 |
| Output starts | `sink_started` and `playback_started`: 1 each |
| Output ends | `sink_terminal`, result `completed`; `playback_completed`: 1 each |

Check `dedup_checked.playing_ids` protects A until terminal and `history_written`
appears at start. During repeated observations inspect rejection reasons and
`identity_text_sha256`. If the trace never sees the returning text past the
history boundary, this is not coverage of the reproduced P0 condition.

For each later distinct line verify dispatch/sink start order, one-to-one counts
and completed PCM duration. Classify cancellation/errors separately; they must
terminate protection but are not successful audible completions.

**Success requires both** complete trace (`trace_closed`, zero dropped events),
one-to-one stage counts/order, and recorded human listening/real PipeWire evidence
of exactly one actual reading of A. Sink callbacks and `processed_ms` alone do not
prove audibility. The analyzer deliberately returns
`physical_playback=NOT_TESTED_BY_ANALYZER` and never closes P0.

Return environment, package/installed commit identity, profile settings, JSONL,
summary, action timeline, human heard counts and stream evidence. Report any
unexecuted scenario as NOT_TESTED. No public upload, push or release publication.