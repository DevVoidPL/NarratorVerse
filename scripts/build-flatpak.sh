#!/bin/sh
# Local unsigned verification bundle, not a distribution-ready release.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BUILD="$ROOT/flatpak/build"
REPO="$ROOT/flatpak/repo"
OUT="$ROOT/flatpak/artifacts"
if [ -e "$BUILD" ]; then
  printf '%s\n' "Refusing to replace existing build directory: $BUILD" >&2
  exit 1
fi
mkdir -p "$OUT"
flatpak build-init "$BUILD" io.github.DevVoidPL.NarratorVerse org.gnome.Sdk org.gnome.Platform 49
python3 "$ROOT/scripts/stage-flatpak.py" --dest "$BUILD/files"
flatpak build-finish --command=narratorverse --share=ipc --share=network --socket=wayland --socket=fallback-x11 --socket=pulseaudio --device=dri "$BUILD"
flatpak build-export "$REPO" "$BUILD" testing
BUNDLE="$OUT/NarratorVerse-0.1.0-x86_64.flatpak"
TEMP="$BUNDLE.pending"
trap 'rm -f "$TEMP"' EXIT HUP INT TERM
flatpak build-bundle "$REPO" "$TEMP" io.github.DevVoidPL.NarratorVerse testing
mv "$TEMP" "$BUNDLE"
(cd "$OUT" && sha256sum NarratorVerse-0.1.0-x86_64.flatpak > SHA256SUMS)