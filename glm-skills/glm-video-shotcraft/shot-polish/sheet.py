#!/usr/bin/env python3
"""sheet.py <video.mp4> <out.jpg> [n=8] — Sample n frames evenly across video into a 4-column contact sheet and print frame indices."""

import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    video = Path(sys.argv[1])
    out = Path(sys.argv[2])
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 8

    # Probe duration
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-count_packets", "-show_entries", "stream=nb_read_packets,r_frame_rate",
        "-of", "csv=p=0", str(video)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    parts = res.stdout.strip().split("\n")
    fps_str = parts[0]
    num, den = map(int, fps_str.split("/")) if "/" in fps_str else (float(fps_str), 1)
    fps = num / den
    total_frames = int(parts[1]) if len(parts) > 1 else int(fps * 5)

    step = total_frames / (n + 1)
    frames = [int(step * (i + 1)) for i in range(n)]
    print(f"Sampled frames ({n}):", frames)

    cols = min(4, n)
    rows = (n + cols - 1) // cols
    filter_expr = f"select='not(mod(n\\,{step_val}))',scale=480:-1,tile={cols}x{rows}"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(video),
        "-vf", filter_expr, "-vframes", "1", str(out)
    ], check=True)
    print("Saved contact sheet to:", out)


if __name__ == "__main__":
    main()
