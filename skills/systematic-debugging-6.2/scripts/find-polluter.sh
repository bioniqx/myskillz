#!/usr/bin/env bash
# find-polluter.sh — PARALLEL hunt for tests that create unwanted files/state.
#
# Modes:
#   scan   (default) Run EVERY test file in its own isolated git worktree,
#          up to -j workers concurrently. Finds ALL independent polluters in
#          a single round. Wall-clock: O(n / JOBS) instead of O(n).
#   bisect For ORDER-DEPENDENT pollution (only appears when tests run in
#          sequence). K-ary prefix bisection with parallel probes:
#          O(log n) rounds instead of O(n) sequential runs.
#
# Usage:
#   scripts/find-polluter.sh [-j JOBS] [-m scan|bisect] [-c TEST_CMD] <pollution_path> <test_pattern>
#
# Examples:
#   scripts/find-polluter.sh '.git' 'src/**/*.test.ts'
#   scripts/find-polluter.sh -j 64 -c 'npx vitest run' '.git' 'src/**/*.test.ts'
#   scripts/find-polluter.sh -m bisect '.git' 'src/**/*.test.ts'
#
# Notes:
#   - Must run inside a git repo (worktrees provide cheap isolation).
#   - Uncommitted changes are applied to each worktree; node_modules is
#     symlinked from the repo root so installs aren't repeated.
#   - <pollution_path> is checked RELATIVE to each isolated worktree root.
#   - TEST_CMD is invoked as: $TEST_CMD <testfile>   (default: 'npm test --')

set -uo pipefail

JOBS=64
MODE=scan
TEST_CMD='npm test --'

usage() {
  sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
}

while getopts "j:m:c:h" opt; do
  case "$opt" in
    j) JOBS="$OPTARG" ;;
    m) MODE="$OPTARG" ;;
    c) TEST_CMD="$OPTARG" ;;
    *) usage ;;
  esac
done
shift $((OPTIND - 1))
[ $# -eq 2 ] || usage
[ "$MODE" = scan ] || [ "$MODE" = bisect ] || usage

POLLUTION="$1"
PATTERN="${2#./}"

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "ERROR: must run inside a git repository (worktree isolation required)." >&2
  exit 2
}
cd "$ROOT"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/polluter.XXXXXX")"
LIST="$WORK/tests.list"
RESULTS="$WORK/polluters.list"
: > "$RESULTS"
trap 'git worktree prune >/dev/null 2>&1; rm -rf "$WORK"' EXIT

# Collect test files. find's -path can't match '**/' against zero directory
# levels, so also try the pattern with '**/' collapsed.
find . \( -path "./$PATTERN" -o -path "./${PATTERN//\*\*\//}" \) -type f 2>/dev/null \
  | sed 's|^\./||' | sort -u > "$LIST"
TOTAL=$(wc -l < "$LIST" | tr -d ' ')

if [ "$TOTAL" -eq 0 ]; then
  echo "No test files matched pattern: $PATTERN" >&2
  exit 2
fi
echo "🔍 Hunting polluter of '$POLLUTION' across $TOTAL test files (mode=$MODE, jobs=$JOBS)"

# Snapshot uncommitted changes once; applied to every worktree.
PATCH="$WORK/uncommitted.patch"
git diff HEAD > "$PATCH" 2>/dev/null || : > "$PATCH"

make_worktree() { # $1 = path (must not exist yet)
  local wt="$1" i
  for i in 1 2 3 4 5; do
    if git worktree add --detach --quiet "$wt" HEAD 2>/dev/null; then
      [ -s "$PATCH" ] && (cd "$wt" && git apply "$PATCH" 2>/dev/null || true)
      [ -d "$ROOT/node_modules" ] && [ ! -e "$wt/node_modules" ] && ln -s "$ROOT/node_modules" "$wt/node_modules"
      return 0
    fi
    sleep 0.$((RANDOM % 5 + 1))   # back off on git lock contention
  done
  return 1
}

destroy_worktree() {
  git worktree remove --force "$1" >/dev/null 2>&1 || rm -rf "$1"
}

run_test_in() { # $1 = worktree, $2 = test file
  (cd "$1" && eval "$TEST_CMD \"\$2\"" >/dev/null 2>&1) || true
}

