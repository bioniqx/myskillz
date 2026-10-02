#!/usr/bin/env bash
# End-to-end self-test of the dev-team engine and its OpenCode guard in a throwaway git repo.
# Usage: bash oc-selftest.sh   (needs git >= 2.31, python3). Exit 0 = all checks passed.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
# copy the skill to a path WITH SPACES to exercise quoting
TMP="$(mktemp -d)/dev team"; mkdir -p "$TMP"; cp -r "$HERE/.." "$TMP/skill"
S="$TMP/skill/scripts"; G="$S/oc_guard.py"
D() { python3 "$S/oc_devteam.py" "$@"; }
# Deterministic environment: no inherited engine or harness variables and a throwaway HOME, so the
# machine's own ~/.config/opencode never leaks in. No opencode binary is started: dispatch only prints rows.
unset DEVTEAM_MAX_PARALLEL OPENCODE OPENCODE_TERMINAL
export HOME="$TMP/home"; mkdir -p "$HOME"
git config --global user.email t@t; git config --global user.name t
R="$(mktemp -d)/repo"; mkdir -p "$R"; cd "$R"
git init -q -b main; git config user.email t@t; git config user.name t; git config commit.gpgsign true
mkdir -p src node_modules/pkg && echo "base" > src/a.js && echo x > node_modules/pkg/i.js
printf 'node_modules/\n' > .gitignore
git -c commit.gpgsign=false add -A && git -c commit.gpgsign=false commit -qm init
pass=0; fail=0
ok()  { pass=$((pass+1)); echo "  ok   $1"; }
bad() { fail=$((fail+1)); echo "  FAIL $1"; }
skip() { echo "  SKIP $1"; }
check() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }
oci() { python3 -c 'import json, sys
tool, role, cwd, key, val = sys.argv[1:6]
args = {key: val}
if len(sys.argv) > 6:
    args["workdir"] = sys.argv[6]
print(json.dumps({"cwd": cwd, "tool": tool, "role": role, "args": args}))' "$@" | python3 "$G" oc; }
# a minimally REAL test file: the engine statically refuses tests with no assertion / no case
mktest() { mkdir -p "$(dirname "$1")"; printf 'test("%s", () => { assert.equal(1, 1); });\n' "${2:-case}" > "$1"; }

cat > plan.md <<'EOF'
# plan
```json
{"request":"add helpers","commands":{"test":"node --test tests/","test_file":"node --test {files}","lint":"none"},
 "contracts":["C1 sub(a,b)"],"notes":"node:test",
 "review_batch":2,"checkpoint_every":2,
 "slices":[
  {"id":"S1","title":"sub","deps":[],"files":["src/sub.js","tests/sub.test.js"],"risk":"low","criteria":["sub works"],"isolation":true},
  {"id":"S2","title":"mul","deps":[],"files":["src/mul.js","tests/mul.test.js"],"risk":"high","criteria":["mul works"]},
  {"id":"S3","title":"combo","deps":["S1","S2"],"files":["src/combo.js","tests/combo.test.js"],"risk":"low","criteria":["combo"]},
  {"id":"S4","title":"also sub","deps":[],"files":["src/sub.js","tests/sub2.test.js"],"risk":"low","criteria":["x"]}]}
```
EOF
echo "== init"
OUT=$(D init plan.md 2>&1); echo "$OUT" | head -3
check "init ok" '[[ "$OUT" == *"INIT ok: 4 slices"* ]]'
check "overlap warning S1<->S4" '[[ "$OUT" == *"S1↔S4"* ]]'
check "ready set is pairwise disjoint (S4 not with S1)" '[[ "$OUT" == *"READY: S2 S1 "* && "$OUT" != *"READY: S2 S1 S4"* ]]'
check "excludes include bare node_modules" 'grep -qx node_modules .git/info/exclude'

echo "== dispatch S1 S2 S4 (S4 must be skipped: overlaps S1)"
OUT=$(D dispatch S1 S2 S4 2>&1)
check "S1,S2 dispatched, S4 skipped" '[[ "$OUT" == *"DISPATCH S1"* && "$OUT" == *"DISPATCH S2"* && ("$OUT" == *"S4 (footprint overlaps"* || "$OUT" == *"S4 (not ready"*) ]]'
check "dispatch created the lane worktree and printed its claim command as a background row" '[ -d "$R/.opencode/oc-dev-team/wt/S1" ] && [[ "$OUT" == *"prompts/S1.md"* && "$OUT" == *"background"* ]] && grep -q "claim S1 --worktree" "$R/.opencode/oc-dev-team/prompts/S1.md"'

run_prog() { # id wt testfile srcfile [red|green]
  local id=$1 wt=$2 t=$3 f=$4 mode=${5:-slice}
  ( cd "$R" && git worktree add -q ".opencode/oc-dev-team/manual/$wt" -b "worktree-$wt" HEAD ) || return 1
  ( cd "$R/.opencode/oc-dev-team/manual/$wt" && D claim "$id" --worktree "$PWD" > "$R/claim-$id.out" 2>&1 || exit 1
    if [[ "$mode" != green ]]; then mktest "$t" "$id" && D commit-red "$id" >/dev/null 2>&1 || exit 1; fi
    if [[ "$mode" != red ]]; then echo "impl $id" >> "$f" && D commit-green "$id" >/dev/null 2>&1 || exit 1; fi )
}
echo "== S1 slice"
run_prog S1 w1 tests/sub.test.js src/sub.js
check "claim printed isolation prefix" 'grep -q "PORT=4001 DB_SUFFIX=_s1 TMPDIR=.oc-slice/tmp" "$R/claim-S1.out"'
check "node_modules symlinked and not stray" '[ -L "$R/.opencode/oc-dev-team/manual/w1/node_modules" ] && [ -z "$(cd "$R/.opencode/oc-dev-team/manual/w1" && git status --porcelain | grep node_modules)" ]'
check "stop hook allows a finished slice" '(cd "$R/.opencode/oc-dev-team/manual/w1" && printf "{\"cwd\":\"%s\",\"last_assistant_message\":\"## Status: Complete\"}" "$PWD" | python3 "$G" stop) >/dev/null 2>&1'
echo "== S2 RED then GREEN"
run_prog S2 w2 tests/mul.test.js src/mul.js red
check "balanced keeps the RED verification run for a HIGH-RISK slice" 'grep -q "confirm right-reason failures" "$R/claim-S2.out"' 
OUT=$(D integrate S1 S2 2>&1); echo "$OUT" | head -2
check "S1 merged (signing+hooks off)" '[[ "$OUT" == *"S1: MERGED"* ]]'
check "S2 RED accepted" '[[ "$OUT" == *"S2: RED accepted"* ]]'
check "review + checkpoint due after 1 merge? no" '[[ "$OUT" == *"CHECKPOINT: not due (1/2"* ]]'
D dispatch S2 S4 >/dev/null 2>&1
run_prog S2 w3 tests/mul.test.js src/mul.js green
check "green worktree starts at RED tip" '(cd "$R/.opencode/oc-dev-team/manual/w3" && git log --format=%s -n 2 | sed -n 2p | grep -q "test(S2)")'
echo "== S4 with a frozen-test modification via raw git (rejected, stays inflight, warm fix, re-integrate)"
run_prog S4 w4 tests/sub2.test.js src/sub.js
( cd "$R/.opencode/oc-dev-team/manual/w4" && echo "weakened" >> tests/sub2.test.js && git -c commit.gpgsign=false commit -qam "sneaky" )
OUT=$(D integrate S4 2>&1); echo "$OUT" | head -1
check "S4 rejected: frozen tests modified" '[[ "$OUT" == *"S4: REJECTED — frozen tests modified"* ]]'
check "S4 still inflight (warm fix possible)" 'D status | grep -q "S4     inflight.*REJECTED:tests-modified"'
( cd "$R/.opencode/oc-dev-team/manual/w4" && RED=$(cat .oc-slice/red) && git checkout -q "$RED" -- tests/sub2.test.js && git -c commit.gpgsign=false commit -qam "restore test" )
OUT=$(D integrate S4 S2 2>&1); echo "$OUT" | head -2
check "S4 merged after warm fix" '[[ "$OUT" == *"S4: MERGED"* ]]'
check "S2 merged (green)" '[[ "$OUT" == *"S2: MERGED"* ]]'
check "review batch due" '[[ "$OUT" == *"REVIEW: batch DUE"* ]]'
check "checkpoint due" '[[ "$OUT" == *"CHECKPOINT: DUE"* ]]'
echo "== checkpoint on a detached snapshot"
OUT=$(D checkpoint 2>&1); echo "$OUT" | head -2
CP1=$(find "$R" -maxdepth 5 -path "$R/.git" -prune -o -type d -name checkpoint-1 -print | head -1)
check "checkpoint uses a detached worktree" '[[ "$OUT" == *"checkpoint-1"* ]] && [ -d "$CP1" ] && [ -L "$CP1/node_modules" ]'
D checkpoint --result pass >/dev/null 2>&1
check "checkpoint worktree removed" '[ ! -d "$CP1" ]'
echo "== review batch + add-fixes"
OUT=$(D review-batch --shards 2 2>&1)
check "two shards" '[[ "$OUT" == *"REVIEW r1-1"* && "$OUT" == *"REVIEW r1-2"* ]]'
cat > .opencode/oc-dev-team/reviews/r1-1.report.md <<'EOF'
## Review verdict: CHANGES_REQUIRED
```json
{"fixes":[{"id":"F?","title":"nan","files":["src/nan.js","tests/nan.test.js"],"criteria":["nan"]}]}
```
EOF
OUT=$(D add-fixes .opencode/oc-dev-team/reviews/r1-1.report.md 2>&1)
check "fix slice F1 added and ready" '[[ "$OUT" == *"added fix slices: F1"* && "$OUT" == *"READY: "*"F1"* ]]'
echo "== retry reloads footprint from plan.md"
D dispatch S3 >/dev/null 2>&1
run_prog S3 w5 tests/combo.test.js src/combo.js
( cd "$R/.opencode/oc-dev-team/manual/w5" && echo hack >> src/a.js && git -c commit.gpgsign=false commit -qam "outside" )
OUT=$(D integrate S3 2>&1)
check "S3 footprint violation rejected" '[[ "$OUT" == *"S3: REJECTED — files outside the footprint: src/a.js"* ]]'
sed 's#"files":\["src/combo.js","tests/combo.test.js"\]#"files":["src/combo.js","src/a.js","tests/combo.test.js"]#' plan.md > plan.md.tmp && mv plan.md.tmp plan.md
cp plan.md .opencode/oc-dev-team/plan.md
OUT=$(D retry S3 2>&1)
check "retry re-queued S3" '[[ "$OUT" == *"S3: re-queued"* ]]'
check "retry reloaded files from plan.md" 'python3 -c "import json;s=json.load(open(\"$R/.opencode/oc-dev-team/state.json\"));assert \"src/a.js\" in s[\"slices\"][\"S3\"][\"files\"]"'
# ---------------------------------------------------------------- FAST MODE --
echo "== fast mode: a second repo, --spike (level 4) + start + next"
R2="$(mktemp -d)/repo2"; mkdir -p "$R2"; cd "$R2"
git init -q -b main; git config user.email t@t; git config user.name t
mkdir -p src tests && echo base > src/a.js
git add -A && git commit -qm init
cat > plan.md <<'EOF'
# fast plan
```json
{"request":"spike it","commands":{"test":"node --test tests/","test_file":"node --test {files}","lint":"echo lint","typecheck":"echo tsc","build":"echo build"},
 "slices":[
  {"id":"S1","title":"low risk","deps":[],"files":["src/one.js","tests/one.test.js"],"risk":"low","criteria":["one"]},
  {"id":"S2","title":"high risk","deps":[],"files":["src/two.js","tests/two.test.js"],"risk":"high","criteria":["two"]}]}
```
EOF
echo "-- start = init + dispatch, one call"
OUT=$(D start plan.md --spike 2>&1)
check "start ran init+dispatch in one call" '[[ "$OUT" == *"INIT ok: 2 slices"* && "$OUT" == *"DISPATCH S2"* && "$OUT" == *"DISPATCH S1"* ]]'
check "spike banner names the trade" '[[ "$OUT" == *"PROFILE spike"* && "$OUT" == *"NO TESTS"* ]]' 
check "low-risk slice dispatched as MODE: FAST" '[[ "$OUT" == *"DISPATCH S1 [CODE/FAST]"* ]]'
check "high-risk slice keeps RED->GREEN even in spike mode" '[[ "$OUT" == *"DISPATCH S2 [CODE/RED]"* ]]'
check "no incremental review / checkpoint in the spike profile" 'D ready | grep -q "REVIEW: profile spike" && D ready | grep -q "CHECKPOINT: profile spike"' 

echo "-- spike slice: claim, no tests, commit-fast, stop gate, integrate"
git worktree add -q ".opencode/oc-dev-team/manual/f1" -b wt-f1 HEAD
( cd "$R2/.opencode/oc-dev-team/manual/f1" && D claim S1 --worktree "$PWD" > "$R2/claim-S1.out" 2>&1 )
check "briefing announces the spike slice" 'grep -q "SPIKE SLICE — no tests required" "$R2/claim-S1.out"'
check "briefing defers lint/typecheck/build" 'grep -q "DEFERRED to one final full gate" "$R2/claim-S1.out"'
check "claim wrote the notest/fast markers" '[ -f "$R2/.opencode/oc-dev-team/manual/f1/.oc-slice/notest" ] && [ "$(cat "$R2/.opencode/oc-dev-team/manual/f1/.oc-slice/fast")" = 4 ]'
W="$R2/.opencode/oc-dev-team/manual/f1"
stopmsg() { (cd "$W" && printf "{\"cwd\":\"%s\",\"last_assistant_message\":\"%s\"}" "$PWD" "$1" | python3 "$G" stop) 2>&1; }
check "stop gate blocks a spike slice with nothing committed" '[[ "$(stopmsg "## Status: Complete -- ## Gate: ran it")" == *"nothing committed yet"* ]]' 
( cd "$W" && echo "impl" > src/one.js && D commit-fast "low risk" > "$R2/cf.out" 2>&1 )
check "commit-fast made a single commit, no RED needed" 'grep -q "COMMITTED" "$R2/cf.out" && [ ! -f "$W/.oc-slice/red" ]'
check "stop gate demands Gate evidence when there are no tests" '[[ "$(stopmsg "## Status: Complete")" == *"no RED/GREEN split protecting it"* ]]' 
check "stop gate passes a committed spike slice with evidence" '[[ -z "$(stopmsg "## Status: Complete -- ## Gate: node -e ... -> ok")" ]]' 


echo "-- next: integrate + dispatch + endgame in ONE call"
cd "$R2"
OUT=$(D next S1 2>&1)
check "next merged the untested slice and labelled it SPIKE" '[[ "$OUT" == *"S1: MERGED"* && "$OUT" == *"SPIKE — no tests"* ]]'
check "next reports S2 still in flight" '[[ "$OUT" == *"1 in flight"* ]]'
( cd "$R2/.opencode/oc-dev-team/manual" && git -C "$R2" worktree add -q "$R2/.opencode/oc-dev-team/manual/f2" -b wt-f2 HEAD )
( cd "$R2/.opencode/oc-dev-team/manual/f2" && D claim S2 --worktree "$PWD" >/dev/null 2>&1 && mktest tests/two.test.js two && D commit-red "high risk" >/dev/null 2>&1 )
OUT=$(D next S2 2>&1)
check "next accepted RED and immediately dispatched the GREEN phase" '[[ "$OUT" == *"S2: RED accepted"* && "$OUT" == *"DISPATCH S2 [CODE/GREEN]"* ]]'
git -C "$R2" worktree add -q "$R2/.opencode/oc-dev-team/manual/f3" -b wt-f3 HEAD
( cd "$R2/.opencode/oc-dev-team/manual/f3" && D claim S2 --worktree "$PWD" >/dev/null 2>&1 && echo impl > src/two.js && D commit-green "high risk" >/dev/null 2>&1 )
OUT=$(D next S2 2>&1)
check "next ran the endgame when the DAG emptied" '[[ "$OUT" == *"S2: MERGED"* && "$OUT" == *"DAG EXHAUSTED"* ]]'
check "endgame auto-started the final review on the spot reviewer" '[[ "$OUT" == *"=== REVIEW r1"* && "$OUT" == *"spot-reviewer"* ]]'
check "endgame auto-started the full-gate checkpoint" '[[ "$OUT" == *"FULL GATE (test && lint && typecheck && build)"* ]]'
check "endgame started the checkpoint detached and its log appears" 'CPLOG=$(ls "$R2"/.opencode/oc-dev-team/logs/checkpoint-*.log 2>/dev/null | head -1); [[ "$OUT" == *"running detached (pid "* && -f "$CPLOG" ]]'
D wait --timeout 30 >/dev/null 2>&1
echo "--- checkpoint log:"; cat "$CPLOG"
check "endgame flags the untested slice for verification" '[[ "$OUT" == *"untested spike slices: S1"* ]]'
check "finish names exactly what the profile traded away" 'OUT2=$(D finish --force 2>&1); [[ "$OUT2" == *"TRADE-OFFS"* && "$OUT2" == *"never watched to fail"* && "$OUT2" == *"UNTESTED slices shipped with no tests at all: S1"* ]]' 

echo "-- level 2 keeps tests but skips the RED verification run"
R3="$(mktemp -d)/repo3"; mkdir -p "$R3"; cd "$R3"
git init -q -b main; git config user.email t@t; git config user.name t
mkdir -p src && echo b > src/a.js && git add -A && git commit -qm init
cat > plan.md <<'EOF'
```json
{"request":"r","commands":{"test":"node --test tests/","lint":"echo lint"},
 "slices":[{"id":"S1","title":"t","deps":[],"files":["src/b.js","tests/b.test.js"],"risk":"low","criteria":["c"]}]}
```
EOF
D init plan.md --fast 2 >/dev/null 2>&1; D dispatch S1 >/dev/null 2>&1
git worktree add -q ".opencode/oc-dev-team/manual/g1" -b wt-g1 HEAD
( cd "$R3/.opencode/oc-dev-team/manual/g1" && D claim S1 --worktree "$PWD" > "$R3/claim.out" 2>&1 )
check "level 2 still requires MODE: SLICE (tests first)" 'grep -q "MODE: SLICE" "$R3/claim.out"'
check "turbo skips the RED verification run" 'grep -q "No verification run in this profile" "$R3/claim.out" && ! grep -q "confirm right-reason failures" "$R3/claim.out"' 
check "level 2 defers lint to the final gate" 'grep -q "DEFERRED to one final full gate" "$R3/claim.out"'

echo "-- normal mode is unchanged"
cd "$R"
check "balanced skips the RED verification run for a low-risk slice" '! grep -q "confirm right-reason failures" "$R/claim-S1.out"' 
check "normal mode keeps incremental review batches" '! D ready | grep -q "REVIEW: fast mode"; D ready | grep -q "REVIEW: .*awaiting the next incremental batch"' 


# ------------------------------------------------- fast-mode hardening ------
echo "== hardening: slot budget, frozen tests in a spike, fix slices, bare --fast"
check "bare --fast means the turbo profile" 'R9="$(mktemp -d)/r9"; mkdir -p "$R9"; ( cd "$R9" && git init -q -b main && git config user.email t@t && git config user.name t && mkdir -p src && echo b > src/a.js && git add -A && git commit -qm i && printf "\140\140\140json\n{\"request\":\"r\",\"commands\":{\"test\":\"true\"},\"slices\":[{\"id\":\"S1\",\"title\":\"a\",\"deps\":[],\"files\":[\"src/b.js\"],\"risk\":\"low\",\"criteria\":[\"c\"],\"kind\":\"chore\",\"verify\":\"true\"}]}\n\140\140\140\n" > p.md && D init p.md --fast 2>&1 | grep -q "PROFILE turbo" )' 


echo "-- a spike slice may skip tests, but may not weaken tests it wrote"
R7="$(mktemp -d)/r7"; mkdir -p "$R7"; cd "$R7"
git init -q -b main; git config user.email t@t; git config user.name t
mkdir -p src tests && echo b > src/a.js && git add -A && git commit -qm i
printf '```json\n{"request":"r","commands":{"test":"true"},"slices":[{"id":"S1","title":"a","deps":[],"files":["src/b.js","tests/b.test.js"],"risk":"low","criteria":["c"]}]}\n```\n' > plan.md
D init plan.md --spike >/dev/null 2>&1; D dispatch S1 >/dev/null 2>&1
git worktree add -q .opencode/oc-dev-team/manual/k1 -b k1 HEAD
W="$R7/.opencode/oc-dev-team/manual/k1"
( cd "$W" && D claim S1 --worktree "$PWD" >/dev/null 2>&1 && mktest tests/b.test.js real && D commit-red a >/dev/null 2>&1 )
check "commit-fast restores a frozen test instead of committing it" '( cd "$W" && echo "// gutted" > tests/b.test.js && echo impl > src/b.js && D commit-fast a 2>&1 | grep -q "frozen and have been restored" )'
check "the gutted test was actually restored on disk" 'grep -q "assert.equal" "$W/tests/b.test.js"'
check "stop gate blocks a spike slice that weakened its own test" '( cd "$W" && git checkout -q -- tests/b.test.js 2>/dev/null; printf "// gutted" > tests/b.test.js; git -c commit.gpgsign=false commit -q --no-verify -am gut ); [[ "$( (cd "$W" && printf "{\"cwd\":\"%s\",\"last_assistant_message\":\"## Status: Complete -- ## Gate: ok\"}" "$PWD" | python3 "$G" stop) 2>&1 )" == *"were changed afterwards"* ]]'
cd "$R7"
check "integrate rejects a spike slice that weakened its own test" '[[ "$(D integrate S1 2>&1)" == *"REJECTED — tests committed in"* ]]'

echo "-- slices a reviewer asked for keep their tests even at level 4"
cat > "$R7/rep.md" <<'EOF'
## Review verdict: CHANGES_REQUIRED
```json
{"fixes": [{"id": "F?", "title": "fix it", "files": ["src/z.js", "tests/z.test.js"], "criteria": ["z works"], "risk": "medium", "deps": []}]}
```
EOF
D add-fixes "$R7/rep.md" >/dev/null 2>&1
check "add-fixes coerced the bogus risk to low" 'python3 -c "import json;s=json.load(open(\"$R7/.opencode/oc-dev-team/state.json\"));assert s[\"slices\"][\"F1\"][\"risk\"]==\"low\";assert s[\"slices\"][\"F1\"][\"from_review\"] is True"'
check "a review fix slice is dispatched with tests (MODE: SLICE), not as a spike" '[[ "$(D dispatch F1 2>&1)" == *"DISPATCH F1 [CODE/SLICE]"* ]]'

echo "-- the endgame waits for unresolved slices"
R6="$(mktemp -d)/r6"; mkdir -p "$R6"; cd "$R6"
git init -q -b main; git config user.email t@t; git config user.name t
mkdir -p src tests && echo b > src/a.js && git add -A && git commit -qm i
printf '```json\n{"request":"r","commands":{"test":"true"},"review_batch":8,"checkpoint_every":8,"slices":[{"id":"S1","title":"a","deps":[],"files":["src/b.js","tests/b.test.js"],"risk":"low","criteria":["c"]},{"id":"S2","title":"b","deps":[],"files":["src/c.js","tests/c.test.js"],"risk":"low","criteria":["c"]}]}\n```\n' > plan.md
D init plan.md >/dev/null 2>&1; D dispatch S1 >/dev/null 2>&1
git worktree add -q .opencode/oc-dev-team/manual/m1 -b m1 HEAD
( cd "$R6/.opencode/oc-dev-team/manual/m1" && D claim S1 --worktree "$PWD" >/dev/null 2>&1 && mktest tests/b.test.js b && D commit-red a >/dev/null 2>&1 && echo i > src/b.js && D commit-green a >/dev/null 2>&1 )
D integrate S1 >/dev/null 2>&1
D fail S2 --why simulated >/dev/null 2>&1
OUT=$(D next 2>&1)
check "next holds the final review + full gate while a slice is unresolved" '[[ "$OUT" == *"UNRESOLVED: S2"* && "$OUT" != *"=== REVIEW"* && "$OUT" != *"run in the BACKGROUND"* ]]'
check "the endgame steps are numbered from 1" '[[ "$OUT" == *"  1. "* ]]'
D retry S2 >/dev/null 2>&1
check "after retry the run is no longer exhausted" '[[ "$(D next 2>&1)" != *"DAG EXHAUSTED"* ]]' 

echo "-- normal-mode briefing wording is unchanged"
check "balanced SLICE briefing prints an explicit per-slice gate line" 'grep -q "your gate:" "$R/.opencode/oc-dev-team/briefs/S1.md"' 
check "balanced GREEN briefing prints an explicit per-slice gate line" 'grep -q "your gate:" "$R/.opencode/oc-dev-team/briefs/S2.md"' 
check "no briefing in a normal run mentions deferring the gate" '! grep -rq "DEFERRED to one final full gate" "$R/.opencode/oc-dev-team/briefs/"'
check "fast-mode briefing says the gates are deferred" 'grep -q "DEFERRED to one final full gate" "$R3/claim.out"'


# =============================================================================================
# v3: profiles, slice kinds, zero-round-trip harvesting, routing, probe/review-pr/brief-debug
# =============================================================================================
newrepo() { # $1 = var-safe name -> echoes the repo path
  local d; d="$(mktemp -d)/$1"; mkdir -p "$d"
  ( cd "$d" && git init -q -b main && git config user.email t@t && git config user.name t \
    && mkdir -p src tests && echo base > src/a.js && git add -A && git commit -qm init ) >/dev/null
  echo "$d"
}

echo "== v3 profiles"
RP="$(newrepo rp)"; cd "$RP"
cat > plan.md <<'EOF'
```json
{"request":"r","commands":{"test":"echo t","test_file":"echo t {files}","lint":"echo lint","lint_file":"echo lint {files}","typecheck":"echo tsc","build":"echo build"},
 "slices":[{"id":"S1","title":"a","deps":[],"files":["src/b.js","tests/b.test.js"],"risk":"low","criteria":["c"]}]}
```
EOF
OUT=$(D init plan.md 2>&1)
check "default profile is balanced" '[[ "$OUT" == *"PROFILE balanced"* ]]'
check "balanced keeps incremental reviews and checkpoints" '[[ "$(D ready)" == *"REVIEW: 0/8"* && "$(D ready)" == *"CHECKPOINT: not due"* ]]'
D dispatch S1 >/dev/null 2>&1
check "balanced gate is FILE-SCOPED lint, not the repo-wide one" 'grep -q "your gate: .*echo lint {files}" .opencode/oc-dev-team/briefs/S1.md'
check "balanced defers what has no file-scoped form" 'grep -q "typecheck/build deferred" .opencode/oc-dev-team/briefs/S1.md'
check "balanced briefing never asks for the repo-wide lint" '! grep -q "your gate: .*\`echo lint\`" .opencode/oc-dev-team/briefs/S1.md'
D reset --yes >/dev/null 2>&1
OUT=$(D init plan.md --profile strict 2>&1); D dispatch S1 >/dev/null 2>&1
check "strict runs the whole gate in every slice" 'grep -q "your gate: .*echo lint.*echo tsc.*echo build" .opencode/oc-dev-team/briefs/S1.md'
check "strict keeps the RED verification run everywhere" 'grep -q "confirm right-reason failures" .opencode/oc-dev-team/briefs/S1.md'
D reset --yes >/dev/null 2>&1
OUT=$(D init plan.md --profile turbo 2>&1)
check "turbo defers every gate and holds reviews to the end" '[[ "$OUT" == *"PROFILE turbo"* && "$(D ready)" == *"REVIEW: profile turbo"* ]]'
check "legacy --fast 4 still means the spike profile" 'D reset --yes >/dev/null; D init plan.md --fast 4 2>&1 | grep -q "PROFILE spike"'

echo "== v3 the vacuous-test guard replaces the skipped RED run"
D reset --yes >/dev/null 2>&1; D init plan.md >/dev/null 2>&1; D dispatch S1 >/dev/null 2>&1
git worktree add -q .opencode/oc-dev-team/manual/v1 -b wt-v1 HEAD
VW="$RP/.opencode/oc-dev-team/manual/v1"
( cd "$VW" && D claim S1 --worktree "$PWD" >/dev/null 2>&1 )
check "commit-red refuses a test with no assertion" '( cd "$VW" && mkdir -p tests && printf "test(\"x\", () => {});\n" > tests/b.test.js && D commit-red a 2>&1 | grep -q "contains no assertion" )'
check "a refused RED commits nothing" '( cd "$VW" && [ -z "$(git log --format=%s -1 | grep "^test(S1)")" ] )'
check "commit-red refuses a file that declares no test case" '( cd "$VW" && printf "// assert.equal(1,1) in a comment\n" > tests/b.test.js && D commit-red a 2>&1 | grep -q "declares no test case" )'
check "commit-red --force is the documented escape hatch" '( cd "$VW" && D commit-red a --force 2>&1 | grep -q "RED committed" )'

echo "== v3 slice kinds"
RK="$(newrepo rk)"; cd "$RK"
echo "legacy" > src/old.js; echo "other" > src/other.js; echo "docs" > README.md; mkdir -p tests
printf 'test("keep", () => { assert.equal(1,1); });\n' > tests/old.test.js
printf 'test("keep2", () => { assert.equal(2,2); });\n' > tests/other.test.js
git add -A && git commit -qm seed
cat > plan.md <<'EOF'
```json
{"request":"everything","commands":{"test":"echo t","test_file":"echo t {files}","lint":"none","typecheck":"none","build":"none"},
 "slices":[
  {"id":"R1","title":"rename","kind":"refactor","deps":[],"files":["src/old.js","tests/old.test.js"],"risk":"low","criteria":["behaviour identical"]},
  {"id":"C1","title":"ci","kind":"chore","size":"trivial","deps":[],"files":["ci.yml"],"risk":"low","criteria":["ci runs"],"verify":"echo verified"},
  {"id":"D1","title":"readme","kind":"docs","deps":[],"files":["README.md"],"risk":"low","criteria":["documented"],"verify":"echo verified"},
  {"id":"T1","title":"backfill","kind":"test","deps":[],"files":["tests/new.test.js"],"risk":"low","criteria":["covered"]},
  {"id":"R2","title":"extract","kind":"refactor","deps":[],"files":["src/other.js","tests/other.test.js"],"risk":"low","criteria":["behaviour identical"]},
  {"id":"X1","title":"survey","kind":"research","deps":[],"files":["-"],"risk":"low","criteria":["which option"]}]}
```
EOF
OUT=$(D init plan.md 2>&1)
check "init accepts every slice kind" '[[ "$OUT" == *"INIT ok: 6 slices"* ]]'
check "init summarises the kinds" '[[ "$OUT" == *"KINDS:"* && "$OUT" == *"refactor"* && "$OUT" == *"research"* ]]'
check "a chore/docs/perf slice with no verify command is refused" 'printf "\140\140\140json\n{\"request\":\"r\",\"commands\":{\"test\":\"echo t\"},\"slices\":[{\"id\":\"Z\",\"title\":\"z\",\"kind\":\"chore\",\"deps\":[],\"files\":[\"z\"],\"risk\":\"low\",\"criteria\":[\"c\"]}]}\n\140\140\140\n" > bad.md; D init bad.md --force 2>&1 | grep -q "needs a .verify. command"'
check "a code slice whose footprint has no test path is warned about" 'printf "\140\140\140json\n{\"request\":\"r\",\"commands\":{\"test\":\"echo t\"},\"slices\":[{\"id\":\"Z\",\"title\":\"z\",\"deps\":[],\"files\":[\"src/z.js\"],\"risk\":\"low\",\"criteria\":[\"c\"]}]}\n\140\140\140\n" > warn.md; D init warn.md --force 2>&1 | grep -q "cannot write its own tests"'
D reset --yes >/dev/null 2>&1; D init plan.md >/dev/null 2>&1
OUT=$(D dispatch R1 R2 C1 D1 T1 X1 2>&1)
check "a trivial slice rides the normal programmer agent" '[[ "$OUT" == *"C1"* ]]'
check "a research slice is dispatched with no claim command" '[[ "$OUT" == *"[RESEARCH]"* ]]'
check "every other kind still goes to the programmer in MODE WORK" '[[ "$OUT" == *"[REFACTOR/WORK]"* && "$OUT" == *"[DOCS/WORK]"* ]]'
check "a chore briefing pins the slice's own verify command" 'grep -q "verify (THIS slice.s evidence command): .*echo verified" .opencode/oc-dev-team/briefs/C1.md'
check "a refactor briefing demands a before AND after run" 'grep -qi "before your first edit" .opencode/oc-dev-team/briefs/R1.md'

echo "-- refactor: the tests are the contract"
KW="$RK/.opencode/oc-dev-team/wt/R1"
( cd "$KW" && D claim R1 --worktree "$PWD" >/dev/null 2>&1 )
check "the edit guard blocks a test edit in a refactor slice" '[[ "$(oci edit programmer "$RK" path "$KW/tests/old.test.js")" == *"REFACTOR slice"* ]]'
check "commit-work restores a test a refactor slice touched" '( cd "$KW" && echo "changed" >> src/old.js && printf "// gutted\n" > tests/old.test.js && D commit-work r 2>&1 | grep -q "may not change any test file" )'
check "the gutted test was restored on disk" 'grep -q "assert.equal" "$KW/tests/old.test.js"'
check "commit-work commits a clean refactor" '( cd "$KW" && D commit-work r 2>&1 | grep -q "COMMITTED" )'
check "the stop gate wants both runs from a refactor" '[[ "$( (cd "$KW" && printf "{\"cwd\":\"%s\",\"last_assistant_message\":\"## Status: Complete -- ## Gate: node --test tests/old.test.js -> ok\"}" "$PWD" | python3 "$G" stop) 2>&1 )" == *"BOTH runs"* ]]' 
OUT=$(D integrate R1 2>&1)
check "integrate merges a refactor as an evidence-gated slice" '[[ "$OUT" == *"R1: MERGED"* && "$OUT" == *"REFACTOR slice"* ]]'
( cd "$RK/.opencode/oc-dev-team/wt/R2" && D claim R2 --worktree "$PWD" >/dev/null 2>&1 \
  && echo "extracted" >> src/other.js && printf "// gutted\n" > tests/other.test.js \
  && git -c commit.gpgsign=false commit -qam "sneaky refactor" )
OUT=$(D integrate R2 2>&1)
check "integrate rejects a refactor that changed a test behind commit-work back" '[[ "$OUT" == *"R2: REJECTED"* && "$OUT" == *"may not change any test file"* ]]'
check "the rejected refactor stays in flight for a warm fix" 'D status | grep -q "R2     inflight.*REJECTED:refactor-touched-tests"'
( cd "$RK/.opencode/oc-dev-team/wt/T1" && D claim T1 --worktree "$PWD" >/dev/null 2>&1 )

echo "-- test-kind and research-kind integration"
( cd "$RK/.opencode/oc-dev-team/wt/T1" && printf "test(\"n\", () => { assert.equal(1,1); });\n" > tests/new.test.js && D commit-work t >/dev/null 2>&1 )
OUT=$(D integrate T1 2>&1)
check "a kind:test slice that added no test file is rejected at merge" '
  D add-fix --id T9 --title "empty backfill" --kind test --files src/nothing.js --criteria "covered" >/dev/null 2>&1
  D dispatch T9 >/dev/null 2>&1
  ( cd "$RK/.opencode/oc-dev-team/wt/T9" && D claim T9 --worktree "$PWD" >/dev/null 2>&1 && echo x > src/nothing.js \
    && git add -A src/nothing.js && git -c commit.gpgsign=false commit -qm "test(T9): no tests at all" )
  [[ "$(D integrate T9 2>&1)" == *"must add or extend test files"* ]]'
check "a kind:test slice merges when it really added tests" '[[ "$OUT" == *"T1: MERGED"* && "$OUT" == *"TEST slice"* ]]'
OUT=$(D integrate X1 2>&1)
check "a research slice without its report is not integrated" '[[ "$OUT" == *"NOT INTEGRATED — no report"* ]]'
mkdir -p .opencode/oc-dev-team/research
cat > .opencode/oc-dev-team/research/X1.md <<'EOF'
## Verdict: LIKELY CAUSE
## Findings
- option B
```json
{"fixes":[{"id":"F?","title":"adopt option B","files":["src/opt.js","tests/opt.test.js"],"criteria":["option B works"]}]}
```
EOF
OUT=$(D integrate X1 2>&1)
check "a research slice is recorded, not merged" '[[ "$OUT" == *"RESEARCH RECORDED"* && "$OUT" == *"nothing merged"* ]]'
check "research follow-up work is queued automatically" '[[ "$OUT" == *"follow-up slices queued: F1"* ]] && D status | grep -q "F1     pending"'

echo "== v3 zero-round-trip harvesting"
RH="$(newrepo rh)"; cd "$RH"
cat > plan.md <<'EOF'
```json
{"request":"r","commands":{"test":"echo t","test_file":"echo t {files}","lint":"none","typecheck":"none","build":"none"},
 "review_batch":1,"checkpoint_every":1,
 "slices":[{"id":"S1","title":"a","deps":[],"files":["src/b.js","tests/b.test.js"],"risk":"low","criteria":["c"]}]}
```
EOF
D init plan.md >/dev/null 2>&1; D dispatch S1 >/dev/null 2>&1
git worktree add -q .opencode/oc-dev-team/manual/h1 -b wt-h1 HEAD
( cd "$RH/.opencode/oc-dev-team/manual/h1" && D claim S1 --worktree "$PWD" >/dev/null 2>&1 && mktest tests/b.test.js b \
  && D commit-red a >/dev/null 2>&1 && echo i > src/b.js && D commit-green a >/dev/null 2>&1 )
OUT=$(D next S1 2>&1)
check "next merged, opened the review batch and started the detached checkpoint in ONE call" '[[ "$OUT" == *"S1: MERGED"* && "$OUT" == *"=== REVIEW r1"* && "$OUT" == *"CHECKPOINT 1 on snapshot"* && "$OUT" == *"running detached (pid "* ]]'
D wait --timeout 30 >/dev/null 2>&1
check "the checkpoint records its own exit code in the log" '[[ "$(tail -n 1 .opencode/oc-dev-team/logs/checkpoint-1.log)" == "EXIT=0" ]]'
cat > .opencode/oc-dev-team/reviews/r1.report.md <<'EOF'
## Review verdict: CHANGES_REQUIRED
## Findings
### [MAJOR] boom
```json
{"fixes":[{"id":"F?","title":"handle null","files":["src/n.js","tests/n.test.js"],"criteria":["null is handled"]}]}
```
EOF
printf 'ok\nEXIT=0\n' > .opencode/oc-dev-team/logs/checkpoint-1.log
OUT=$(D next 2>&1)
check "next reads the reviewer verdict out of the report file" '[[ "$OUT" == *"REVIEW r1: CHANGES_REQUIRED"* ]]'
check "next queues the reviewer's fix slices with no add-fixes call" '[[ "$OUT" == *"queued F1"* ]] && D status | grep -q "F1     "'
check "next records the checkpoint from its log with no --result call" '[[ "$OUT" == *"CHECKPOINT 1"* && "$OUT" == *"PASS (exit 0)"* ]]'
check "harvesting is idempotent: a second next re-queues nothing" '[[ "$(D next 2>&1)" != *"queued F1"* ]]'
D dispatch F1 >/dev/null 2>&1
git worktree add -q .opencode/oc-dev-team/manual/h2 -b wt-h2 HEAD
( cd "$RH/.opencode/oc-dev-team/manual/h2" && D claim F1 --worktree "$PWD" >/dev/null 2>&1 && mktest tests/n.test.js n \
  && D commit-red f >/dev/null 2>&1 && echo i > src/n.js && D commit-green f >/dev/null 2>&1 )
D next F1 >/dev/null 2>&1
printf 'boom\nFAILED test x\nEXIT=1\n' > .opencode/oc-dev-team/logs/checkpoint-2.log
OUT=$(D next 2>&1)
check "a failing checkpoint is harvested with its failing tail" '[[ "$OUT" == *"FAIL (exit 1)"* && "$OUT" == *"FAILED test x"* ]]'
check "a failing checkpoint tells the Conductor to queue a regression fix" '[[ "$OUT" == *"add-fix --title"* ]]'

echo "== v3 routing helpers"
cd "$RH"
cat > package.json <<'EOF'
{"name":"x","scripts":{"test":"vitest run","lint":"eslint .","build":"tsc -b"},
 "devDependencies":{"vitest":"^1","eslint":"^8","typescript":"^5"}}
EOF
OUT=$(D probe 2>&1)
check "probe finds the npm scripts" '[[ "$OUT" == *"\"test\": \"npm run test\""* && "$OUT" == *"\"build\": \"npm run build\""* ]]'
check "probe proposes the FILE-SCOPED lint and test commands that make the balanced gate cheap" '[[ "$OUT" == *"npx eslint {files}"* && "$OUT" == *"npx vitest run {files}"* ]]'
OUT=$(D review-pr HEAD~1..HEAD --shards 2 2>&1)
check "review-pr fans reviewers over a diff with no plan" '[[ "$OUT" == *"=== REVIEW pr"* && "$OUT" == *"code-reviewer"* ]]'
check "review-pr --spot uses the spot reviewer" '[[ "$(D review-pr HEAD~1..HEAD --spot 2>&1)" == *"spot-reviewer"* ]]'
OUT=$(D brief-debug "tokens leak after refresh" -n 4 2>&1)
check "brief-debug fans out investigators on distinct angles" '[[ "$(echo "$OUT" | grep -c "investigator")" -ge 4 ]]'
check "each investigator brief names the angles the others own" 'grep -q "Other angles being investigated in parallel" .opencode/oc-dev-team/research/debug1.md'
check "investigator briefs demand evidence, not theories" 'grep -q "Every claim needs evidence" .opencode/oc-dev-team/research/debug2.md'

echo "== v3 scheduling and permissions"
RS="$(newrepo rs)"; cd "$RS"
cat > plan.md <<'EOF'
```json
{"request":"r","commands":{"test":"echo t","test_file":"echo t {files}","lint":"none","typecheck":"none","build":"none"},
 "slices":[
  {"id":"A1","title":"trivial head","size":"trivial","deps":[],"files":["src/t1.js","tests/t1.test.js"],"risk":"low","criteria":["c"]},
  {"id":"A2","title":"trivial mid","size":"trivial","deps":["A1"],"files":["src/t2.js","tests/t2.test.js"],"risk":"low","criteria":["c"]},
  {"id":"A3","title":"trivial tail","size":"trivial","deps":["A2"],"files":["src/t3.js","tests/t3.test.js"],"risk":"low","criteria":["c"]},
  {"id":"B1","title":"large head","size":"large","deps":[],"files":["src/b1.js","tests/b1.test.js"],"risk":"low","criteria":["c"]}]}
```
EOF
OUT=$(D init plan.md 2>&1)
check "priority is the heaviest remaining path, not the most hops" '[[ "$OUT" == *"READY: B1 A1"* ]]'
check "the deeper chain of trivial work does not jump the queue" '[[ "$OUT" != *"READY: A1"* ]]' 
D dispatch A1 >/dev/null 2>&1
git worktree add -q .opencode/oc-dev-team/manual/p1 -b wt-p1 HEAD; PW="$RS/.opencode/oc-dev-team/manual/p1"
( cd "$PW" && D claim A1 --worktree "$PWD" >/dev/null 2>&1 )
check "claim records the commands the permission guard may auto-allow" 'grep -q "^echo t" "$PW/.oc-slice/allow"'


# =============================================================================================
# v3.1 hardening — every finding from the adversarial review, with the attack that found it
# =============================================================================================
echo "== v3.1 the test-first rule cannot be forged"
RF="$(newrepo rf)"; cd "$RF"
cat > plan.md <<'EOF'
```json
{"request":"r","commands":{"test":"echo ok","lint":"none","typecheck":"none","build":"none"},
 "slices":[{"id":"S1","title":"a","deps":[],"files":["src/b.js","tests/b.test.js"],"risk":"low","criteria":["c"]}]}
```
EOF
D init plan.md >/dev/null 2>&1; D dispatch S1 >/dev/null 2>&1
git worktree add -q .opencode/oc-dev-team/manual/f1 -b wf1 HEAD; FW="$RF/.opencode/oc-dev-team/manual/f1"
( cd "$FW" && D claim S1 --worktree "$PWD" >/dev/null 2>&1 \
  && echo impl > src/b.js && git add -A src/b.js && git -c commit.gpgsign=false commit -qm "test(S1): RED — forged" \
  && echo more >> src/b.js && git add -A src/b.js && git -c commit.gpgsign=false commit -qm "feat(S1): green" \
  && rm -f .oc-slice/red )
OUT=$(D integrate S1 2>&1)
check "a hand-rolled RED commit with no test file is rejected" '[[ "$OUT" == *"contains no test file"* ]]'
check "the forged slice is not merged" '! D status | grep -q "S1     done"'
check "integrate does not trust the agent-writable .oc-slice/red" '( cd "$FW" && echo deadbeef > .oc-slice/red 2>/dev/null; true ); [[ "$(D integrate S1 2>&1)" == *"contains no test file"* ]]'

echo "== v3.1 a rename or a delete inside the footprint can be committed"
RN="$(newrepo rn)"; cd "$RN"
echo old > src/old.ts; echo gone > src/gone.ts; echo keep > src/keep.ts; git add -A; git commit -qm seed
cat > plan.md <<'EOF'
```json
{"request":"r","commands":{"test":"echo ok","lint":"none","typecheck":"none","build":"none"},
 "slices":[{"id":"R1","title":"rename","kind":"refactor","deps":[],"files":["src/old.ts","src/new.ts"],"risk":"low","criteria":["same"]},
           {"id":"C1","title":"drop","kind":"chore","deps":[],"files":["src/gone.ts","src/keep.ts"],"risk":"low","criteria":["gone"],"verify":"echo ok"}]}
```
EOF
D init plan.md >/dev/null 2>&1; D dispatch R1 C1 >/dev/null 2>&1
git worktree add -q .opencode/oc-dev-team/manual/n1 -b wn1 HEAD
check "a rename inside the footprint commits (was: refused as outside the footprint)" '( cd "$RN/.opencode/oc-dev-team/manual/n1" && D claim R1 --worktree "$PWD" >/dev/null 2>&1 && git mv src/old.ts src/new.ts && D commit-work rename 2>&1 | grep -q COMMITTED )'
git worktree add -q .opencode/oc-dev-team/manual/n2 -b wn2 HEAD
( cd "$RN/.opencode/oc-dev-team/manual/n2" && D claim C1 --worktree "$PWD" >/dev/null 2>&1 && rm src/gone.ts && echo more >> src/keep.ts && D commit-work drop >/dev/null 2>&1 )
check "a delete inside the footprint is really in the commit (was: silently dropped)" '( cd "$RN/.opencode/oc-dev-team/manual/n2" && git show --name-status --format= HEAD | grep -q "^D.*src/gone.ts" )'
check "and the worktree is clean afterwards, so the Stop gate passes" '( cd "$RN/.opencode/oc-dev-team/manual/n2" && [ -z "$(git status --porcelain)" ] \
  && [ -z "$( printf "{\"cwd\":\"%s\",\"last_assistant_message\":\"## Status: Complete -- ## Gate: echo ok -> ok, and again -> ok\"}" "$PWD" | python3 "$G" stop 2>&1 )" ] )'


echo "== v3.1 read-only roles cannot rewrite the run"
eq() { oci edit code-reviewer "$RF" path "$1"; }
check "a reviewer cannot write state.json" '[[ "$(eq "$RF/.opencode/oc-dev-team/state.json")" == *"read-only"* ]]'
check "a reviewer cannot rewrite plan.md" '[[ "$(eq "$RF/.opencode/oc-dev-team/plan.md")" == *"read-only"* ]]'
check "a reviewer cannot rewrite another slice briefing" '[[ "$(eq "$RF/.opencode/oc-dev-team/briefs/S1.md")" == *"read-only"* ]]'
check "a reviewer CAN write its own report" '[[ "$(eq "$RF/.opencode/oc-dev-team/reviews/r1.report.md")" != *deny* ]]'
check "an investigator CAN write its research report" '[[ "$(oci edit investigator "$RF" path "$RF/.opencode/oc-dev-team/research/X1.md")" != *deny* ]]'
eqa() { oci edit "$1" "$RF" path "$2"; }
check "the team-leader CAN write plan.md" '[[ "$(eqa team-leader "$RF/.opencode/oc-dev-team/plan.md")" != *deny* ]]'
check "a code-reviewer identified by agent_type still cannot" '[[ "$(eqa code-reviewer "$RF/.opencode/oc-dev-team/plan.md")" == *"read-only"* ]]'

echo "== v3.1 the vacuous-test check matches assertion CALLS, not English words"
vac() { python3 -c "
import sys; sys.path.insert(0, '$S')
import oc_devteam as devteam, pathlib, tempfile
d = pathlib.Path(tempfile.mkdtemp()); (d/'t.js').write_text(sys.argv[1])
print(len(devteam.vacuous_test_check(d, ['t.js'], ['c1'])))" "$1"; }
check "a require() import line does not count as an assertion" '[[ "$(vac "const foo = require(\"../src/foo\");
test(\"a\", () => { foo(1); });")" != "0" ]]'
check "the English word should in a comment does not count" '[[ "$(vac "// this should do things
test(\"a\", () => { foo(1); });")" != "0" ]]'
check "a real assertion call does count" '[[ "$(vac "test(\"a\", () => { assert.equal(1,1); });")" == "0" ]]'
check "expect(...) counts" '[[ "$(vac "test(\"a\", () => { expect(x).toBe(1); });")" == "0" ]]'
check "unittest assertEqual/assertIn count" '[[ "$(vac "def test_a(self):
    self.assertEqual(1, 1); self.assertIn(1, [1])")" == "0" ]]'

