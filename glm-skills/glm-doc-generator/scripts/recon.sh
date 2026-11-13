#!/usr/bin/env bash
# Turn 1 recon for glm-doc-generator. handoff.py open runs this. Do not edit the
# cache or fact-pack behavior without the snippet test.
S="${DOCGEN_STATE_DIR:-.zcode/doc-gen}"; mkdir -p "$S"; {
H=$(git rev-parse --short HEAD 2>/dev/null); [ -z "$H" ] && H=$( (find . -path ./.git -prune -o -type f -print0 2>/dev/null | xargs -0 ls -la 2>/dev/null) | cksum | tr -d ' ' | cut -c1-12);
if [ -f "$S/recon.md" ] && [ "$(sed -n 's/^HEAD: //p' "$S/recon.md" | head -n 1)" = "$H" ]; then echo "=== CACHE HIT ==="; cat "$S/recon.md"; cat "$S/state.json" 2>/dev/null; exit 0; fi
O=$(sed -n 's/^HEAD: //p' "$S/recon.md" 2>/dev/null | head -n 1); [ -n "$O" ] && { echo "=== CHANGED SINCE $O ==="; git diff --name-only "$O"..HEAD 2>/dev/null | head -200; }
echo "HEAD: $H"; echo "ROOT: $(pwd)"
FL=$(git ls-files 2>/dev/null); [ -z "$FL" ] && FL=$(find . -type f -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/venv/*' -not -path '*/dist/*' -not -path '*/build/*' -not -path '*/target/*' -not -path '*/vendor/*' -not -path '*/.next/*' 2>/dev/null | sed 's|^\./||')
echo "FILES: $(printf '%s\n' "$FL" | wc -l)"
echo "== TREE =="; printf '%s\n' "$FL" | awk -F/ 'NF>1{print $1"/"$2} NF==1{print $1}' | sort | uniq -c | sort -rn | head -40
echo "== EXT =="; printf '%s\n' "$FL" | sed -n 's/.*\.\([A-Za-z0-9]\{1,6\}\)$/\1/p' | sort | uniq -c | sort -rn | head -12
for m in package.json pyproject.toml requirements.txt go.mod Cargo.toml pom.xml build.gradle composer.json Gemfile Makefile Dockerfile docker-compose.yml .env.example; do [ -f "$m" ] && { echo "== $m =="; head -60 "$m"; }; done
for r in README.md README.rst readme.md CONTRIBUTING.md; do [ -f "$r" ] && { echo "== $r =="; sed -n '1,120p' "$r"; }; done
for d in requirements specs spec docs doc design; do for s in "$d"/*.md "$d"/*.txt; do [ -f "$s" ] && { echo "== SPEC(READ-ONLY): $s =="; sed -n '1,120p' "$s"; }; done; done
echo "== FACTPACK =="
P='app\.(get|post|put|patch|delete)\(|@app\.route|@(Get|Post|Put|Patch|Delete)Mapping|router\.(get|post|put|patch|delete)\(|func \(.*\) [A-Z][A-Za-z]*\(|http\.HandleFunc|export (default |async )?(function|class|const) [A-Za-z]|^[[:space:]]*(public|private) [A-Za-z<>\[\]]+ [a-zA-Z]+\(|class [A-Za-z]+(Model|Entity|Service|Controller|Repository)|CREATE TABLE|^[[:space:]]*(interface|type) [A-Z][A-Za-z]*|@(Entity|Table|Column)|models\.[A-Z][a-zA-Z]*Field|process\.env\.[A-Z_]+|os\.getenv\('
if command -v rg >/dev/null 2>&1; then rg -n --no-heading -m 500 --max-filesize 512K -g '!*.min.*' -g '!*.lock' -e "$P" . 2>/dev/null | head -400; else grep -rnE --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=vendor "$P" . 2>/dev/null | head -400; fi
echo "== TESTS =="; printf '%s\n' "$FL" | grep -iE '(^|/)(tests?|spec|__tests__)/|\.(test|spec)\.[a-z]+$|_test\.[a-z]+$' | head -25
echo "== CI =="; ls .github/workflows/*.y*ml Jenkinsfile .gitlab-ci.yml 2>/dev/null | head -10
echo "== EXISTING DOCS =="; printf '%s\n' "$FL" | grep -iE '\.(md|rst|adoc)$' | head -40
} 2>/dev/null | head -900
