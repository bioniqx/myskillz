#!/usr/bin/env bash
# Install the claude-* skills and their agents into Claude Code.
#
#   ./install-skill.sh [--project DIR] [--dry-run] [--only NAME[,NAME...]] [--keep-old] [--uninstall]
# By default the old un-prefixed copies (dev-team-v3.2, programmer.md, ...) are DELETED, no backup.
# --keep-old leaves them in place.
#
# Layout written (BASE = ~/.claude, or DIR/.claude with --project):
#   BASE/skills/<claude-skill-dir>/      one copy of each skill directory
#   BASE/agents/claude-*.md              agents shipped in <skill>/agents/
# The requirements-audit skill is a plugin (.claude-plugin/): its agents and hooks load from the
# skill folder itself, so its agents are NOT copied to BASE/agents (that would shadow the plugin).
# Compatible with bash 3.2 (macOS) and needs only tar.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="$HOME/.claude"
DRY=0 UNINSTALL=0 KEEP_OLD=0 ONLY=""

# Un-prefixed names used before the claude- rename; deleted on install.
OLD_SKILLS="brainstorming-6.3 dev-team-v3.2 doc-generator frontend-design-Jun18 git-diff-summary requirements-code-audit systematic-debugging-6.3 writing-plans-6.2"
OLD_AGENTS="programmer code-reviewer spot-reviewer investigator team-leader plan-task-writer rca-parser rca-investigator rca-verifier"

usage() { sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }
die() { echo "install.sh: $*" >&2; exit 1; }
run() { if [ "$DRY" = 1 ]; then echo "  [dry-run] $*"; else "$@"; fi; }

while [ $# -gt 0 ]; do
  case "$1" in
    --project) [ $# -ge 2 ] || die "--project needs a directory"; BASE="$(cd "$2" && pwd)/.claude"; shift 2 ;;
    --only) [ $# -ge 2 ] || die "--only needs a list"; ONLY=",$2,"; shift 2 ;;
    --dry-run|-n) DRY=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    --keep-old) KEEP_OLD=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
done

case "$BASE" in *[!A-Za-z0-9_./-]*) die "install path has characters unsafe for hook commands: $BASE" ;; esac

SKILLS_DIR="$BASE/skills"
AGENTS_DIR="$BASE/agents"

# Skills to handle: every claude-*/ directory here that has a SKILL.md (honouring --only).
skills=()
for d in "$SRC"/claude-*/; do
  [ -f "$d/SKILL.md" ] || continue
  name="$(basename "$d")"
  if [ -n "$ONLY" ]; then case "$ONLY" in *",$name,"*) ;; *) continue ;; esac; fi
  skills+=("$name")
done
[ "${#skills[@]}" -gt 0 ] || die "no claude-* skill matched in $SRC"

is_plugin() { [ -f "$SRC/$1/.claude-plugin/plugin.json" ]; }

if [ "$UNINSTALL" = 1 ]; then
  echo "Uninstalling from $BASE"
  for s in "${skills[@]}"; do
    [ -d "$SKILLS_DIR/$s" ] && { echo "  - skill $s"; run rm -rf "$SKILLS_DIR/$s"; }
    for a in "$SRC/$s"/agents/claude-*.md; do
      [ -f "$a" ] && ! is_plugin "$s" || continue
      [ -f "$AGENTS_DIR/$(basename "$a")" ] && { echo "  - agent $(basename "$a")"; run rm -f "$AGENTS_DIR/$(basename "$a")"; }
    done
  done
  echo "Done. Restart Claude Code."
  exit 0
fi

if [ "$KEEP_OLD" != 1 ]; then
  todo=()
  for s in $OLD_SKILLS; do [ -f "$SKILLS_DIR/$s/SKILL.md" ] && todo+=("$SKILLS_DIR/$s"); done
  for a in $OLD_AGENTS; do [ -f "$AGENTS_DIR/$a.md" ] && todo+=("$AGENTS_DIR/$a.md"); done
  if [ "${#todo[@]}" -gt 0 ]; then
    echo "Deleting old un-prefixed copies:"
    printf '  %s\n' "${todo[@]}"
    for p in "${todo[@]}"; do run rm -rf "$p"; done
  fi
fi

echo "Installing ${#skills[@]} skill(s) into $BASE"
run mkdir -p "$SKILLS_DIR" "$AGENTS_DIR"

for s in "${skills[@]}"; do
  dest="$SKILLS_DIR/$s"
  echo "  + skill $s"
  # Clean overwrite so files removed in a newer version do not linger.
  run rm -rf "$dest"
  run mkdir -p "$dest"
  if [ "$DRY" != 1 ]; then
    tar -C "$SRC/$s" --exclude='.DS_Store' --exclude='.idea' --exclude='__pycache__' --exclude='*.pyc' -cf - . \
      | tar -C "$dest" -xf -
    # Keep scripts executable regardless of how the source tree was checked out.
    find "$dest" \( -path '*/scripts/*' -o -path '*/hooks/*' \) -type f \( -name '*.py' -o -name '*.sh' \) -exec chmod +x {} +
  fi

  is_plugin "$s" && continue
  for a in "$SRC/$s"/agents/claude-*.md; do
    [ -f "$a" ] || continue
    out="$AGENTS_DIR/$(basename "$a")"
    echo "  + agent $(basename "$a")"
    if [ "$DRY" = 1 ]; then continue; fi
    if grep -q '__PLAN_TOOL__' "$a"; then
      # The plan-task-writer hook needs the absolute path of the installed plan_tool.py.
      tool="python3 $dest/scripts/plan_tool.py"
      body="$(cat "$a")"
      printf '%s\n' "${body//__PLAN_TOOL__/$tool}" > "$out"
    else
      cp "$a" "$out"
    fi
  done
done

cat <<EOF

Installed. Next steps:
  1. Restart Claude Code (new agents and settings load at startup).
  2. Verify: /agents lists the claude-* agents; the skills appear as /claude-<name>.
  3. Optional, once per repo: python3 $SKILLS_DIR/claude-dev-team-v3.2/scripts/devteam.py doctor --fix
     and python3 $SKILLS_DIR/claude-writing-plans-6.2/scripts/plan_tool.py setup --apply
     raise the concurrent-subagent cap to 64 (default 20).
  Old un-prefixed copies were deleted (pass --keep-old to keep them).
EOF