# ---------- scan mode: every file isolated, all in parallel ----------
scan_one() {
  local file="$1" wt
  wt="$WORK/wt.$$.$RANDOM.$RANDOM"
  make_worktree "$wt" || { echo "WARN: worktree failed for $file" >&2; return 0; }
  run_test_in "$wt" "$file"
  if [ -e "$wt/$POLLUTION" ]; then
    printf '%s\n' "$file" >> "$RESULTS"
    echo "🎯 POLLUTER: $file"
  fi
  destroy_worktree "$wt"
}

# ---------- bisect mode: parallel k-ary prefix search ----------
probe_prefix() { # $1 = prefix length m; writes clean|dirty to $PROBES/$1
  local m="$1" wt i=0 f verdict=clean
  wt="$WORK/bwt.$$.$RANDOM.$RANDOM"
  make_worktree "$wt" || { echo unknown > "$PROBES/$m"; return 0; }
  while IFS= read -r f; do
    i=$((i + 1)); [ "$i" -gt "$m" ] && break
    run_test_in "$wt" "$f"
    if [ -e "$wt/$POLLUTION" ]; then verdict=dirty; break; fi
  done < "$LIST"
  echo "$verdict" > "$PROBES/$m"
  destroy_worktree "$wt"
}

export ROOT WORK LIST RESULTS PATCH POLLUTION TEST_CMD PROBES=""
export -f make_worktree destroy_worktree run_test_in scan_one probe_prefix

if [ "$MODE" = scan ]; then
  xargs -P "$JOBS" -I{} bash -c 'scan_one "$@"' _ {} < "$LIST"
  FOUND=$(wc -l < "$RESULTS" | tr -d ' ')
  echo ""
  if [ "$FOUND" -gt 0 ]; then
    echo "🎯 Found $FOUND polluter(s):"
    sed 's/^/   - /' "$RESULTS"
    echo ""
    echo "Note: if no file pollutes in isolation but pollution appears in full runs,"
    echo "the pollution is order-dependent → rerun with: -m bisect"
    exit 1
  fi
  echo "✅ No polluter found in isolation. If pollution appears in full runs, try: -m bisect"
  exit 0
fi

# bisect mode
PROBES="$WORK/probes"; mkdir -p "$PROBES"; export PROBES

echo "[bisect] Verifying full prefix ($TOTAL files) reproduces pollution..."
probe_prefix "$TOTAL"
if [ "$(cat "$PROBES/$TOTAL")" != dirty ]; then
  echo "✅ Full sequential run produced no pollution — nothing to bisect."
  exit 0
fi

LO=0   # prefix(LO) clean
HI=$TOTAL  # prefix(HI) dirty
K="$JOBS"; [ "$K" -gt 8 ] && K=8   # probes are expensive; 8-way is plenty

while [ $((HI - LO)) -gt 1 ]; do
  RANGE=$((HI - LO))
  STEP=$(( (RANGE + K) / (K + 1) )); [ "$STEP" -lt 1 ] && STEP=1
  MIDS="$WORK/mids"; : > "$MIDS"
  m=$((LO + STEP))
  while [ "$m" -lt "$HI" ]; do
    [ -f "$PROBES/$m" ] || printf '%s\n' "$m" >> "$MIDS"
    m=$((m + STEP))
  done
  [ -s "$MIDS" ] || break
  echo "[bisect] range ($LO,$HI] — probing prefixes: $(tr '\n' ' ' < "$MIDS")"
  xargs -P "$K" -I{} bash -c 'probe_prefix "$@"' _ {} < "$MIDS"
  # Tighten bounds using all probe results.
  while IFS= read -r m; do
    v="$(cat "$PROBES/$m" 2>/dev/null || echo unknown)"
    if [ "$v" = clean ] && [ "$m" -gt "$LO" ]; then LO=$m; fi
    if [ "$v" = dirty ] && [ "$m" -lt "$HI" ]; then HI=$m; fi
  done < "$MIDS"
done

POLLUTER="$(sed -n "${HI}p" "$LIST")"
echo ""
echo "🎯 FOUND POLLUTER (order-dependent): $POLLUTER"
echo "   Pollution '$POLLUTION' first appears when it runs after the first $LO clean file(s)."
echo ""
echo "To investigate:"
echo "  $TEST_CMD $POLLUTER    # run just this test"
echo "  cat $POLLUTER          # review test code"
exit 1
