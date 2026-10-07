#!/usr/bin/env bash
# Install every skill in this repo into Claude Code (user level or project level).
#
#   claude-skills/claude-*/  (originals) -> BASE/skills/<same folder>/  (clean overwrite)
#   hybrid-skills/hybrid-*/  (hybrids)   -> BASE/skills/<same folder>/  (rsync merge, keeps routing.json)
#   agents from both families            -> BASE/agents/
#   --model / --lite                     -> "env" block of BASE/settings.json (HYBRID_OPENCODE_*)
#
# Usage: ./install-claude-code.sh [--claude-dir DIR] [--project DIR] [--only NAME[,NAME...]]
#                                  [--dry-run] [--uninstall] [--keep-old] [--no-claude] [--no-hybrid]
#                                  [--model provider/model#variant] [--lite provider/model#variant]
#                                  [--remove-legacy] [--skip-check] [-h]
#   --claude-dir DIR   Claude config dir (default: $CLAUDE_CONFIG_DIR or ~/.claude)
#   --project DIR      install into DIR/.claude instead (project-level install)
#   --only LIST        comma-separated skill folder names, e.g. claude-dev-team-v3.2,hybrid-team-v1.0
#   --dry-run, -n      print what would happen, change nothing
#   --uninstall        remove the installed skills and agents from BASE instead of installing
#   --keep-old         keep old un-prefixed copies (dev-team-v3.2, programmer.md, ...); default: delete them
#   --no-claude        skip the claude-skills family (install hybrids only)
#   --no-hybrid        skip the hybrid-skills family (install originals only)
#   --model SPEC       set HYBRID_OPENCODE_STD in settings.json unless already set
#   --lite SPEC        set HYBRID_OPENCODE_LITE in settings.json unless already set (defaults to STD)
#   --remove-legacy    delete agent files with the old "ht-*" names left by earlier installs
#   --skip-check       do not look for the opencode CLI
# Works with bash 3.2 (macOS); needs python3, and rsync when installing hybrid skills.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_CLAUDE="$ROOT/claude-skills"
SRC_HYBRID="$ROOT/hybrid-skills"
BASE="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
DRY=0 UNINSTALL=0 KEEP_OLD=0 NO_CLAUDE=0 NO_HYBRID=0 LEGACY=0 CHECK=1
ONLY="" MODEL="" LITE=""

# Un-prefixed names used before the claude- rename; deleted on install.
OLD_SKILLS="brainstorming-6.3 dev-team-v3.2 doc-generator frontend-design-Jun18 git-diff-summary requirements-code-audit systematic-debugging-6.3 writing-plans-6.2"
OLD_AGENTS="programmer code-reviewer spot-reviewer investigator team-leader plan-task-writer rca-parser rca-investigator rca-verifier"

usage() { sed -n '2,24p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }
die() { echo "install-claude-code.sh: $*" >&2; exit 1; }
run() { if [ "$DRY" = 1 ]; then echo "  [dry-run] $*"; else "$@"; fi; }

while [ $# -gt 0 ]; do
  case "$1" in
    --claude-dir) [ $# -ge 2 ] || die "--claude-dir needs a directory"; BASE="$2"; shift 2 ;;
    --project) [ $# -ge 2 ] || die "--project needs a directory"; BASE="$(cd "$2" && pwd)/.claude"; shift 2 ;;
    --only) [ $# -ge 2 ] || die "--only needs a list"; ONLY=",$2,"; shift 2 ;;
    --dry-run|-n) DRY=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    --keep-old) KEEP_OLD=1; shift ;;
    --no-claude) NO_CLAUDE=1; shift ;;
    --no-hybrid) NO_HYBRID=1; shift ;;
    --model) [ $# -ge 2 ] || die "--model needs a value"; MODEL="$2"; shift 2 ;;
    --lite) [ $# -ge 2 ] || die "--lite needs a value"; LITE="$2"; shift 2 ;;
    --remove-legacy) LEGACY=1; shift ;;
    --skip-check) CHECK=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