echo "== v3.1 verdict parsing fails closed"
RV="$(newrepo rv)"; cd "$RV"
cat > plan.md <<'EOF'
```json
{"request":"r","commands":{"test":"echo ok","lint":"none","typecheck":"none","build":"none"},
 "review_batch":1,"checkpoint_every":99,
 "slices":[{"id":"S1","title":"a","deps":[],"files":["src/b.js","tests/b.test.js"],"risk":"low","criteria":["c"]}]}
```
EOF
D init plan.md >/dev/null 2>&1; D dispatch S1 >/dev/null 2>&1
git worktree add -q .opencode/oc-dev-team/manual/v1 -b wv1 HEAD
( cd "$RV/.opencode/oc-dev-team/manual/v1" && D claim S1 --worktree "$PWD" >/dev/null 2>&1 && mktest tests/b.test.js b \
  && D commit-red a >/dev/null 2>&1 && echo i > src/b.js && D commit-green a >/dev/null 2>&1 )
D next S1 >/dev/null 2>&1
printf '## Review verdict: CHANGES REQUIRED\n## Findings\n### [MAJOR] x\n' > .opencode/oc-dev-team/reviews/r1.report.md
OUT=$(D next 2>&1)
check "CHANGES REQUIRED with a space is not read as APPROVED" '[[ "$OUT" == *"REVIEW r1: CHANGES_REQUIRED"* ]]'
check "finish refuses to close over a review that is not APPROVED" '[[ "$(D finish 2>&1)" == *"reviews not closed"* ]]'
printf '## Review verdict: APPROVED\n## Findings\nNo issues found.\n' > .opencode/oc-dev-team/reviews/r1.report.md
OUT=$(D next 2>&1)
check "a report rewritten in place IS re-harvested (the re-review loop can close)" '[[ "$OUT" == *"REVIEW r1: APPROVED"* && "$OUT" == *"re-review, round 2"* ]]'
check "and finish then closes cleanly" '[[ "$(D finish 2>&1)" == *"FINISHED"* ]]'

