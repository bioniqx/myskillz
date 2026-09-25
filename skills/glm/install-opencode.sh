#!/bin/sh
# Install all five Phase 1 GLM skills into OpenCode and print the config snippet.
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

python3 "$HARNESS" snippet "$MAJOR"
echo "# Also export OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 so OpenCode skips the Claude-tuned originals in ~/.claude/skills"
