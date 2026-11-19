#!/bin/sh
# Front end that installs every glm-* skill folder that has SKILL.md at its
# root into the four harness targets:
#
#   zcode     delegates to install-zcode.sh (skills, agents, commands, manifest)
#   agents    <home>/.agents/skills/<name>/   (as-is copy, junk pruned)
#   claude    <home>/.claude/skills/<name>/   (as-is copy, junk pruned)
#   opencode  ${XDG_CONFIG_HOME:-<home>/.config}/opencode/skills/<name>/
#             repo agents/ moved under opencode/agents/, pre-existing
#             opencode/commands bodies kept verbatim, .oc-major bumped (or 1)
#
# Non-glm folders under a target are never touched. --dry-run writes nothing
# anywhere (the zcode leg is delegated with --dry-run).
#
# The read-only preflight in install-zcode.sh runs before every target set:
# a rejected tree aborts non-zero before the first copy, whatever --only says.
#
# Usage: sh install-all.sh [--home DIR] [--dry-run] [--only zcode,agents,claude,opencode]
set -eu

HOME_DIR="${HOME:-}"
DRY=0
ONLY="zcode,agents,claude,opencode"

while [ $# -gt 0 ]; do
    case "$1" in
        --home) [ $# -ge 2 ] || { echo "Error: --home needs a value" >&2; exit 1; }; HOME_DIR="$2"; shift 2 ;;
        --dry-run) DRY=1; shift ;;
        --only) [ $# -ge 2 ] || { echo "Error: --only needs a value" >&2; exit 1; }; ONLY="$2"; shift 2 ;;
        *) echo "Usage: $0 [--home DIR] [--dry-run] [--only zcode,agents,claude,opencode]" >&2; exit 1 ;;
    esac
done

[ -n "$HOME_DIR" ] || { echo "Error: HOME is unset; pass --home DIR" >&2; exit 1; }

TARGETS=""
for t in $(printf '%s' "$ONLY" | tr ',' ' '); do
    case "$t" in
        zcode|agents|claude|opencode) TARGETS="$TARGETS $t " ;;
        *) echo "Error: unknown target '$t' (expected zcode, agents, claude, opencode)" >&2; exit 1 ;;
    esac
done
[ -n "$TARGETS" ] || { echo "Error: --only needs at least one of zcode, agents, claude, opencode" >&2; exit 1; }

has_target() {
    case "$TARGETS" in
        *" $1 "*) return 0 ;;
    esac
    return 1
}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OC_ROOT="${XDG_CONFIG_HOME:-$HOME_DIR/.config}/opencode"

# Discover installable skills: directories named glm-* with SKILL.md at the root.
FOLDERS=$(
    for d in "$SCRIPT_DIR"/glm-*; do
        [ -d "$d" ] || continue
        [ -f "$d/SKILL.md" ] || continue
        basename "$d"
    done | sort | tr '\n' ' '
)
FOLDERS=${FOLDERS%" "}
[ -n "$FOLDERS" ] || { echo "Error: no glm-*/SKILL.md folders under $SCRIPT_DIR" >&2; exit 1; }
skill_n=0
for _folder in $FOLDERS; do
    skill_n=$((skill_n + 1))
done

# Shared preflight: install-zcode.sh's read-only checks, delegated as a dry run
# (stdout discarded, its Error: lines reach stderr). It writes nothing, so it is
# safe in --dry-run mode too; a non-zero exit aborts here via set -e.
[ -f "$SCRIPT_DIR/install-zcode.sh" ] || { echo "Error: install-zcode.sh not found next to install-all.sh" >&2; exit 1; }
sh "$SCRIPT_DIR/install-zcode.sh" --home "$HOME_DIR" --dry-run >/dev/null

# Same junk set install-zcode.sh prunes after its copy step (opencode/ dirs are
# per-target local state, never shipped).
prune_junk() {
    find "$1" \( -name opencode -o -name .DS_Store -o -name .idea -o -name __pycache__ -o -name '*.pyc' \) -prune -exec rm -rf {} +
}

