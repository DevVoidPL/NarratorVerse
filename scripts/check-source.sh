#!/bin/sh
# Source/frontend checks only: no installation, application launch or audio writes.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
export PATH="$ROOT/.tools/node-v22.22.0-linux-x64/bin:$PATH"

test -f "$ROOT/package.json"
test -d "$ROOT/backend"
test -f "$ROOT/tests/test_quick_read.py"
test -f "$ROOT/tests/test_narrator_audio_balance.py"

printf '\n=== Kontrola zmian Git ===\n'
GIT_CHECK=skipped
if command -v git >/dev/null 2>&1 &&
    [ "$(git -C "$ROOT" rev-parse --is-inside-work-tree 2>/dev/null || :)" = true ]; then
    git -C "$ROOT" diff --check
    GIT_CHECK=passed
else
    printf 'POMINIETO: Git niedostepny lub katalog projektu nie jest drzewem roboczym Git.\n'
    printf 'Nie sprawdzono roznic wzgledem wersji bazowej; nie tworzymy repozytorium.\n'
fi

printf '\n=== Kompilacja Pythona ===\n'
python3 -m compileall -q "$ROOT/backend" "$ROOT/tests"

printf '\n=== Skladnia skryptow kontrolnych ===\n'
sh -n "$ROOT/scripts/check-source.sh"
sh -n "$ROOT/scripts/probe-audio.sh"

printf '\n=== Kontrola Svelte i TypeScript ===\n'
npm run check

printf '\n=== Testy stanu formularza i interfejsu ===\n'
npm run test:ui

printf '\n=== Build frontendu ===\n'
npm run build

printf '\n=== Python, skladnia skryptow i frontend: OK ===\n'
if [ "$GIT_CHECK" = passed ]; then
    printf 'Git diff --check: OK (nie obejmuje plikow niesledzonych).\n'
else
    printf 'Git diff --check: POMINIETO, nie zaliczono tej kontroli.\n'
fi
printf 'Ten skrypt nie wykonuje testow backendu, pakowania ani instalacji.\n'