#!/usr/bin/env bash
# k-ary parallel bisection: tests J commits per round in isolated git worktrees.
usage() { cat <<'U'
Usage: bisect-parallel.sh [-j JOBS] [--link DIR]... [-t SECONDS] [--no-verify] [--keep] <good> <bad> -- <command> [args...]
  -j           commits tested per round, 1..64 (default: min(64, CPUs) - 1). Rounds = ceil(log_(J+1) N)
  --link DIR   symlink repo-relative DIR (e.g. node_modules, .venv) into each worktree; repeatable
  -t SECONDS   timeout for the whole probe command (timeout/gtimeout); a timeout counts as bad (exit 124)
  --no-verify  skip testing <good> (must pass) and <bad> (must fail) in round 1; frees 2 of the J round-1 slots
  --keep       keep worktrees and logs
Command runs from each worktree root, env BISECT_JOB=<n>. Exit codes as git bisect run:
  0 = good, 125 = skip (untestable, e.g. build broken), 1..127 other = bad, >=128 = treated as skip (signal).
History is linearized with --first-parent (merges tested as units).
Example: bisect-parallel.sh -j 15 --link node_modules v2.3.0 HEAD -- npm test -- tests/cart.test.ts
U
}
set -u
. "$(dirname "$0")/_lib.sh"
J=$(( $(sd_default_jobs) - 1 )); [ "$J" -lt 1 ] && J=1
SD_LINKS=""; T=""; VERIFY=1; KEEP=0; KEEPLOGS=0; POS=()
while [ $# -gt 0 ]; do case "$1" in
  -j) J=$(sd_clamp_jobs "$2") || exit 2; shift 2;; --link) SD_LINKS="$SD_LINKS
$2"; shift 2;; -t) T=$2; shift 2;;
  --no-verify) VERIFY=0; shift;; --keep) KEEP=1; shift;; -h|--help) usage; exit 0;;
  --) shift; break;; -*) echo "unknown option: $1" >&2; exit 2;; *) POS+=("$1"); shift;; esac; done
