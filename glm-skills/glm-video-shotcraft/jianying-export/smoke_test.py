#!/usr/bin/env python3
"""Smoke test: verify local Mac JianYing/CapCut can open programmatically generated drafts.

Run this first on new machines or new app versions to confirm drafts open without errors
before proceeding with full exports (references/jianying-export.md).

Generates a minimal 3-track draft (ffmpeg synthetic 6s clip + bundled SFX + title text)
through mac_draft's installation pipeline.

Usage:
    .venv/bin/python smoke_test.py            # generate + install
    .venv/bin/python smoke_test.py --restore  # delete test draft (including registry entry)
"""

import os
import subprocess
import sys

import pyJianYingDraft as draft
from pyJianYingDraft import trange

import mac_draft

DRAFT_NAME = "vs-smoke-test"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STAGING = os.path.join(HERE, "staging")
# Audio uses bundled repo assets; video synthesized on the fly via ffmpeg
AUDIO = os.path.join(REPO, "assets/audio/sfx/transition/air-whoosh-powerful.mp3")
TEST_CLIP = os.path.join(STAGING, "smoke-clip.mp4")


def make_clip() -> None:
    os.makedirs(STAGING, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "testsrc2=duration=6:size=1920x1080:rate=30",
         "-pix_fmt", "yuv420p", TEST_CLIP], check=True)


def build() -> str:
    folder = draft.DraftFolder(STAGING)
    script = folder.create_draft(DRAFT_NAME, 1920, 1080, fps=30,
                                 allow_replace=True)
    script.append_track(draft.TrackSpec(draft.TrackType.video))
    script.append_track(draft.TrackSpec(draft.TrackType.audio))
    script.append_track(draft.TrackSpec(draft.TrackType.text))

    script.add_segment(draft.VideoSegment(TEST_CLIP, trange("0s", "6s")))
    mat = draft.AudioMaterial(AUDIO)
    script.add_segment(draft.AudioSegment(
        mat, draft.Timerange(1_000_000, min(mat.duration, 1_500_000)),
        volume=0.6))
    script.add_segment(draft.TextSegment(
        "SMOKE TEST", trange("0s", "4s"),
        style=draft.TextStyle(size=6.0, color=(0.9, 0.6, 0.2), align=1)))
    script.save()
    return os.path.join(STAGING, DRAFT_NAME)


def main() -> None:
    if "--restore" in sys.argv:
        mac_draft.uninstall(DRAFT_NAME)
        print(f"[ok] Removed test draft {DRAFT_NAME}")
        return
    if not os.path.exists(AUDIO):
        print(f"[abort] Missing audio asset: {AUDIO}")
        sys.exit(1)
    make_clip()
    draft_dir = build()
    info = mac_draft.macify(draft_dir, DRAFT_NAME)
    bak = mac_draft.install(draft_dir, DRAFT_NAME, info)
    print(f"[ok] Draft installed: {info['fold_path']}")
    print(f"[ok] Registry backup: {bak}")
    print("Now open JianYing and verify vs-smoke-test in draft list:")
    print("  1. Opens normally without errors")
    print("  2. All three video/audio/text tracks present")
    print("  3. Text editable directly")


if __name__ == "__main__":
    main()