done

[ "$NO_CLAUDE" = 1 ] && [ "$NO_HYBRID" = 1 ] && die "nothing to do: --no-claude and --no-hybrid together"
case "$BASE" in *[!A-Za-z0-9_./-]*) die "install path has characters unsafe for hook commands: $BASE" ;; esac
for spec in "$MODEL" "$LITE"; do
  if [ -n "$spec" ]; then
    printf '%s' "$spec" | grep -Eq '^[^/[:space:]]+/[^[:space:]#]+(#[^[:space:]#]+)?$' \
      || die "model spec must look like provider/model or provider/model#variant: $spec"
  fi
done

SKILLS_DIR="$BASE/skills"
AGENTS_DIR="$BASE/agents"

# Collect skills: every <family>-*/ directory with a SKILL.md, honouring --only.
claude_skills=()
hybrid_skills=()
if [ "$NO_CLAUDE" != 1 ]; then
  for d in "$SRC_CLAUDE"/claude-*/; do
    [ -f "$d/SKILL.md" ] || continue
    name="$(basename "$d")"
    if [ -n "$ONLY" ]; then case "$ONLY" in *",$name,"*) ;; *) continue ;; esac; fi
    claude_skills+=("$name")
  done
fi
if [ "$NO_HYBRID" != 1 ]; then
  for d in "$SRC_HYBRID"/hybrid-*/; do
    [ -f "$d/SKILL.md" ] || continue
    name="$(basename "$d")"
    if [ -n "$ONLY" ]; then case "$ONLY" in *",$name,"*) ;; *) continue ;; esac; fi
    hybrid_skills+=("$name")
  done
fi
[ "${#claude_skills[@]}" -gt 0 ] || [ "${#hybrid_skills[@]}" -gt 0 ] \
  || die "no skill matched (checked $SRC_CLAUDE and $SRC_HYBRID)"

is_plugin() { [ -f "$SRC_CLAUDE/$1/.claude-plugin/plugin.json" ]; }

# install_agent SRC DEST TOOL: fill __PLAN_TOOL__ with the installed plan_tool.py path
# (spelled exactly as plan_tool.py's qtool()/setup allow-rule expects), then write it,
# replacing any previous copy (no backup).
install_agent() {
  if [ "$DRY" -eq 1 ]; then echo "  [dry-run] agent $1 -> $2"; return 0; fi
  python3 - "$1" "$2" "$3" <<'PY' || die "could not install agent $2"
import os, shlex, sys
src, dest, tool = sys.argv[1:4]
with open(src, encoding="utf-8") as fh:
    text = fh.read().replace("__PLAN_TOOL__", "python3 " + shlex.quote(os.path.abspath(tool)))
name = os.path.basename(dest)
if os.path.exists(dest):
    with open(dest, encoding="utf-8") as fh:
        if fh.read() == text:
            print("  %s (unchanged)" % name)
            sys.exit(0)
    print("  %s (updated)" % name)
else:
    print("  %s" % name)
with open(dest, "w", encoding="utf-8") as fh:
    fh.write(text)
PY
}

clean_dest() { # rm -rf "$1": clean overwrite so removed files do not linger
  echo "  + skill $2"
  run rm -rf "$1"
  run mkdir -p "$1"
  if [ "$DRY" != 1 ]; then
    # cp, not a tar pipe: macOS tar adds com.apple.provenance xattrs the extracting side cannot write.
    cp -R "$3/." "$1/"
    find "$1" \( -name .DS_Store -o -name .idea -o -name __pycache__ -o -name '*.pyc' \) -prune -exec rm -rf {} +
    # Keep scripts executable regardless of how the source tree was checked out.
    find "$1" \( -path '*/scripts/*' -o -path '*/hooks/*' \) -type f \( -name '*.py' -o -name '*.sh' \) -exec chmod +x {} +
  fi
}

