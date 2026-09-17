#!/bin/sh
# Live context for the brainstorming skill, injected before Claude reads SKILL.md.
# Contract: read-only (no git index locks), bounded output (<=~55 lines),
# fast on huge repos, ALWAYS exits 0 — a non-zero exit cancels the skill
# (verified on Claude Code 2.1.274).
cap() { head -n "$1" 2>/dev/null; }
export GIT_OPTIONAL_LOCKS=0

skill_dir=$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)
echo "date: $(date +%F)   cwd: $(pwd)"
echo "skill_dir: $skill_dir"
echo "caps: subagents=${CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS:-20} workflow=${CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS:-16}"

in_home=no
[ "$(pwd)" = "${HOME:-/nonexistent}" ] || [ "$(pwd)" = "/" ] && in_home=yes

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  files=$(git ls-files 2>/dev/null | wc -l | tr -d ' ')
  dirty=$(git status --porcelain --untracked-files=no 2>/dev/null | wc -l | tr -d ' ')
  echo "git: root=$(git rev-parse --show-toplevel 2>/dev/null) branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) tracked=$files modified=$dirty"
  echo "recent_commits:"
  git log --oneline -n 6 2>/dev/null | cut -c1-100 | sed 's/^/  /'
  echo "hot_dirs_30d: $(git log --since=30.days -n 300 --name-only --pretty=format: 2>/dev/null \
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
    echo "npm_deps: $(awk '/"(dependencies|devDependencies|peerDependencies)"[[:space:]]*:/{f=1;next} f&&/}/{f=0} f{gsub(/[ \t",]/,"");print}' package.json 2>/dev/null | cap 30 | tr '\n' ' ')"
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
  [ -d docs/superpowers/specs ] && echo "recent_specs: $(ls -1t docs/superpowers/specs 2>/dev/null | cap 4 | tr '\n' ' ')"
fi
exit 0
