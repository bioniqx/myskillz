#!/usr/bin/env bash
# Download the motion-preview MP4s from the gallery-media release into
# gallery/media/ for local preview. They are not tracked in git — the
# deploy-pages workflow assembles them the same way (assemble-media.py:
# bulk gallery-media.zip + any single mp4 uploaded after it) when publishing.
set -euo pipefail
cd "$(dirname "$0")"
python3 assemble-media.py media --repo Vincentwei1021/video-shotcraft
echo "done: $(ls media/*.mp4 | wc -l | tr -d ' ') clips in gallery/media/"

# Showcase community submissions (stored in showcase-media release, not in git).
# If the release does not exist yet (no submissions), silently skip; showcase page displays an empty list.
if gh release view showcase-media --repo Vincentwei1021/video-shotcraft >/dev/null 2>&1; then
  mkdir -p showcase-media
  gh release download showcase-media \
    --repo Vincentwei1021/video-shotcraft \
    --dir showcase-media \
    --clobber
  if [ -f showcase-media/showcase.json ]; then
    mv showcase-media/showcase.json api/showcase.json
  fi
  echo "done: $(ls showcase-media/*.mp4 2>/dev/null | wc -l | tr -d ' ') showcase clips"
else
  printf '{"items": []}\n' > api/showcase.json
  echo "no showcase-media release yet: wrote empty api/showcase.json"
fi