echo "== v3.1 fix slices from agent-written reports are untrusted input"
cd "$RV"
cat > bad.report.md <<'EOF'
## Review verdict: CHANGES_REQUIRED
```json
{"fixes":[{"id":"F?","title":"wildcard","files":["*"],"criteria":["c"]},
          {"id":"F?","title":"string files","files":"src/a.js","criteria":["c"]},
          {"id":"F?","title":"unproven chore","kind":"chore","files":["src/c.js"],"criteria":["c"]}]}
```
EOF
OUT=$(D add-fixes bad.report.md 2>&1 || true)
check "a wildcard footprint is refused (it would disable every footprint check)" '[[ "$OUT" == *"wildcard footprint"* ]]'
OUT=$(printf '```json\n{"fixes":[{"id":"F?","title":"unproven chore","kind":"chore","files":["src/c.js","tests/c.test.js"],"criteria":["c"]}]}\n```\n' > ok.report.md; D add-fixes ok.report.md 2>&1)
check "a chore fix with no verify command is downgraded to a test-first code slice" 'D status | grep -E "F[0-9]+ +pending +code"'

echo "== v3.1 review sharding never launches an empty reviewer"
RE="$(newrepo re)"; cd "$RE"
python3 - <<'PY' > plan.md
import json
sl = [{"id": f"S{i}", "title": f"s{i}", "deps": [], "files": [f"src/f{i}.js", f"tests/f{i}.test.js"],
       "risk": "low", "criteria": ["c"]} for i in range(1, 5)]
