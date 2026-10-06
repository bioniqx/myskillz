#!/bin/sh
# Install the eight GLM skills into ZCode.
#
#   skills  glm-<name>/  ->  <home>/.zcode/skills/glm-<name>/     (installed as-is; the glm- prefix keeps them
#           distinct from the Claude-tuned originals; ZCode loads SKILL.md `name`)
#   agents  <skill>/agents/zcode/*.md and glm-systematic-debugging's glm-debug-worker
#           ->  <home>/.zcode/agents/   (rewritten to ZCode frontmatter; a changed file is kept as <name>.md.bak first)
#           glm-dev-team's seven ZCode agents (five file agents plus rendered glm-programmer-lite and
#           glm-programmer-strong) via devteam.py doctor --harness zcode --fix, which also merges the
#           guard hooks into ~/.zcode/cli/config.json; plus glm-plan-task-writer, written by
#           plan_tool.py setup --harness zcode --apply
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
FOLDERS="glm-brainstorming glm-dev-team glm-doc-generator glm-git-diff-summary glm-idea-to-spec glm-requirements-code-audit glm-systematic-debugging glm-writing-plans"

command -v python3 >/dev/null 2>&1 || { echo "python3 not found" >&2; exit 1; }
command -v tar >/dev/null 2>&1 || { echo "tar not found" >&2; exit 1; }

run() { if [ "$DRY" -eq 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }

# ZCode drops a skill whose description is over 1024 characters; a body over 100KB is truncated when loaded.
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

# convert SRC DEST [LEVEL]: rewrite one agent file to ZCode frontmatter (real GLM ids, thoughtLevel,
# steps: N -> maxTurns: N and omitClaudeMd: true -> injectAgentsMd: false instead of dropping them,
# drop permissionMode and the other Claude/OpenCode-only keys, keep background; LEVEL is a thoughtLevel
# applied only when the source has neither thoughtLevel nor effort).
convert() {
    if [ "$DRY" -eq 1 ]; then echo "[dry-run] agent $1 -> $2"; return 0; fi
    python3 - "$1" "$2" "$FLASH" "$MAIN" "${3:-}" <<'PY' || { echo "could not install agent $2" >&2; exit 1; }
import os, re, shutil, sys
src, dest, flash, main, level = sys.argv[1:6]
DROP = {"effort", "isolation", "memory", "hooks", "mode", "temperature", "permission", "permissionMode", "variant"}
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
    if key == "steps":
        out.append("maxTurns: " + val)
        continue
    if key == "omitClaudeMd":
        out.append("injectAgentsMd: " + ("false" if val == "true" else "true"))
        continue
    if key == "model":
        val = {"haiku": flash, "sonnet": main, "opus": main, "glm-5.3-flash": flash, "glm-5.3": main}.get(val, val)
        lines = ["model: " + val]
    out.extend(lines)
if not has_level:
    if effort:
        out.append("thoughtLevel: " + effort)
    elif level:
        out.append("thoughtLevel: " + level)
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
for f in "$SCRIPT_DIR"/glm-requirements-code-audit/agents/zcode/*.md "$SCRIPT_DIR"/glm-doc-generator/agents/zcode/*.md; do
    [ -f "$f" ] && convert "$f" "$AGENTS_DIR/$(basename "$f")"
done
# glm-debug-worker is a mechanical worker; it never pays for max thinking.
[ -f "$SCRIPT_DIR/glm-systematic-debugging/agents/glm-debug-worker.md" ] && \
    convert "$SCRIPT_DIR/glm-systematic-debugging/agents/glm-debug-worker.md" "$AGENTS_DIR/glm-debug-worker.md" low
if [ "$DRY" -eq 1 ]; then
    echo "[dry-run] glm-plan-task-writer via plan_tool.py setup --harness zcode --apply"
    echo "[dry-run] glm-dev-team zcode agents via devteam.py doctor --harness zcode --fix --flash $FLASH --main $MAIN"
else
    HOME="$HOME_DIR" python3 "$SKILLS_DIR/glm-writing-plans/scripts/plan_tool.py" setup --harness zcode --apply >/dev/null
    convert "$AGENTS_DIR/glm-plan-task-writer.md" "$AGENTS_DIR/glm-plan-task-writer.md"
    # The seven glm-dev-team ZCode agents are delegated to the engine's doctor subcommand (cmd_doctor
    # in devteam.py routes to def doctor_zcode(a, root):), same pattern as the plan_tool.py setup
    # delegation above: the doctor converts the five file agents (glm-team-leader, glm-code-reviewer,
    # glm-investigator, glm-spot-reviewer, glm-programmer.md), renders glm-programmer-lite and
    # glm-programmer-strong via def render_agent_zcode(agents_src, name, flash, main) -> str:,
    # installs all seven into ~/.zcode/agents/, and merges the guard hooks into
    # ~/.zcode/cli/config.json. --flash/--main pass through, so a custom plan id reaches the agents.
    HOME="$HOME_DIR" python3 "$SKILLS_DIR/glm-dev-team/scripts/devteam.py" doctor --harness zcode --fix --flash "$FLASH" --main "$MAIN" >/dev/null
fi

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
Next: export ZAI_API_KEY (GLM Coding Plan key) and check it with
  python3 $SKILLS_DIR/glm-writing-plans/scripts/plan_tool.py doctor --ping
The Z.ai plan allows 8 concurrent API calls: the skills cap their fan-out at 8 (default width 6).
glm-dev-team guards (frozen tests, footprint) are ZCode hooks on Write|Edit and Bash tool events.
The install above already ran
  python3 $SKILLS_DIR/glm-dev-team/scripts/devteam.py doctor --harness zcode --fix
which installs the seven glm-dev-team agents into ~/.zcode/agents/ and merges the guard hooks
(type: process, hooks.enabled: true, commands pointing at the installed skill's guard.py) into
~/.zcode/cli/config.json — a key-preserving merge: .bak before rewrite, a re-run is a no-op, and
every user key already in the file survives.
A frontmatter description over 1024 characters makes ZCode drop the whole skill; a body over 100KB is truncated when loaded, not dropped.
MSG
