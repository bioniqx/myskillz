#!/usr/bin/env python3
"""Make 3 thumbnail variants (for YouTube Test & Compare) without Canva. Needs Pillow + numpy.

  python3 make_thumbnail.py --text "STOP SAVING MONEY" --highlight "SAVING" --sub "if you want to get rich" \
      [--image face.png] [--format 16x9|9x16] --out thumb
Outputs thumb_A.png, thumb_B.png, thumb_C.png (1280x720 or 1080x1920), each < 2 MB.
Rules baked in: <= 4 big words, high contrast, thick outline, subject on the right third, readable at small size.
"""
import argparse, os, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

PALETTES = {  # (bg top, bg bottom, accent, text)
    "A": ("#0B1026", "#1E2A78", "#FFD400", "#FFFFFF"),
    "B": ("#2B0000", "#B3001B", "#FFFFFF", "#FFE14D"),
    "C": ("#002B1F", "#00875A", "#FFE14D", "#FFFFFF"),
}



try:  # print Unicode safely on Windows consoles
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def font_path():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import fonts
    p = fonts.find("black")
    if not p:
        sys.exit("No usable font found. Set VVS_FONT_BOLD to a .ttf/.otf file that supports your language.")
    return p


def fit_lines(words, fp, max_w, max_h, max_size):
    for size in range(max_size, 20, -4):
        f = ImageFont.truetype(fp, size)
        lines, cur = [], []
        for w in words:
            if cur and f.getlength(" ".join(cur + [w])) > max_w:
                lines.append(cur); cur = []
            cur.append(w)
        lines.append(cur)
        asc, desc = f.getmetrics()
        if len(lines) * (asc + desc) * 1.02 <= max_h and all(f.getlength(" ".join(l)) <= max_w for l in lines):
            return f, lines, int((asc + desc) * 1.02)
    f = ImageFont.truetype(fp, 24); return f, [words], 30


def make(text, highlight, sub, image, fmt, pal, out):
    W, H = (1280, 720) if fmt == "16x9" else (1080, 1920)
    top, bot, acc, txt = (rgb(c) for c in pal)
    g = np.linspace(0, 1, H)[:, None, None]
    arr = (np.array(top) * (1 - g) + np.array(bot) * g).astype(np.uint8)
    img = Image.fromarray(np.repeat(arr, W, axis=1), "RGB").convert("RGBA")
    # radial glow behind subject
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cx, cy = (int(W * 0.72), int(H * 0.5)) if fmt == "16x9" else (W // 2, int(H * 0.62))
    r = int(min(W, H) * 0.55)
    ImageDraw.Draw(glow).ellipse([cx - r, cy - r, cx + r, cy + r], fill=acc + (90,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(r // 3)))
    if image:
        sub_im = Image.open(image).convert("RGBA")
        if fmt == "16x9":
            s = H * 0.98 / sub_im.height; sub_im = sub_im.resize((int(sub_im.width * s), int(sub_im.height * s)), Image.LANCZOS)
            x = int(W * 0.98 - sub_im.width); x = max(x, int(W * 0.42)); y = H - sub_im.height
        else:
            s = W * 1.0 / sub_im.width; sub_im = sub_im.resize((int(sub_im.width * s), int(sub_im.height * s)), Image.LANCZOS)
            x = (W - sub_im.width) // 2; y = H - sub_im.height
        # fade the left edge of photos without transparency so text stays readable
        if sub_im.getchannel("A").getextrema()[0] == 255 and fmt == "16x9":
            fade = np.ones((sub_im.height, sub_im.width), np.float32)
            ramp = int(sub_im.width * 0.35); fade[:, :ramp] = np.linspace(0, 1, ramp)[None, :]
            sub_im.putalpha(Image.fromarray((fade * 255).astype(np.uint8)))
        img.alpha_composite(sub_im, (x, y))
    fp = font_path(); d = ImageDraw.Draw(img)
    words = text.upper().split(); hl = set(w.upper() for w in (highlight or "").split())
    if fmt == "16x9":
        box = (int(W * 0.05), int(H * 0.08), int(W * (0.55 if image else 0.9)), int(H * (0.70 if sub else 0.86)))
    else:
        box = (int(W * 0.07), int(H * 0.08), int(W * 0.93), int(H * 0.36))
    f, lines, lh = fit_lines(words, fp, box[2] - box[0], box[3] - box[1], 190 if fmt == "16x9" else 170)
    y = box[1] + ((box[3] - box[1]) - lh * len(lines)) // 2
    stroke = max(6, f.size // 12)
    for ln in lines:
        lw = f.getlength(" ".join(ln))
        x = box[0] if fmt == "16x9" else (W - lw) / 2
        for w in ln:
            is_hl = w.strip(".,!?") in hl
            if is_hl:  # accent block behind highlighted word
                ww = f.getlength(w); pad = f.size * 0.08
                d.rounded_rectangle([x - pad, y + f.size * 0.08, x + ww + pad, y + lh * 0.98], radius=int(f.size * 0.12), fill=acc + (255,))
                d.text((x, y), w, font=f, fill=(15, 15, 20, 255))
            else:
                d.text((x, y), w, font=f, fill=txt + (255,), stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
            x += f.getlength(w + " ")
        y += lh
    if sub:
        fs = ImageFont.truetype(fp, max(28, f.size // 3))
        sy = box[3] + 10 if fmt == "16x9" else box[3] + 20
        sw = fs.getlength(sub)
        sx = box[0] if fmt == "16x9" else (W - sw) / 2
        d.rounded_rectangle([sx - 18, sy - 8, sx + sw + 18, sy + fs.size * 1.25], radius=14, fill=(0, 0, 0, 170))
        d.text((sx, sy), sub, font=fs, fill=(255, 255, 255, 255))
    img.convert("RGB").save(out, optimize=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True); ap.add_argument("--highlight"); ap.add_argument("--sub")
    ap.add_argument("--image"); ap.add_argument("--format", default="16x9", choices=["16x9", "9x16"])
    ap.add_argument("--out", default="thumb")
    a = ap.parse_args()
    if len(a.text.split()) > 4:
        print("Warning: more than 4 words — thumbnails read best with 4 words or fewer.")
    for k, pal in PALETTES.items():
        print("Saved", make(a.text, a.highlight, a.sub, a.image, a.format, pal, f"{a.out}_{k}.png"))


if __name__ == "__main__":
    main()
