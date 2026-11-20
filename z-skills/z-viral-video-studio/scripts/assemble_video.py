#!/usr/bin/env python3
"""Assemble Veo clips / stills + voiceover + subtitles into a platform-ready MP4 (free, ffmpeg).

Examples:
  python3 assemble_video.py --clips c1.mp4 c2.mp4 still3.png c4.mp4 --voice voice.mp3 \
      --srt subs.srt --format 9x16 --out final.mp4
  python3 assemble_video.py --clips c1.mp4 c2.mp4 --music bg.mp3 --music-volume 0.15 --out final.mp4
  python3 assemble_video.py --txt2srt timings.txt --out subs.srt   # lines: 0.0|2.5|Text

Options:
  --trim-head 0.3   cut the first N seconds of every video clip (Veo clips often start with a stutter)
  --still-seconds 3 duration of each still image (shown with a slow zoom-in)
  --keep-clip-audio keep Veo native audio (mixed under voice/music)
"""
import argparse, os, subprocess, sys, tempfile

SIZES = {"9x16": (1080, 1920), "16x9": (1920, 1080), "1x1": (1080, 1080)}
IMG = (".png", ".jpg", ".jpeg", ".webp")



try:  # print Unicode safely on Windows consoles
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("ffmpeg failed:\n" + r.stderr[-2000:])


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def txt2srt(src, dst):
    def ts(x):
        x = float(x); h, m = int(x // 3600), int(x % 3600 // 60); s = x % 60
        return f"{h:02}:{m:02}:{int(s):02},{int(round((s - int(s)) * 1000)):03}"
    out = []
    for i, line in enumerate([l for l in open(src, encoding="utf-8") if l.strip()], 1):
        a, b, t = line.rstrip("\n").split("|", 2)
        out.append(f"{i}\n{ts(a)} --> {ts(b)}\n{t.strip()}\n")
    open(dst, "w", encoding="utf-8").write("\n".join(out))
    print("Saved", dst)


def normalize(src, dst, w, h, fps, trim, still_s, keep_audio):
    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={fps},format=yuv420p"
    if src.lower().endswith(IMG):
        frames = int(still_s * fps)
        zoom = (f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},"
                f"zoompan=z='min(zoom+0.0008,1.12)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},"
                f"setsar=1,format=yuv420p")
        run(["ffmpeg", "-y", "-loop", "1", "-i", src, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
             "-vf", zoom, "-t", str(still_s), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", "-shortest", dst])
    else:
        has_audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                                    "stream=index", "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip()
        cmd = ["ffmpeg", "-y", "-ss", str(trim), "-i", src]
        if not (keep_audio and has_audio):
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v", "-map", "1:a", "-shortest"]
        cmd += ["-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-ar", "48000", "-ac", "2", dst]
        run(cmd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", nargs="*", default=[])
    ap.add_argument("--voice"); ap.add_argument("--music"); ap.add_argument("--srt"); ap.add_argument("--txt2srt")
    ap.add_argument("--format", default="9x16", choices=SIZES)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--trim-head", type=float, default=0.0)
    ap.add_argument("--still-seconds", type=float, default=3.0)
    ap.add_argument("--music-volume", type=float, default=0.15)
    ap.add_argument("--keep-clip-audio", action="store_true")
    ap.add_argument("--font-size", type=int, default=0, help="subtitle font size (auto if 0)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    if a.txt2srt:
        return txt2srt(a.txt2srt, a.out)
    if not a.clips:
        sys.exit("Give --clips")
    w, h = SIZES[a.format]
    tmp = tempfile.mkdtemp()
    parts = []
    for i, c in enumerate(a.clips):
        p = os.path.join(tmp, f"p{i:03}.mp4")
        normalize(c, p, w, h, a.fps, a.trim_head, a.still_seconds, a.keep_clip_audio)
        parts.append(p)
    lst = os.path.join(tmp, "list.txt")
    open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    joined = os.path.join(tmp, "joined.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    total = duration(joined)

    inputs, filters, mix = ["-i", joined], [], ["[0:a]volume=0.35[a0]" if a.keep_clip_audio else "[0:a]volume=0[a0]"]
    labels, idx = ["[a0]"], 1
    if a.voice:
        inputs += ["-i", a.voice]; mix.append(f"[{idx}:a]volume=1.0[a{idx}]"); labels.append(f"[a{idx}]"); idx += 1
    if a.music:
        inputs += ["-stream_loop", "-1", "-i", a.music]
        mix.append(f"[{idx}:a]volume={a.music_volume}[a{idx}]"); labels.append(f"[a{idx}]"); idx += 1
    mix.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0[aout]")

    vchain = "[0:v]null[vout]"
    if a.srt:
        # libass SRT canvas is 288 units tall; for 9:16 keep subtitles ~28% above the bottom (TikTok/Shorts UI zone)
        fs = a.font_size or (14 if a.format == "9x16" else 20)
        margin = 80 if a.format == "9x16" else 25
        esc = lambda p: os.path.abspath(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import fonts
        fdir, fname = fonts.subtitle_font()
        style = (f"FontName={fname},FontSize={fs},Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                 f"BorderStyle=1,Outline=3,Shadow=0,Alignment=2,MarginL=20,MarginR=20,MarginV={margin}")
        fd = f":fontsdir='{esc(fdir)}'" if fdir else ""
        vchain = f"[0:v]subtitles='{esc(a.srt)}'{fd}:force_style='{style}'[vout]"
    filters = ";".join([vchain] + mix)
    run(["ffmpeg", "-y", *inputs, "-filter_complex", filters, "-map", "[vout]", "-map", "[aout]",
         "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out])
    print(f"Saved {a.out} ({total:.1f}s, {w}x{h})")


if __name__ == "__main__":
    main()
