#!/bin/sh
# Install the six skills into OpenCode v2.
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

SKILLS="oc-brainstorming oc-dev-team oc-doc-generator oc-requirements-code-audit oc-systematic-debugging oc-writing-plans"

for skill in $SKILLS; do
    skill_path="$SCRIPT_DIR/$skill"
    if [ ! -d "$skill_path" ]; then
        echo "Error: $skill_path not found" >&2
        exit 1
    fi
    python3 "$HARNESS" install "$skill_path" 2 "$HOME_DIR"
done

# OpenCode v2 always scans ~/.claude/skills, so a same-named skill there clashes with the install.
FOREIGN_SKILLS="$HOME_DIR/.claude/skills"
for name in $SKILLS; do
    path="$FOREIGN_SKILLS/$name"
    if [ -e "$path" ] || [ -L "$path" ]; then
        echo "WARN: clash: $path carries the same skill name as the installed $name; OpenCode scans ~/.claude/skills too, so the two copies may conflict. Leave it in place if another tool uses it."
    fi
done

echo "NEXT: restart OpenCode so it reloads the installed skills and agents"
