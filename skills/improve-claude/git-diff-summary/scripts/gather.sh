#!/usr/bin/env bash
# git-diff-summary / gather.sh — one-shot, parallel, byte-gated context gatherer.
# Portable: bash 3.2 (macOS) + BSD/mawk/gawk. No GNU `timeout` needed. Read-only for the repo.
# Usage: gather.sh [base-branch]     Env: GDS_REMOTE GDS_FETCH_TIMEOUT GDS_FRESH_SECS GDS_NO_FETCH GDS_EXCLUDE
set -u
export GIT_PAGER=cat GIT_OPTIONAL_LOCKS=0 GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=never LC_ALL=C
export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -oBatchMode=yes -oConnectTimeout=4}"
FETCH_TIMEOUT=${GDS_FETCH_TIMEOUT:-6}   # seconds; fetch never blocks longer than this
FRESH_SECS=${GDS_FRESH_SECS:-300}       # skip fetch if base ref was updated this recently
OUT_CAP=28500                            # stay under the ~30KB Bash/tool output cap
READ_MAX=${GDS_READ_MAX:-200000}         # <= this: main agent reads chunks itself (no subagents)
READ_CHUNK=45000                         # per-Read chunk (well under Read token cap)
FAN_CHUNK=${GDS_FAN_CHUNK:-64000}        # min bytes per subagent chunk (~18k tokens: one Read)
MAXN=64
G="git -c core.quotepath=off -c diff.external= -c color.ui=never"

$G rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo NOT_A_REPO; exit 0; }
cd "$($G rev-parse --show-toplevel)" || exit 0
T=$(mktemp -d "${TMPDIR:-/tmp}/gds.XXXXXX") || exit 1
( find "${TMPDIR:-/tmp}" -maxdepth 1 -name 'gds.*' -mmin +180 -exec rm -rf {} + ) >/dev/null 2>&1 &   # GC old runs

EXC=()
for p in package-lock.json npm-shrinkwrap.json yarn.lock pnpm-lock.yaml bun.lockb bun.lock Cargo.lock \
         poetry.lock uv.lock Pipfile.lock Gemfile.lock composer.lock go.sum Podfile.lock pubspec.lock packages.lock.json \
         '*.min.js' '*.min.css' '*.map' '*.snap' '*.pb.go' '*_pb2.py' '*.g.dart' '*.freezed.dart' '*.generated.*' '*.meta' \
         'dist/**' 'build/**' 'out/**' 'vendor/**' 'node_modules/**' ${GDS_EXCLUDE:-}; do
  EXC+=(":(exclude,glob)**/$p")
done

