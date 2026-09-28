#!/usr/bin/env bash
# Find which test file creates an unwanted file/dir. Parallel, one isolated git worktree per worker.
usage() { cat <<'U'
Usage: find-polluter.sh [-j JOBS] [--cmd 'TEST COMMAND'] [--link DIR]... [--all] <pollution_path> <test_glob>
  pollution_path  repo-relative path that should NOT exist after tests (e.g. .git, tmp/out.db)
  test_glob       e.g. 'src/**/*.test.ts'  ('**/' also matches zero directories)
  -j JOBS         parallel workers 1..64 (default: min(16, CPUs)). Forced to 1 outside git or for absolute paths
  --cmd CMD       test runner prefix; the test file is appended (default: 'npm test --')
  --link DIR      symlink repo-relative DIR (node_modules, .venv ...) into each worktree; repeatable
  --all           report every polluter instead of stopping at the first
Tests run from the same subdirectory inside each worktree, env POLLUTER_JOB=<n>; the worktree is reset between tests.
Uncommitted edits and untracked (non-ignored) files are copied into the worktrees. Exit 1 = polluter found, 0 = none.
U
}
set -u
. "$(dirname "$0")/_lib.sh"
J=$(sd_cpus); [ "$J" -gt 16 ] && J=16
RUNNER='npm test --'; SD_LINKS=""; ALL=0; POS=()
while [ $# -gt 0 ]; do case "$1" in
  -j) J=$(sd_clamp_jobs "$2") || exit 2; shift 2;; --cmd) RUNNER=$2; shift 2;;
  --link) SD_LINKS="$SD_LINKS
$2"; shift 2;; --all) ALL=1; shift;; -h|--help) usage; exit 0;;
  -*) echo "unknown option: $1" >&2; exit 2;; *) POS+=("$1"); shift;; esac; done
