#!/bin/sh
# Install every oc-* skill into OpenCode v2.
set -eu

HOME_DIR="${HOME:-}"

while [ $# -gt 0 ]; do
    case "$1" in
        --home)
            [ $# -ge 2 ] || { echo "Usage: $0 [--home DIR]" >&2; exit 1; }
            HOME_DIR="$2"
            shift 2
            ;;
        *)
            echo "Usage: $0 [--home DIR]" >&2
            exit 1
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HARNESS="$SCRIPT_DIR/_shared/oc_harness.py"

MAJOR="$(python3 "$HARNESS" detect || true)"
if [ "$MAJOR" != "2" ]; then
    echo "OpenCode v2 required (detected major: ${MAJOR:-none})" >&2
    exit 1
fi

# Every oc-*/ folder next to this script that carries a SKILL.md is a skill to install.
SKILLS=""
for skill_path in "$SCRIPT_DIR"/oc-*/; do
    [ -d "$skill_path" ] || continue
    skill="$(basename "$skill_path")"
    if [ ! -f "$skill_path/SKILL.md" ]; then
        echo "WARN: skipping $skill: no SKILL.md" >&2
        continue
    fi
    SKILLS="$SKILLS $skill"
    python3 "$HARNESS" install "${skill_path%/}" 2 "$HOME_DIR"
done
if [ -z "$SKILLS" ]; then
    echo "Error: no oc-* skill folder found in $SCRIPT_DIR" >&2
    exit 1
fi
echo "Installed:$SKILLS"

# OpenCode v2 always scans ~/.claude/skills, so a same-named skill there clashes with the install.
FOREIGN_SKILLS="$HOME_DIR/.claude/skills"
for name in $SKILLS; do
    path="$FOREIGN_SKILLS/$name"
    if [ -e "$path" ] || [ -L "$path" ]; then
        echo "WARN: clash: $path carries the same skill name as the installed $name; OpenCode scans ~/.claude/skills too, so the two copies may conflict. Leave it in place if another tool uses it."
    fi
done

echo "NEXT: restart OpenCode so it reloads the installed skills and agents"