# ---- remote & base branch -------------------------------------------------------------
REMOTE=${GDS_REMOTE:-origin}
$G remote | grep -qx "$REMOTE" || REMOTE=$($G remote | head -n1)
has(){ $G rev-parse -q --verify "$1^{commit}" >/dev/null 2>&1; }
ARG=${1:-}; ARG=${ARG#refs/heads/}; [ -n "$REMOTE" ] && ARG=${ARG#"$REMOTE"/}
case "$ARG" in *[!A-Za-z0-9._/-]*|'') ARG_OK=0 ;; *) ARG_OK=1 ;; esac
[ -n "${1:-}" ] && [ $ARG_OK -eq 0 ] && echo "WARN_BASE_ARG_IGNORED=$1"
if [ $ARG_OK -eq 1 ]; then B=$ARG
else
  B=""
  [ -n "$REMOTE" ] && B=$($G symbolic-ref -q --short "refs/remotes/$REMOTE/HEAD" 2>/dev/null) && B=${B#"$REMOTE"/}
  if [ -z "$B" ]; then
    for c in main master develop trunk; do
      { [ -n "$REMOTE" ] && has "$REMOTE/$c"; } || has "refs/heads/$c" && { B=$c; break; }
    done
  fi
  B=${B:-main}
fi

# ---- fetch in background (portable timeout, never prompts, never holds our stdout) ----------
FST=skip
if [ -n "$REMOTE" ] && [ -z "${GDS_NO_FETCH:-}" ]; then
  last=$($G log -g -n1 --date=unix --format=%gd "refs/remotes/$REMOTE/$B" 2>/dev/null | sed -n 's/.*@{\([0-9]*\)}.*/\1/p')  # reflog time, not commit time
  STAMP=$($G rev-parse --git-path "gds-fetched-$(printf %s "$REMOTE-$B" | tr '/' '_')")
  st=$(cat "$STAMP" 2>/dev/null); [ -n "$st" ] && { [ -z "$last" ] || [ "$st" -gt "$last" ]; } && last=$st
  if [ -n "$last" ] && [ $(( $(date +%s) - last )) -lt "$FRESH_SECS" ]; then FST=fresh
  else
    FST=run
    (
      $G fetch --no-tags --quiet --no-write-fetch-head --no-recurse-submodules "$REMOTE" \
        "+refs/heads/$B:refs/remotes/$REMOTE/$B" >/dev/null 2>&1 & fp=$!
      ( sleep "$FETCH_TIMEOUT"; kill "$fp" 2>/dev/null ) >/dev/null 2>&1 & wp=$!
      wait "$fp"; rc=$?; echo $rc > "$T/frc"; kill "$wp" 2>/dev/null; [ $rc -eq 0 ] && date +%s > "$STAMP"
    ) >/dev/null 2>&1 &
    FJOB=$!
  fi
fi

pick_ref(){ if [ -n "$REMOTE" ] && has "$REMOTE/$B"; then echo "$REMOTE/$B"; elif has "refs/heads/$B"; then echo "$B"; fi; }

# diff generation depends ONLY on the merge-base -> speculate on the cached ref while fetch runs.
gen(){ # $1=merge-base $2=outdir
  mkdir -p "$2"
  $G diff -M --no-ext-diff --ignore-submodules=dirty --numstat "$1" > "$2/numstat" 2>/dev/null &
  $G diff -M --no-ext-diff --ignore-submodules=dirty "$1" -- . "${EXC[@]}" 2>/dev/null | grep -v '^index [0-9a-f]' > "$2/patch" &
  wait; : > "$2/done"
}
untracked(){ # synthetic patch for untracked (not ignored) text files; git diff <mb> misses them
  : > "$T/u.patch"; : > "$T/u.numstat"; n=0
  $G ls-files --others --exclude-standard 2>/dev/null | sort > "$T/u.all"
  $G ls-files --others --exclude-standard -- . "${EXC[@]}" 2>/dev/null | sort > "$T/u.keep"
  comm -23 "$T/u.all" "$T/u.keep" | head -n 50 | sed 's/^/-	-	/; s/$/ (new, untracked, noise: content skipped)/' >> "$T/u.numstat"
  $G ls-files -z --others --exclude-standard -- . "${EXC[@]}" 2>/dev/null |
  while IFS= read -r -d '' f; do
    n=$((n+1)); [ $n -gt 400 ] && { echo "... more untracked files omitted" >> "$T/u.numstat"; break; }
    [ -f "$f" ] || continue
    if [ ! -s "$f" ]; then printf '0\t0\t%s (new, untracked, empty)\n' "$f" >> "$T/u.numstat"; continue; fi
    if ! grep -Iq . "$f" 2>/dev/null || [ "$(wc -c < "$f")" -gt 400000 ]; then
      printf -- '-\t-\t%s (new, untracked, binary/large)\n' "$f" >> "$T/u.numstat"; continue; fi
    l=$(awk 'END{print NR}' "$f")
    printf '%s\t0\t%s (new, untracked)\n' "$l" "$f" >> "$T/u.numstat"
    { printf 'diff --git a/%s b/%s\nnew file (untracked)\n--- /dev/null\n+++ b/%s\n@@ -0,0 +1,%s @@\n' "$f" "$f" "$f" "$l"
      sed 's/^/+/' "$f"; } >> "$T/u.patch"
  done
}
untracked & UJOB=$!

REF0=$(pick_ref); MB0=""
if [ -n "$REF0" ]; then MB0=$($G merge-base "$REF0" HEAD 2>/dev/null); [ -n "$MB0" ] && { gen "$MB0" "$T/a" & SPEC=$!; }; fi

BR=$($G branch --show-current 2>/dev/null); TICKET=$(printf '%s' "$BR" | grep -oE '[A-Z][A-Z0-9]+-[0-9]+' | head -n1)

[ "$FST" = run ] && wait "$FJOB"
FRC=$(cat "$T/frc" 2>/dev/null || echo 1)
REF=$(pick_ref)
[ -z "$REF" ] && { echo "NO_BASE=$B (remote=${REMOTE:-none}). Ask user for the base branch."; exit 0; }
MB=$($G merge-base "$REF" HEAD 2>/dev/null) || { echo "NO_MERGE_BASE ref=$REF"; exit 0; }
if [ "$MB" = "$MB0" ]; then D="$T/a"; wait "${SPEC:-}" 2>/dev/null; else gen "$MB" "$T/b"; D="$T/b"; fi
wait "$UJOB" 2>/dev/null

cat "$D/patch" "$T/u.patch" > "$T/diff.patch"
cat "$D/numstat" "$T/u.numstat" > "$T/numstat"
NF=$(grep -c . "$T/numstat"); BYTES=$(wc -c < "$T/diff.patch" | tr -d ' ')

# ---- header ------------------------------------------------------------------------------
H="$T/head"
{
  echo "BRANCH=${BR:-(detached HEAD)} TICKET=${TICKET:-none} REF=$REF MB=$(printf %.10s "$MB")"
  case "$FST:$FRC" in
    run:0) echo "BASE=fresh (fetched)";; fresh:*) echo "BASE=fresh (fetched <${FRESH_SECS}s ago)";;
    skip:*) echo "WARN_STALE_BASE (no remote / fetch disabled): using $REF";;
    *) echo "WARN_STALE_BASE (fetch failed/timeout ${FETCH_TIMEOUT}s): using cached $REF";;
  esac
  [ "$REF" = "$B" ] && [ -n "$REMOTE" ] && echo "WARN_STALE_BASE_LOCAL (no $REMOTE/$B; using local $B)"
  echo "AHEAD_BEHIND(behind ahead)=$($G rev-list --left-right --count "$REF...HEAD" 2>/dev/null | tr '\t' ' ')"
  $G diff --quiet HEAD 2>/dev/null || echo "UNCOMMITTED=yes (included)"
  echo "== STYLE (recent base subjects) =="; $G log -n 6 --no-merges --format='%s' "$REF" 2>/dev/null
  echo "== INTENT (branch commits) =="; $G log -n 40 --no-merges --format='* %s%n%b' "$REF..HEAD" 2>/dev/null | grep -v '^[[:space:]]*$' | head -c 3000; echo
  echo "== NUMSTAT (+ - path; noise files counted, content excluded) files=$NF diff_bytes=$BYTES =="
  head -n 150 "$T/numstat"; [ "$NF" -gt 150 ] && echo "... +$((NF-150)) more in $T/numstat"
} > "$H"
HB=$(wc -c < "$H" | tr -d ' ')

