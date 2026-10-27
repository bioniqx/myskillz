#!/bin/sh
# Install every glm-* skill folder that has SKILL.md at its root, plus those
# skills' subagents and slash commands, into ZCode.
#
#   skills    glm-<name>/  ->  <home>/.zcode/skills/glm-<name>/   (copied as-is; the glm- prefix
#             keeps them distinct from the Claude-tuned originals; ZCode loads SKILL.md `name`)
#             Folders matching glm-* without a root SKILL.md are skipped (they are not
#             ZCode skill packs; glm-viral-video-studio has its own installer).
#   agents    <skill>/agents/*.md across the discovered skills
#             ->  <home>/.zcode/agents/   (copied verbatim; existing files are overwritten, no backup)
#   commands  <skill>/commands/*.md
#             ->  <home>/.zcode/commands/ and the copy inside the installed skill
#             {{SKILL_DIR}} is replaced with the installed skill directory. ZCode only
#             discovers commands under ~/.zcode/commands (not under a skill directory).
#
# The agent files already carry final ZCode frontmatter (real GLM model ids and
# thoughtLevel; maxTurns where the file sets a turn budget), so this script only
# copies agents — it never rewrites them. It does not touch ~/.zcode/cli/config.json.
# glm-dev-team's guard hooks are opt-in afterwards:
#   python3 <skills>/glm-dev-team/scripts/devteam.py doctor --harness zcode --fix
#
# A manifest at <home>/.zcode/glm-skills-manifest.txt lists the agents and commands
# this installer wrote. A later run deletes only those entries that left the repo.
# Anything not in the manifest is left alone.
#
# Usage: sh install-zcode.sh [--home DIR] [--dry-run]
# In an interactive terminal the script waits for Enter before the window closes.
set -eu

HOME_DIR="${HOME:-}"
DRY=0

while [ $# -gt 0 ]; do
    case "$1" in
        --home) [ $# -ge 2 ] || { echo "Error: --home needs a value" >&2; exit 1; }; HOME_DIR="$2"; shift 2 ;;
        --dry-run) DRY=1; shift ;;
        *) echo "Usage: $0 [--home DIR] [--dry-run]" >&2; exit 1 ;;
    esac
done

[ -n "$HOME_DIR" ] || { echo "Error: HOME is unset; pass --home DIR" >&2; exit 1; }

pause() {
    [ -t 0 ] && [ -t 1 ] || return 0
    printf "Press Enter to close. "
    read -r _ || true
}
trap pause EXIT

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$HOME_DIR/.zcode/skills"
AGENTS_DIR="$HOME_DIR/.zcode/agents"
COMMANDS_DIR="$HOME_DIR/.zcode/commands"
MANIFEST="$HOME_DIR/.zcode/glm-skills-manifest.txt"

command -v python3 >/dev/null 2>&1 || { echo "Error: python3 not found" >&2; exit 1; }

# Discover installable skills: directories named glm-* with SKILL.md at the root.
FOLDERS=$(
    for d in "$SCRIPT_DIR"/glm-*; do
        [ -d "$d" ] || continue
        [ -f "$d/SKILL.md" ] || continue
        basename "$d"
    done | sort | tr '\n' ' '
)
FOLDERS=${FOLDERS%" "}
SKIPPED=$(
    for d in "$SCRIPT_DIR"/glm-*; do
        [ -d "$d" ] || continue
        [ -f "$d/SKILL.md" ] && continue
        basename "$d"
    done | sort | tr '\n' ' '
)
SKIPPED=${SKIPPED%" "}
[ -n "$FOLDERS" ] || { echo "Error: no glm-*/SKILL.md folders under $SCRIPT_DIR" >&2; exit 1; }
skill_n=0
for _folder in $FOLDERS; do
    skill_n=$((skill_n + 1))
done
invoke=""
inv_sep=""
for _folder in $FOLDERS; do
    invoke="${invoke}${inv_sep}\$${_folder}"
    inv_sep=", "
done