# 4x2 + 1 = 9 files: ceil(9/4) = 3 leaves the 4th shard with nothing to review
sl.append({"id": "S5", "title": "s5", "kind": "chore", "deps": [], "files": ["src/f5.js"],
           "risk": "low", "criteria": ["c"], "verify": "echo ok"})
print("```json"); print(json.dumps({"request": "r", "review_batch": 99, "checkpoint_every": 99,
      "commands": {"test": "echo ok", "lint": "none", "typecheck": "none", "build": "none"},
      "slices": sl})); print("```")
PY
D init plan.md >/dev/null 2>&1
for i in 1 2 3 4; do
  D dispatch "S$i" >/dev/null 2>&1
  git worktree add -q ".opencode/oc-dev-team/manual/e$i" -b "we$i" HEAD
  ( cd "$RE/.opencode/oc-dev-team/manual/e$i" && D claim "S$i" --worktree "$PWD" >/dev/null 2>&1 && mktest "tests/f$i.test.js" "f$i" \
    && D commit-red "s$i" >/dev/null 2>&1 && echo i > "src/f$i.js" && D commit-green "s$i" >/dev/null 2>&1 )
  D next "S$i" --shards 4 >/dev/null 2>&1
done
D dispatch S5 >/dev/null 2>&1
git worktree add -q .opencode/oc-dev-team/manual/e5 -b we5 HEAD
( cd "$RE/.opencode/oc-dev-team/manual/e5" && D claim S5 --worktree "$PWD" >/dev/null 2>&1 && echo i > src/f5.js && D commit-work s5 >/dev/null 2>&1 )
# the DAG empties here, so this `next` opens the FINAL review: 9 files asked to split over 4 shards
OUT=$(D next S5 --shards 4 2>&1)
check "the final review really was sharded 4 ways" '[[ "$(echo "$OUT" | grep -c "=== REVIEW r1-")" -ge 3 ]]'
check "9 files over 4 shards never produces a 0-file reviewer" '[[ "$OUT" != *", 0 files ==="* ]]'
check "the review records the number of shards actually launched" '[[ "$(python3 -c "import json;print(json.load(open(\".opencode/oc-dev-team/state.json\"))[\"reviews\"][\"r1\"][\"shards\"])")" -ge 1 ]]'

