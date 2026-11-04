#!/bin/sh
# Fresh candidate only. No export, install, push or release publication.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  printf 'Usage: sh scripts/build-fresh.sh NEW_ABSOLUTE_WORKDIR [OWNER_VOIDEK_DIR]\n' >&2
  exit 2
fi
WORK=$1
case "$WORK" in /*) ;; *) echo 'Work directory must be absolute' >&2; exit 2;; esac
test ! -e "$WORK" || { echo 'Refusing to overwrite existing work directory' >&2; exit 2; }
BUILDER=${FLATPAK_BUILDER:-flatpak-builder}
command -v "$BUILDER" >/dev/null
mkdir -p "$WORK"
export PYTHONDONTWRITEBYTECODE=1
python3 - "$ROOT" "$WORK" <<'PY'
import json, os, subprocess, sys
from pathlib import Path
r,w=map(Path,sys.argv[1:]);pins=json.loads((r/'flatpak/sdk-lock.json').read_text())
for ref,expected in pins.items():
    actual=subprocess.check_output(['flatpak','--user','info','--show-commit',ref],text=True).strip()
    if actual!=expected:raise SystemExit('SDK pin mismatch: '+ref)
(w/'git-status.txt').write_text(subprocess.check_output(['git','-C',str(r),'status','--porcelain=v1'],text=True))
(w/'git-head.txt').write_text(subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD'],text=True))
PY
if [ "$#" -eq 2 ]; then
  if [ -n "${NARRATORVERSE_WHEEL_CACHE:-}" ]; then
    python3 "$ROOT/scripts/fresh-inputs.py" --work "$WORK" --voidek-input "$2" --wheel-cache "$NARRATORVERSE_WHEEL_CACHE"
  else
    python3 "$ROOT/scripts/fresh-inputs.py" --work "$WORK" --voidek-input "$2"
  fi
else
  if [ -n "${NARRATORVERSE_WHEEL_CACHE:-}" ]; then
    python3 "$ROOT/scripts/fresh-inputs.py" --work "$WORK" --wheel-cache "$NARRATORVERSE_WHEEL_CACHE"
  else
    python3 "$ROOT/scripts/fresh-inputs.py" --work "$WORK"
  fi
fi
# All dependency preparation is isolated from project node_modules/target/cache.
NODE_ARCHIVE=$(python3 - "$ROOT" "$WORK" <<'PY'
import importlib.util,json,sys
from pathlib import Path
r,w=map(Path,sys.argv[1:]);s=importlib.util.spec_from_file_location('inputs',r/'scripts/fresh-inputs.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
a=next(a for a in json.loads((r/'flatpak/build-tools-lock.json').read_text()) if a['filename'].startswith('node'))
print(m.fetch(a,w/'downloads'))
PY
)
mkdir "$WORK/node"
tar -xJf "$NODE_ARCHIVE" --strip-components=1 -C "$WORK/node"
(cd "$WORK/source"; PATH="$WORK/node/bin:$PATH" npm ci --cache "$WORK/npm-cache" --ignore-scripts --no-audit --no-fund)
mkdir "$WORK/cargo-config" "$WORK/build-locks"
cp "$ROOT"/flatpak/*-lock.json "$WORK/build-locks/"
flatpak --user run --share=network --filesystem="$WORK" --command=sh org.gnome.Sdk//49 -c '
  set -eu
  export PATH=/usr/lib/sdk/rust-stable/bin:$PATH
  export CARGO_HOME="$1/cargo-home"
  cd "$1/source/src-tauri"
  cargo vendor --locked --versioned-dirs "$1/vendor" > "$1/cargo-config/config.toml"
' fresh-vendor "$WORK"
# cargo vendor emits an absolute source directory; remap for builder sandbox.
sed -i "s|$WORK/vendor|/run/build/narratorverse/vendor|g" "$WORK/cargo-config/config.toml"
python3 - "$ROOT" "$WORK" <<'PY'
import json,sys
from pathlib import Path
r,w=map(Path,sys.argv[1:]);text=(r/'flatpak/io.github.DevVoidPL.NarratorVerse.json').read_text()
# Replace string values structurally, keeping unusual paths valid JSON.
def expand(v):
    if isinstance(v,str):return v.replace('@WORK@',str(w))
    if isinstance(v,list):return [expand(x) for x in v]
    if isinstance(v,dict):return {k:expand(x) for k,x in v.items()}
    return v
(w/'manifest.json').write_text(json.dumps(expand(json.loads(text)),indent=2)+'\n')
PY
"$BUILDER" --user --state-dir="$WORK/builder-state" --download-only "$WORK/build" "$WORK/manifest.json" > "$WORK/download.log" 2>&1
"$BUILDER" --user --state-dir="$WORK/builder-state" --disable-download "$WORK/build" "$WORK/manifest.json" > "$WORK/build.log" 2>&1
# Builder embeds the expanded host manifest after install; normalize before any
# inventory/export while retaining the original privately in the work directory.
python3 "$ROOT/scripts/packaging_policy.py" "$WORK/build/files/manifest.json" "$WORK"
flatpak build --runtime --unshare=network --filesystem="$ROOT/scripts:ro" "$WORK/build" \
  sh -c 'export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1; exec python3 "$1/validate-fresh.py"' \
  validate "$ROOT/scripts" > "$WORK/validation.log" 2>&1
python3 "$ROOT/scripts/payload-inventory.py" --root "$WORK/build/files" --output "$WORK/payload-inventory.json"
printf 'Fresh candidate built, NOT published: %s\nValidation and license/source gates remain mandatory.\n' "$WORK"