#!/bin/sh
# Install every z-* skill folder that has SKILL.md at its root into DeepSeek Harness (dsh).
#
#   skills    z-FOLDER/  ->  DSH_HOME/skills/z-FOLDER/   (copied as-is minus junk)
#
# dsh discovers skills in the user root under its home: the home is --home DIR when given,
# else $DSH_HOME, else $HOME/.dsh. A skill is a FOLDER/SKILL.md directory bundle at the top
# level of a scanned root; nested SKILL.md files are deliberately not discovered. dsh
# requires a kebab-case name and a non-empty description in the frontmatter; the preflight
# below rejects violations before the first copy.
#
# The harness itself is not installed here; see the harness README. Folders that are not
# z-* in the target are never touched. The script does not read or write any dsh config.
#
# Usage: sh install-dsh.sh [--home DIR] [--dry-run]
# In an interactive terminal the script waits for Enter before the window closes.
set -eu

HOME_DIR="${DSH_HOME:-${HOME:+$HOME/.dsh}}"
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
SKILLS_DIR="$HOME_DIR/skills"

# Discover installable skills: directories named z-* with SKILL.md at the root.
FOLDERS=$(
    for d in "$SCRIPT_DIR"/z-*; do
        [ -d "$d" ] || continue
        [ -f "$d/SKILL.md" ] || continue
        basename "$d"
    done | sort | tr '\n' ' '
)
FOLDERS=${FOLDERS%" "}
SKIPPED=$(
    for d in "$SCRIPT_DIR"/z-*; do
        [ -d "$d" ] || continue
        [ -f "$d/SKILL.md" ] && continue
        basename "$d"
    done | sort | tr '\n' ' '
)
SKIPPED=${SKIPPED%" "}
[ -n "$FOLDERS" ] || { echo "Error: no z-*/SKILL.md folders under $SCRIPT_DIR" >&2; exit 1; }
skill_n=0
for _folder in $FOLDERS; do
    skill_n=$((skill_n + 1))
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

# Read-only pre-flight. dsh drops a skill whose description is missing and requires a
# kebab-case name; a body over 100KB would be truncated when loaded.
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
        bad.append("%s: description is %d characters (dsh drops it above 1024)" % (folder, len(desc)))
    if len(text.encode("utf-8")) > 100 * 1024:
        bad.append("%s: SKILL.md is over 100KB" % folder)
    n = re.search(r"(?m)^name:[ \t]*(.+)$", fm)
    name = n.group(1).strip().strip("\"'") if n else ""
    if not name:
        bad.append("%s: no name in frontmatter" % folder)
    elif not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
        bad.append("%s: name %s is not kebab-case" % (folder, name))
for line in bad:
    print("Error: " + line, file=sys.stderr)
sys.exit(1 if bad else 0)
PY

echo "dsh skills dir: $SKILLS_DIR$([ "$DRY" -eq 1 ] && echo '  (dry run)')"
echo "== skills"
echo "    dest: $SKILLS_DIR/   (rm -rf then copy)"
run mkdir -p "$SKILLS_DIR"
skill_files=0
for folder in $FOLDERS; do
    src="$SCRIPT_DIR/$folder"
    [ -d "$src" ] || { echo "Error: $src not found" >&2; exit 1; }
    dest="$SKILLS_DIR/$folder"
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
    echo "  $dest/"
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

# Leftover installs under the old unprefixed (or -glm) folder names would load a second
# skill with a confusingly similar name next to the z- one.
STALE=""
for folder in $FOLDERS; do
    for old in "glm-${folder#z-}" "${folder#z-}" "${folder#z-}-glm"; do
        path="$SKILLS_DIR/$old"
        if [ -e "$path" ] || [ -L "$path" ]; then
            echo "WARN: stale: $path is an old install of $folder; the new install is $SKILLS_DIR/$folder"
            STALE="$STALE \"$path\""
        fi
    done
done
[ -z "$STALE" ] || echo "To remove the stale installs, run: rm -rf$STALE"

echo "== skipped"
if [ -n "$SKIPPED" ]; then
    for skip in $SKIPPED; do
        echo "    $SCRIPT_DIR/$skip/   (z-* folder with no SKILL.md at root; not installed)"
    done
fi

if [ "$DRY" -eq 1 ]; then
    echo
    echo "Dry run. Nothing written."
    exit 0
fi

cat <<MSG

Done. $skill_files files in $skill_n skill folders -> $SKILLS_DIR.
Skills load from the scanned roots when dsh starts; restart dsh to pick up changes.
MSG
