# Source-only publication preparation — 2026-11-04

This is a working-tree publication manifest, **not** a staged commit, push,
GitHub Release or binary-release approval. Base:
`b99bf5e3a630fef32e9a945afcf3051c17ce213c`, branch `release/0.2.0-beta.1`.
Unchanged tracked source files remain part of the source tree. The list below
is the exact set of modified/new files proposed in addition to that base.

## Changes made in this preparation

- README/INSTALL now describe the implemented fresh-build driver, not snapshot
  packaging. A local candidate is distinct from a public binary release.
- Release notes retain **P0 OPEN** and explicitly classify the GTA zero-repeat
  observation as historical, not closure evidence.
- Fresh-build/preparation reports distinguish completed local builds from open
  interactive, reproducibility, provenance and redistribution gates.
- Four P0/validation documents retain historical findings but replace private
  machine paths with descriptive placeholders. Raw evidence is not supplied.
- Local audit/diagnostic exclusions are scoped to directories; no blanket
  JSONL/WAV exclusion was introduced. No tracked JSONL/WAV assets were present.
- Three legacy scripts were reviewed and retained as non-executable text with
  an archive README; they are not supported build commands.
- Existing backend fixes, packaging scripts/locks and tests were reviewed as
  candidates, not rewritten in this documentation/privacy task.

## Exact modified/new publication candidates

```text
.gitignore
README.md
RELEASE_NOTES.md
backend/game_optimization_linux/services/narrator_audio.py
backend/game_optimization_linux/services/narrator_pipeline.py
backend/narratorverse/experiments.py
bin/backend
docs/FINAL_VALIDATION.md
docs/FRESH_BUILD.md
docs/INSTALL.md
docs/P0_ARCH_ACCEPTANCE.md
docs/P0_REPETITION.md
docs/P0_TERMINAL_REVIEW.md
docs/RELEASE_PREPARATION.md
docs/SOURCE_PUBLICATION_0.2.0-beta.1.md
flatpak/build-tools-lock.json
flatpak/components-lock.json
flatpak/io.github.DevVoidPL.NarratorVerse.json
flatpak/python-lock.json
flatpak/python-requirements.lock
flatpak/python.in
flatpak/sdk-lock.json
scripts/analyze-p0-trace.py
scripts/build-flatpak.sh
scripts/build-fresh.sh
scripts/build.sh
scripts/fresh-inputs.py
scripts/install-fresh.py
scripts/legacy-snapshot/README.md
scripts/legacy-snapshot/build-flatpak.sh.txt
scripts/legacy-snapshot/build.sh.txt
scripts/legacy-snapshot/prepare-quickmt-runtime.sh.txt
scripts/payload-inventory.py
scripts/prepare-quickmt-runtime.sh
scripts/reinstall.sh
scripts/validate-fresh.py
scripts/validate-quickmt-e2e.py
tests/test_beta_packaging.py
tests/test_fresh_build.py
tests/test_narrator_behavior_contract.py
tests/test_narrator_experiments.py
tests/test_narrator_p0_repetition.py
tests/test_narrator_p0_terminals.py
tests/test_narrator_unified_dedup.py
tests/test_p0_trace_analysis.py
tests/test_project_identity.py
tests/test_quickmt_packaging.py
tests/test_quickmt_runtime.py
```

## Fresh checks performed during this preparation

The default `sh scripts/test.sh -p no:cacheprovider ...` attempt could not start:
GNOME SDK 49 was unavailable in the default Flatpak installation. No SDK was
installed or replaced. The full source suite was instead run on host Python 3.13
with the existing local pytest/Qt libraries:

```sh
ROOT="$PWD"
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$ROOT/.tools/test-python:$ROOT/backend:$ROOT/tests:$ROOT/.runtime/lib/python3.13/site-packages" \
LD_LIBRARY_PATH="$ROOT/.runtime/lib" QT_QPA_PLATFORM=offscreen \
python3 -m pytest -q -p no:cacheprovider
```

Result: **913 passed, 9 skipped in 16.58s**. All skips report unavailable local
Tesseract runtime/models. This includes P0/terminal/episode/FIFO, trace analysis,
fresh-build, packaging, QuickMT and project-identity tests; it is not a built
Platform, GUI or physical-audio acceptance result.

Using the existing local Node 22.22.0 toolchain:

- `npm run check`: 0 errors, 0 warnings.
- `npm run test:ui`: 8 passed, 0 failed.
- `npm run build`: successful Vite production build; generated `dist/` is ignored.

The prospective source tree was scanned for private home paths and common
private-key/GitHub-token/AWS-key patterns, without matches. Candidate Python AST,
JSON syntax and relative Markdown links were checked. Shell syntax was checked
with `sh -n`, including archived scripts. Ignore probes confirmed local evidence
is excluded while test JSONL/WAV fixture paths are eligible. These checks are not
a guarantee against every secret or a legal compliance declaration.

## Excluded files/directories and reasons

- `.runtime/`, `.tools/`, `components/`: installed dependencies, tooling and models,
  not publication sources. Existing copies are preserved.
- `node_modules/`, `dist/`, `src-tauri/target/`, Python caches, `.pytest_cache/`:
  dependency/build/test output; not publication candidates.
- `flatpak/build/`, `flatpak/repo/`, `flatpak/artifacts/`, `flatpak/fresh-work-*/`:
  payloads, bundles, downloaded inputs, private build/validation evidence.
- `docs/performance-balanced.json`: pre-existing raw benchmark telemetry.
- `.private/`, `reference/`, `audit/`, `audits/`, `diagnostics/`, `logs/`,
  `narratorverse-p0-arch.*/`: local/private evidence locations, whether present
  now or created later. Profile/user-data exclusions remain in force.
- External private final-validation and Arch acceptance evidence directories:
  outside the repository, neither read for publication nor modified. No raw
  JSONL, WAV, screenshots, dialogue logs or private bundles are added.

## Remaining gates

**P0 OPEN**: actual Arch/GTA capture -> OCR -> Piper/Voidek -> PipeWire with a
fresh JSONL and human acceptance remains incomplete. Case `1508 -> 1515`
("Rzecz jasna...") is unresolved; no speculative filter is added. ESC interface
OCR is expected. ASR is deferred with no implementation or concept document.

Binary release remains blocked by the corresponding-source/notice/license
review and clean interactive installation/capture/audio/ducking/update checks.
No fresh full Flatpak rebuild, model download, binary export or real-game test
was performed in this preparation. Historical reports are not fresh results.
No staging, commit, push, tag, release or changes to private reference builds
are part of this task. Source publication still requires owner review/decision.