# rm -rf then copy each skill folder as-is with junk pruned. Only glm-* names
# under the target's skills/ dir are touched; non-glm folders are left alone.
install_asis() {
    label=$1
    root=$2
    echo "== $label"
    if [ "$DRY" -eq 1 ]; then
        echo "    [dry-run] $skill_n skills -> $root/skills/   (as-is copy, junk pruned)"
        return 0
    fi
    echo "    dest: $root/skills/<name>/   (rm -rf then pruned copy; non-glm folders untouched)"
    mkdir -p "$root/skills"
    for folder in $FOLDERS; do
        src="$SCRIPT_DIR/$folder"
        dest="$root/skills/$folder"
        rm -rf "$dest"
        mkdir -p "$dest"
        # cp, not a tar pipe: macOS tar adds com.apple.provenance xattrs the extracting side cannot write.
        cp -R "$src/." "$dest/"
        prune_junk "$dest"
        echo "  $dest/"
    done
}

install_opencode() {
    echo "== opencode"
    if [ "$DRY" -eq 1 ]; then
        echo "    [dry-run] $skill_n skills -> $OC_ROOT/skills/   (agents under opencode/agents, .oc-major bump-or-1)"
        return 0
    fi
    echo "    dest: $OC_ROOT/skills/<name>/   (agents/ -> opencode/agents/; opencode/commands kept; .oc-major bump-or-1)"
    mkdir -p "$OC_ROOT/skills"
    for folder in $FOLDERS; do
        src="$SCRIPT_DIR/$folder"
        dest="$OC_ROOT/skills/$folder"
        major=1
        saved_cmds=""
        if [ -d "$dest" ]; then
            if [ -f "$dest/.oc-major" ]; then
                old_major=$(head -n 1 "$dest/.oc-major" 2>/dev/null || true)
                case "$old_major" in
                    ''|*[!0-9]*) ;;
                    *) major=$((old_major + 1)) ;;
                esac
            fi
            # Local opencode command bodies survive the reinstall verbatim.
            if [ -d "$dest/opencode/commands" ]; then
                saved_cmds=$(mktemp -d)
                mv "$dest/opencode/commands" "$saved_cmds/commands"
            fi
        fi
        rm -rf "$dest"
        mkdir -p "$dest"
        cp -R "$src/." "$dest/"
        prune_junk "$dest"
        if [ -d "$dest/agents" ]; then
            mkdir -p "$dest/opencode"
            rm -rf "$dest/opencode/agents"
            mv "$dest/agents" "$dest/opencode/agents"
        fi
        if [ -n "$saved_cmds" ]; then
            mkdir -p "$dest/opencode"
            mv "$saved_cmds/commands" "$dest/opencode/commands"
            rm -rf "$saved_cmds"
        fi
        printf '%s\n' "$major" > "$dest/.oc-major"
        echo "  $dest/   .oc-major=$major"
    done
}

echo "glm-skills install-all: $skill_n skills ->$TARGETS"
if has_target zcode; then
    echo "== zcode (delegated to install-zcode.sh)"
    [ -f "$SCRIPT_DIR/install-zcode.sh" ] || { echo "Error: install-zcode.sh not found next to install-all.sh" >&2; exit 1; }
    if [ "$DRY" -eq 1 ]; then
        sh "$SCRIPT_DIR/install-zcode.sh" --home "$HOME_DIR" --dry-run
    else
        sh "$SCRIPT_DIR/install-zcode.sh" --home "$HOME_DIR"
    fi
fi
if has_target agents; then
    install_asis agents "$HOME_DIR/.agents"
fi
if has_target claude; then
    install_asis claude "$HOME_DIR/.claude"
fi
if has_target opencode; then
    install_opencode
fi
if [ "$DRY" -eq 1 ]; then
    echo
    echo "Dry run. Nothing written."
else
    echo "Done."
fi
