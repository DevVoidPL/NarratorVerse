#!/bin/sh
# Build and reinstall NarratorVerse only; preserve user data and old staging.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

# Do not let the old two-stage installer consume historical staging or silently
# install an unvalidated candidate. Fresh builds have no automatic installation.
printf '%s\n' 'Automatic reinstall is disabled during the fresh-build transition.' \
  'Build a new candidate with scripts/build-fresh.sh; installation requires validation.' >&2
exit 2

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