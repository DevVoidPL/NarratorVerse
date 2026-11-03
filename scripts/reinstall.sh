#!/bin/sh
# Build and reinstall NarratorVerse only; preserve user data and old staging.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

printf '%s\n' '1/3 Budowanie NarratorVerse...'
sh "$ROOT/scripts/build.sh"

BUILD="$ROOT/flatpak/build"
if [ -e "$BUILD" ]; then
  BACKUP=$(mktemp -d "$ROOT/flatpak/build-backup.XXXXXX")
  mv -- "$BUILD" "$BACKUP/build"
  printf 'Poprzedni katalog budowania zachowany: %s/build\n' "$BACKUP"
fi

printf '%s\n' '2/3 Pakowanie Flatpaka...'
sh "$ROOT/scripts/build-flatpak.sh"

printf '%s\n' '3/3 Reinstalacja NarratorVerse bez usuwania danych...'
flatpak install --user --noninteractive --assumeyes --reinstall --bundle \
  "$ROOT/flatpak/artifacts/NarratorVerse-${VERSION}-beta-integration-x86_64.flatpak"

printf '%s\n' 'Zainstalowany commit NarratorVerse:'
flatpak info --user --show-commit io.github.DevVoidPL.NarratorVerse
printf '%s\n' 'Gotowe. Uruchom NarratorVerse ponownie. Ten skrypt nie uruchamia testów backendu.'