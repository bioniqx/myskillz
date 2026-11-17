#!/usr/bin/env bash
# Debugging snapshot in one call: current git state, toolchain versions, CPU count.
# No git history is read: the diagnosis works from the code as it is now.
# Always exits 0. Output is capped to stay context-cheap.  Usage: snapshot.sh [dir]
set +e
. "$(dirname "$0")/_lib.sh"
if [ -n "$1" ]; then cd "$1" 2>/dev/null || { echo "snapshot: no such dir: $1"; exit 0; }; fi
echo "## cwd: $(pwd)   cpus: $(sd_cpus)   os: $(uname -sm)"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "## git: $(git rev-parse --abbrev-ref HEAD 2>/dev/null) @ $(git rev-parse --short HEAD 2>/dev/null)"
  st=$(git status --short 2>/dev/null); n=$(printf '%s' "$st" | grep -c . )
  echo "## uncommitted: $n file(s)"; printf '%s\n' "$st" | head -25 | grep .
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