[ ${#POS[@]} -ne 2 ] && { usage >&2; exit 2; }
POLL=${POS[0]}; PAT=${POS[1]#./}; ORIG=$(pwd)
SD_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || SD_ROOT=""
case "$POLL" in /*) [ "$J" -gt 1 ] && echo "warn: absolute pollution path is shared by all workers -> -j 1" >&2; J=1;; esac
[ -z "$SD_ROOT" ] && { [ "$J" -gt 1 ] && echo "warn: not a git repo -> sequential in place" >&2; J=1; }
REL=""; [ -n "$SD_ROOT" ] && REL=$(git rev-parse --show-prefix)   # run from the same subdir inside worktrees
FILES=$(find . -type f \( -path "./$PAT" -o -path "./${PAT//\*\*\//}" \) -not -path '*/node_modules/*' -not -path './.git/*' 2>/dev/null | sed 's|^\./||' | sort -u)
TOTAL=$(printf '%s' "$FILES" | grep -c .)
[ "$TOTAL" -eq 0 ] && { echo "no test files match '$PAT'"; exit 0; }
[ "$J" -gt "$TOTAL" ] && J=$TOTAL
WORK=$(mktemp -d "${TMPDIR:-/tmp}/polluter.XXXXXX")
cleanup() { for w in "$WORK"/w*; do [ -d "$w" ] && git worktree remove --force "$w" >/dev/null 2>&1; done
  [ -n "$SD_ROOT" ] && git worktree prune >/dev/null 2>&1; rm -rf "$WORK"; }
trap cleanup EXIT; trap 'exit 130' INT TERM
echo "find-polluter: '$POLL' across $TOTAL test files, $J worker(s)" >&2
ISO=0; [ -n "$SD_ROOT" ] && ISO=1                  # isolated worktrees whenever we are in git
if [ "$ISO" = 1 ] && { [ "$REL$POLL" = ".git" ] || [ "$REL$POLL" = ".git/" ]; }; then echo "warn: pollution path is the repo .git -> in place, sequential" >&2; ISO=0; J=1; fi
case "$POLL" in /*) ABS=1;; *) ABS=0;; esac
{ [ "$ABS" = 1 ] || [ "$ISO" = 0 ]; } && ALL=0        # cannot safely reset shared pollution -> stop at first
if [ "$ABS" = 1 ] || [ "$ISO" = 0 ]; then [ -e "$POLL" ] && { echo "error: '$POLL' already exists; remove it first" >&2; exit 2; }; fi
if [ "$ISO" = 1 ] && [ "$ABS" = 0 ] && git ls-files --error-unmatch "$POLL" >/dev/null 2>&1; then echo "error: '$POLL' is tracked by git" >&2; exit 2; fi
# round-robin buckets
i=0; printf '%s\n' "$FILES" | while IFS= read -r f; do echo "$f" >>"$WORK/bucket.$(( i % J + 1 ))"; i=$((i+1)); done
if [ "$ISO" = 1 ]; then   # carry uncommitted edits + untracked (non-ignored) files into worktrees
  git diff HEAD --binary >"$WORK/wip.patch" 2>/dev/null
  (cd "$SD_ROOT" && u=$(git ls-files --others --exclude-standard | head -1) && [ -n "$u" ] &&
    git ls-files -z --others --exclude-standard | tar -cf "$WORK/untracked.tar" --null -T - 2>/dev/null)
fi
reset_tree() {   # $1 = worktree dir: back to HEAD + uncommitted changes + dep links
  git -C "$1" checkout -q -f -- . 2>/dev/null; git -C "$1" clean -fdxq 2>/dev/null   # -x: pollution is often gitignored
  [ -s "$WORK/wip.patch" ] && git -C "$1" apply "$WORK/wip.patch" 2>/dev/null
  [ -s "$WORK/untracked.tar" ] && tar -xf "$WORK/untracked.tar" -C "$1" 2>/dev/null
  sd_link_deps "$1"
}
run_bucket() {
  local k=$1 dir f target rc
  if [ "$ISO" = 1 ]; then
    dir="$WORK/w$k"; sd_worktree_add HEAD "$dir" || { echo "worker $k: git worktree add failed" >&2; return; }
    reset_tree "$dir"
  else dir=$(pwd); fi
  [ "$ISO" = 1 ] && dir="$dir/$REL"; dir=${dir%/}
  if [ "$ABS" = 1 ]; then target=$POLL; else target="$dir/$POLL"; fi
  while IFS= read -r f; do
    [ "$ALL" = 0 ] && [ -e "$WORK/.found" ] && return
    ( cd "$dir" && POLLUTER_JOB=$k eval "$RUNNER \"\$f\"" ) >"$WORK/log.$k" 2>&1
    rc=$?; echo "$f" >>"$WORK/tested.$k"
    [ $rc -ne 0 ] && { echo "$f" >>"$WORK/nonzero.$k"; [ -s "$WORK/firstfail" ] || cp "$WORK/log.$k" "$WORK/firstfail" 2>/dev/null; }
    if [ -e "$target" ]; then
      [ "$ALL" = 0 ] && [ -e "$WORK/.found" ] && return
      : >"$WORK/.found"; echo "$f" >>"$WORK/found"
      echo "FOUND POLLUTER: $f  (created $POLL)"; ls -ld "$target" | sed 's/^/  /'
      echo "  reproduce: (cd $ORIG && $RUNNER $f)   last output: $(tail -1 "$WORK/log.$k" 2>/dev/null | cut -c1-120)"
      [ "$ALL" = 0 ] && return
      reset_tree "$WORK/w$k"
    fi
  done <"$WORK/bucket.$k"
}
k=1; pids=""; while [ $k -le $J ]; do run_bucket $k & pids="$pids $!"; k=$((k+1)); done
wait $pids
tested=$(cat "$WORK"/tested.* 2>/dev/null | grep -c .); nz=$(cat "$WORK"/nonzero.* 2>/dev/null | grep -c .)
echo "test runs: $tested executed, $nz exited non-zero" >&2
if [ "$nz" -gt 0 ] && [ "$nz" -eq "$tested" ]; then
  echo "WARNING: every test run failed - results are untrustworthy. Check --cmd / --link (ignored files such as .env are not copied). First failure output:" >&2
  head -15 "$WORK/firstfail" >&2
fi
if [ -s "$WORK/found" ]; then exit 1; fi
echo "No polluter found across $TOTAL files (single-file runs). If pollution only appears in the full suite, it is order-dependent: see parallel-playbook.md (order-dependent failures)."
exit 0