if [ "$UNINSTALL" = 1 ]; then
  echo "Uninstalling from $BASE$([ "$DRY" = 1 ] && echo '  (dry run)')"
  for s in ${claude_skills[@]+"${claude_skills[@]}"}; do
    [ -d "$SKILLS_DIR/$s" ] && { echo "  - skill $s"; run rm -rf "$SKILLS_DIR/$s"; }
    is_plugin "$s" && continue # plugin agents were never copied to AGENTS_DIR
    for a in "$SRC_CLAUDE/$s"/agents/claude-*.md; do
      [ -f "$a" ] || continue
      [ -f "$AGENTS_DIR/$(basename "$a")" ] && { echo "  - agent $(basename "$a")"; run rm -f "$AGENTS_DIR/$(basename "$a")"; }
    done
  done
  for s in ${hybrid_skills[@]+"${hybrid_skills[@]}"}; do
    [ -d "$SKILLS_DIR/$s" ] && { echo "  - skill $s"; run rm -rf "$SKILLS_DIR/$s"; }
    for a in "$SRC_HYBRID/$s"/agents/*.md; do
      [ -f "$a" ] || continue
      [ -f "$AGENTS_DIR/$(basename "$a")" ] && { echo "  - agent $(basename "$a")"; run rm -f "$AGENTS_DIR/$(basename "$a")"; }
    done
  done
  echo "Done. Restart Claude Code."
  exit 0
fi

command -v python3 >/dev/null 2>&1 || die "python3 not found"
if [ "${#hybrid_skills[@]}" -gt 0 ]; then
  command -v rsync >/dev/null 2>&1 || die "rsync not found (needed for hybrid skills)"
fi

echo "Claude dir: $BASE$([ "$DRY" = 1 ] && echo '  (dry run)')"
echo "Skills: ${claude_skills[@]+"${claude_skills[@]}"} ${hybrid_skills[@]+"${hybrid_skills[@]}"}"

if [ "$KEEP_OLD" != 1 ] && [ "$NO_CLAUDE" != 1 ]; then
  todo=()
  for s in $OLD_SKILLS; do [ -f "$SKILLS_DIR/$s/SKILL.md" ] && todo+=("$SKILLS_DIR/$s"); done
  for a in $OLD_AGENTS; do [ -f "$AGENTS_DIR/$a.md" ] && todo+=("$AGENTS_DIR/$a.md"); done
  if [ "${#todo[@]}" -gt 0 ]; then
    echo "Deleting old un-prefixed copies:"
    printf '  %s\n' "${todo[@]}"
    for p in "${todo[@]}"; do run rm -rf "$p"; done
  fi
fi

if [ "$CHECK" = 1 ] && [ "${#hybrid_skills[@]}" -gt 0 ]; then
  if command -v opencode >/dev/null 2>&1; then
    echo "opencode: $(opencode --version 2>/dev/null | head -1)"
  else
    echo "WARNING: the opencode CLI is not on PATH. Hybrid skills install, but hybrid and opencode modes stay unavailable"
    echo "         until opencode is installed and logged in (Claude-only mode still works)."
  fi
fi

run mkdir -p "$SKILLS_DIR" "$AGENTS_DIR"

echo "== claude skills (originals)"
for s in ${claude_skills[@]+"${claude_skills[@]}"}; do
  clean_dest "$SKILLS_DIR/$s" "$s" "$SRC_CLAUDE/$s"
  if is_plugin "$s"; then
    echo "  (plugin skill: agents and hooks load from the skill folder itself)"
    continue
  fi
  for a in "$SRC_CLAUDE/$s"/agents/claude-*.md; do
    [ -f "$a" ] || continue
    if grep -q '__PLAN_TOOL__' "$a"; then
      install_agent "$a" "$AGENTS_DIR/$(basename "$a")" "$SKILLS_DIR/$s/scripts/plan_tool.py"
    else
      echo "  + agent $(basename "$a")"
      [ "$DRY" = 1 ] || cp "$a" "$AGENTS_DIR/$(basename "$a")"
    fi
  done
done

echo "== hybrid skills"
for s in ${hybrid_skills[@]+"${hybrid_skills[@]}"}; do
  echo "  + skill $s"
  # rsync merge, never --delete: keeps the user's routing.json in the destination.
  run rsync -a --exclude __pycache__ --exclude .DS_Store --exclude '*.pyc' --exclude /routing.json \
    "$SRC_HYBRID/$s/" "$SKILLS_DIR/$s/"
  if [ "$DRY" != 1 ]; then
    find "$SKILLS_DIR/$s" \( -path '*/scripts/*' -o -path '*/hooks/*' \) -type f \( -name '*.py' -o -name '*.sh' \) -exec chmod +x {} +
  fi
  for a in "$SRC_HYBRID/$s"/agents/*.md; do
    [ -f "$a" ] || continue
    install_agent "$a" "$AGENTS_DIR/$(basename "$a")" "$SKILLS_DIR/$s/scripts/plan_tool.py"
  done
done
if [ -d "$SKILLS_DIR/hybrid" ]; then
  echo "  NOTE: $SKILLS_DIR/hybrid/ is an old nested copy; Claude Code does not load skills nested that deep."
  echo "        Remove it by hand once the flat install above works."
fi

if [ "$LEGACY" = 1 ]; then
  echo "== legacy agents (old ht-* names)"
  for f in "$AGENTS_DIR"/ht-*.md; do
    [ -f "$f" ] || continue
    run rm -f "$f"
    echo "  removed $(basename "$f")"
  done
fi

echo "== models"
if [ -z "$MODEL" ] && [ -z "$LITE" ]; then
  echo "  unchanged (pass --model provider/model#variant to set HYBRID_OPENCODE_STD in settings.json)"
elif [ "$DRY" = 1 ]; then
  echo "  [dry-run] would set${MODEL:+ HYBRID_OPENCODE_STD=$MODEL}${LITE:+ HYBRID_OPENCODE_LITE=$LITE} in $BASE/settings.json"
else
  python3 - "$BASE/settings.json" "$MODEL" "$LITE" <<'PY' || die "could not update settings.json"
import json, os, sys, tempfile

path, std, lite = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
except FileNotFoundError:
    data = {}
if not isinstance(data, dict):
    sys.exit("settings.json is not a JSON object; not touching it")
env = data.setdefault("env", {})
if not isinstance(env, dict):
    sys.exit('settings.json "env" is not an object; not touching it')
changed = False
for key, value in (("HYBRID_OPENCODE_STD", std), ("HYBRID_OPENCODE_LITE", lite)):
    if not value:
        continue
    if env.get(key):
        print("  %s already set to %s (kept)" % (key, env[key]))
    else:
        env[key] = value
        changed = True
        print("  %s=%s" % (key, value))
if changed:
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), prefix=".settings.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    print("  settings.json updated (restart Claude Code to pick up the env block)")
PY
fi

cat <<EOF

Installed. Next steps:
  1. Restart Claude Code (new agents and settings load at startup).
  2. Verify: /agents lists the claude-* and hybrid-* agents; the skills appear as /claude-<name> and /hybrid-<name>.
  3. Optional, once per repo: python3 $SKILLS_DIR/claude-dev-team-v3.2/scripts/devteam.py doctor --fix
     and python3 $SKILLS_DIR/claude-writing-plans-6.2/scripts/plan_tool.py setup --apply
     only matter if your concurrent-subagent cap is below 12 (Claude Code default is 20); they raise it to 16.
EOF
if [ -z "${HYBRID_OPENCODE_STD:-}" ] && [ -z "$MODEL" ] && ! python3 - "$BASE/settings.json" <<'PY' 2>/dev/null
import json, sys
env = json.load(open(sys.argv[1], encoding="utf-8")).get("env") or {}
sys.exit(0 if env.get("HYBRID_OPENCODE_STD") else 1)
PY
then
  echo "Next: set HYBRID_OPENCODE_STD (provider/model#variant) in the \"env\" block of $BASE/settings.json, or re-run with --model."
fi
