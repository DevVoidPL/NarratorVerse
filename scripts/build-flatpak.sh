#!/bin/sh
# Local unsigned beta candidate; publishing requires the redistribution gate.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BUILD="$ROOT/flatpak/build"
REPO="$ROOT/flatpak/repo"
OUT="$ROOT/flatpak/artifacts"
if [ "$#" -ne 0 ]; then printf 'Usage: sh scripts/build-flatpak.sh\n' >&2; exit 2; fi
VERSION=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$ROOT/package.json")
if [ -e "$BUILD" ]; then
  printf '%s\n' "Refusing to replace existing build directory: $BUILD" >&2
  exit 1
fi
mkdir -p "$OUT"
flatpak build-init "$BUILD" io.github.DevVoidPL.NarratorVerse org.gnome.Sdk org.gnome.Platform 49
python3 "$ROOT/scripts/stage-flatpak.py" --dest "$BUILD/files"
flatpak build --unshare=network "$BUILD" sh -c '
  export PYTHONDONTWRITEBYTECODE=1
  export PYTHONPATH=/app/share/narratorverse/backend:/app/share/narratorverse/.runtime/lib/python3.13/site-packages
  export LD_LIBRARY_PATH=/app/share/narratorverse/.runtime/lib:/app/share/narratorverse/.runtime/lib64
  exec python3 -m narratorverse.quickmt_runtime
'
flatpak build-finish --command=narratorverse --share=ipc --share=network --socket=wayland --socket=fallback-x11 --socket=pulseaudio --device=dri "$BUILD"
flatpak build-export "$REPO" "$BUILD" testing
BUNDLE="$OUT/NarratorVerse-${VERSION}-x86_64.flatpak"
SUMS=SHA256SUMS
TEMP="$BUNDLE.pending"
trap 'rm -f "$TEMP"' EXIT HUP INT TERM
flatpak build-bundle "$REPO" "$TEMP" io.github.DevVoidPL.NarratorVerse testing
mv "$TEMP" "$BUNDLE"
(cd "$OUT" && sha256sum "$(basename "$BUNDLE")" > "$SUMS")
printf 'Utworzono: %s\nSuma SHA-256: %s/%s\n' "$BUNDLE" "$OUT" "$SUMS"