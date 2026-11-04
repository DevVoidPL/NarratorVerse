# NarratorVerse 0.2.0-beta.1: final validation, 2026-11-04

Public-safe historical report/procedure: `<private-...>` paths are descriptive
placeholders, not supplied evidence or runnable paths. Raw logs, JSONL, WAV and
packages are intentionally not published. Test counts below are historical.
Source publication does not authorize binary release or close P0.

## P0 RELEASE HOLD — repeated narration (2026-11-04)

Release preparation is suspended. The reference payload below remains unchanged
and does **not** contain the P0 source fixes. Its prior automated checks are not
acceptance of the reported Arch Linux repetition problem. See
`P0_REPETITION.md`.
No publication, push or replacement build is authorized by this validation.

Private P0 Arch candidate prepared separately at
`<private-work>/p0-attempt-1`.
Delivery directory:
`<private-delivery>/package`.
See `P0_ARCH_ACCEPTANCE.md` and `P0_TERMINAL_REVIEW.md` in this docs directory.
This candidate is for authorized private testing only; actual Arch capture,
Piper/Voidek audibility and PipeWire acceptance remain NOT_TESTED here.

## Passed

- Full project test rerun: **892 passed, 9 skipped** in 12.62s. Skips concern the
  legacy test fixture's unavailable local Tesseract, not a GUI acceptance result.
- Fresh Platform offline smoke rerun: Tesseract EN/PL, RapidOCR inference,
  Piper synthesis, native runtime and GStreamer element checks passed.
- Private bundle creation completed; checksum and local repository integrity
  are checked separately. Packaging is not clean installation acceptance.

Reference build (not modified):
`<private-work>/full-attempt-2`.

Evidence and local-only test package directory:
`<private-evidence>/final-validation-20261104`.

- QuickMT installed into empty isolated XDG storage through the built application's
  `Backend.handle` component/install handler. No separate downloader or existing
  user model was used. GUI button interaction itself is NOT tested.
- All seven downloaded files match catalog sizes and SHA-256, including the
  401699775-byte model and original README. Same-size config corruption is rejected
  by both the component verifier and provider; original bytes restored and verified.
- In a separate Platform sandbox with `--unshare=network`, production QuickMT
  subprocesses translated two uncached accepted subtitles:
  - `Do not open the door. Wait for me!` ->
    `Nie otwieraj drzwi. Czekaj na mnie!`
  - `We need to find a safe place before nightfall.` ->
    `Musimy znaleźć bezpieczne miejsce przed nocą.`
- Both were drained in order through StandalonePipeline's narration queue and
  real Piper/Voidek subprocess synthesis: 52736 and 62464 mono s16le samples at
  22050 Hz. The audio device alone was replaced by WAV output. This does NOT
  establish playback, portal, capture, OCR or ducking success.

Evidence: `install-report.json`, `offline-report.json`, `quickmt-1.wav`,
`quickmt-2.wav`. Reproduction harness:
`scripts/validate-quickmt-e2e.py`.
It requires a dedicated work directory containing `.isolated-validation` and
refuses overwriting reports. Use a fresh work directory for a fresh install test.
Two preliminary harness failures (enum spelling and missing inherited PYTHONPATH)
are preserved as `offline-harness-error-*.log`; they are not payload regressions.

## Not passed: interactive acceptance

No Wayland compositor was present in this agent session. Existing X11 sockets
and portal processes are NOT evidence of successful graphical acceptance.
Every row below remains NOT_TESTED until a human records evidence.

Local package/instructions are for PRIVATE testing, not authorized publication.
Use a disposable Linux user or VM with a real GNOME/KDE Wayland session,
PipeWire, the matching desktop portal backend, PulseAudio compatibility and
working speakers. Do not overwrite a daily-use installation or its model store.

1. Copy the entire private `package` directory and verify its `SHA256SUMS`:
   `cd /absolute/path/to/package && sha256sum -c SHA256SUMS`.
