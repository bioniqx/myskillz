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

oc_bin="${HYBRID_BRAINSTORMING_OC_BIN:-opencode}"
doctor_cache="${HYBRID_BRAINSTORMING_DOCTOR_CACHE:-$HOME/.cache/hybrid-brainstorming/doctor.json}"

status_line=""
if command -v "$oc_bin" >/dev/null 2>&1 && [ -f "$doctor_cache" ]; then
  doctor_oneline=$(tr '\n\r' '  ' <"$doctor_cache" 2>/dev/null)
  status_line=$(printf '%s' "$doctor_oneline" | sed -n 's/.*"status_line"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
fi
if [ -n "$status_line" ] && [ -n "$(find "$doctor_cache" -mmin +10 2>/dev/null)" ]; then
  status_line="opencode: doctor cache older than 10 min → stale (run bslane.py doctor)"
fi

if [ -n "$status_line" ]; then
  echo "$status_line"
else
  echo "opencode: unavailable → preset claude (run bslane.py doctor)"
fi

# Shared models come from $HYBRID_OPENCODE_STD / $HYBRID_OPENCODE_LITE (provider/model[#variant]);
# LITE defaults to STD. Prints the spec when valid, nothing otherwise.
trim() { printf '%s' "$1" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//'; }
valid_spec() {
  case "$1" in *[[:space:]]*) return 0 ;; esac
  v=""
  case "$1" in *'#'*) v=${1#*#} ;; esac
  case "$v" in *'#'*) return 0 ;; esac
  case "${1%%#*}" in [!/]*/?*) printf '%s' "${1%%#*}${v:+#$v}" ;; esac
}

shared_src='$HYBRID_OPENCODE_STD/$HYBRID_OPENCODE_LITE'
std_env=$(trim "${HYBRID_OPENCODE_STD:-}")
lite_env=""
if [ -n "$std_env" ]; then
  lite_env=$(trim "${HYBRID_OPENCODE_LITE:-}")
  [ -n "$lite_env" ] || lite_env="$std_env"
fi
skill_cfg="${HYBRID_BRAINSTORMING_ROUTING:-${skill_dir:-$HOME/.claude/skills/hybrid-brainstorming-v1.0}/routing.json}"
skill_flat=""
skill_json_bad=""
if [ -f "$skill_cfg" ]; then
  skill_flat=$(tr '\n\r' '  ' <"$skill_cfg" 2>/dev/null)
  # A truncated or non-object routing.json must not read as valid (sed alone cannot tell).
  if command -v python3 >/dev/null 2>&1 \
     && ! python3 -c 'import json,sys; assert isinstance(json.load(open(sys.argv[1])), dict)' "$skill_cfg" >/dev/null 2>&1; then
    skill_json_bad=yes
    skill_flat=""
  fi
fi
model_specs=""
model_bad=""
skill_bad=""
for tier in std lite; do
  spec=""
  from=skill
  tier_body=$(printf '%s' "$skill_flat" | sed -n 's/.*"'"$tier"'"[[:space:]]*:[[:space:]]*{\([^}]*\)}.*/\1/p')
  tier_model=$(printf '%s' "$tier_body" | sed -n 's/.*"model"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
  tier_variant=$(printf '%s' "$tier_body" | sed -n 's/.*"variant"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
  if [ -n "$tier_model" ]; then
    case "$tier_model" in
      ?*/?*)
        spec="$tier_model"
        [ -z "$tier_variant" ] || spec="$spec#$tier_variant"
        ;;
    esac
    [ -n "$spec" ] || skill_bad="$skill_bad $tier"
  else
    from=shared
    if [ "$tier" = std ]; then spec=$(valid_spec "$std_env"); else spec=$(valid_spec "$lite_env"); fi
  fi
  if [ -n "$spec" ]; then
    model_specs="$model_specs $tier=$spec ($from)"
  elif [ "$from" = shared ]; then
    model_bad="$model_bad $tier"
  fi
done
if [ -n "$skill_json_bad$skill_bad" ]; then
  # The problem is in this skill's own routing.json: say so instead of blaming the shared env vars.
  problems=""
  [ -z "$skill_json_bad" ] || problems="$skill_cfg is not a valid JSON object"
  [ -z "$skill_bad" ] || problems="$problems$skill_cfg sets a model that is not provider/model for$skill_bad"
  [ -z "$model_bad" ] || problems="$problems; model missing or not provider/model in the env vars for$model_bad"
  echo "shared config: $shared_src no config (invalid: $problems)"
elif [ -z "$model_bad" ]; then
  echo "shared config: $shared_src$model_specs (valid)"
elif [ -z "$std_env" ]; then
  echo "shared config: $shared_src no config (missing)"
else
  echo "shared config: $shared_src no config (invalid: model missing or not provider/model for$model_bad)"
fi

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
  [ -d docs/superpowers/specs ] && echo "recent_specs: $(ls -1t docs/superpowers/specs 2>/dev/null | cap 4 | tr '\n' ' ')"
fi
exit 0
