# Building a Flatpak candidate

This path replaces copying `.runtime`, `target/release`, existing components and
`.tools/quickmt-python`. Historical files are neither deleted nor build inputs.
Automatic reinstall is disabled during validation.

## Inputs and command

Run from an isolated checkout. Required host tools: Python 3.13, git, tar/xz,
Flatpak, flatpak-builder, AppStream including its Compose addon, elfutils and
debugedit. Use official distribution packages.

Install into the user Flatpak installation the x86_64 GNOME SDK/Platform 49 and
Rust stable extension 25.08 through
the official Flathub remote, then check out **the exact OSTree commits** listed in
`flatpak/sdk-lock.json`. A branch alone is not a pin: the script rejects a
different installed commit. The lock is tied to CPython 3.13, Linux x86_64.

Provide the owner's original voice files in an external input directory named
`voidek-pl-e991.onnx` and `voidek-pl-e991.onnx.json`. Both hashes are checked. Do
not use files from an installed component.

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

## Validation

The driver writes build logs, the source snapshot, dependency locks and
`payload-inventory.json` into the selected work directory. Preserve these when
comparing candidates. Offline smoke checks cover component integrity, native
imports, OCR and synthesis; they do not exercise the graphical interface or
physical audio.

Before release, test capture through the desktop portal, playback and ducking,
pause/stop, installation, updates and data isolation. Repetition handling still
needs a real Arch/GTA session with capture, OCR, Piper and PipeWire. Test a
longer QuickMT session and a lower-powered CPU separately.

Package contents are controlled by `flatpak/publication-files.json`; see
[PUBLICATION_BOUNDARIES](PUBLICATION_BOUNDARIES.md). Existing redistribution
notes remain in [REDISTRIBUTION](REDISTRIBUTION.md).