echo "== v3.1 a research-only run reaches its endgame"
RR="$(newrepo rr)"; cd "$RR"
cat > plan.md <<'EOF'
```json
{"request":"audit","commands":{"test":"echo ok","lint":"none","typecheck":"none","build":"none"},
 "slices":[{"id":"V1","title":"audit","kind":"research","deps":[],"files":["-"],"risk":"low","criteria":["is it safe"]}]}
```
EOF
D init plan.md >/dev/null 2>&1; D dispatch V1 >/dev/null 2>&1
mkdir -p .opencode/oc-dev-team/research
printf '## Verdict: INCONCLUSIVE\n## Findings\n- nothing\n' > .opencode/oc-dev-team/research/V1.md
OUT=$(D next V1 2>&1)
check "a research-only run does not crash the review batch (research is not a merge)" '[[ "$OUT" == *"RESEARCH RECORDED"* && "$OUT" != *"ambiguous argument"* && "$OUT" != *"Traceback"* ]]'
check "and it reaches DAG EXHAUSTED" '[[ "$OUT" == *"DAG EXHAUSTED"* ]]'

echo "== v3.1 --fast 0 means strict"
cd "$RR"
check "--fast 0 selects strict even when the plan asks for turbo" 'printf "\140\140\140json\n{\"request\":\"r\",\"profile\":\"turbo\",\"commands\":{\"test\":\"echo ok\"},\"slices\":[{\"id\":\"Z1\",\"title\":\"z\",\"deps\":[],\"files\":[\"src/z.js\",\"tests/z.test.js\"],\"risk\":\"low\",\"criteria\":[\"c\"]}]}\n\140\140\140\n" > p0.md; D init p0.md --force --fast 0 2>&1 | grep -q "PROFILE strict"'

