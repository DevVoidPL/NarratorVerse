# Source and package boundaries

Source review and Flatpak review are independent gates. `.gitignore` is not a
package filter and does not remove historical Git objects.

## Classification

| Class | Contents | Public source | `/app` |
|---|---|---|---|
| A | Backend, frontend and Rust source, launchers | Yes | Backend/launcher and compiled executable only |
| B | Build scripts, manifests, pinned dependency locks, project configuration | Yes | Selected provenance locks only |
| C | Deterministic regression tests and sanitized OCR TSV fixtures | Yes | No |
| D | User/developer documentation and public screenshots | Yes | No |
| E | Historical import ledger, machine-specific verification JSON, old delta manifest | No; originals remain local | No |
| F | Local models, runtime, tools, logs, audits, caches, builds, user data | No | Only explicitly pinned distributable components and fresh dependencies |
| G | Licenses, notices, model attribution, application desktop assets | Yes | Explicitly selected texts/assets, dependency notices |

`EXPERIMENTS.md` documents removal of obsolete switches, not a private experiment
dataset. Diagnostic and benchmark scripts are reproducible contributor tools.
All existing regression tests remain public: their names (including P0, GTA,
diagnostics and experiments) alone are not a reason to remove them. OCR fixtures
are small sanitized text cases; raw captures and session traces remain local.
Historical public-safe reports retain their explicit limitations and open gates.
Generated Tauri schemas and legacy snapshot examples remain public reference
material but do not enter fresh build inputs.

## Explicit package policy

`flatpak/publication-files.json` lists build inputs, project files installed under
`share/narratorverse`, desktop targets and every distributable component file
with SHA-256. It is reviewed source, not regenerated automatically during builds.
Adding a file requires reviewing the relevant lists. Package code never derives
permissions from Git tracking, ignore rules, or a model's mutable self-inventory.

`scripts/fresh-inputs.py` validates all selected source directories before
creating a snapshot. Unknown files fail closed. Explicit generated/reference
exclusions and build/cache trees are never copied. Root-level private material
outside selected directories is not a source input. Missing required files and
symlinks in selected paths fail validation.

`scripts/install-fresh.py` validates before writing application output, accepts
only the listed project files, and checks exact component names and hashes.
The generated Cargo configuration is a build-only exception. Canonically named
dependency license/notice texts are retained from freshly locked npm/Cargo
inputs; license completeness still needs separate review. These dependency trees
must not be substituted with arbitrary local runtimes.

Dependencies installed by pip/native build modules are a separate layer. The
installer's allowlist alone does not certify their content. Inventory the whole
`/app`, including dependencies, symlinks, native/debug metadata and notices, and
independently inspect the actual exported bundle. A staging inventory is not an
export check. Historical artifacts are not evidence for changed source.

After builder finish, the fresh-build driver normalizes its generated `/app/manifest.json`
back to `@WORK@` placeholders. Builder emits this file after the application
installer, so installer filtering alone cannot prevent host path disclosure.
The expanded original remains local in the work directory for reproducibility.

The legacy `stage-flatpak.py` command is disabled: it must not package a local
runtime snapshot. Its importable helpers remain only for historical regression
tests, not an approved packaging API. Use the fresh build path.

## Remaining publication gates

Local history review on 2026-11-04 found machine-local identity metadata and
historical local paths. They were not rewritten. A clean current tree is not a
clean public history. Resolve the intended publication/history scope with the
owner before changing visibility or pushing.

Local audit evidence, backups and inventories belong under ignored `audit/`,
not public documentation. No source cleanup closes P0 Arch capture/OCR/Piper/
PipeWire acceptance or the redistribution obligations in `REDISTRIBUTION.md`.
