#!/usr/bin/env bash
# Install the hybrid skills into Claude Code.
#
#   skills  hybrid-*-v*/  ->  <claude dir>/skills/<same folder>/   (rsync, never --delete: keeps your routing.json)
#   agents  hybrid-*/agents/*.md  ->  <claude dir>/agents/          (names all start with "hybrid-"; __PLAN_TOOL__
#           is filled in with the installed plan_tool.py; a changed agent is kept as <name>.md.bak first)
#   models  HYBRID_OPENCODE_STD / _LITE  ->  "env" block of <claude dir>/settings.json (only with --model / --lite)
#
# Usage: ./install.sh [--dry-run] [--claude-dir DIR] [--model provider/model#variant] [--lite provider/model#variant]
#                     [--remove-legacy] [--skip-check] [-h]
#   --dry-run        print what would happen, change nothing
#   --claude-dir     Claude Code config dir (default: $CLAUDE_CONFIG_DIR or ~/.claude)
#   --model SPEC     set HYBRID_OPENCODE_STD in settings.json unless it is already set
#   --lite SPEC      set HYBRID_OPENCODE_LITE in settings.json unless it is already set (defaults to STD when unset)
#   --remove-legacy  delete agent files of the old "ht-*" names left by earlier installs
#   --skip-check     do not look for the opencode CLI
# Works with bash 3.2 (macOS) and needs only rsync and python3.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
DRY=0; MODEL=""; LITE=""; LEGACY=0; CHECK=1

usage() { sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; }
die() { echo "install.sh: $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --claude-dir) [ $# -ge 2 ] || die "--claude-dir needs a value"; CLAUDE_DIR="$2"; shift ;;
    --model) [ $# -ge 2 ] || die "--model needs a value"; MODEL="$2"; shift ;;
    --lite) [ $# -ge 2 ] || die "--lite needs a value"; LITE="$2"; shift ;;
    --remove-legacy) LEGACY=1 ;;
    --skip-check) CHECK=0 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
  shift
done

command -v rsync >/dev/null 2>&1 || die "rsync not found"
command -v python3 >/dev/null 2>&1 || die "python3 not found"
for spec in "$MODEL" "$LITE"; do
  if [ -n "$spec" ]; then
    printf '%s' "$spec" | grep -Eq '^[^/[:space:]]+/[^[:space:]#]+(#[^[:space:]#]+)?$' \
      || die "model spec must look like provider/model or provider/model#variant: $spec"
  fi
done

run() { if [ "$DRY" -eq 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }

# install_agent SRC DEST TOOL: fill __PLAN_TOOL__ exactly as plan_tool.py's qtool() spells it (its setup
# allow rule must match the hook command), back up a changed DEST, then write it.
install_agent() {
  if [ "$DRY" -eq 1 ]; then echo "[dry-run] install agent $1 -> $2"; return 0; fi
  python3 - "$1" "$2" "$3" <<'PY' || die "could not install agent $2"
import os, shlex, shutil, sys
src, dest, tool = sys.argv[1:4]
with open(src, encoding="utf-8") as fh:
    text = fh.read().replace("__PLAN_TOOL__", "python3 " + shlex.quote(os.path.abspath(tool)))
name = os.path.basename(dest)
if os.path.exists(dest):
    with open(dest, encoding="utf-8") as fh:
        if fh.read() == text:
            print("  %s (unchanged)" % name)
            sys.exit(0)
    shutil.copy2(dest, dest + ".bak")
    print("  %s (updated; previous copy kept as %s.bak)" % (name, name))
else:
    print("  %s" % name)
with open(dest, "w", encoding="utf-8") as fh:
    fh.write(text)
PY
}

SKILLS=""
for d in "$HERE"/hybrid-*/; do
  [ -f "${d}SKILL.md" ] && SKILLS="$SKILLS $(basename "$d")"
done
[ -n "$SKILLS" ] || die "no hybrid-* skill folders next to this script"

echo "Claude dir: $CLAUDE_DIR$([ "$DRY" -eq 1 ] && echo '  (dry run)')"

if [ "$CHECK" -eq 1 ]; then
  if command -v opencode >/dev/null 2>&1; then
    echo "opencode: $(opencode --version 2>/dev/null | head -1)"
  else
    echo "WARNING: the opencode CLI is not on PATH. The skills install, but hybrid and opencode modes stay unavailable"
    echo "         until opencode is installed and logged in (Claude-only mode still works)."
  fi
fi

echo "== skills"
run mkdir -p "$CLAUDE_DIR/skills"
for s in $SKILLS; do
  run rsync -a --exclude __pycache__ --exclude .DS_Store --exclude '*.pyc' --exclude /routing.json \
    "$HERE/$s/" "$CLAUDE_DIR/skills/$s/"
  echo "  $s"
done

if [ -d "$CLAUDE_DIR/skills/hybrid" ]; then
  echo "  NOTE: $CLAUDE_DIR/skills/hybrid/ is an old nested copy; Claude Code does not load skills nested that deep."
  echo "        Remove it by hand once the flat install above works."
fi
if [ "$CLAUDE_DIR" != "$HOME/.claude" ]; then
  echo "  NOTE: the hybrid-team agent hooks look for guard.py only under \$HOME/.claude/skills and <project>/.claude/skills;"
  echo "        with --claude-dir they enforce nothing until \`devteam doctor --fix\` pins them in each project."
fi

echo "== agents"
run mkdir -p "$CLAUDE_DIR/agents"
for s in $SKILLS; do
  for f in "$HERE/$s"/agents/*.md; do
    [ -f "$f" ] || continue
    install_agent "$f" "$CLAUDE_DIR/agents/$(basename "$f")" "$CLAUDE_DIR/skills/$s/scripts/plan_tool.py"
  done
done

if [ "$LEGACY" -eq 1 ]; then
  echo "== legacy agents (old ht-* names)"
  for f in "$CLAUDE_DIR"/agents/ht-*.md; do
    [ -f "$f" ] || continue
    run rm -f "$f"
    echo "  removed $(basename "$f")"
  done
fi

echo "== models"
if [ -z "$MODEL" ] && [ -z "$LITE" ]; then
  echo "  unchanged (pass --model provider/model#variant to set HYBRID_OPENCODE_STD in settings.json)"
elif [ "$DRY" -eq 1 ]; then
  echo "[dry-run] would set${MODEL:+ HYBRID_OPENCODE_STD=$MODEL}${LITE:+ HYBRID_OPENCODE_LITE=$LITE} in $CLAUDE_DIR/settings.json"
else
  python3 - "$CLAUDE_DIR/settings.json" "$MODEL" "$LITE" <<'PY' || die "could not update settings.json"
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

echo
echo "Done. Restart Claude Code, then use /hybrid-brainstorming, /hybrid-writing-plans, /hybrid-team or /hybrid-requirements-code-audit."
if [ -z "${HYBRID_OPENCODE_STD:-}" ] && [ -z "$MODEL" ] && ! python3 - "$CLAUDE_DIR/settings.json" <<'PY' 2>/dev/null
import json, sys
env = json.load(open(sys.argv[1], encoding="utf-8")).get("env") or {}
sys.exit(0 if env.get("HYBRID_OPENCODE_STD") else 1)
PY
then
  echo "Next: set HYBRID_OPENCODE_STD (provider/model#variant) in the \"env\" block of $CLAUDE_DIR/settings.json, or re-run with --model."
fi
