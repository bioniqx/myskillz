#!/bin/sh
# Install all six GLM skills into OpenCode and print the config snippet.
set -eu

MAJOR=""
HOME_DIR="${HOME:-}"

while [ $# -gt 0 ]; do
    case "$1" in
        --major)
            MAJOR="$2"
            shift 2
            ;;
        --home)
            HOME_DIR="$2"
            shift 2
            ;;
        *)
            echo "Usage: $0 [--major N] [--home DIR]" >&2
            exit 1
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HARNESS="$SCRIPT_DIR/_shared/oc_harness.py"

if [ -z "$MAJOR" ]; then
    MAJOR="$(python3 "$HARNESS" detect || true)"
fi
if [ -z "$MAJOR" ] || [ "$MAJOR" = "0" ]; then
    echo "opencode not found; pass --major 1 or --major 2" >&2
    exit 1
fi

SKILLS="systematic-debugging-glm writing-plans-glm requirements-code-audit-glm brainstorming-glm doc-generator-glm"

for skill in $SKILLS; do
    skill_path="$SCRIPT_DIR/$skill"
    if [ ! -d "$skill_path" ]; then
        echo "Error: $skill_path not found" >&2
        exit 1
    fi
    python3 "$HARNESS" install "$skill_path" "$MAJOR" "$HOME_DIR"
done

DEV_TEAM_PATH="$SCRIPT_DIR/dev-team-glm"
if [ ! -d "$DEV_TEAM_PATH" ]; then
    echo "Error: $DEV_TEAM_PATH not found" >&2
    exit 1
fi
python3 "$HARNESS" install "$DEV_TEAM_PATH" "$MAJOR" "$HOME_DIR"

python3 "$HARNESS" snippet "$MAJOR"
if [ "$MAJOR" = "1" ]; then
    echo "# Also export OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 so OpenCode skips the Claude-tuned originals in ~/.claude/skills"
fi

CLAUDE_SKILLS="$HOME_DIR/.claude/skills"
CONFIG_SKILLS="$HOME_DIR/.config/opencode/skills"

for folder in $SKILLS dev-team-glm; do
    name="${folder%-glm}"
    for path in "$CLAUDE_SKILLS/$name" "$CLAUDE_SKILLS/$folder"; do
        if [ -e "$path" ] || [ -L "$path" ]; then
            echo "WARN: clash: $path carries the same skill name as the installed $name; OpenCode scans ~/.claude/skills too, and $CONFIG_SKILLS/$name is used (the config-dir copy wins). Leave it in place if Claude Code uses it."
        fi
    done
done

STALE=""
for path in "$CONFIG_SKILLS"/*-glm; do
    if [ -e "$path" ] || [ -L "$path" ]; then
        base="${path##*/}"
        echo "WARN: stale: $path is an old *-glm install; OpenCode loads it next to $CONFIG_SKILLS/${base%-glm}"
        STALE="$STALE \"$path\""
    fi
done
if [ -n "$STALE" ]; then
    echo "To remove the stale installs, run: rm -rf$STALE"
fi
