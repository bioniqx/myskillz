#!/usr/bin/env python3
"""Check (and optionally install) everything the video scripts need. Works on macOS, Windows, Linux.

  python3 setup_check.py            # report only
  python3 setup_check.py --install  # also pip-install missing Python packages (Pillow, numpy)

Prints the exact command to run for anything it cannot install itself (e.g. ffmpeg).
"""
import argparse, importlib, os, platform, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PY_PKGS = {"PIL": "Pillow", "numpy": "numpy"}


def ffmpeg_hint():
    s = platform.system()
    if s == "Darwin":
        return "brew install ffmpeg      (install Homebrew first from https://brew.sh if needed)"
    if s == "Windows":
        return "winget install --id Gyan.FFmpeg -e   (then open a NEW terminal so PATH updates)"
    return "sudo apt install ffmpeg   (or your distro's package manager)"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", action="store_true")
    a = ap.parse_args()
    ok = True
    print(f"OS: {platform.system()} {platform.machine()} | Python {sys.version.split()[0]} ({sys.executable})")
    if sys.version_info < (3, 9):
        print("  ✗ Python 3.9+ required"); ok = False

    missing = []
    for mod, pkg in PY_PKGS.items():
        try:
            importlib.import_module(mod); print(f"  ✓ {pkg}")
        except ImportError:
            print(f"  ✗ {pkg} missing"); missing.append(pkg)
    if missing and a.install:
        cmd = [sys.executable, "-m", "pip", "install", "--user", *missing]
        print("  → running:", " ".join(cmd))
        r = subprocess.run(cmd)
        if r.returncode:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "--break-system-packages", *missing])
        if r.returncode == 0:
            missing = []
    if missing:
        ok = False
        print(f"  → install with: {sys.executable} -m pip install {' '.join(missing)}")

    for tool in ("ffmpeg", "ffprobe"):
        p = shutil.which(tool)
        print(f"  {'✓' if p else '✗'} {tool}{'  ' + p if p else ''}")
        if not p:
            ok = False
    if not shutil.which("ffmpeg"):
        print("  → install with:", ffmpeg_hint())

    try:
        import fonts
        b, r = fonts.find("bold"), fonts.find("regular")
        print(f"  {'✓' if b else '✗'} font (bold): {b}")
        print(f"  {'✓' if r else '✗'} font (regular): {r}")
        ok = ok and bool(b)
    except Exception as e:  # noqa
        print("  ✗ font check failed:", e); ok = False

    keys = ["FPT_API_KEY", "ELEVENLABS_API_KEY", "GOOGLE_TTS_API_KEY", "GEMINI_API_KEY", "FAL_KEY", "PEXELS_API_KEY",
            "YOUTUBE_API_KEY"]
    have = [k for k in keys if os.environ.get(k)]
    print("Optional API keys set:", ", ".join(have) if have else "none (mode B works without any)")
    print("READY" if ok else "NOT READY — fix the ✗ items above, then run this check again.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
