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

Publishing this source tree is not redistribution approval for the copied runtime.
The tree contains application sources, manifests, license texts and test fixtures,
not the third-party wheels, native libraries or model weights. The SentencePiece
Apache-2.0 license and upstream NOTICE (including its copyright/contact) are
preserved. Dependency lock files are not copies of the dependency implementations.

## Voidek

Voidek is **not covered by MIT**. On October 31, 2026, its owner explicitly
authorized including the voice in NarratorVerse in the project conversation.
`VOIDEK-LICENSE.md` preserves the original notice and records this additional,
project-specific permission to redistribute the unmodified model with NarratorVerse.
The package builder includes `tts.voidek`; custom voices and all user
configuration/cache remain excluded. This permission does not relicense the
model or cover other third-party dependencies.

## Integration candidate runtime snapshot

The local package is assembled from an independently copied runtime snapshot,
not a reproducible source build of every native dependency. An inventory with
SHA-256 values and Python package license metadata is included under
`share/narratorverse/licenses`. This inventory does **not** replace the required
third-party notices, corresponding-source obligations or a redistribution
review (notably for Qt/Piper/GStreamer and bundled native dependencies).

The package is a local verification artifact, not a distribution-ready release.
No claim is made that this snapshot's license/source audit is complete.

## QuickMT

The normal EN-to-PL provider uses quickmt/quickmt-en-pl, revision
6209580ce1fe525214f29fc39725007b73410109 (QuickMT, CC BY 4.0).
The downloaded model is not bundled. Attribution, original README and
unmodified-file notice are preserved by the component catalog.
See docs/REDISTRIBUTION.md: public distribution of the runtime is blocked
until the listed corresponding-source and third-party-notice checks close.

## Open runtime obligations

The inspected snapshot also contains LGPL-labelled archive dependencies
(inflate64, multivolumefile, py7zr, pybcj and pyppmd), GEOS through Shapely,
and MPL-labelled certifi/tqdm metadata. These require file-level review, not
an assumption that every Python wheel is permissive. Bundled espeak-ng,
GStreamer plugins, codecs and the Qt WebEngine third-party tree remain part
of the native-library audit. Preserved ONNX Runtime/OpenCV third-party notices
and Piper COPYING do not close the missing Qt/CTranslate2 notice/source checks.

Before binary distribution, decide and document the supported source-delivery
method for each applicable GPL/LGPL/MPL component and assess whether the actual
Piper integration forms a combined work. No automatic relicensing of the
application, nor a blanket MIT-only binary distribution claim, is made here.
See `docs/REDISTRIBUTION.md` for the evidence and unresolved actions.