# ---- chunker: whole-file blocks, contiguous by path (related code stays together); giant files split at hunks
chunk(){ # $1=max bytes $2=max lines -> $T/c/NNN.patch (default sizes fit ONE Read call)
  rm -rf "$T/c"; mkdir -p "$T/c"
  awk -v tgt="$1" -v maxl="$2" -v dir="$T/c" '
    function put(txt, L, n, nm){
      if (cn==0 || (cl>0 && (cl+L>tgt || cln+n>maxl))) { if (cn) close(fn); cn++; cl=0; cln=0; fn=sprintf("%s/%03d.patch",dir,cn); nf[cn]=0; first[cn]=nm }
      printf "%s", txt > fn; cl+=L; cln+=n; if (nm!=last[cn]) { nf[cn]++; last[cn]=nm } }
    function emit(   i, pc, pb, pl){ if (hdr=="") return
      if (hb+bb <= tgt && hl+bl <= maxl) { pc=""; for (i=1;i<=nh;i++) pc=pc hk[i]; put(hdr pc, hb+bb, hl+bl, nm) }
      else { pc=""; pb=0; pl=0
        for (i=1;i<=nh;i++){ if (pc!="" && (hb+pb+hkb[i]>tgt || hl+pl+hkl[i]>maxl)) { put(hdr pc, hb+pb, hl+pl, nm); pc=""; pb=0; pl=0 }
          pc=pc hk[i]; pb+=hkb[i]; pl+=hkl[i] }
        if (pc!="" || nh==0) put(hdr pc, hb+pb, hl+pl, nm) }
      hdr=""; nh=0; hb=0; hl=0; bb=0; bl=0 }
    function addhk(line,   L){ L=length(line)+1; hk[nh]=hk[nh] line "\n"; hkb[nh]+=L; hkl[nh]++; bb+=L; bl++ }
    /^diff --git / { emit(); hdr=$0 "\n"; hb=length($0)+1; hl=1; inh=1; nm=$0; sub(/^diff --git a\//,"",nm); sub(/ b\/.*$/,"",nm); next }
    inh && /^@@/ { inh=0 }
    inh { hdr=hdr $0 "\n"; hb+=length($0)+1; hl++; next }
    /^@@/ { nh++; hk[nh]=""; hkb[nh]=0; hkl[nh]=0; addhk($0); next }
    { if (nh==0 || hkl[nh]>=maxl-hl-2 || hkb[nh]>=tgt-hb-200) { nh++; hk[nh]=""; hkb[nh]=0; hkl[nh]=0; if (nh>1) addhk("@@ (hunk continued) @@") }
      addhk($0) }
    END { emit(); if (cn) close(fn); print cn+0 > (dir "/count")
      for (i=1;i<=cn;i++) print i "\t" nf[i] "\t" first[i] (nf[i]>1 ? " .. " last[i] : "") > (dir "/index") }
  ' "$T/diff.patch"
  cat "$T/c/count"
}

cat "$H"
if [ "$NF" -eq 0 ]; then echo "EMPTY_DIFF"
elif [ "$BYTES" -eq 0 ]; then echo "ONLY_NOISE_OR_BINARY (see NUMSTAT; describe from paths)"
elif [ $((HB + BYTES)) -le $OUT_CAP ]; then echo "MODE=INLINE"; echo "== DIFF =="; cat "$T/diff.patch"
elif [ "$BYTES" -le "$READ_MAX" ]; then
  N=$(chunk $READ_CHUNK 1900)
  echo "MODE=READ chunks=$N  -> Read ALL these files in ONE message (parallel Read calls):"
  i=1; while [ $i -le "$N" ]; do printf '%s/c/%03d.patch\n' "$T" $i; i=$((i+1)); done
else
  TL=$(awk 'END{print NR}' "$T/diff.patch")
  tgt=$(( BYTES * 23 / 20 / MAXN + 1 )); [ $tgt -lt $FAN_CHUNK ] && tgt=$FAN_CHUNK
  ml=$(( TL * 23 / 20 / MAXN + 1 )); [ $ml -lt 1900 ] && ml=1900
  N=$(chunk $tgt $ml); while [ "$N" -gt $MAXN ]; do tgt=$((tgt*3/2)); ml=$((ml*3/2)); N=$(chunk $tgt $ml); done
  [ $ml -gt 1900 ] && echo "NOTE: chunks exceed one Read (lines<=$ml): subagents must page with offset/limit"
  echo "MODE=FAN_OUT chunks=$N dir=$T/c  (idx files first..last):"
  while IFS="$(printf '\t')" read -r i n r; do printf '%s/c/%03d.patch  files=%s  %s\n' "$T" "$i" "$n" "$r"; done < "$T/c/index"
fi