2. Ensure GNOME Platform 49/x86_64 is installed in the test user. If using Flathub,
   configure its normal runtime remote first. The bundle does not embed Platform.
3. Clean install (test user only):
   `flatpak install --user /absolute/path/to/package/NarratorVerse-0.2.0-beta.1-x86_64.flatpak`.
4. Launch and save stderr:
   `flatpak run --user io.github.DevVoidPL.NarratorVerse//beta-test 2>&1 | tee /absolute/path/to/gui.log`.
5. Run the matrix below. Record desktop/Wayland/session, Flatpak/runtime commits,
   bundle hash, exact actions, expected/actual result and screenshot or log per row.
   Do not mark PASS solely because a button did not crash.

| Test | Required acceptance evidence | Result |
| --- | --- | --- |
| Clean install + GUI | No existing app data; visible usable window, no missing assets/backend errors | NOT_TESTED |
| Components GUI | Install QuickMT with progress; verify; cancel/retry safely; existing local model survives restart | NOT_TESTED |
| Wayland portal | Consent dialog, chosen window/monitor only; denial recoverable; change source and stop close session | NOT_TESTED |
| PipeWire/capture | Preview updates with selected source; confirmed subtitle ROI excludes unrelated screen content | NOT_TESTED |
| Tesseract | EN subtitle -> matching text -> Polish narration; PL mode speaks PL without translation | NOT_TESTED |
| RapidOCR | Repeat same scene with RapidOCR; readable output and correct ROI; no repeated speech for static line | NOT_TESTED |
| Piper/Voidek | Audible Polish, no clipping/truncation, ordered dialogue; preview/pause/stop work | NOT_TESTED |
| Offline | After GUI model install, disconnect network; restart and repeat EN->PL->speech | NOT_TESTED |
| Audio balance | Record original game stream volume; only selected stream ducks during narration; restored after completion, pause, stop, source loss, error and app exit; test restart recovery | NOT_TESTED |
| Profiles/settings | Create two profiles, different ROI/OCR/rate/volume; switch, restart, confirm persistence and no cross-profile leakage | NOT_TESTED |
| Update | Install a separately identified supported older NarratorVerse candidate in disposable user; create profiles and install QuickMT there; record model hashes/settings; update to supplied candidate; unchanged models/settings and successful offline narration | NOT_TESTED |

An uninstall/reinstall or reinstalling this same bundle is NOT an update test.
A suitable previous NarratorVerse package must be supplied/identified first;
do not substitute a historical runtime or application build. Preserve test-user
data until comparisons are complete. Optional cleanup after evidence collection:
`flatpak uninstall --user io.github.DevVoidPL.NarratorVerse//beta-test` (no delete-data).

## Release blockers: actual payload compliance

Scope: files in reference `payload-inventory.json`, not old installations.
Detailed machine-readable evidence: `payload-compliance-findings.json` beside
the validation logs. Metadata license counts alone are not compliance evidence.

