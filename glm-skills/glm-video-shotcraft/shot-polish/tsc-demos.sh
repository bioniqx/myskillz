#!/usr/bin/env bash
# tsc-demos.sh [relative path or directory under demos…] — Type-check demos with workbench node_modules matching CI (strict).
# No arguments = check all demos. Example: shot-polish/tsc-demos.sh camera/crash-zoom-punch data
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKBENCH="$ROOT/workbench"
TSC="$WORKBENCH/node_modules/.bin/tsc"

if [[ ! -x "$TSC" ]]; then
  echo "tsc not found under workbench/node_modules. Run: (cd workbench && npm install)" >&2
  exit 2
fi

TMP_CONFIG="$(mktemp -t tsc-demos-XXXXXX.json)"
trap 'rm -f "$TMP_CONFIG"' EXIT

if [[ $# -eq 0 ]]; then
  INCLUDES='"demos/**/*.tsx", "demos/**/*.ts"'
else
  INCLUDES=""
  for arg in "$@"; do
    clean="${arg#demos/}"
    clean="${clean#/}"
    if [[ -d "$ROOT/demos/$clean" ]]; then
      pattern="demos/$clean/**/*.tsx\", \"demos/$clean/**/*.ts"
    elif [[ -f "$ROOT/demos/$clean" ]]; then
      pattern="demos/$clean"
    elif [[ -f "$ROOT/demos/$clean.tsx" ]]; then
      pattern="demos/$clean.tsx"
    else
      echo "No such file or directory under demos/: $arg" >&2
      exit 2
    fi
    if [[ -z "$INCLUDES" ]]; then
      INCLUDES="\"$pattern\""
    else
      INCLUDES="$INCLUDES, \"$pattern\""
    fi
  done
fi

cat > "$TMP_CONFIG" <<EOF
{
  "extends": "$WORKBENCH/tsconfig.json",
  "compilerOptions": {
    "noEmit": true
  },
  "include": [
    "workbench/src/vite-env.d.ts",
    $INCLUDES
  ]
}
EOF

echo "Type-checking with workbench/tsconfig.json..."
"$TSC" -p "$TMP_CONFIG"
echo "OK"
