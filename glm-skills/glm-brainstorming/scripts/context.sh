#!/bin/sh
# Live context for the glm-brainstorming skill, injected before the model reads SKILL.md.
# Contract: read-only (no git index locks), bounded output (<=~55 lines),
# fast on huge repos, ALWAYS exits 0 — a non-zero exit cancels the skill.
cap() { head -n "$1" 2>/dev/null; }
# Concurrent model calls are limited to 8: clamp to 1..8; $2 = value for empty/non-numeric input.
c8() { case "$1" in ''|*[!0-9]*) echo "${2:-8}" ;; *) if [ "$1" -gt 8 ]; then echo 8; elif [ "$1" -lt 1 ]; then echo 1; else echo "$1"; fi ;; esac; }
export GIT_OPTIONAL_LOCKS=0

skill_dir=$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)
echo "date: $(date +%F)   cwd: $(pwd)"
echo "skill_dir: $skill_dir"

# --- runtime: harness, model slots, caps -----------------------------------
harness=unknown
oc_major=unknown
oc_line=
if [ -f "$skill_dir/scripts/oc_harness.py" ] && command -v python3 >/dev/null 2>&1; then
  oc_line=$(python3 "$skill_dir/scripts/oc_harness.py" harness --script "$skill_dir/scripts/context.sh" 2>/dev/null | head -n 1)
fi
if [ -n "$CLAUDECODE" ] || [ -n "$CLAUDE_CODE_ENTRYPOINT" ] || [ -n "$CLAUDE_SKILL_DIR" ]; then
  harness=claude-code
