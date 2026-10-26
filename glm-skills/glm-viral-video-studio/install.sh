#!/usr/bin/env bash
# Install viral-video-studio for ZCode (macOS / Linux).
#   ./install.sh            -> user-level  (~/.zcode/skills, all workspaces)
#   ./install.sh /path/repo -> project-level (<repo>/.zcode/skills)
set -e
SRC="$(cd "$(dirname "$0")" && pwd)/viral-video-studio"
if [ -n "$1" ]; then DEST="$1/.zcode/skills"; else DEST="$HOME/.zcode/skills"; fi
mkdir -p "$DEST"
if [ -d "$DEST/viral-video-studio" ]; then
  mv "$DEST/viral-video-studio" "$DEST/viral-video-studio.bak-$(date +%Y%m%d%H%M%S)"
  echo "Previous version moved to a .bak folder (delete it yourself when no longer needed)."
fi
cp -R "$SRC" "$DEST/"
echo "Installed to $DEST/viral-video-studio"
PY=python3; command -v python3 >/dev/null 2>&1 || PY=python
"$PY" "$DEST/viral-video-studio/scripts/setup_check.py" || true
echo
echo "Next: open ZCode -> Settings -> Skills -> click Refresh, make sure 'viral-video-studio' is enabled."
echo "Then type \$viral-video-studio in chat."
