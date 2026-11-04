# Historical snapshot scripts — not build instructions

The three `.sh.txt` files preserve the former snapshot-based packaging path for
review only. They are not executable entry points, their relative root assumes
their former location, and they require historical local runtime/tooling inputs.
Do not rename or run them as the current build procedure.

Use `scripts/build-fresh.sh` as documented in `docs/FRESH_BUILD.md` instead.
Preserving these files does not approve a binary release or close the P0 gate.
