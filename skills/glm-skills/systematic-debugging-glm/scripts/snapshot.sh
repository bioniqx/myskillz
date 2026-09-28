#!/usr/bin/env bash
# Debugging snapshot in one call: git state, recent changes, relevant toolchain versions, CPU count.
# Always exits 0. Output is capped to stay context-cheap.  Usage: snapshot.sh [dir]
set +e
if [ -n "$1" ]; then cd "$1" 2>/dev/null || { echo "snapshot: no such dir: $1"; exit 0; }; fi
. "$(dirname "$0")/_lib.sh"
echo "## cwd: $(pwd)   cpus: $(sd_cpus)   os: $(uname -sm)"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "## git: $(git rev-parse --abbrev-ref HEAD 2>/dev/null) @ $(git log -1 --pretty='%h %ad %s' --date=short 2>/dev/null)"
  up=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null) &&
    echo "## upstream: $up (ahead/behind: $(git rev-list --left-right --count 'HEAD...@{u}' 2>/dev/null | tr '\t' '/'))"
  st=$(git status --short 2>/dev/null); n=$(printf '%s' "$st" | grep -c . )
  echo "## uncommitted: $n file(s)"; printf '%s\n' "$st" | head -25 | grep .
  git diff HEAD --stat 2>/dev/null | tail -1 | grep . | sed 's/^/## diff vs HEAD:/'
  echo "## last 12 commits"; git log -12 --pretty='%h %ad %<(12,trunc)%an %s' --date=short 2>/dev/null
  echo "## hot files (last 20 commits)"; git log -20 --name-only --pretty=format: 2>/dev/null | grep . | sort | uniq -c | sort -rn | awk '$1>1' | head -10
  dep=$(git log -20 --pretty='%h %ad %s' --date=short -- package.json '*lock*' requirements*.txt pyproject.toml poetry.lock uv.lock go.mod go.sum Cargo.toml Cargo.lock Gemfile.lock composer.lock pom.xml build.gradle* '*.csproj' 2>/dev/null | head -5)
  [ -n "$dep" ] && { echo "## dependency-file commits (last 20)"; echo "$dep"; }
  st=$(git stash list 2>/dev/null | head -3); [ -n "$st" ] && { echo "## stashes"; echo "$st"; }
else
  echo "## not a git repository"
fi
v() { printf '%s: %s\n' "$1" "$("$@" 2>&1 | head -1)"; }
echo "## toolchain (detected from project files)"
[ -f package.json ] && { command -v node >/dev/null && v node --version
  for pm in pnpm yarn bun npm; do case $pm in
    pnpm) [ -f pnpm-lock.yaml ];; yarn) [ -f yarn.lock ];; bun) [ -f bun.lockb ] || [ -f bun.lock ];; npm) [ -f package-lock.json ];; esac && command -v $pm >/dev/null && v $pm --version; done
  t=$(grep -oE '"(vitest|jest|mocha|@playwright/test|cypress|ava|tap)"' package.json | tr -d '"' | tr '\n' ' '); [ -n "$t" ] && echo "test deps: $t"; }
{ [ -f pyproject.toml ] || [ -f setup.py ] || ls requirements*.txt >/dev/null 2>&1; } && { command -v python3 >/dev/null && v python3 --version; [ -d .venv ] && echo ".venv present"; }
[ -f go.mod ] && command -v go >/dev/null && v go version
[ -f Cargo.toml ] && command -v cargo >/dev/null && v cargo --version
{ [ -f pom.xml ] || ls build.gradle* >/dev/null 2>&1; } && command -v java >/dev/null && v java -version
[ -f Gemfile ] && command -v ruby >/dev/null && v ruby --version
[ -f composer.json ] && command -v php >/dev/null && v php --version
ls ./*.csproj ./*.sln >/dev/null 2>&1 && command -v dotnet >/dev/null && v dotnet --version
ls -d .github/workflows .gitlab-ci.yml Dockerfile docker-compose*.yml .tool-versions .nvmrc 2>/dev/null | tr '\n' ' ' | grep . | sed 's/^/## infra: /'; echo
exit 0