[ ${#POS[@]} -ne 2 ] || [ $# -eq 0 ] && { usage >&2; exit 2; }
CMD=("$@")
SD_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "error: not inside a git repository" >&2; exit 2; }
cd "$SD_ROOT" || exit 2
GOOD=$(git rev-parse --verify -q "${POS[0]}^{commit}") || { echo "error: bad revision ${POS[0]}" >&2; exit 2; }
BAD=$(git rev-parse --verify -q "${POS[1]}^{commit}")  || { echo "error: bad revision ${POS[1]}" >&2; exit 2; }
git merge-base --is-ancestor "$GOOD" "$BAD" || echo "warn: <good> is not an ancestor of <bad>; using first-parent range anyway" >&2
TO=$(sd_timeout_bin)
# L[0]=GOOD, L[1..N]=first-parent commits after GOOD up to BAD (L[N]=BAD)
L=("$GOOD"); while IFS= read -r c; do L+=("$c"); done < <(git rev-list --reverse --first-parent "$GOOD..$BAD")
N=$(( ${#L[@]} - 1 ))
[ "$N" -lt 1 ] && { echo "error: no commits between good and bad" >&2; exit 2; }
WORK=$(mktemp -d "${TMPDIR:-/tmp}/pbisect.XXXXXX")
cleanup() {   # worktrees always go (unless --keep); logs stay when KEEPLOGS=1
  if [ "$KEEP" != 1 ]; then
    for w in "$WORK"/w*; do [ -d "$w" ] && git worktree remove --force "$w" >/dev/null 2>&1; done
    git worktree prune >/dev/null 2>&1
  fi
  if [ "$KEEP" = 1 ] || [ "$KEEPLOGS" = 1 ]; then echo "logs: $WORK" >&2; else rm -rf "$WORK"; fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM
status_of() { cat "$WORK/st.$1" 2>/dev/null; }   # good|bad|skip

# test_batch idx...  — runs each index in its own worktree concurrently
test_batch() {
  local k=0 idx w sha pids=""
  for idx in "$@"; do
    [ -n "$(status_of "$idx")" ] && continue
    k=$((k+1)); w="$WORK/w$k"; sha=${L[$idx]}
    (
      if [ -d "$w" ]; then git -C "$w" checkout -q --detach -f "$sha" >/dev/null 2>&1 && git -C "$w" clean -fdq >/dev/null 2>&1
      else sd_worktree_add "$sha" "$w"; fi || { echo skip >"$WORK/st.$idx"; exit 0; }
      sd_link_deps "$w"
      log="$WORK/log.$idx.$(git rev-parse --short "$sha")"
      if [ -n "$T" ] && [ -n "$TO" ]; then (cd "$w" && BISECT_JOB=$k "$TO" "$T" "${CMD[@]}") >"$log" 2>&1
      else (cd "$w" && BISECT_JOB=$k "${CMD[@]}") >"$log" 2>&1; fi
      rc=$?
      if [ $rc -eq 0 ]; then s=good; elif [ $rc -eq 125 ] || [ $rc -ge 128 ]; then s=skip; else s=bad; fi
      echo "$s" >"$WORK/st.$idx"; echo "$log" >"$WORK/lg.$idx"
    ) &
    pids="$pids $!"
  done
  [ -n "$pids" ] && wait $pids
  return 0
}

start=$(sd_now); round=0; LO=0; HI=$N
echo "bisect: $N commits, $J per round, work dir $WORK" >&2
while :; do
  round=$((round+1)); set --
  if [ "$round" = 1 ] && [ "$VERIFY" = 1 ]; then set -- 0 "$N"; fi
  # interior candidates, evenly spaced, skipping already-known ones
  M=$(( HI - LO - 1 )); SLOTS=$(( J - $# )); [ "$SLOTS" -lt 1 ] && SLOTS=1
  if [ "$M" -gt 0 ]; then
    unknown=(); i=$((LO+1)); while [ $i -lt $HI ]; do [ -z "$(status_of $i)" ] && unknown+=("$i"); i=$((i+1)); done
    U=${#unknown[@]}; P=$SLOTS; [ "$P" -gt "$U" ] && P=$U
    k=1; last=-1; while [ $k -le $P ]; do pos=$(( (k*(U+1))/(P+1) - 1 )); [ $pos -lt 0 ] && pos=0; [ $pos -ge $U ] && pos=$((U-1))
      [ $pos -ne $last ] && set -- "$@" "${unknown[$pos]}"; last=$pos; k=$((k+1)); done
  fi
  [ $# -eq 0 ] && break
  test_batch "$@"
  if [ "$round" = 1 ] && [ "$VERIFY" = 1 ]; then
    [ "$(status_of 0)" != good ] && { echo "ABORT: <good> ${GOOD:0:10} is $(status_of 0), expected good. Log: $(cat "$WORK/lg.0" 2>/dev/null)" >&2; KEEPLOGS=1; exit 3; }
    [ "$(status_of $N)" != bad ] && { echo "ABORT: <bad> ${BAD:0:10} is $(status_of $N), expected bad (flaky? use stress.sh first). Log: $(cat "$WORK/lg.$N" 2>/dev/null)" >&2; KEEPLOGS=1; exit 3; }
  fi
  # narrow: HI = first known bad after LO; LO = last known good before HI
  i=$((LO+1)); while [ $i -lt $HI ]; do [ "$(status_of $i)" = bad ] && { HI=$i; break; }; i=$((i+1)); done
  i=$((HI-1)); while [ $i -gt $LO ]; do [ "$(status_of $i)" = good ] && { LO=$i; break; }; i=$((i-1)); done
  i=$((HI+1)); while [ $i -lt $N ]; do [ "$(status_of $i)" = good ] && { echo "warn: ${L[$i]:0:10} is good after bad ${L[$HI]:0:10} — non-monotonic (flaky test or fix+rebreak)" >&2; break; }; i=$((i+1)); done
  echo "round $round: tested $#, range now ${L[$LO]:0:10}..${L[$HI]:0:10} ($((HI-LO-1)) untested between)" >&2
  [ $((HI-LO)) -le 1 ] && break
done
el=$(( $(sd_now) - start ))
echo
if [ $((HI-LO)) -le 1 ]; then
  echo "FIRST BAD COMMIT (round $round, ${el}s):"
  git --no-pager log -1 --stat --pretty='%H%n%an <%ae> %ad%n%n    %s%n' "${L[$HI]}" | head -30
  echo "bad log:  $(cat "$WORK/lg.$HI" 2>/dev/null)"; echo "good log: $(cat "$WORK/lg.$LO" 2>/dev/null)"
  [ -f "$WORK/lg.$HI" ] && { echo "--- tail of bad log ---"; tail -15 "$(cat "$WORK/lg.$HI")"; }
  KEEPLOGS=1
  exit 0
else
  echo "UNRESOLVED (untestable commits). First bad is one of:"
  i=$((LO+1)); while [ $i -le $HI ]; do echo "  ${L[$i]:0:12} [$(status_of $i || true)] $(git log -1 --pretty=%s "${L[$i]}")"; i=$((i+1)); done
  KEEPLOGS=1; exit 4
fi