elif [ -n "$OPENCODE_TERMINAL" ] || [ -n "$OPENCODE" ] || [ -n "$OPENCODE_BIN" ] || [ -f "$skill_dir/.oc-major" ]; then harness=opencode
elif case "$skill_dir" in */.zcode/*) true ;; *) false ;; esac; then harness=zcode
elif case "$skill_dir" in */opencode/*|*/.opencode/*) true ;; *) false ;; esac; then harness=opencode
elif [ -n "$CODEX_CI" ] || [ -n "$CODEX_HOME" ]; then harness=codex
elif [ -n "$CLINE_VERSION" ] || [ -n "$ROO_CODE" ]; then harness=cline
elif [ -n "$GEMINI_CLI" ]; then harness=gemini-cli
elif [ -n "$GITHUB_COPILOT_CLI" ]; then harness=copilot-cli
fi
set -- $oc_line
if [ "$harness" != claude-code ] && [ "$harness" != zcode ] && [ "${1:-}" = opencode ]; then
  harness=$1
  [ -n "${2:-}" ] && oc_major=$2
fi
if [ "$harness" = opencode ] && [ "$oc_major" = unknown ] && [ -f "$skill_dir/.oc-major" ]; then
  oc_major=$(head -n 1 "$skill_dir/.oc-major" 2>/dev/null | tr -cd '0-9')
  [ -n "$oc_major" ] || oc_major=unknown
fi
if [ "$harness" = opencode ]; then
  echo "harness: opencode oc_major=$oc_major"
else
  echo "harness: $harness"
fi

route=anthropic
case "${ANTHROPIC_BASE_URL:-}" in
  *z.ai*|*zhipu*|*bigmodel*) route=glm ;;
  "") : ;;
  *) route=custom ;;
esac
big=${ANTHROPIC_DEFAULT_OPUS_MODEL:-${ANTHROPIC_MODEL:-default}}
mid=${ANTHROPIC_DEFAULT_SONNET_MODEL:-default}
fast=${ANTHROPIC_DEFAULT_HAIKU_MODEL:-${ANTHROPIC_SMALL_FAST_MODEL:-default}}
echo "route: $route   models: main=$big sonnet=$mid haiku=$fast"
case "$fast$mid$big" in
  *glm*|*GLM*) echo "glm: yes — lanes default to model=\"haiku\" (Flash); at most 2 lanes on \"sonnet\"; see glm-tuning.md" ;;
  *) [ "$route" = glm ] && echo "glm: route is GLM but model slots are unmapped — set ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-5.3-flash (glm-tuning.md §2)" ;;
esac
if [ "$harness" = opencode ]; then
  echo "caps: lanes=$(c8 "${OC_MAX_LANES:-8}" 8) (set OC_MAX_LANES or pass oc_harness run --width N; default 8, hard max 8) oc_major=$oc_major"
elif [ "$harness" = zcode ]; then
  echo "caps: lanes=$(c8 "${OC_MAX_LANES:-8}" 8) (default 8, hard max 8)"
else
  echo "caps: subagents=$(c8 "${CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS:-8}") workflow=$(c8 "${CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS:-8}") compact_window=${CLAUDE_CODE_AUTO_COMPACT_WINDOW:-default}"
fi

# --- repo ------------------------------------------------------------------
in_home=no
[ "$(pwd)" = "${HOME:-/nonexistent}" ] || [ "$(pwd)" = "/" ] && in_home=yes

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  files=$(git ls-files 2>/dev/null | wc -l | tr -d ' ')
  dirty=$(git status --porcelain --untracked-files=no 2>/dev/null | wc -l | tr -d ' ')
  echo "git: root=$(git rev-parse --show-toplevel 2>/dev/null) branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) tracked=$files modified=$dirty"
  echo "recent_commits:"
  git log --oneline -n 6 2>/dev/null | cut -c1-100 | sed 's/^/  /'
  # --relative -- . scopes both which commits count and which paths are shown to $PWD;
  # head -n 20000 caps the pipeline before awk/sort so a huge commit stays fast.
  echo "hot_dirs_30d: $(git log --since=30.days -n 300 --name-only --pretty=format: --relative -- . 2>/dev/null \
    | head -n 20000 \
    | awk -F/ 'NF>2{print $1"/"$2} NF==2{print $1} NF==1&&$1!=""{print "."}' | sort | uniq -c | sort -rn | cap 6 \
    | awk '{printf "%s(%s) ", $2, $1}')"
  if [ "$files" -le 50 ] 2>/dev/null; then
    echo "files: $(git ls-files 2>/dev/null | tr '\n' ' ')"
  else
    echo "tree: $(git ls-files 2>/dev/null | awk -F/ 'NF>1{print $1"/"} NF==1{print "."}' | sort | uniq -c | sort -rn | cap 14 \
      | awk '{printf "%s(%s) ", $2, $1}')"
  fi
elif [ "$in_home" = no ]; then
  echo "git: none"
  echo "top_level: $(ls -A 2>/dev/null | cap 30 | tr '\n' ' ')"
else
  echo "git: none (cwd is home or root — skipped scanning)"
fi

if [ "$in_home" = no ]; then
  m=$(find . -maxdepth 3 \( -name node_modules -o -name .git -o -name vendor -o -name .venv -o -name venv \
        -o -name dist -o -name build -o -name target -o -name .claude \) -prune -o \
      \( -name package.json -o -name pyproject.toml -o -name requirements.txt -o -name go.mod -o -name Cargo.toml \
         -o -name pom.xml -o -name build.gradle -o -name build.gradle.kts -o -name Gemfile -o -name composer.json \
         -o -name '*.csproj' -o -name pubspec.yaml -o -name Package.swift -o -name deno.json \) -print 2>/dev/null | cap 12)
  [ -n "$m" ] && echo "manifests: $(echo "$m" | sed 's|^\./||' | tr '\n' ' ')"
  if [ -f package.json ]; then
    # Squash to one line first so a one-line package.json parses the same as a multi-line one.
    echo "npm_deps: $(tr '\n' ' ' < package.json 2>/dev/null \
      | grep -oE '"(dependencies|devDependencies|peerDependencies)"[[:space:]]*:[[:space:]]*\{[^}]*\}' \
      | sed -E 's/^"[a-zA-Z]+"[[:space:]]*:[[:space:]]*\{//; s/\}$//' \
      | tr ',' '\n' | cut -d: -f1 | tr -d ' "' | grep -v '^$' | cap 30 | tr '\n' ' ')"
  fi
  if [ -f pyproject.toml ]; then
    echo "py_deps: $(awk '/^[[:space:]]*dependencies[[:space:]]*=[[:space:]]*\[/{f=1} f{print} f&&/\][[:space:]]*$/{exit}' pyproject.toml 2>/dev/null \
      | sed 's/^[[:space:]]*dependencies[[:space:]]*=[[:space:]]*\[//; s/\][[:space:]]*$//' | tr ',' '\n' | tr -d ' "' | grep -v '^$' | cap 25 | tr '\n' ' ')"
  elif [ -f requirements.txt ]; then
    echo "py_deps: $(grep -v '^[[:space:]]*#' requirements.txt 2>/dev/null | grep -v '^$' | cap 25 | tr '\n' ' ')"
  fi
  [ -f go.mod ] && echo "go_mod: $(grep -E '^(go |module |[[:space:]]+[a-z].* v[0-9])' go.mod 2>/dev/null | cap 20 | tr -s ' \t' ' ' | tr '\n' ';')"
  [ -f Cargo.toml ] && echo "cargo_deps: $(awk '/^\[dependencies\]/{f=1;next} /^\[/{f=0} f&&NF' Cargo.toml 2>/dev/null | cap 20 | tr -d ' ' | tr '\n' ' ')"
  echo "docs: $(ls -d README* CLAUDE.md AGENTS.md docs doc adr 2>/dev/null | tr '\n' ' ')"
  [ -d docs/specs ] && echo "recent_specs: $(ls -1t docs/specs 2>/dev/null | cap 4 | tr '\n' ' ')"
fi
exit 0
