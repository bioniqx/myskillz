"""Cross-platform font lookup (macOS, Windows, Linux) with Vietnamese/Latin-diacritics support.

Order: env override -> bundled Inter (assets/fonts) -> common system fonts.
  VVS_FONT_BOLD=/path/to/bold.ttf  VVS_FONT_REGULAR=/path/to/regular.ttf
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLED = os.path.join(os.path.dirname(HERE), "assets", "fonts")
WIN = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

CANDIDATES = {
    "black": [os.path.join(BUNDLED, "Inter-Black.otf"), os.path.join(BUNDLED, "Inter-ExtraBold.otf")],
    "bold": [os.path.join(BUNDLED, "Inter-ExtraBold.otf")],
    "regular": [os.path.join(BUNDLED, "Inter-Medium.otf")],
}
SYSTEM = {
    "bold": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
        os.path.join(WIN, "arialbd.ttf"), os.path.join(WIN, "segoeuib.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    ],
    "regular": [
        "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
        os.path.join(WIN, "arial.ttf"), os.path.join(WIN, "segoeui.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ],
}


def find(weight="bold"):
    env = os.environ.get("VVS_FONT_REGULAR" if weight == "regular" else "VVS_FONT_BOLD")
    if env and os.path.exists(env):
        return env
    sys_key = "regular" if weight == "regular" else "bold"
    for p in CANDIDATES.get(weight, []) + SYSTEM[sys_key]:
        if os.path.exists(p):
            return p
    return None


def subtitle_font():
    """(fontsdir, family name) for ffmpeg's subtitles filter. Uses the bundled Inter when present."""
    if os.path.exists(os.path.join(BUNDLED, "Inter-ExtraBold.otf")):
        return BUNDLED, "Inter"
    return None, "Arial"
