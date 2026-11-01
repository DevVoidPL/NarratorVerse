# NarratorVerse — provenance and packaging limits

The Python Narrator models and services originate from DevVoidPL's GameOpti,
publication commit `df300c23e8a0a45a43fb136d75093f5b5e80e1a1`. The MIT license
and copyright notice are preserved in `LICENSE`. RapidOCR attribution in the
adapter is preserved in the original source files.

The application also uses Tauri, Svelte, Qt for Python/PySide6, Tesseract,
Leptonica, GStreamer, RapidOCR, ONNX Runtime, CTranslate2 and Piper. Their
licenses are separate from the application license. Python distribution
metadata and supplied license files are retained in the local runtime. Model
manifests preserve component attribution and artifact/runtime license IDs.

## Voidek

Voidek is **not covered by MIT**. On October 31, 2026, its owner explicitly
authorized including the voice in NarratorVerse in the project conversation.
`VOIDEK-LICENSE.md` preserves the original notice and records this additional,
project-specific permission to redistribute the unmodified model with NarratorVerse.
The package builder includes `tts.voidek`; custom voices and all user
configuration/cache remain excluded. This permission does not relicense the
model or cover other third-party dependencies.

## Experimental runtime snapshot

The local package is assembled from an independently copied runtime snapshot,
not a reproducible source build of every native dependency. An inventory with
SHA-256 values and Python package license metadata is included under
`share/narratorverse/licenses`. This inventory does **not** replace the required
third-party notices, corresponding-source obligations or a redistribution
review (notably for Qt/Piper/GStreamer and bundled native dependencies).

The package is a local verification artifact, not a distribution-ready release.
No claim is made that this snapshot's license/source audit is complete.