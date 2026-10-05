#!/bin/sh
# Install the six GLM skills into ZCode.
#
#   skills  <name>-glm/  ->  <home>/.zcode/skills/<name>/     (the -glm suffix is dropped; ZCode loads SKILL.md `name`)
#   agents  <skill>/agents/zcode/*.md, systematic-debugging's debug-worker and dev-team's agents
#           ->  <home>/.zcode/agents/   (rewritten to ZCode frontmatter; a changed file is kept as <name>.md.bak first)
#           plus plan-task-writer, written by plan_tool.py setup --harness zcode --apply
#
# Usage: sh install-zcode.sh [--home DIR] [--flash MODEL_ID] [--main MODEL_ID] [--dry-run]
#   --flash / --main  model ids written into the agents (default glm-5.3-flash / glm-5.3; ZCode has no haiku/sonnet aliases,
#                     so use your plan's exact id, e.g. account:zai-individual-coding-plan/GLM-5.3-Flash)
set -eu

HOME_DIR="${HOME:-}"
FLASH="glm-5.3-flash"
MAIN="glm-5.3"
DRY=0

while [ $# -gt 0 ]; do
    case "$1" in
        --home) [ $# -ge 2 ] || { echo "--home needs a value" >&2; exit 1; }; HOME_DIR="$2"; shift 2 ;;
        --flash) [ $# -ge 2 ] || { echo "--flash needs a value" >&2; exit 1; }; FLASH="$2"; shift 2 ;;
        --main) [ $# -ge 2 ] || { echo "--main needs a value" >&2; exit 1; }; MAIN="$2"; shift 2 ;;
        --dry-run) DRY=1; shift ;;
        *) echo "Usage: $0 [--home DIR] [--flash MODEL_ID] [--main MODEL_ID] [--dry-run]" >&2; exit 1 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$HOME_DIR/.zcode/skills"
AGENTS_DIR="$HOME_DIR/.zcode/agents"
FOLDERS="brainstorming-glm dev-team-glm doc-generator-glm requirements-code-audit-glm systematic-debugging-glm writing-plans-glm"

command -v python3 >/dev/null 2>&1 || { echo "python3 not found" >&2; exit 1; }
command -v tar >/dev/null 2>&1 || { echo "tar not found" >&2; exit 1; }

run() { if [ "$DRY" -eq 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }

# ZCode silently drops a skill whose description is over 1024 characters or whose body is over 100KB.
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

# convert SRC DEST: rewrite one agent file to ZCode frontmatter (real GLM ids, thoughtLevel, no Claude/OpenCode-only keys).
convert() {
    if [ "$DRY" -eq 1 ]; then echo "[dry-run] agent $1 -> $2"; return 0; fi
    python3 - "$1" "$2" "$FLASH" "$MAIN" <<'PY' || { echo "could not install agent $2" >&2; exit 1; }
import os, re, shutil, sys
src, dest, flash, main = sys.argv[1:5]
DROP = {"effort", "isolation", "memory", "omitClaudeMd", "hooks", "mode", "temperature", "steps", "permission", "variant"}
text = open(src, encoding="utf-8").read()
m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
if not m:
    sys.exit("no frontmatter in " + src)
blocks, cur = [], None  # (key, lines): a key starts at column 0, its continuation lines are indented or blank
for line in m.group(1).split("\n"):
    k = re.match(r"([A-Za-z][\w-]*):(.*)", line)
    if k:
        cur = [k.group(1), [line]]
        blocks.append(cur)
    elif cur:
        cur[1].append(line)
out, effort, has_level = [], None, False
for key, lines in blocks:
    val = lines[0].split(":", 1)[1].strip().strip("\"'")
    if key == "effort":
        effort = val
    if key == "thoughtLevel":
        has_level = True
    if key in DROP:
        continue
    if key == "model":
        val = {"haiku": flash, "sonnet": main, "opus": main, "glm-5.3-flash": flash, "glm-5.3": main}.get(val, val)
        lines = ["model: " + val]
    out.extend(lines)
if effort and not has_level:
    out.append("thoughtLevel: " + effort)
new = "---\n" + "\n".join(out) + "\n---\n" + m.group(2)
if os.path.exists(dest):
    if open(dest, encoding="utf-8").read() == new:
        print("  %s (unchanged)" % os.path.basename(dest))
        sys.exit(0)
    if os.path.abspath(src) != os.path.abspath(dest):
        shutil.copy2(dest, dest + ".bak")
    print("  %s (updated%s)" % (os.path.basename(dest), "" if os.path.abspath(src) == os.path.abspath(dest) else "; previous copy kept as %s.bak" % os.path.basename(dest)))
else:
    print("  " + os.path.basename(dest))
with open(dest, "w", encoding="utf-8") as fh:
    fh.write(new)
PY
}

echo "ZCode dir: $HOME_DIR/.zcode$([ "$DRY" -eq 1 ] && echo '  (dry run)')"
echo "== skills"
run mkdir -p "$SKILLS_DIR"
for folder in $FOLDERS; do
    src="$SCRIPT_DIR/$folder"
    [ -d "$src" ] || { echo "Error: $src not found" >&2; exit 1; }
    name="${folder%-glm}"
    run rm -rf "$SKILLS_DIR/$name"
    run mkdir -p "$SKILLS_DIR/$name"
    if [ "$DRY" -eq 0 ]; then
        tar -C "$src" --exclude=opencode --exclude=.DS_Store --exclude=.idea --exclude=__pycache__ --exclude='*.pyc' -cf - . \
            | tar -C "$SKILLS_DIR/$name" -xf -
    fi
    echo "  $name"
done

echo "== agents"
run mkdir -p "$AGENTS_DIR"
for f in "$SCRIPT_DIR"/requirements-code-audit-glm/agents/zcode/*.md "$SCRIPT_DIR"/doc-generator-glm/agents/zcode/*.md \
         "$SCRIPT_DIR"/systematic-debugging-glm/agents/debug-worker.md "$SCRIPT_DIR"/dev-team-glm/agents/*.md; do
    [ -f "$f" ] && convert "$f" "$AGENTS_DIR/$(basename "$f")"
done
if [ "$DRY" -eq 1 ]; then
    echo "[dry-run] plan-task-writer via plan_tool.py setup --harness zcode --apply"
else
    HOME="$HOME_DIR" python3 "$SKILLS_DIR/writing-plans/scripts/plan_tool.py" setup --harness zcode --apply >/dev/null
    convert "$AGENTS_DIR/plan-task-writer.md" "$AGENTS_DIR/plan-task-writer.md"
fi

# A leftover <name>-glm folder carries the same skill name as the one just installed.
STALE=""
for folder in $FOLDERS; do
    path="$SKILLS_DIR/$folder"
    if [ -e "$path" ] || [ -L "$path" ]; then
        echo "WARN: stale: $path is an old install of ${folder%-glm}; ZCode would load two skills with the same name"
        STALE="$STALE \"$path\""
    fi
done
[ -z "$STALE" ] || echo "To remove the stale installs, run: rm -rf$STALE"

cat <<MSG

Done. Restart ZCode, then invoke a skill with \$brainstorming, \$dev-team, \$doc-generator, \$requirements-code-audit,
\$systematic-debugging or \$writing-plans.
Next: export ZAI_API_KEY (GLM Coding Plan key) and check it with
  python3 $SKILLS_DIR/writing-plans/scripts/plan_tool.py doctor --ping
The Z.ai plan allows 8 concurrent API calls: the skills cap their fan-out at 8.
dev-team needs hook-based guards that ZCode does not have, so its footprint and frozen-test rules are prompt-enforced only.
MSG
