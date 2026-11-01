#!/bin/sh
# Read-only diagnosis: no volume writes, routing changes, installs or overrides.
set -eu

APP_ID=io.github.DevVoidPL.NarratorVerse

printf '%s\n' '=== NarratorVerse: diagnostyka audio (tylko odczyt) ==='
printf '%s\n' 'Uruchom grę z dźwiękiem, aby jej strumień był widoczny.'

# Bound every server query. Do not connect at all when timeout is unavailable.
PROBE='
  printf "pactl: "
  if ! command -v pactl; then
    printf "%s\n" "Brak narzędzia pactl; nie instalowano niczego."
    exit 0
  fi
  if ! command -v timeout >/dev/null 2>&1; then
    printf "%s\n" "Brak timeout; pomijam połączenie z serwerem audio."
    exit 0
  fi
  printf "%s\n" "--- Serwer audio ---"
  if ! LC_ALL=C timeout 5 pactl info; then
    printf "%s\n" "Nie udało się odczytać informacji o serwerze."
    exit 0
  fi
  printf "%s\n" "--- Odtwarzające aplikacje (sink inputs) ---"
  if ! LC_ALL=C timeout 5 pactl list sink-inputs; then
    printf "%s\n" "Nie udało się odczytać strumieni aplikacji."
  fi
'

printf '\n%s\n' '=== HOST ==='
sh -c "$PROBE"

printf '\n%s\n' '=== ZAINSTALOWANY FLATPAK ==='
if ! command -v flatpak >/dev/null 2>&1; then
  printf '%s\n' 'Brak polecenia flatpak; pomijam sprawdzenie pakietu.'
  exit 0
fi
if ! command -v timeout >/dev/null 2>&1; then
  printf '%s\n' 'Brak timeout; pomijam uruchomienie powłoki diagnostycznej.'
  exit 0
fi
if ! timeout 5 flatpak info --user "$APP_ID" >/dev/null 2>&1; then
  printf '%s\n' 'Nie znaleziono instalacji użytkownika NarratorVerse lub odczyt nie powiódł się.'
  exit 0
fi
# Launch only sh from the package, NOT the application or its Python backend.
# No host execution or extra permissions are granted.
if ! timeout 20 flatpak run --command=sh "$APP_ID" -c "$PROBE"; then
  printf '%s\n' 'Sprawdzenie wnętrza Flatpaka nie powiodło się lub przekroczyło limit czasu.'
fi

printf '\n%s\n' 'Koniec diagnostyki. Nie zmieniono głośności ani konfiguracji audio.'
printf '%s\n' 'Wynik może zawierać nazwy aplikacji/urządzeń i ścieżki użytkownika; przejrzyj przed udostępnieniem.'