# =============================================================================================
# v3.2 — no-relay integration (Stop-gate markers), never-prompt permissions, tighter dispatch
# =============================================================================================
echo "== v3.2 the Stop gate reports for the programmer: next needs no ids"
RM="$(newrepo rm32)"; cd "$RM"
cat > plan.md <<'EOF'
```json
{"request":"markers","commands":{"test":"echo ok","test_file":"echo ok {files}","lint":"none","typecheck":"none","build":"none"},
 "slices":[{"id":"M1","title":"one","deps":[],"files":["src/m1.js","tests/m1.test.js"],"risk":"low","criteria":["c"]},
           {"id":"M2","title":"two","deps":[],"files":["src/m2.js","tests/m2.test.js"],"risk":"low","criteria":["c"]},
           {"id":"M3","title":"research","kind":"research","deps":[],"files":["docs/x.md"],"risk":"low","criteria":["q?"]},
           {"id":"M4","title":"after one","deps":["M1"],"files":["src/m4.js","tests/m4.test.js"],"risk":"low","criteria":["c"]}]}
```
EOF
D init plan.md >/dev/null 2>&1; D dispatch M1 M2 M3 >/dev/null 2>&1
git worktree add -q .opencode/oc-dev-team/manual/m1 -b wm1 HEAD; MW1="$RM/.opencode/oc-dev-team/manual/m1"
git worktree add -q .opencode/oc-dev-team/manual/m2 -b wm2 HEAD; MW2="$RM/.opencode/oc-dev-team/manual/m2"
( cd "$MW1" && D claim M1 --worktree "$PWD" >/dev/null 2>&1 && mktest tests/m1.test.js M1 && D commit-red m1 >/dev/null 2>&1 && echo impl > src/m1.js && D commit-green m1 >/dev/null 2>&1 )
check "claim records the integration root for the Stop gate" '[ "$(cat "$MW1/.oc-slice/root")" = "$RM" ]'
printf '## Status: Complete\n## Gate: echo ok -> ok\n## Notes: none\n' > "$TMP/rep-M1.md"
check "a finished programmer report is accepted" 'D report M1 --file "$TMP/rep-M1.md" >/dev/null 2>&1'
check "and the report wrote a .done marker into the integration checkout" '[ -f "$RM/.opencode/oc-dev-team/slices/M1.done" ]'
( cd "$MW2" && D claim M2 --worktree "$PWD" >/dev/null 2>&1 && mktest tests/m2.test.js M2 && D commit-red m2 >/dev/null 2>&1 )
printf '## Status: Blocked\n## Notes: need src/shared.js which is outside my footprint\n' > "$TMP/rep-M2.md"
check "a Blocked report writes a .blocked marker carrying the question" 'D report M2 --file "$TMP/rep-M2.md" >/dev/null 2>&1; grep -q "outside my footprint" "$RM/.opencode/oc-dev-team/slices/M2.blocked"'
printf '## Verdict: INCONCLUSIVE\n## Findings\n- nothing\n' > .opencode/oc-dev-team/research/M3.md
OUT=$(D next 2>&1)
check "next with NO ids integrated the lane whose marker landed" '[[ "$OUT" == *"M1: MERGED"* ]]'
check "next recorded the research slice from its report alone" '[[ "$OUT" == *"M3: RESEARCH RECORDED"* ]]'
check "next surfaced the blocked lane with its exact question" '[[ "$OUT" == *"BLOCKED M2: need src/shared.js"* ]]'
check "next dispatched the dependent slice in the same call" '[[ "$OUT" == *"DISPATCH M4"* ]]'
check "consumed markers are removed (no double integration, no stale block)" '[ ! -f "$RM/.opencode/oc-dev-team/slices/M1.done" ] && [ ! -f "$RM/.opencode/oc-dev-team/slices/M2.blocked" ]'
check "a second next does not re-integrate or re-print anything" 'OUT2=$(D next 2>&1); [[ "$OUT2" != *"M1:"* && "$OUT2" != *"BLOCKED M2"* ]]'
check "a forged .done for an unfinished lane is harmless: integrate re-checks and rejects" 'echo "{}" > .opencode/oc-dev-team/slices/M2.done; OUT=$(D next 2>&1); [[ "$OUT" == *"M2: REJECTED"* ]] && [ ! -f .opencode/oc-dev-team/slices/M2.done ]'
check "M2 stays inflight for a warm fix after the rejection" 'D status | grep -q "M2     inflight"'

