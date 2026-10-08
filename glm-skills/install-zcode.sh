#!/bin/sh
# Install the eight GLM skills and all of their subagents into ZCode.
#
#   skills  glm-<name>/  ->  <home>/.zcode/skills/glm-<name>/     (copied as-is; the glm- prefix keeps them
#           distinct from the Claude-tuned originals; ZCode loads SKILL.md `name`)
#   agents  <skill>/agents/*.md across all eight skills
#           ->  <home>/.zcode/agents/   (copied verbatim; existing files are overwritten, no backup)
#
# The agent files already carry final ZCode frontmatter (real GLM model ids,
# thoughtLevel, maxTurns), so this script only copies — it never rewrites
# anything and it does not touch ~/.zcode/cli/config.json. glm-dev-team's
# guard hooks are opt-in afterwards:
#   python3 <skills>/glm-dev-team/scripts/devteam.py doctor --harness zcode --fix
#
# Usage: sh install-zcode.sh [--home DIR] [--dry-run]
set -eu

HOME_DIR="${HOME:-}"
DRY=0

while [ $# -gt 0 ]; do
    case "$1" in
        --home) [ $# -ge 2 ] || { echo "--home needs a value" >&2; exit 1; }; HOME_DIR="$2"; shift 2 ;;
        --dry-run) DRY=1; shift ;;
        *) echo "Usage: $0 [--home DIR] [--dry-run]" >&2; exit 1 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$HOME_DIR/.zcode/skills"
AGENTS_DIR="$HOME_DIR/.zcode/agents"
FOLDERS="glm-brainstorming glm-dev-team glm-doc-generator glm-git-diff-summary glm-idea-to-spec glm-requirements-code-audit glm-systematic-debugging glm-writing-plans"

command -v python3 >/dev/null 2>&1 || { echo "python3 not found" >&2; exit 1; }

run() { if [ "$DRY" -eq 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }

# Read-only pre-flight: ZCode drops a skill whose description is over 1024
# characters; a body over 100KB is truncated when loaded.
python3 - "$SCRIPT_DIR" $FOLDERS <<'PY' || exit 1
import os, re, sys
root, bad = sys.argv[1], []
for folder in sys.argv[2:]:
    path = os.path.join(root, folder, "SKILL.md")
    if not os.path.isfile(path):
        bad.append("%s: SKILL.md not found" % folder)
        continue
    text = open(path, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    fm = m.group(1) if m else ""
    d = re.search(r"^description:[ \t]*(.*?)(?=^\S|\Z)", fm, re.S | re.M)
    desc = " ".join(l.strip() for l in d.group(1).splitlines()) if d else ""
    head, _, rest = desc.partition(" ")
    if head in (">-", ">", "|-", "|"):
        desc = rest
    if not desc:
        bad.append("%s: no description" % folder)
    elif len(desc.strip("\"'")) > 1024:
        bad.append("%s: description is %d characters (ZCode drops it above 1024)" % (folder, len(desc)))
    if len(text.encode("utf-8")) > 100 * 1024:
        bad.append("%s: SKILL.md is over 100KB" % folder)
for line in bad:
    print("Error: " + line, file=sys.stderr)
sys.exit(1 if bad else 0)
PY

echo "ZCode dir: $HOME_DIR/.zcode$([ "$DRY" -eq 1 ] && echo '  (dry run)')"
echo "== skills"
run mkdir -p "$SKILLS_DIR"
for folder in $FOLDERS; do
    src="$SCRIPT_DIR/$folder"
    [ -d "$src" ] || { echo "Error: $src not found" >&2; exit 1; }
    name="$folder"
    run rm -rf "$SKILLS_DIR/$name"
    run mkdir -p "$SKILLS_DIR/$name"
    if [ "$DRY" -eq 0 ]; then
        # cp, not a tar pipe: macOS tar adds com.apple.provenance xattrs the extracting side cannot write.
        cp -R "$src/." "$SKILLS_DIR/$name/"
        find "$SKILLS_DIR/$name" \( -name opencode -o -name .DS_Store -o -name .idea -o -name __pycache__ -o -name '*.pyc' \) -prune -exec rm -rf {} +
    fi
    echo "  $name"
done

echo "== agents"
run mkdir -p "$AGENTS_DIR"
count=0
for f in "$SCRIPT_DIR"/*/agents/*.md; do
    [ -f "$f" ] || continue
    count=$((count + 1))
    run cp "$f" "$AGENTS_DIR/$(basename "$f")"
done
[ "$count" -gt 0 ] || { echo "Error: no agents/*/agent .md files found under $SCRIPT_DIR" >&2; exit 1; }
echo "  $count agent files -> $AGENTS_DIR"

# Leftover installs under the old unprefixed (or *-glm) folder names would
# load a second skill with a confusingly similar name next to the glm- one.
STALE=""
for folder in $FOLDERS; do
    for old in "${folder#glm-}" "${folder#glm-}-glm"; do
        path="$SKILLS_DIR/$old"
        if [ -e "$path" ] || [ -L "$path" ]; then
            echo "WARN: stale: $path is an old install of $folder; the new install is $SKILLS_DIR/$folder"
            STALE="$STALE \"$path\""
        fi
    done
done
[ -z "$STALE" ] || echo "To remove the stale installs, run: rm -rf$STALE"

cat <<MSG

Done. Start a NEW ZCode session to load the installed skills and agents (a restart is not enough), then invoke a skill with \$glm-brainstorming, \$glm-dev-team, \$glm-doc-generator, \$glm-git-diff-summary or
\$glm-idea-to-spec, \$glm-requirements-code-audit, \$glm-systematic-debugging, \$glm-writing-plans.
The agents were copied verbatim from the skills' agents/*.md: their frontmatter (real GLM model ids,
thoughtLevel, maxTurns) is the single source of truth — nothing was rewritten.
glm-dev-team guard hooks are NOT configured by this installer; they are opt-in:
  python3 $SKILLS_DIR/glm-dev-team/scripts/devteam.py doctor --harness zcode --fix
That also re-verifies the seven glm-dev-team agents against their source files and merges the guard
hooks (type: process, hooks.enabled: true, commands pointing at the installed guard.py) into
~/.zcode/cli/config.json — a key-preserving merge that rewrites in place: a re-run is a no-op, and
every user key already in the file survives. Disable with hooks.enabled=false in the same file.
Next: export ZAI_API_KEY (GLM Coding Plan key) and check it with
  python3 $SKILLS_DIR/glm-writing-plans/scripts/plan_tool.py doctor --ping
The Z.ai plan allows 8 concurrent API calls: the skills cap their fan-out at 8 (dev-team opens all 8 by default, tier api).
A frontmatter description over 1024 characters makes ZCode drop the whole skill; a body over 100KB is truncated when loaded, not dropped.
MSG
