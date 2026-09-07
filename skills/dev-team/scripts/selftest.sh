#!/usr/bin/env bash
# End-to-end self-test of the dev-team engine + hook guards in a throwaway git repo.
# Usage: bash selftest.sh   (needs git >= 2.31, python3). Exit 0 = all checks passed.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
# copy the skill to a path WITH SPACES to exercise quoting
TMP="$(mktemp -d)/dev team"; mkdir -p "$TMP"; cp -r "$HERE/.." "$TMP/skill"
S="$TMP/skill/scripts"; G="$S/guard.py"
D() { python3 "$S/devteam.py" "$@"; }
R="$(mktemp -d)/repo"; mkdir -p "$R"; cd "$R"
git init -q -b main; git config user.email t@t; git config user.name t; git config commit.gpgsign true
mkdir -p src node_modules/pkg && echo "base" > src/a.js && echo x > node_modules/pkg/i.js
printf 'node_modules/\n' > .gitignore
git -c commit.gpgsign=false add -A && git -c commit.gpgsign=false commit -qm init
pass=0; fail=0
ok()  { pass=$((pass+1)); echo "  ok   $1"; }
bad() { fail=$((fail+1)); echo "  FAIL $1"; }
check() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }
hook() { printf '%s' "$2" | python3 "$G" "$1"; }

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
check "allow rules written" 'grep -q "node --test tests/:\*" .claude/settings.local.json && grep -q "PORT=4001 DB_SUFFIX=_s1 TMPDIR=.slice/tmp node --test" .claude/settings.local.json'
check "excludes include bare node_modules" 'grep -qx node_modules .git/info/exclude'

echo "== dispatch S1 S2 S4 (S4 must be skipped: overlaps S1)"
OUT=$(D dispatch S1 S2 S4 2>&1)
check "S1,S2 dispatched, S4 skipped" '[[ "$OUT" == *"DISPATCH S1"* && "$OUT" == *"DISPATCH S2"* && ("$OUT" == *"S4 (footprint overlaps"* || "$OUT" == *"S4 (not ready"*) ]]'
check "quoted script path in prompt" '[[ "$OUT" == *"claim S1"* && "$OUT" == *"'"'"'"*"dev team"*"'"'"'"* ]]'

