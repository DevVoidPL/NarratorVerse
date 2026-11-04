# Fresh candidate build (not a release/install approval)

This path replaces copying `.runtime`, `target/release`, existing components and
`.tools/quickmt-python`. Historical files are neither deleted nor build inputs.
The previous scripts are retained as non-executable text under
`scripts/legacy-snapshot/`; `scripts/stage-flatpak.py` is legacy fixture code,
not called by the new pipeline. Automatic reinstall is disabled during validation.

## Inputs and command

Run from an isolated checkout. Required host tools: Python 3.13, git, tar/xz,
Flatpak, flatpak-builder, AppStream including its Compose addon, elfutils and
debugedit. Use official distribution packages. The first implementation run used
Debian packages unpacked into a private bootstrap because sudo was unavailable;
no system installation or old toolchain was imported.

Install into the user Flatpak installation the x86_64 GNOME SDK/Platform 49 and
Rust stable extension 25.08 through
the official Flathub remote, then check out **the exact OSTree commits** listed in
`flatpak/sdk-lock.json`. A branch alone is not a pin: the script rejects a
different installed commit. The lock is tied to CPython 3.13, Linux x86_64.

Provide the owner's original voice files in an external input directory named
`voidek-pl-e991.onnx` and `voidek-pl-e991.onnx.json`. Both hashes are checked. Do
not use files from an installed component. The first run used owner-delivered
`Voidek.onnx`/`Voidek.onnx.json`, copied with the required filenames into a new
input directory; originals were preserved. No private voice directory is copied.

```sh
sh scripts/build-fresh.sh /absolute/new/work-directory /absolute/owner-input
```

`scripts/build.sh`, `scripts/build-flatpak.sh` and
`scripts/prepare-quickmt-runtime.sh` delegate to this same command. All require a
new work directory. `NARRATORVERSE_WHEEL_CACHE` optionally points at **wheel
archives**, not installed packages: every cached artifact is verified against the
lock before copying. `FLATPAK_BUILDER` optionally selects the host builder binary.
An isolated user Flatpak installation can be selected using `XDG_DATA_HOME`.

The pipeline:

1. Verifies SDK pins; records source HEAD and dirty status; snapshots only source
   directories/configuration. It excludes old runtime, target, dist, node_modules,
   models, user configuration and caches. The working changes are included, so
   HEAD alone does not identify a dirty candidate; retain the snapshot.
2. Downloads the complete Python wheel set using `python-lock.json` URLs/hashes.
   `python.in` contains the direct roots, **not** an installation requirements
   file. `python-requirements.lock` pins all 30 resolved distributions and wheel
   hashes. Normal builds never re-resolve them. Model licenses bundled in the
   RapidOCR wheel are retained.
3. Prepares OCR EN/PL from commit-pinned tessdata_fast downloads, RapidOCR from a
   hashed upstream wheel (including models/licenses), and Voidek from the hashed
   owner originals. It creates component manifests accepted by the current app.
4. Downloads verified Node 22.22.0, populates a new npm cache using `npm ci`, and
   vendors the Cargo.lock graph with `cargo vendor --locked` in the pinned SDK.
5. Generates a resolved manifest; runs the builder download phase separately;
   compiles without download access using `npm ci --offline`, `cargo --frozen`
   and pip `--no-index --require-hashes --no-deps --ignore-installed`. Tesseract
   5.5.4/Leptonica 1.87.0 are built from hashed sources; other native dependencies
   use Platform or wheels. No upstream build-everything exercise is involved.
6. Installs the new Rust binary, backend, models, package license texts and
   available npm/Cargo notices. Runs offline inference/import smoke checks using
   **Platform**, not SDK, and inventories final postprocessed payload bytes.

No export, bundle installation, push, tag or release publication occurs. The
directory `build` is a local Flatpak candidate, not a published release file.

## Evidence and limits

The first implementation run's logs are under
`flatpak/fresh-work-20261104/` (ignored, not committed). They include dependency
resolution, isolated frontend/Cargo compilation, native build attempts,
`full-attempt-1/{build,finish,platform-validation}.log` and payload inventory.
The initial download attempt timed out; component preparation then identified the
missing owner voice originals. After delivery and host-tool setup, the complete
candidate finished. `full-attempt-2` checks the complete driver from an empty
directory without manual phase resumption: it completed successfully, including
offline Platform inference validation and final payload inventory. The bootstrap
builder warns that `/usr/bin/debugedit` is unavailable (its configured absolute
path); this did not fail the build but debug-source mapping is not validated.

First candidate inventory: 7890 paths, 30 Python distributions, four components,
610 ELF files. Inventory includes symlinks, exact file hashes, installed versions,
component manifests, Python license metadata/notices, ELF dynamic dependencies
and ownership where the wheel RECORD provides it. Missing license metadata and
unmapped native licenses are explicitly marked for review, not guessed.

Known release blockers (do not treat smoke checks as closing these):

- Complete corresponding-source bundle and third-party notice/license mapping
  for the actual payload, particularly Piper/espeak GPL, Qt/PySide/shiboken LGPL,
  bundled native wheel libraries and MPL obligations. A wheel hash or a license
  classifier does not meet source obligations. `redistribution_review` is OPEN.
- Interactive GUI/Wayland, portals/PipeWire capture, audio playback/ducking and
  restoration, update and data-isolation testing in a clean installation.
- Real graphical QuickMT session acceptance. A separate historical backend install
  and offline translation/Piper-to-WAV check is recorded in `FINAL_VALIDATION.md`;
  it does not prove GUI interaction, capture or physical audio. The build itself
  tests the CPU runtime but does not download/package QuickMT weights.
- **P0 repetition OPEN**: real Arch/GTA capture/OCR/Piper/PipeWire acceptance with
  a new JSONL remains incomplete. See `P0_ARCH_ACCEPTANCE.md`.
- Packaging release artifact, independent rebuild comparison and authorization
  to publish. The candidate is built from uncommitted source changes.

No dependency was removed on speculation. QtMultimedia is actually imported and
provided by PySide6 Addons; it cannot be removed by selecting Essentials alone.
Platform GStreamer capture/GL elements and `pactl` were checked before removing
the backend launcher's overrides pointing at the historical runtime. Source-build
instructions describe the candidate workflow, not a validated public installation
or a release date. Historical evidence above is not a fresh test result.