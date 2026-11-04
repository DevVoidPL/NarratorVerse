#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
export PATH="$ROOT/.tools/node-v22.22.0-linux-x64/bin:$PATH"
export CARGO_HOME="$ROOT/.tools/cargo"
export RUSTUP_HOME="$ROOT/.tools/rustup"
npm install --no-audit --no-fund
npm run check
npm run build
RUST=$(flatpak info --show-location org.freedesktop.Sdk.Extension.rust-stable//25.08)/files
mkdir -p "$ROOT/.tools/rust"
if [ ! -x "$ROOT/.tools/rust/bin/cargo" ]; then
  for dir in bin lib libexec share; do if [ -d "$RUST/$dir" ]; then cp -aL "$RUST/$dir" "$ROOT/.tools/rust/"; fi; done
fi
flatpak run --share=network --filesystem="$ROOT" --command=sh org.gnome.Sdk//49 -c "export PATH='$ROOT/.tools/rust/bin':\$PATH; export CARGO_HOME='$ROOT/.tools/cargo'; export RUSTUP_HOME='$ROOT/.tools/rustup'; cd '$ROOT/src-tauri'; cargo build --release"