echo "== v3.2 routing: every slice goes to one agent name, one background row each"
RT="$(newrepo rt32)"; cd "$RT"
cat > plan.md <<'EOF'
```json
{"request":"routing","commands":{"test":"echo ok","test_file":"echo ok {files}","lint":"none","typecheck":"none","build":"none"},
 "slices":[{"id":"T1","title":"tiny","size":"trivial","deps":[],"files":["src/t1.js","tests/t1.test.js"],"risk":"low","criteria":["c"]},
           {"id":"D1","title":"readme","kind":"docs","deps":[],"files":["README.md"],"risk":"low","criteria":["c"],"verify":"echo ok"},
           {"id":"D2","title":"big docs","kind":"docs","size":"large","deps":[],"files":["docs/big.md"],"risk":"low","criteria":["c"],"verify":"echo ok"},
           {"id":"N1","title":"normal","deps":[],"files":["src/n1.js","tests/n1.test.js"],"risk":"low","criteria":["c"]}]}
```
EOF
OUT=$(D init plan.md 2>&1 && D dispatch T1 D1 D2 N1 2>&1)
check "trivial, docs and large slices all go to the one programmer agent" '[[ "$OUT" == *"DISPATCH T1"* && "$OUT" == *"DISPATCH D2"* ]]'
check "each dispatch prints a claim command and creates its lane worktree" 'grep -q "claim N1 --worktree" "$RT/.opencode/oc-dev-team/prompts/N1.md" && [ -d "$RT/.opencode/oc-dev-team/wt/N1" ] && [ -d "$RT/.opencode/oc-dev-team/wt/D2" ]'
check "one dispatch prints one background row per slice" '[ "$(echo "$OUT" | grep -c "background")" -ge 4 ]'


echo "== v3.2 start: greenfield git init; finish: PR summary"
GF="$(mktemp -d)/greenfield"; mkdir -p "$GF"; cd "$GF"
cat > plan.md <<'EOF'
```json
{"request":"new project","commands":{"test":"echo ok","test_file":"echo ok {files}","lint":"none","typecheck":"none","build":"none"},
 "slices":[{"id":"G1","title":"scaffold","kind":"chore","deps":[],"files":["package.json","src/index.js"],"risk":"low","criteria":["runs"],"verify":"echo ok"}]}
```
EOF
OUT=$(D start plan.md 2>&1)
check "start on a directory that is not a git repo initialises one and dispatches" '[[ "$OUT" == *"GIT: initialised"* && "$OUT" == *"INIT ok: 1 slices"* && "$OUT" == *"DISPATCH G1"* ]] && git -C "$GF" rev-parse --verify HEAD >/dev/null 2>&1'
cd "$RM"
check "finish --force writes a PR-ready summary.md" 'D finish --force >/dev/null 2>&1; [ -f .opencode/oc-dev-team/summary.md ] && grep -q "M1" .opencode/oc-dev-team/summary.md && grep -q "## Diff stat" .opencode/oc-dev-team/summary.md'

echo "== v3.2 a CHANGES_REQUIRED review queues its fix slices"
RV="$(newrepo rv32)"; cd "$RV"
cat > plan.md <<'EOF'
```json
{"request":"r","commands":{"test":"echo ok","lint":"none","typecheck":"none","build":"none"},"review_batch":1,
 "slices":[{"id":"V1","title":"a","deps":[],"files":["src/v1.js","tests/v1.test.js"],"risk":"low","criteria":["c"]}]}
```
EOF
D init plan.md >/dev/null 2>&1; D dispatch V1 >/dev/null 2>&1
git worktree add -q .opencode/oc-dev-team/manual/v1 -b wv1 HEAD
( cd .opencode/oc-dev-team/manual/v1 && D claim V1 --worktree "$PWD" >/dev/null 2>&1 && mktest tests/v1.test.js V1 && D commit-red v >/dev/null 2>&1 && echo i > src/v1.js && D commit-green v >/dev/null 2>&1 )
D next V1 >/dev/null 2>&1
printf '## Review verdict: CHANGES_REQUIRED\n```json\n{"fixes":[{"id":"F?","title":"x","files":["src/x.js","tests/x.test.js"],"criteria":["c"]}]}\n```\n' > .opencode/oc-dev-team/reviews/r1.report.md
OUT=$(D next 2>&1)
check "the review was harvested as CHANGES_REQUIRED with a fix queued" '[[ "$OUT" == *"REVIEW r1: CHANGES_REQUIRED"* && "$OUT" == *"queued F1"* ]]'

echo "== v3.2 adversarial round: every hole the reviewer found, with the attack that found it"
RA="$(newrepo ra32)"; cd "$RA"
cat > plan.md <<'EOF'
```json
{"request":"adv","commands":{"test":"node --test tests/","test_file":"node --test {files}","lint":"none","typecheck":"none","build":"none"},
 "slices":[{"id":"M2","title":"two","deps":[],"files":["src/m2.js","tests/m2.test.js"],"risk":"low","criteria":["c"],"isolation":true}]}
```
EOF
D init plan.md >/dev/null 2>&1; D dispatch M2 >/dev/null 2>&1
git worktree add -q .opencode/oc-dev-team/manual/m2 -b wa2 HEAD; PW="$RA/.opencode/oc-dev-team/manual/m2"
( cd "$PW" && D claim M2 --worktree "$PWD" >/dev/null 2>&1 )
check "a half-written research report is not harvested; a finished one is" 'RH="$(newrepo rh32)"; cd "$RH"; printf "\140\140\140json\n{\"request\":\"r\",\"commands\":{\"test\":\"echo ok\"},\"slices\":[{\"id\":\"Q1\",\"title\":\"q\",\"kind\":\"research\",\"deps\":[],\"files\":[\"docs/q.md\"],\"risk\":\"low\",\"criteria\":[\"q?\"]}]}\n\140\140\140\n" > plan.md; D init plan.md >/dev/null 2>&1; D dispatch Q1 >/dev/null 2>&1; mkdir -p .opencode/oc-dev-team/research; printf "# draft\n" > .opencode/oc-dev-team/research/Q1.md; [[ "$(D next 2>&1)" != *"RESEARCH RECORDED"* ]] && printf "## Verdict: INCONCLUSIVE\n## Findings\n- x\n" > .opencode/oc-dev-team/research/Q1.md && [[ "$(D next 2>&1)" == *"Q1: RESEARCH RECORDED"* ]]'


echo "== closed stdout pipe"; cd "$RS"
check "a closed pipe (status | grep -q) is not a traceback" '[[ "$(D status 2>&1 | head -1; D status 2>&1 >/dev/null | grep -c Traceback)" != *Traceback* ]]'

check "a closed pipe on a read-only command is quiet; on a state-changing one it is loud" 'cd "$RS"; python3 - "$S" <<PY2
import sys, io
sys.path.insert(0, sys.argv[1]); import oc_devteam as d
class Broken(io.TextIOBase):
    def write(self, s): raise BrokenPipeError()
    def flush(self): raise BrokenPipeError()
err = io.StringIO(); real_err = sys.stderr
sys.stdout = Broken(); rc_status = d.main(["status"])
sys.stdout = Broken(); sys.stderr = err; rc_next = d.main(["next"]); sys.stderr = real_err
assert rc_status == 0, rc_status
assert rc_next == 1 and "was cut off" in err.getvalue(), (rc_next, err.getvalue())
PY2'

