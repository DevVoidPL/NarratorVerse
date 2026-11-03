#!/bin/sh
# Use the same local Python/Qt runtime as NarratorVerse, without launching it.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec flatpak run --filesystem="$ROOT" --command=sh org.gnome.Sdk//49 -c '
  ROOT=$1
  shift
  cd "$ROOT"
  export PYTHONPATH="$ROOT/.tools/test-python:$ROOT/backend:$ROOT/tests:$ROOT/.runtime/lib/python3.13/site-packages"
  export LD_LIBRARY_PATH="$ROOT/.runtime/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  export PATH="$ROOT/.runtime/bin:$PATH"
  export QT_QPA_PLATFORM=offscreen
   export PYTHONDONTWRITEBYTECODE=1
  exec python3 -m pytest -q "$@"
' narratorverse-tests "$ROOT" "$@"