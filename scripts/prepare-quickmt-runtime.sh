#!/bin/sh
# Pinned native build dependency setup. No model download or shared runtime writes.
set -eu
umask 077
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ "$#" -ne 0 ]; then
  printf 'Użycie: sh scripts/prepare-quickmt-runtime.sh\nJawnie pobiera przypięty SentencePiece do .tools/quickmt-python; nie zmienia .runtime.\n' >&2
  exit 2
fi
command -v flatpak >/dev/null 2>&1 || { printf 'Brak Flatpaka\n' >&2; exit 2; }
flatpak info org.gnome.Sdk//49 >/dev/null 2>&1 || { printf 'Brak org.gnome.Sdk//49\n' >&2; exit 2; }
if flatpak run --share=network --filesystem="$ROOT" --command=sh org.gnome.Sdk//49 -c '
  set -eu
  ROOT=$1
  export PYTHONPATH="$ROOT/backend:$ROOT/.runtime/lib/python3.13/site-packages"
  export LD_LIBRARY_PATH="$ROOT/.runtime/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  python3 -c "import platform, sys; assert sys.version_info[:2] == (3, 13) and platform.machine() == \"x86_64\", \"Wymagany CPython 3.13 / x86_64\""
  python3 -c "import ctranslate2; assert callable(getattr(ctranslate2, \"Translator\", None)), \"Brak natywnego Translator CTranslate2\"; print(\"CTranslate2 CPU:\", ctranslate2.get_supported_compute_types(\"cpu\"))"
  mkdir -p "$ROOT/.tools"
  TARGET="$ROOT/.tools/quickmt-python"
  if [ -e "$TARGET" ] || [ -L "$TARGET" ]; then
    if PYTHONPATH="$ROOT/backend:$TARGET:$ROOT/.runtime/lib/python3.13/site-packages" python3 -m narratorverse.quickmt_runtime; then
      printf "Istniejący runtime działa; niczego nie zmieniono.\n"
      exit 0
    fi
    printf "Istniejący katalog %s nie przeszedł diagnostyki. Zachowano go bez zmian; przenieś go do kopii i ponów polecenie.\n" "$TARGET" >&2
    exit 1
  fi
  WORK=$(mktemp -d "$ROOT/.tools/quickmt-prepare.XXXXXX")
  trap '\''rm -rf -- "$WORK"'\'' EXIT
  python3 -m venv "$WORK/venv"
  "$WORK/venv/bin/python3" -m pip --isolated install --disable-pip-version-check \
    --no-index --no-deps --no-compile --only-binary=:all: --require-hashes \
    --target "$WORK/packages" -r "$ROOT/scripts/quickmt-runtime-requirements.txt"
  PYTHONPATH="$ROOT/backend:$WORK/packages:$ROOT/.runtime/lib/python3.13/site-packages" python3 -m narratorverse.quickmt_runtime
  # Publish only a fully import-tested directory, never merge into shared runtime.
  python3 -c "import os, sys; os.rename(sys.argv[1], sys.argv[2])" "$WORK/packages" "$TARGET"
  printf "SentencePiece gotowy w %s; wspólny .runtime bez zmian.\n" "$TARGET"
' narratorverse-quickmt-prepare "$ROOT"; then
  printf '
SentencePiece gotowy do standardowego pakowania.
'
else
  printf '\nPrzygotowanie nieudane. Sprawdź błąd powyżej i ponów to samo polecenie. Model i wspólny runtime zachowano.\n' >&2
  exit 1
fi