echo "== OpenCode flow: dispatch row, claim --worktree, guard by lane path, report, resume"
ocplan() { printf '\140\140\140json\n{"request":"oc","commands":{"test":"true"},"review_batch":99,"checkpoint_every":99,"slices":[{"id":"%s","title":"t","deps":[],"files":["src/%s.js","tests/%s.test.js"],"risk":"low","criteria":["c"]}]}\n\140\140\140\n' "$1" "$2" "$2" > plan.md; }
RG="$(newrepo rgd)"; cd "$RG"; ocplan G1 g1
OUT=$(D start plan.md 2>&1)
GW="$RG/.opencode/oc-dev-team/wt/G1"
check "start printed a background row and created the lane worktree on branch oc-devteam/G1" '[[ "$OUT" == *"DISPATCH G1"* && "$OUT" == *"background"* ]] && [ -d "$GW" ] && [ "$(git -C "$GW" rev-parse --abbrev-ref HEAD)" = oc-devteam/G1 ]'
check "the programmer prompt is the claim command with the worktree path" 'grep -q "claim G1 --worktree" "$RG/.opencode/oc-dev-team/prompts/G1.md"'
CL=$(cd "$RG" && D claim G1 --worktree "$GW" 2>&1)
check "claim takes the worktree from its argument and tells the programmer to pass workdir" '[ -d "$GW/.oc-slice" ] && [[ "$CL" == *"workdir"* ]]'
check "a programmer edit inside its footprint is allowed" '[[ "$(oci edit programmer "$RG" path "$GW/src/g1.js")" != *deny* ]]'
check "a programmer edit outside its footprint is denied with the reason" '[[ "$(oci edit programmer "$RG" path "$GW/src/a.js")" == *"outside your slice footprint"* ]]'
check "a programmer write into the integration checkout is denied" '[[ "$(oci write programmer "$RG" path "$RG/src/g1.js")" == *deny* ]]'
check "a programmer shell call with no workdir is denied" '[[ "$(oci shell programmer "$RG" command "git status --porcelain")" == *deny* ]]'
check "a programmer shell call with the lane workdir is allowed" '[[ "$(oci shell programmer "$RG" command "git status --porcelain" "$GW")" != *deny* ]]'
check "git reset of a file is not refused by the history rule, push and history rewrites are denied" '[[ "$(oci shell programmer "$RG" command "git reset -- src/g1.js" "$GW")" != *"drop commits"* && "$(oci shell programmer "$RG" command "git push origin main" "$GW")" == *deny* && "$(oci shell programmer "$RG" command "git reset HEAD~1" "$GW")" == *deny* ]]'
check "git cannot be pointed at another checkout" '[[ "$(oci shell programmer "$RG" command "git -C ../../.. merge oc-devteam/G1" "$GW")" == *"another checkout"* && "$(oci shell programmer "$RG" command "GIT_DIR=/tmp/x/.git git reset --hard" "$GW")" == *"another checkout"* ]]'
check "writing .oc-slice/red by redirection is denied" '[[ "$(oci shell programmer "$RG" command "echo deadbeef > .oc-slice/red" "$GW")" == *"dev-team metadata"* ]]'
check "git stash (push) is denied" '[[ "$(oci shell programmer "$RG" command "git stash" "$GW")" == *"Conductor"* ]]'
check "a reviewer may redirect to /dev/null but not to a file" '[[ "$(oci shell code-reviewer "$RG" command "ls > /dev/null 2>&1")" != *deny* && "$(oci shell code-reviewer "$RG" command "echo a > b.txt")" == *deny* ]]'
PLUGDIR="$S/../opencode/plugins"
check "no v1 plugin is left and the v2 plugin reads the role from the event agent" '[ ! -e "$PLUGDIR/oc-devteam-guard.v1.js" ] && grep -q "id: \"oc-devteam-guard\"" "$PLUGDIR/oc-devteam-guard.v2.js" && grep -q "api.tool.hook" "$PLUGDIR/oc-devteam-guard.v2.js" && grep -q "oc_guard.py" "$PLUGDIR/oc-devteam-guard.v2.js" && grep -q "agent" "$PLUGDIR/oc-devteam-guard.v2.js" && ! grep -q "DEVTEAM_ROLE" "$PLUGDIR/oc-devteam-guard.v2.js" && ! grep -q "DEVTEAM_SLICE" "$PLUGDIR/oc-devteam-guard.v2.js" && ! grep -q "ctx.directory" "$PLUGDIR/oc-devteam-guard.v2.js"'
if command -v node >/dev/null 2>&1; then
  sed "s|{{SKILL_DIR}}|$(dirname "$S")|g" "$PLUGDIR/oc-devteam-guard.v2.js" > "$TMP/v2.mjs"
  cat > "$TMP/v2check.js" <<'JS'
(async () => {
  const mod = await import(process.argv[2]);
  const hooks = {};
  await mod.default.setup({ tool: { hook: (name, fn) => { hooks[name] = fn; } } });
  try {
    await hooks["execute.before"]({
      tool: "edit", sessionID: "s", agent: "oc-programmer", messageID: "m", id: "c",
      input: { path: process.argv[3], oldString: "a", newString: "b" },
    });
    console.log("ALLOWED");
  } catch (e) {
    console.log("DENIED: " + e.message);
  }
})();
JS
  V2RES=$(cd "$RG" && node "$TMP/v2check.js" "$TMP/v2.mjs" "$GW/outside.js" 2>&1)
  check "the v2 plugin denies an out-of-footprint edit in the lane worktree via oc_guard.py oc" '[[ "$V2RES" == *"outside your slice footprint"* ]]'
  V2OK=$(cd "$RG" && node "$TMP/v2check.js" "$TMP/v2.mjs" "$GW/src/g1.js" 2>&1)
  check "the v2 plugin allows an in-footprint edit via oc_guard.py oc" '[[ "$V2OK" == *"ALLOWED"* ]]'
else
  skip "node not on PATH: v2 plugin round-trip checks skipped"
fi
( cd "$GW" && mktest tests/g1.test.js g1 && D commit-red g1 >/dev/null 2>&1 && echo impl > src/g1.js && D commit-green g1 >/dev/null 2>&1 )
printf '## Status: Complete\n## Gate: true -> ok\n## Notes: none\n' > "$TMP/g1-report.md"
D report G1 --file "$TMP/g1-report.md" >/dev/null 2>&1; RC=$?
check "report accepts a finished slice and writes the .done marker" '[ "$RC" -eq 0 ] && [ -f "$RG/.opencode/oc-dev-team/slices/G1.done" ]'
RG2="$(newrepo rgf)"; cd "$RG2"; ocplan G2 g2
D start plan.md >/dev/null 2>&1
GW2="$RG2/.opencode/oc-dev-team/wt/G2"
D claim G2 --worktree "$GW2" >/dev/null 2>&1
printf '## Status: Complete\n## Gate: true -> ok\n' > "$TMP/g2-report.md"
OUT=$(D report G2 --file "$TMP/g2-report.md" 2>&1); RC=$?
check "report prints the gate problems in-band and exits 2 when the slice is not finished" '[ "$RC" -eq 2 ] && [ -n "$OUT" ] && [ ! -f "$RG2/.opencode/oc-dev-team/slices/G2.done" ]'
for i in 1 2 3; do D report G2 --file "$TMP/g2-report.md" >/dev/null 2>&1; done
check "after MAX_STOP_BLOCKS refusals the report is force-completed" '[ -f "$RG2/.opencode/oc-dev-team/slices/G2.done" ] || [ -f "$RG2/.opencode/oc-dev-team/slices/G2.blocked" ]'
RG3="$(newrepo rgr)"; cd "$RG3"; ocplan G3 g3
D start plan.md >/dev/null 2>&1
GW3="$RG3/.opencode/oc-dev-team/wt/G3"
D claim G3 --worktree "$GW3" >/dev/null 2>&1
printf '## Status: Blocked\n## Notes: need src/shared.js which is outside my footprint\n' > "$TMP/g3-report.md"
D report G3 --file "$TMP/g3-report.md" >/dev/null 2>&1
check "a Blocked report leaves a .blocked marker" '[ -f "$RG3/.opencode/oc-dev-team/slices/G3.blocked" ]'
OUT=$(D next 2>&1)
check "next surfaces the block and names resume" '[[ "$OUT" == *"BLOCKED G3"* && "$OUT" == *"resume G3"* ]]'
RES=$(D resume G3 --note "use src/y.js instead" 2>&1)
check "resume prints the background row again and puts the note in the brief" '[[ "$RES" == *"background"* && "$RES" == *"NEXT:"* ]] && grep -rqs "use src/y.js instead" "$RG3/.opencode/oc-dev-team" "$GW3/.oc-slice"'
echo "== OpenCode hardening DG4/DG5: read-only roles cannot write or exec through allow-listed tools"
roq() { printf '{"cwd":"%s","tool":"shell","role":"code-reviewer","args":{"command":%s}}' "$RA" "$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$1")" | python3 "$G" oc; }
roallow() { [[ "$(roq "$1")" != *deny* ]]; }
ronotallow() { [[ "$(roq "$1")" == *deny* ]]; }
check "DG4: plain git diff / git log / sort stay pre-approved for a reviewer" 'roallow "git diff HEAD" && roallow "git log -1" && roallow "sort src/a.js"'
check "DG4: git diff/log --output (a file write) is not pre-approved" 'ronotallow "git diff --output=/tmp/dg4 HEAD" && ronotallow "git log --output=notes.txt -1"'
check "DG4: git grep --open-files-in-pager (exec) is not pre-approved" 'ronotallow "git grep --open-files-in-pager=sh base"'
check "DG4: rg --pre (exec) is not pre-approved" 'ronotallow "rg --pre ./x.sh base src" && ronotallow "rg --pre=sh base src"'
check "DG4: uniq with an output file is not pre-approved" 'ronotallow "uniq src/a.js out.txt"'
check "DG4: sed w / e commands are not pre-approved" 'ronotallow "sed -n \"w out.txt\" src/a.js" && ronotallow "sed \"1e ls\" src/a.js"'
check "DG4: sort --compress-program (exec) is not pre-approved" 'ronotallow "sort --compress-program=sh src/a.js"'
mkdir -p "$RA/node_modules/.bin" && touch "$RA/node_modules/.bin/prettier"
check "DG5: a reviewer still runs the test runners for evidence" 'roallow "go test ./..." && roallow "make test"'
check "DG5: black / isort are not pre-approved for a reviewer" 'ronotallow "black src" && ronotallow "isort src"'
check "DG5: ruff --fix / ruff format are not pre-approved" 'ronotallow "ruff check --fix src" && ronotallow "ruff format src"'
check "DG5: prettier --write is not pre-approved" 'ronotallow "npx prettier --write src"'
check "DG5: gofmt -w / go fmt / cargo fmt are not pre-approved" 'ronotallow "gofmt -w ." && ronotallow "go fmt ./..." && ronotallow "cargo fmt"'


echo "== docs"
SK="$TMP/skill/SKILL.md"; RDM="$TMP/skill/README.md"
check "SKILL.md frontmatter holds only name, description, metadata (description <= 1024 chars)" 'python3 - "$SK" <<PY2
import re, sys
text = open(sys.argv[1]).read()
front = text.split("---")[1]
keys = re.findall(r"^([a-z-]+):", front, re.M)
assert keys == ["name", "description", "metadata"], keys
block = re.search(r"^description: >-\n((?:  .*\n)+)", front, re.M).group(1)
assert len(" ".join(x.strip() for x in block.splitlines())) <= 1024
PY2'
check "README.md names the .opencode/oc-dev-team state directory and the report command" 'grep -q "[.]opencode/oc-dev-team" "$RDM" && grep -q "report <id> --file" "$RDM"'
check "SKILL.md keeps the bootstrap loop, the numbered conductor rules and the claim/report protocol" 'grep -q "^R0[.]" "$SK" && grep -q "scripts/oc_devteam.py" "$SK" && grep -q "claim <id> --worktree" "$SK" && grep -q "report <id> --file" "$SK"'

echo
echo "passed=$pass failed=$fail"
[ "$fail" -eq 0 ]