run_prog() { # id wt testfile srcfile [red|green]
  local id=$1 wt=$2 t=$3 f=$4 mode=${5:-slice}
  ( cd "$R" && git worktree add -q ".claude/worktrees/$wt" -b "worktree-$wt" HEAD ) || return 1
  ( cd "$R/.claude/worktrees/$wt" && D claim "$id" > "$R/claim-$id.out" 2>&1 || exit 1
    if [[ "$mode" != green ]]; then mkdir -p tests && echo "test $id" > "$t" && D commit-red "$id" >/dev/null 2>&1 || exit 1; fi
    if [[ "$mode" != red ]]; then echo "impl $id" >> "$f" && D commit-green "$id" >/dev/null 2>&1 || exit 1; fi )
}
echo "== S1 slice"
run_prog S1 w1 tests/sub.test.js src/sub.js
check "claim printed isolation prefix" 'grep -q "PORT=4001 DB_SUFFIX=_s1 TMPDIR=.slice/tmp" "$R/claim-S1.out"'
check "node_modules symlinked and not stray" '[ -L "$R/.claude/worktrees/w1/node_modules" ] && [ -z "$(cd "$R/.claude/worktrees/w1" && git status --porcelain | grep node_modules)" ]'
check "stop hook allows a finished slice" '(cd "$R/.claude/worktrees/w1" && printf "{\"cwd\":\"%s\",\"last_assistant_message\":\"## Status: Complete\"}" "$PWD" | python3 "$G" stop) >/dev/null 2>&1'
echo "== S2 RED then GREEN"
run_prog S2 w2 tests/mul.test.js src/mul.js red
OUT=$(D integrate S1 S2 2>&1); echo "$OUT" | head -2
check "S1 merged (signing+hooks off)" '[[ "$OUT" == *"S1: MERGED"* ]]'
check "S2 RED accepted" '[[ "$OUT" == *"S2: RED accepted"* ]]'
check "review + checkpoint due after 1 merge? no" '[[ "$OUT" == *"CHECKPOINT: not due (1/2"* ]]'
D dispatch S2 S4 >/dev/null 2>&1
run_prog S2 w3 tests/mul.test.js src/mul.js green
check "green worktree starts at RED tip" '(cd "$R/.claude/worktrees/w3" && git log --format=%s -n 2 | sed -n 2p | grep -q "test(S2)")'
echo "== S4 with a frozen-test modification via raw git (rejected, stays inflight, warm fix, re-integrate)"
run_prog S4 w4 tests/sub2.test.js src/sub.js
( cd "$R/.claude/worktrees/w4" && echo "weakened" >> tests/sub2.test.js && git -c commit.gpgsign=false commit -qam "sneaky" )
OUT=$(D integrate S4 2>&1); echo "$OUT" | head -1
check "S4 rejected: frozen tests modified" '[[ "$OUT" == *"S4: REJECTED — frozen tests modified"* ]]'
check "S4 still inflight (warm fix possible)" 'D status | grep -q "S4     inflight.*REJECTED:tests-modified"'
( cd "$R/.claude/worktrees/w4" && RED=$(cat .slice/red) && git checkout -q "$RED" -- tests/sub2.test.js && git -c commit.gpgsign=false commit -qam "restore test" )
OUT=$(D integrate S4 S2 2>&1); echo "$OUT" | head -2
check "S4 merged after warm fix" '[[ "$OUT" == *"S4: MERGED"* ]]'
check "S2 merged (green)" '[[ "$OUT" == *"S2: MERGED"* ]]'
check "review batch due" '[[ "$OUT" == *"REVIEW: batch DUE"* ]]'
check "checkpoint due" '[[ "$OUT" == *"CHECKPOINT: DUE"* ]]'
echo "== checkpoint on a detached snapshot"
OUT=$(D checkpoint 2>&1); echo "$OUT" | head -2
check "checkpoint uses a detached worktree" '[[ "$OUT" == *"checkpoint-1"* ]] && [ -d "$R/.claude/worktrees/checkpoint-1" ] && [ -L "$R/.claude/worktrees/checkpoint-1/node_modules" ]'
D checkpoint --result pass >/dev/null 2>&1
check "checkpoint worktree removed" '[ ! -d "$R/.claude/worktrees/checkpoint-1" ]'
echo "== review batch + add-fixes"
OUT=$(D review-batch --shards 2 2>&1)
check "two shards" '[[ "$OUT" == *"REVIEW r1-1"* && "$OUT" == *"REVIEW r1-2"* ]]'
cat > .claude/dev-team/reviews/r1-1.report.md <<'EOF'
## Review verdict: CHANGES_REQUIRED
```json
{"fixes":[{"id":"F?","title":"nan","files":["src/nan.js","tests/nan.test.js"],"criteria":["nan"]}]}
```
EOF
OUT=$(D add-fixes .claude/dev-team/reviews/r1-1.report.md 2>&1)
check "fix slice F1 added and ready" '[[ "$OUT" == *"added fix slices: F1"* && "$OUT" == *"READY: "*"F1"* ]]'
echo "== retry reloads footprint from plan.md"
D dispatch S3 >/dev/null 2>&1
run_prog S3 w5 tests/combo.test.js src/combo.js
( cd "$R/.claude/worktrees/w5" && echo hack >> src/a.js && git -c commit.gpgsign=false commit -qam "outside" )
OUT=$(D integrate S3 2>&1)
check "S3 footprint violation rejected" '[[ "$OUT" == *"S3: REJECTED — files outside the footprint: src/a.js"* ]]'
sed -i 's#"files":\["src/combo.js","tests/combo.test.js"\]#"files":["src/combo.js","src/a.js","tests/combo.test.js"]#' plan.md
cp plan.md .claude/dev-team/plan.md
OUT=$(D retry S3 2>&1)
check "retry re-queued S3" '[[ "$OUT" == *"S3: re-queued"* ]]'
check "retry reloaded files from plan.md" 'python3 -c "import json;s=json.load(open(\"$R/.claude/dev-team/state.json\"));assert \"src/a.js\" in s[\"slices\"][\"S3\"][\"files\"]"'
echo "== guards"
check "bash guard denies git reset HEAD~1" '[[ "$(hook bash "{\"tool_input\":{\"command\":\"git reset HEAD~1\"}}")" == *deny* ]]'
check "bash guard allows git reset -- file" '[[ -z "$(hook bash "{\"tool_input\":{\"command\":\"git reset -- src/x.js\"}}")" ]]'
check "bash guard allows git checkout <ref> -- file" '[[ -z "$(hook bash "{\"tool_input\":{\"command\":\"git checkout abc123 -- tests/x.js\"}}")" ]]'
check "bash-ro allows redirect to /dev/null" '[[ -z "$(hook bash-ro "{\"tool_input\":{\"command\":\"ls > /dev/null; x 2>/dev/null; y 2>&1 | tail\"}}")" ]]'
check "bash-ro denies redirect to file" '[[ "$(hook bash-ro "{\"tool_input\":{\"command\":\"echo a > b.txt\"}}")" == *deny* ]]'
echo "== doctor on installed agents (hook pinning)"
D doctor --fix >/dev/null 2>&1
check "doctor pins hooks to guard.py" 'grep -q "guard.py\\\\\" edit\"" "$R/.claude/agents/programmer.md"'
OUT=$(CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=64 CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY=64 D doctor 2>&1)
check "doctor all good after fix" '[[ "$OUT" == *"DOCTOR: all good"* ]]'
echo
echo "passed=$pass failed=$fail"
[ "$fail" -eq 0 ]
