#!/bin/sh
# The old snapshot implementation is retained as non-executable archival text.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec sh "$ROOT/scripts/build-fresh.sh" "$@"