run() { if [ "$DRY" -eq 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }

# Print relative file paths under root, skipping the same junk the copy step deletes.
list_rel_files() {
    python3 - "$1" <<'PY'
import os, sys
root = sys.argv[1]
skip_dir = {"opencode", ".idea", "__pycache__"}
out = []
for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames if d not in skip_dir]
    for fn in filenames:
        if fn == ".DS_Store" or fn.endswith(".pyc"):
            continue
        rel = os.path.relpath(os.path.join(dirpath, fn), root)
        out.append(rel.replace("\\", "/"))
for rel in sorted(out):
    print(rel)
PY
}

write_command() {
    src=$1
    dest=$2
    skill=$3
    if [ "$DRY" -eq 1 ]; then
        echo "[dry-run] command $(basename "$src") -> $dest"
        return 0
    fi
    python3 - "$src" "$dest" "$skill" <<'PY'
import os, sys
src, dest, skill = sys.argv[1:]
text = open(src, encoding="utf-8").read().replace("{{SKILL_DIR}}", skill)
os.makedirs(os.path.dirname(dest), exist_ok=True)
with open(dest, "w", encoding="utf-8") as fh:
    fh.write(text)
PY
}

# Read-only pre-flight. ZCode drops a skill whose name or description is missing,
# or whose description is over 1024 characters. A body over 100KB is truncated
# when loaded. thoughtLevel is ignored unless the agent also pins a model id.
# A command that contains a dynamic shell line is rejected by ZCode.
python3 - "$SCRIPT_DIR" $FOLDERS <<'PY' || exit 1
import os, re, sys
root, bad = sys.argv[1], []
folders = sys.argv[2:]
agents_seen, commands_seen, agent_n = {}, {}, 0
for folder in folders:
    path = os.path.join(root, folder, "SKILL.md")
    if not os.path.isfile(path):
        bad.append("%s: SKILL.md not found" % folder)
        continue
    text = open(path, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    fm = m.group(1) if m else ""
    nm = re.search(r"(?m)^name:[ \t]*[\"']?([^\"'\n]+?)[\"']?[ \t]*$", fm)
    if not nm or not nm.group(1).strip():
        bad.append("%s: frontmatter name is missing (ZCode drops the skill)" % folder)
    elif nm.group(1).strip() != folder:
        bad.append("%s: frontmatter name is %s (must equal the folder)" % (folder, nm.group(1).strip()))
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
    agents = os.path.join(root, folder, "agents")
    if os.path.isdir(agents):
        for fn in sorted(os.listdir(agents)):
            if not fn.endswith(".md"):
                continue
            agent_n += 1
            if fn in agents_seen:
                bad.append("duplicate agent %s in %s and %s" % (fn, agents_seen[fn], folder))
            agents_seen[fn] = folder
            afm = open(os.path.join(agents, fn), encoding="utf-8").read().split("\n---\n", 1)[0]
            if not re.search(r'(?m)^model:[ \t]*"?account:zai-', afm):
                bad.append("%s: %s has no model id (ZCode ignores thoughtLevel without one)" % (folder, fn))
            if not re.search(r"(?m)^thoughtLevel:[ \t]*(low|high|max)[ \t]*$", afm):
                bad.append("%s: %s has no thoughtLevel low|high|max" % (folder, fn))
    commands = os.path.join(root, folder, "commands")
    if os.path.isdir(commands):
        for fn in sorted(os.listdir(commands)):
            if not fn.endswith(".md"):
                continue
            if not re.match(r"^[a-z0-9][a-z0-9_:-]{0,63}\.md$", fn):
                bad.append("%s: command name %s is not a ZCode command name" % (folder, fn))
            if fn in commands_seen:
                bad.append("duplicate command %s in %s and %s" % (fn, commands_seen[fn], folder))
            commands_seen[fn] = folder
            body = open(os.path.join(commands, fn), encoding="utf-8").read()
            if "!`" in body or re.search(r"(?m)^[ \t]*!", body):
                bad.append("%s: %s contains a dynamic shell line ZCode rejects" % (folder, fn))
if agent_n == 0:
    bad.append("no agents/*.md files found under %s" % root)
for line in bad:
    print("Error: " + line, file=sys.stderr)
sys.exit(1 if bad else 0)
PY

echo "ZCode dir: $HOME_DIR/.zcode$([ "$DRY" -eq 1 ] && echo '  (dry run)')"
echo "== skills"
echo "    dest: $SKILLS_DIR/<name>/   (rm -rf then copy; invoke \$<name>)"
run mkdir -p "$SKILLS_DIR"
skill_files=0
for folder in $FOLDERS; do
    src="$SCRIPT_DIR/$folder"
    [ -d "$src" ] || { echo "Error: $src not found" >&2; exit 1; }
    name="$folder"
    dest="$SKILLS_DIR/$name"
    run rm -rf "$dest"
    run mkdir -p "$dest"
    if [ "$DRY" -eq 0 ]; then
        # cp, not a tar pipe: macOS tar adds com.apple.provenance xattrs the extracting side cannot write.
        cp -R "$src/." "$dest/"
        find "$dest" \( -name opencode -o -name .DS_Store -o -name .idea -o -name __pycache__ -o -name '*.pyc' \) -prune -exec rm -rf {} +
        tree="$dest"
    else
        tree="$src"
    fi
    n=0
    echo "  $dest/   invoke \$$name"
    while IFS= read -r rel; do
        [ -n "$rel" ] || continue
        echo "    $rel"
        n=$((n + 1))
    done <<EOF
$(list_rel_files "$tree")
EOF
    echo "    ($n files)"
    skill_files=$((skill_files + n))
done
echo "  $skill_files files in $skill_n skill folders -> $SKILLS_DIR"

echo "== agents"
echo "    dest: $AGENTS_DIR/<name>.md   (overwrite, no backup; Settings -> Subagents)"
run mkdir -p "$AGENTS_DIR"
count=0
for folder in $FOLDERS; do
    for f in "$SCRIPT_DIR/$folder/agents/"*.md; do
        [ -f "$f" ] || continue
        count=$((count + 1))
        base=$(basename "$f")
        run cp "$f" "$AGENTS_DIR/$base"
        echo "    $folder/agents/$base  ->  $AGENTS_DIR/$base"
    done
done
[ "$count" -gt 0 ] || { echo "Error: no agents/*.md files found under $SCRIPT_DIR" >&2; exit 1; }
echo "  $count agent files -> $AGENTS_DIR"

echo "== commands"
echo "    dest: $COMMANDS_DIR/<name>.md   (ZCode slash menu; {{SKILL_DIR}} filled in)"
run mkdir -p "$COMMANDS_DIR"
ccount=0
slash=""
slash_sep=""
for folder in $FOLDERS; do
    for f in "$SCRIPT_DIR/$folder/commands/"*.md; do
        [ -f "$f" ] || continue
        ccount=$((ccount + 1))
        base=$(basename "$f")
        write_command "$f" "$COMMANDS_DIR/$base" "$SKILLS_DIR/$folder"
        if [ "$DRY" -eq 0 ]; then
            write_command "$f" "$SKILLS_DIR/$folder/commands/$base" "$SKILLS_DIR/$folder"
        fi
        echo "    $folder/commands/$base  ->  $COMMANDS_DIR/$base   /${base%.md}"
        echo "    $folder/commands/$base  ->  $SKILLS_DIR/$folder/commands/$base   ({{SKILL_DIR}} filled)"
        slash="${slash}${slash_sep}/${base%.md}"
        slash_sep=", "
    done
done
echo "  $ccount command files -> $COMMANDS_DIR"
echo "== skipped"
echo "    $HOME_DIR/.zcode/cli/config.json   (guard hooks stay opt-in: doctor --harness zcode --fix)"
if [ -n "$SKIPPED" ]; then
    for skip in $SKIPPED; do
        echo "    $SCRIPT_DIR/$skip/   (glm-* folder with no SKILL.md at root; not installed)"
    done
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

NEWLIST=$(mktemp)
trap 'rm -f "$NEWLIST"; pause' EXIT
: > "$NEWLIST"
for folder in $FOLDERS; do
    for f in "$SCRIPT_DIR/$folder/agents/"*.md "$SCRIPT_DIR/$folder/commands/"*.md; do
        [ -f "$f" ] || continue
        case "$f" in
            */agents/*) echo "agents/$(basename "$f")" >> "$NEWLIST" ;;
            */commands/*) echo "commands/$(basename "$f")" >> "$NEWLIST" ;;
        esac
    done
done
python3 - "$MANIFEST" "$NEWLIST" "$HOME_DIR/.zcode" "$DRY" <<'PY'
import os, re, sys
manifest, newlist, zroot, dry = sys.argv[1:5]
dry = dry == "1"
name_re = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}\.md$")

def ok(rel):
    parts = rel.split("/")
    if len(parts) != 2 or ".." in parts:
        return False
    kind, name = parts
    return kind in ("agents", "commands") and name_re.match(name) is not None

def dest_of(rel):
    root = os.path.realpath(zroot)
    dest = os.path.realpath(os.path.join(root, rel))
    parent = os.path.realpath(os.path.join(root, rel.split("/")[0]))
    if os.path.commonpath([root, dest]) != root or os.path.commonpath([parent, dest]) != parent:
        sys.stderr.write("Error: refusing to remove %s\n" % rel)
        sys.exit(1)
    return os.path.join(root, rel)

new = []
for line in open(newlist, encoding="utf-8"):
    rel = line.strip()
    if not rel:
        continue
    if not ok(rel):
        sys.stderr.write("Error: bad manifest entry %s\n" % rel)
        sys.exit(1)
    new.append(rel)
new_set = set(new)
old = []
if os.path.isfile(manifest):
    for line in open(manifest, encoding="utf-8"):
        rel = line.strip()
        if rel:
            old.append(rel)
for rel in old:
    if rel in new_set:
        continue
    if not ok(rel):
        sys.stderr.write("Error: bad old manifest entry %s\n" % rel)
        sys.exit(1)
    dest = dest_of(rel)
    if dry:
        print("would remove: " + dest)
        continue
    if os.path.lexists(dest):
        os.remove(dest)
        print("removed: " + dest)
if not dry:
    os.makedirs(os.path.dirname(manifest), exist_ok=True)
    with open(manifest, "w", encoding="utf-8") as fh:
        for rel in sorted(new_set):
            fh.write(rel + "\n")
PY

if [ "$DRY" -eq 1 ]; then
    echo
    echo "Dry run. Nothing written."
    exit 0
fi

if [ -z "$slash" ]; then
    slash_line="No slash commands in the discovered skills."
else
    slash_line="Slash commands are $slash, installed under ~/.zcode/commands with the skill path filled in."
fi
devteam_block=""
case " $FOLDERS " in
    *" glm-dev-team "*)
        devteam_block="
glm-dev-team guard hooks are NOT configured by this installer; they are opt-in:
  python3 $SKILLS_DIR/glm-dev-team/scripts/devteam.py doctor --harness zcode --fix
That also re-verifies the six glm-dev-team agents against their source files and merges the guard
hooks (type: process, hooks.enabled: true, commands pointing at the installed guard.py) into
~/.zcode/cli/config.json — a key-preserving merge that rewrites in place: a re-run is a no-op, and
every user key already in the file survives. Disable with hooks.enabled=false in the same file."
        ;;
esac
plans_block=""
case " $FOLDERS " in
    *" glm-writing-plans "*)
        plans_block="
Next: export ZAI_API_KEY (GLM Coding Plan key) and check it with
  python3 $SKILLS_DIR/glm-writing-plans/scripts/plan_tool.py doctor --ping"
        ;;
esac

cat <<MSG

Done. Start a NEW ZCode session to load the installed skills, agents and commands (a restart is not enough), then invoke a skill with $invoke.
$slash_line
The agents were copied verbatim from the skills' agents/*.md: each file pins its model id and thoughtLevel (ZCode honors thoughtLevel only together with a model id). Nothing in the agent files was rewritten.$devteam_block$plans_block
The Z.ai plan allows 8 concurrent API calls: the skills cap their fan-out at 8 (dev-team opens all 8 by default, tier api).
A frontmatter description over 1024 characters makes ZCode drop the whole skill; a body over 100KB is truncated when loaded, not dropped.
MSG
