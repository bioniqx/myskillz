#!/usr/bin/env bash
# Run a command many times in parallel to measure an intermittent failure and capture failing logs.
usage() { cat <<'U'
Usage: stress.sh [-n RUNS] [-j JOBS] [-t SECONDS] [-o DIR] [-k] [-x] [-b F/N] -- <command> [args...]
  -n  total runs (default 100)
  -j  parallel runs, 1..64 (default: min(64, CPUs)); raise above CPUs to add load
  -t  per-run timeout in seconds (needs timeout/gtimeout; default none)
  -o  output dir (default: mktemp)
  -k  keep logs of passing runs too (for diffing pass vs fail)
  -x  stop launching new runs after the first failure
  -b  baseline F/N (failures/runs before a fix): prints one-sided Fisher exact p (fixed if p < 0.05)
Each run gets env STRESS_RUN=<i> and its own TMPDIR. Exit 0 = no failures, 1 = failures, 2 = usage, 125 = every run exited 125 (skip, for bisect).
Example: stress.sh -n 200 -j 32 -t 120 -- npx vitest run src/queue.test.ts
U
}
set -u
. "$(dirname "$0")/_lib.sh"
N=100; J=$(sd_default_jobs); T=""; OUT=""; OWN_OUT=0; KEEP=0; STOP=0; BASE=""
while [ $# -gt 0 ]; do case "$1" in
  -n) N=$2; shift 2;; -j) J=$(sd_clamp_jobs "$2") || exit 2; shift 2;; -t) T=$2; shift 2;; -o) OUT=$2; shift 2;;
  -k) KEEP=1; shift;; -x) STOP=1; shift;; -b) BASE=$2; shift 2;; -h|--help) usage; exit 0;; --) shift; break;;
  *) echo "unknown option: $1" >&2; usage >&2; exit 2;; esac; done
[ $# -eq 0 ] && { usage >&2; exit 2; }
case "$N" in ''|*[!0-9]*|0) echo "error: -n must be a positive integer" >&2; exit 2;; esac
case "$BASE" in ''|*[0-9]/*[0-9]) ;; *) echo "error: -b expects F/N, e.g. 14/200" >&2; exit 2;; esac
[ -z "$OUT" ] && { OUT=$(mktemp -d "${TMPDIR:-/tmp}/stress.XXXXXX"); OWN_OUT=1; }; mkdir -p "$OUT"
TO=$(sd_timeout_bin); [ -n "$T" ] && [ -z "$TO" ] && echo "warn: no timeout/gtimeout found; -t ignored" >&2
# Serialize command safely for the worker.
CMD=""; for a in "$@"; do CMD="$CMD $(printf '%q' "$a")"; done
export OUT KEEP STOP T TO CMD
worker() {
  i=$1; [ "$STOP" = 1 ] && [ -e "$OUT/.stop" ] && exit 0
  d="$OUT/tmp.$i"; mkdir -p "$d"; log="$OUT/run.$i.log"
  if [ -n "$T" ] && [ -n "$TO" ]; then STRESS_RUN=$i TMPDIR=$d "$TO" "$T" bash -c "$CMD" >"$log" 2>&1
  else STRESS_RUN=$i TMPDIR=$d bash -c "$CMD" >"$log" 2>&1; fi
  rc=$?; rm -rf "$d"; echo "$rc" >"$OUT/rc.$i"
  if [ "$rc" -ne 0 ]; then mv "$log" "$OUT/FAIL.$i.rc$rc.log"; [ "$STOP" = 1 ] && : >"$OUT/.stop"
  elif [ "$KEEP" != 1 ]; then rm -f "$log"; fi
  exit 0
}
export -f worker
start=$(sd_now)
echo "stress: $N runs, $J parallel, logs in $OUT" >&2
seq 1 "$N" | xargs -P "$J" -I{} bash -c 'worker "$@"' _ {}
el=$(( $(sd_now) - start ))
ran=$(ls "$OUT" | grep -c '^rc\.'); fails=$(ls "$OUT" | grep -c '^FAIL\.')
awk -v f="$fails" -v n="$ran" -v el="$el" -v base="$BASE" '
function wilson(f,n,  p,z,d,c,h){ p=f/n; z=1.96; d=1+z*z/n; c=(p+z*z/(2*n))/d; h=z*sqrt(p*(1-p)/n+z*z/(4*n*n))/d; WL=(c-h<0?0:c-h); WH=(c+h>1?1:c+h) }
function lc(a,b){ return LF[a]-LF[b]-LF[a-b] }
BEGIN{
  if(n==0){print "no runs completed"; exit}
  wilson(f,n); printf "RESULT: %d/%d failed (%.1f%%), 95%% Wilson CI [%.2f%%, %.1f%%], wall %ds\n", f, n, 100*f/n, 100*WL, 100*WH, el
  if(f==0){u=300/n; if(u>100)u=100; printf "No failures: 95%% upper bound on failure rate ~ %.2f%% (rule of three)\n", u}
  else if(base==""){ printf "To prove a fix: >= %d clean runs (3 / Wilson lower bound), or rerun with -b %d/%d\n", int(3/WL)+1, f, n }
  if(base!=""){ split(base,B,"/"); F=B[1]+0; M=B[2]+0; T=M+n; K=F+f
    LF[0]=0; for(i=1;i<=T;i++) LF[i]=LF[i-1]+log(i)
    pv=0; for(x=0;x<=f;x++){ if(x>K||n-x>T-K) continue; pv+=exp(lc(K,x)+lc(T-K,n-x)-lc(T,n)) }
    if(pv>1)pv=1; wilson(F,M)
    printf "VS BASELINE %d/%d: one-sided Fisher exact p = %.4g -> %s\n", F, M, pv, (pv<0.05 ? "rate is significantly LOWER (fix supported)" : "NOT significant: need more runs or the fix did not work")
    if(F>0) printf "  zero-failure runs needed vs baseline ~ %d (3 / baseline Wilson lower bound %.2f%%)\n", int(3/WL)+1, 100*WL }
}'
if [ "$fails" -gt 0 ] && [ "$(cat "$OUT"/rc.* | grep -vc '^125$')" -eq 0 ]; then
  echo "all runs exited 125 (untestable) -> exit 125"; exit 125
fi
if [ "$fails" -gt 0 ]; then
  echo "exit codes:"; cat "$OUT"/rc.* | grep -v '^0$' | sort | uniq -c | sed 's/^/  /'
  echo "failing logs (first 5):"; ls "$OUT"/FAIL.*.log | head -5 | sed 's/^/  /'
  first=$(ls "$OUT"/FAIL.*.log | head -1); echo "--- tail of $first ---"; tail -25 "$first"
  exit 1
fi
[ "$OWN_OUT" = 1 ] && [ "$KEEP" != 1 ] && rm -rf "$OUT"
exit 0