| Actual included bytes | Missing / unresolved | Exact closure action |
| --- | --- | --- |
| PySide6 Essentials/Addons, shiboken6 6.11.1; 468 PySide6 ELF including QtWebEngineProcess | No license/notice/copying files found in these installed trees; module-specific licenses and Chromium/Qt third parties unresolved; matching source delivery absent | Map shipped modules to exact Qt/PySide sources/build options and third-party notices; include their license texts and corresponding sources, or remove unneeded modules in a NEW candidate and retest. Do not label every Qt module LGPL by assumption. Document library replacement/relinking rights/mechanism. |
| Piper 1.7.0, espeakbridge.so and phonemizer data | GPL text is present; exact source/build recipe for bridge and incorporated espeak code/data not supplied with a verified delivery mechanism | Archive corresponding source including incorporated native dependencies, patches and build/install scripts for these exact bytes; establish source access alongside any eventual binary distribution. |
| GEOS 3.14.1/GEOS C 1.20.5 from Shapely; FFmpeg avcodec 62.28.101 and related libraries from OpenCV | LGPL notices present, but matching source/configuration/patches and replacement compliance not closed | Obtain exact wheel build provenance, matching GEOS/FFmpeg source and options; preserve notices, provide matching source delivery and replacement instructions. |
| CTranslate2 4.8.1 and its bundled libgomp; Flatbuffers 25.12.19 | No wheel notice files recorded for CTranslate2/Flatbuffers; native runtime mapping incomplete | Add exact upstream license/copyright texts; map libgomp to its GCC source and runtime exception, verify applicability to this binary and preserve required exception/license texts. |
| SentencePiece 0.2.1 | Wheel metadata lacks license files | Root-level SentencePiece LICENSE and NOTICE ARE preserved under application licenses; verify they correspond to this exact wheel/source version, record mapping. Do not report them as wholly missing. |
| NumPy/OpenCV/Pillow/ONNX Runtime native dependencies | Substantial third-party notices ARE present, but file-to-upstream/license mapping is incomplete (OpenBLAS, GCC runtimes, codecs, OpenSSL, image/font libraries) | Map actual bundled ELF to exact upstream/build and existing notice section; add only missing texts/sources. Determine copyleft/source obligations from actual build, not package-level MIT/Apache metadata. |
| certifi/MPL and tqdm MPL/MIT portions | Texts present; source delivery for covered shipped files not explicitly documented | Map covered files to unmodified exact source; retain notices and document compliant source access. |
| Piper tashkeel/model.onnx and hebrew/nakdimon.onnx | Nakdimon MIT notice/source pointer present; tashkeel model-specific provenance/redistribution terms not established by inventory | Obtain exact model source/revision/license and applicable notices; document authorization or exclude unused model payload in a new candidate. |
| share/narratorverse/licenses/NOTICE.md | Contains obsolete runtime-snapshot language and claims about libraries not in this payload | Replace obsolete sections with payload-specific statement in source, rebuild a new candidate, regenerate inventory. Reference build remains unchanged. |
| Rust/frontend embedded code, OCR models, Voidek | Many license texts and model permissions preserved; exact linked/embedded dependency-to-notice completeness not demonstrated | Compare actual compiled/embedded dependencies against preserved texts and provenance; fill genuine gaps. Retain Tesseract/Leptonica notices and Voidek permission. No new owner permission is presumed necessary. |

QuickMT is NOT in the application bundle. Its separate download preserved the
original README and attribution in component metadata; do not count its 403 MB
as shipped payload. GNOME Platform libraries are separately supplied runtime,
not a reason to import the old dependency list into this review.

Authoritative requirements consulted: GNU GPLv3 sections 1 and 6; Qt open-source
obligations and Qt WebEngine licensing. Corresponding source means source and
build/install scripts matching the binary, not merely a wheel, lock or generic
upstream link. This is an engineering release gate, not a blanket legal opinion.

## debugedit: not an independent release blocker

- Builder logged missing absolute `/usr/bin/debugedit` but completed strip,
  debug extraction, finish and Platform inference validation.
- Main executable retains build ID `9ff3caad6aaa6528c8b57730639dff12dbc1b454`
  and `.gnu_debuglink`; its separate debug file has `.symtab`, but no DWARF
  line information (release Rust build does not request debuginfo).
- Tesseract debug file DOES retain DWARF with `/run/build/tesseract/...` and
  `/run/build/tesseract/_flatpak_build`; no populated `lib/debug/source` tree
  was found. Source path normalization/automatic source collection is incomplete.
- Inference and execution do not require debugedit. It is a build-time debug
  metadata tool; missing it is not itself a source-distribution violation or
  evidence that corresponding source is complete.
- Optional improvement: supply debugedit at the path expected by builder in a
  NEW build, enable Rust line debuginfo if wanted, inspect DWARF/debuglink and
  test source lookup with matching sources. For current C/C++ symbols, configure
  debugger source substitution for `/run/build/tesseract` and Leptonica.
  Independently close the actual source-delivery obligations above.