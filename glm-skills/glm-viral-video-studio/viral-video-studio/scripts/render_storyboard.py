#!/usr/bin/env python3
"""Render a faceless motion-graphics video from storyboard.json (no paid tools; needs Pillow, numpy, ffmpeg).

  python3 render_storyboard.py storyboard.json --out final.mp4 [--preview]

Scene types: hook, text, stat, bullets, bars, compare, quote, cta. See references/claude-only.md.
Also writes <out>.srt (captions) next to the video. --preview renders at half resolution for a quick check.
"""
import argparse, json, math, os, re, subprocess, sys, tempfile, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SIZES = {"9x16": (1080, 1920), "16x9": (1920, 1080), "1x1": (1080, 1080)}


# ---------------- helpers ----------------

try:  # print Unicode safely on Windows consoles
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def hex2rgb(h, a=255):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fonts  # noqa: E402  (bundled Inter + macOS/Windows/Linux fallbacks)

FONT_BOLD, FONT_REG = fonts.find("bold"), fonts.find("regular")
if not FONT_BOLD:
    sys.exit("No usable font found. Set VVS_FONT_BOLD and VVS_FONT_REGULAR to .ttf/.otf files that support your language.")
_font_cache = {}


def font(size, bold=True):
    k = (int(size), bold)
    if k not in _font_cache:
        path = FONT_BOLD if bold else FONT_REG
        _font_cache[k] = ImageFont.truetype(path, int(size)) if path else ImageFont.load_default()
    return _font_cache[k]


def ease_out(x):
    x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3


def ease_back(x):
    x = max(0.0, min(1.0, x)); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def media_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def norm_words(s):
    return [w for w in re.split(r"\s+", s.strip()) if w]


def highlight_mask(words, phrases):
    low = [re.sub(r"[^\w%]", "", w.lower()) for w in words]
    mask = [False] * len(words)
    for p in phrases or []:
        pw = [re.sub(r"[^\w%]", "", w.lower()) for w in norm_words(p)]
        for i in range(len(low) - len(pw) + 1):
            if pw and low[i:i + len(pw)] == pw:
                for j in range(i, i + len(pw)):
                    mask[j] = True
    return mask


def wrap(words, fnt, max_w):
    lines, cur = [], []
    space = fnt.getlength(" ")
    for i, w in enumerate(words):
        test = sum(fnt.getlength(words[j]) for j in cur + [i]) + space * len(cur)
        if cur and test > max_w:
            lines.append(cur); cur = [i]
        else:
            cur.append(i)
    if cur:
        lines.append(cur)
    return lines


def text_block(text, size, max_w, color, accent, highlight=None, bold=True, stroke=0, align="center", line_gap=1.12):
    """Render text to a tight RGBA image. Highlighted words use the accent color."""
    fnt = font(size, bold)
    words = norm_words(text)
    mask = highlight_mask(words, highlight)
    lines = wrap(words, fnt, max_w)
    space = fnt.getlength(" ")
    asc, desc = fnt.getmetrics()
    lh = int((asc + desc) * line_gap)
    widths = [sum(fnt.getlength(words[i]) for i in ln) + space * (len(ln) - 1) for ln in lines]
    W = int(max(widths or [1]) + stroke * 2 + 4); H = int(lh * len(lines) + stroke * 2 + desc)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    for li, ln in enumerate(lines):
        x = stroke + (W - 2 * stroke - widths[li]) / 2 if align == "center" else stroke
        y = stroke + li * lh
        for i in ln:
            col = accent if mask[i] else color
            d.text((x, y), words[i], font=fnt, fill=col, stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
            x += fnt.getlength(words[i]) + space
    return img


def paste(canvas, im, cx, cy, scale=1.0, alpha=1.0):
    if alpha <= 0.01 or scale <= 0.01:
        return
    if abs(scale - 1) > 0.005:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if alpha < 0.999:
        a = im.getchannel("A").point(lambda v: int(v * alpha)); im = im.copy(); im.putalpha(a)
    canvas.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def rounded(w, h, r, fill, outline=None, width=0):
    im = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], radius=int(r), fill=fill, outline=outline, width=width)
    return im


# ---------------- music ----------------
def make_music(path, seconds, sr=44100, bpm=92):
    """Simple royalty-free bed: Am-F-C-G pad + soft arpeggio + light kick. Generated, so no copyright issues."""
    n = int(seconds * sr); t = np.arange(n) / sr
    beat = 60 / bpm; bar = beat * 4
    chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Am F C G (MIDI)
    f = lambda m: 440 * 2 ** ((m - 69) / 12)
    out = np.zeros(n)
    for ci in range(int(seconds / bar) + 1):
        ch = chords[ci % 4]; s0 = int(ci * bar * sr); s1 = min(n, int((ci + 1) * bar * sr))
        if s0 >= n:
            break
        tt = t[s0:s1] - t[s0]
        env = np.minimum(1, tt / 0.6) * np.minimum(1, (bar - tt) / 0.4)
        for m in ch:
            out[s0:s1] += 0.10 * env * (np.sin(2 * np.pi * f(m - 12) * tt) + 0.3 * np.sin(2 * np.pi * f(m) * tt))
        for k in range(8):  # eighth-note arpeggio
            a0 = s0 + int(k * beat / 2 * sr)
            if a0 >= s1:
                break
            a1 = min(s1, a0 + int(0.5 * sr)); ta = t[a0:a1] - t[a0]
            out[a0:a1] += 0.06 * np.exp(-ta * 7) * np.sin(2 * np.pi * f(ch[k % 3] + 12) * ta)
        for k in range(4):  # soft kick
            k0 = s0 + int(k * beat * sr)
            if k0 >= s1:
                break
            k1 = min(s1, k0 + int(0.25 * sr)); tk = t[k0:k1] - t[k0]
            out[k0:k1] += 0.35 * np.exp(-tk * 18) * np.sin(2 * np.pi * (50 + 60 * np.exp(-tk * 30)) * tk)
    fade = int(1.5 * sr)
    out[:fade] *= np.linspace(0, 1, min(fade, n)); out[-fade:] *= np.linspace(1, 0, min(fade, n))
    out = out / (np.max(np.abs(out)) or 1) * 0.8
    pcm = (np.repeat(out[:, None], 2, axis=1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())


# ---------------- background ----------------
class Background:
    def __init__(self, W, H, colors, accent):
        c1, c2 = np.array(hex2rgb(colors[0])[:3], float), np.array(hex2rgb(colors[1])[:3], float)
        hh = int(H * 1.4)
        g = np.linspace(0, 1, hh)[:, None, None]
        arr = (c1 * (1 - g) + c2 * g).astype(np.uint8)
        self.grad = Image.fromarray(np.repeat(arr, W, axis=1), "RGB").convert("RGBA")
        self.W, self.H = W, H
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(glow)
        rng = np.random.default_rng(7); ac = hex2rgb(accent)
        self.blobs = []
        for _ in range(6):
            r = int(rng.uniform(0.12, 0.28) * W)
            self.blobs.append((rng.uniform(0, W), rng.uniform(0, H), r, rng.uniform(0.2, 0.6), rng.uniform(0, 6.28)))
        self.blob_img = {}
        for i, (_, _, r, _, _) in enumerate(self.blobs):
            pad = r  # room for the blur so edges fade out instead of being clipped square
            b = Image.new("RGBA", (r * 2 + pad * 2, r * 2 + pad * 2), (0, 0, 0, 0))
            col = ac[:3] + (40,) if i % 2 == 0 else (255, 255, 255, 20)
            ImageDraw.Draw(b).ellipse([pad, pad, pad + r * 2, pad + r * 2], fill=col)
            self.blob_img[i] = b.filter(ImageFilter.GaussianBlur(r / 2.5))

    def frame(self, t):
        off = int((math.sin(t * 0.25) * 0.5 + 0.5) * (self.grad.height - self.H))
        img = self.grad.crop((0, off, self.W, off + self.H)).copy()
        for i, (x, y, r, sp, ph) in enumerate(self.blobs):
            bx = x + math.sin(t * sp + ph) * self.W * 0.08; by = y + math.cos(t * sp * 0.8 + ph) * self.H * 0.05
            b = self.blob_img[i]
            img.alpha_composite(b, (int(bx - b.width / 2), int(by - b.height / 2))) if self._fits(bx, by, b) else \
                self._paste_clipped(img, b, int(bx - b.width / 2), int(by - b.height / 2))
        return img

    def _fits(self, bx, by, b):
        x0, y0 = int(bx - b.width / 2), int(by - b.height / 2)
        return x0 >= 0 and y0 >= 0 and x0 + b.width <= self.W and y0 + b.height <= self.H

    @staticmethod
    def _paste_clipped(img, b, x0, y0):
        cx0, cy0 = max(0, -x0), max(0, -y0)
        cx1, cy1 = min(b.width, img.width - x0), min(b.height, img.height - y0)
        if cx1 > cx0 and cy1 > cy0:
            img.alpha_composite(b.crop((cx0, cy0, cx1, cy1)), (x0 + cx0, y0 + cy0))


class MediaBG:
    """Image (Ken Burns) or video (looped) background with a dark overlay for readable text."""
    def __init__(self, path, W, H, fps, dur):
        self.W, self.H, self.n = W, H, int(math.ceil(dur * fps)) + 2
        self.is_img = path.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        shade = np.zeros((H, 1, 4), np.uint8); g = np.linspace(0, 1, H)
        shade[:, 0, 3] = (110 + 90 * np.abs(g - 0.45) * 2).clip(0, 210).astype(np.uint8)
        self.shade = Image.fromarray(np.repeat(shade, W, axis=1), "RGBA")
        if self.is_img:
            im = Image.open(path).convert("RGBA")
            s = max(W / im.width, H / im.height) * 1.15
            self.im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
        else:
            vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps}"
            self.proc = subprocess.Popen(["ffmpeg", "-v", "error", "-stream_loop", "-1", "-i", path, "-vf", vf,
                                          "-frames:v", str(self.n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                         stdout=subprocess.PIPE)
            self.last = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        self.i = 0

    def frame(self, t, dur):
        if self.is_img:
            # slow zoom-in: crop window shrinks from 1/1.0 to 1/1.08 of the frame size, centered
            z = 1 + 0.08 * t / max(dur, 0.1)
            cx, cy = self.im.width / 2, self.im.height / 2
            w2, h2 = self.W / z, self.H / z
            box = (int(cx - w2 / 2), int(cy - h2 / 2), int(cx + w2 / 2), int(cy + h2 / 2))
            img = self.im.crop(box).resize((self.W, self.H), Image.BILINEAR)
        else:
            buf = self.proc.stdout.read(self.W * self.H * 3)
            if len(buf) == self.W * self.H * 3:
                self.last = Image.frombytes("RGB", (self.W, self.H), buf).convert("RGBA")
            img = self.last.copy()
        img.alpha_composite(self.shade)
        return img

    def close(self):
        if not self.is_img:
            self.proc.stdout.close(); self.proc.wait()


# ---------------- scenes ----------------
class Scene:
    def __init__(self, data, W, H, theme, start, dur):
        self.d, self.W, self.H, self.start, self.dur = data, W, H, start, dur
        self.u = min(W, H) / 1080
        self.vert = H > W
        self.col = hex2rgb(theme.get("text", "#FFFFFF")); self.acc = hex2rgb(theme.get("accent", "#FFD400"))
        self.cache = {}
        self.cy = H * (0.36 if self.vert else 0.42)   # content center (keeps clear of captions/UI)
        self.maxw = W * (0.80 if self.vert else 0.70)

    def tb(self, key, *a, **k):
        if key not in self.cache:
            self.cache[key] = text_block(*a, **k)
        return self.cache[key]

    def draw(self, c, t):
        getattr(self, "draw_" + self.d.get("type", "text"), self.draw_text)(c, t)

    def draw_text(self, c, t, size=118):
        d = self.d
        im = self.tb("main", d.get("text", ""), size * self.u, self.maxw, self.col, self.acc, d.get("highlight"), stroke=int(5 * self.u))
        paste(c, im, self.W / 2, self.cy, scale=ease_back(t / 0.35) * (1 + 0.035 * t / self.dur), alpha=ease_out(t / 0.2))

    def draw_hook(self, c, t):
        self.draw_text(c, t, size=132)

    def draw_stat(self, c, t):
        d = self.d; val = str(d.get("value", ""))
        m = re.match(r"^([^\d]*)([\d.,]+)(.*)$", val)
        if m:
            pre, num, suf = m.groups()
            target = float(num.replace(",", ""))
            p = ease_out(t / 0.9); cur = target * p
            dec = len(num.split(".")[1]) if "." in num else 0
            shown = f"{pre}{cur:,.{dec}f}{suf}"
        else:
            shown = val
        im = text_block(shown, 280 * self.u, self.W * 0.9, self.acc, self.acc, stroke=int(6 * self.u))
        paste(c, im, self.W / 2, self.cy - 90 * self.u, scale=ease_back(t / 0.35))
        lab = self.tb("label", d.get("label", ""), 66 * self.u, self.maxw, self.col, self.acc, d.get("highlight"), stroke=int(4 * self.u))
        paste(c, lab, self.W / 2, self.cy + 140 * self.u + lab.height / 2 - 40 * self.u, alpha=ease_out((t - 0.4) / 0.3))

    def title(self, c, t, y):
        if self.d.get("title"):
            im = self.tb("title", self.d["title"], 92 * self.u, self.maxw, self.acc, self.acc, stroke=int(5 * self.u))
            paste(c, im, self.W / 2, y, scale=ease_back(t / 0.3), alpha=ease_out(t / 0.2))

    def draw_bullets(self, c, t):
        items = self.d.get("items", []); n = max(len(items), 1)
        top = self.H * (0.16 if self.vert else 0.18)
        self.title(c, t, top)
        gap = (self.H * (0.56 if self.vert else 0.72) - top - 110 * self.u) / n
        card_w = self.maxw
        for i, txt in enumerate(items):
            appear = 0.35 + i * min(0.9, (self.dur * 0.6) / n)
            p = ease_out((t - appear) / 0.35)
            if p <= 0:
                continue
            key = f"item{i}"
            if key not in self.cache:
                lab = text_block(txt, 58 * self.u, card_w - 190 * self.u, self.col, self.acc, self.d.get("highlight"), align="left")
                h = max(lab.height + 50 * self.u, 120 * self.u)
                card = rounded(card_w, h, 28 * self.u, (255, 255, 255, 34), outline=(255, 255, 255, 60), width=int(2 * self.u))
                badge = rounded(84 * self.u, 84 * self.u, 42 * self.u, self.acc)
                num = text_block(str(i + 1), 50 * self.u, 200, (10, 10, 20, 255), self.acc)
                badge.alpha_composite(num, (int((badge.width - num.width) / 2), int((badge.height - num.height) / 2)))
                card.alpha_composite(badge, (int(26 * self.u), int((h - badge.height) / 2)))
                card.alpha_composite(lab, (int(140 * self.u), int((h - lab.height) / 2)))
                self.cache[key] = card
            card = self.cache[key]
            y = top + 110 * self.u + gap * i + gap / 2
            paste(c, card, self.W / 2 - (1 - p) * self.W * 0.25, y, alpha=p)

    def draw_bars(self, c, t):
        data = self.d.get("data", []); unit = self.d.get("unit", "")
        top = self.H * (0.15 if self.vert else 0.16); self.title(c, t, top)
        n = max(len(data), 1); vmax = max([v for _, v in data] or [1])
        area_w = self.maxw; base_y = self.H * (0.56 if self.vert else 0.70); area_h = base_y - top - 220 * self.u
        bw = area_w / n * 0.62; d = ImageDraw.Draw(c)
        for i, (lab, v) in enumerate(data):
            p = ease_out((t - 0.3 - i * 0.18) / 0.8)
            x0 = self.W / 2 - area_w / 2 + area_w / n * (i + 0.19); h = area_h * (v / vmax) * p
            col = self.acc if i == n - 1 else (255, 255, 255, 170)
            if h > 2:
                d.rounded_rectangle([x0, base_y - h, x0 + bw, base_y], radius=int(14 * self.u), fill=col)
            vt = text_block(f"{v * p:,.0f}{unit}" if float(v).is_integer() else f"{v * p:,.1f}{unit}", 52 * self.u, bw * 1.6, self.col, self.acc, stroke=int(3 * self.u))
            paste(c, vt, x0 + bw / 2, base_y - h - 45 * self.u, alpha=min(1, p * 2))
            lt = self.tb(f"bl{i}", str(lab), 44 * self.u, bw * 1.6, self.col, self.acc, bold=False)
            paste(c, lt, x0 + bw / 2, base_y + 45 * self.u)

    def draw_compare(self, c, t):
        L, R = self.d.get("left", {}), self.d.get("right", {})
        gap = 75 * self.u  # room for the VS badge between the columns
        colw = (self.W * (0.92 if self.vert else 0.72)) / 2 - gap
        for side, info, sign, color in ((0, L, -1, (255, 90, 90, 255)), (1, R, 1, self.acc)):
            p = ease_out((t - 0.15 * side) / 0.45)
            key = f"col{side}"
            if key not in self.cache:
                head = text_block(info.get("title", ""), 70 * self.u, colw - 40 * self.u, color, color, stroke=int(4 * self.u))
                rows = [text_block("• " + s, 48 * self.u, colw - 50 * self.u, self.col, self.acc, bold=False, align="left") for s in info.get("items", [])]
                h = head.height + sum(r.height + 18 * self.u for r in rows) + 90 * self.u
                card = rounded(colw, h, 30 * self.u, (255, 255, 255, 30), outline=color, width=int(4 * self.u))
                card.alpha_composite(head, (int((colw - head.width) / 2), int(30 * self.u)))
                y = head.height + 55 * self.u
                for r in rows:
                    card.alpha_composite(r, (int(28 * self.u), int(y))); y += r.height + 18 * self.u
                self.cache[key] = card
            card = self.cache[key]
            paste(c, card, self.W / 2 + sign * (colw / 2 + gap) + sign * (1 - p) * 120 * self.u, self.cy, alpha=p)
        vs = self.tb("vs", "VS", 56 * self.u, 300, (10, 10, 20, 255), self.acc)
        circ = rounded(110 * self.u, 110 * self.u, 55 * self.u, self.acc)
        circ.alpha_composite(vs, (int((circ.width - vs.width) / 2), int((circ.height - vs.height) / 2)))
        paste(c, circ, self.W / 2, self.cy, scale=ease_back((t - 0.4) / 0.3))

    def draw_quote(self, c, t):
        q = self.tb("q", "“", 300 * self.u, 400, self.acc, self.acc)
        paste(c, q, self.W / 2, self.cy - 260 * self.u, scale=ease_back(t / 0.3))
        im = self.tb("main", self.d.get("text", ""), 84 * self.u, self.maxw, self.col, self.acc, self.d.get("highlight"), stroke=int(4 * self.u))
        paste(c, im, self.W / 2, self.cy, alpha=ease_out((t - 0.15) / 0.4))
        if self.d.get("author"):
            a = self.tb("a", "— " + self.d["author"], 50 * self.u, self.maxw, (220, 220, 230, 255), self.acc, bold=False)
            paste(c, a, self.W / 2, self.cy + im.height / 2 + 70 * self.u, alpha=ease_out((t - 0.5) / 0.4))

    def draw_cta(self, c, t):
        lab = self.tb("main", self.d.get("text", ""), 76 * self.u, self.maxw - 80 * self.u, (10, 10, 20, 255), (10, 10, 20, 255))
        if "btn" not in self.cache:
            b = rounded(lab.width + 110 * self.u, lab.height + 70 * self.u, 50 * self.u, self.acc)
            b.alpha_composite(lab, (int(55 * self.u), int(35 * self.u))); self.cache["btn"] = b
        pulse = 1 + 0.04 * math.sin(t * 6)
        paste(c, self.cache["btn"], self.W / 2, self.cy, scale=ease_back(t / 0.35) * pulse)


# ---------------- captions ----------------
def build_captions(scenes, max_words=3, max_chars=20):
    caps = []
    for sc in scenes:
        say = sc["data"].get("say")
        if not say:
            continue
        words = norm_words(say)
        chunks, cur = [], []
        for w in words:
            if cur and (len(cur) >= max_words or len(" ".join(cur + [w])) > max_chars):
                chunks.append(cur); cur = []
            cur.append(w)
            if re.search(r"[.!?,:;]$", w):
                chunks.append(cur); cur = []
        if cur:
            chunks.append(cur)
        span = sc.get("speech", sc["dur"] * 0.95)
        total = sum(len(" ".join(ch)) + 2 for ch in chunks) or 1
        t = sc["start"] + 0.05
        for ch in chunks:
            d = span * (len(" ".join(ch)) + 2) / total
            caps.append({"start": t, "end": t + d, "words": ch, "hl": sc["data"].get("highlight", [])}); t += d
    return caps


def srt_time(x):
    h, m = int(x // 3600), int(x % 3600 // 60); s = x % 60
    return f"{h:02}:{m:02}:{int(s):02},{int((s - int(s)) * 1000):03}"


# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard"); ap.add_argument("--out", required=True)
    ap.add_argument("--preview", action="store_true", help="half resolution, faster")
    a = ap.parse_args()
    base = os.path.dirname(os.path.abspath(a.storyboard))
    sb = json.load(open(a.storyboard, encoding="utf-8"))
    rel = lambda p: p if (not p or os.path.isabs(p)) else os.path.join(base, p)
    W, H = SIZES[sb.get("format", "9x16")]
    if a.preview:
        W, H = W // 2, H // 2
    fps = int(sb.get("fps", 30)); theme = sb.get("theme", {})
    bg_colors = theme.get("bg", ["#0B1026", "#1E2A78"]); accent = theme.get("accent", "#FFD400")

    # timing
    full_voice = rel(sb.get("voice"))
    scenes, t = [], 0.0
    if full_voice:
        vd = media_duration(full_voice); weights = [max(len(s.get("say", "")), 1) for s in sb["scenes"]]
        for s, w in zip(sb["scenes"], weights):
            share = vd * w / sum(weights); dur = max(share, float(s.get("duration", 0)) if not s.get("say") else share)
            scenes.append({"data": s, "start": t, "dur": dur, "speech": share}); t += dur
    else:
        for s in sb["scenes"]:
            v = rel(s.get("voice")); vd = media_duration(v) if v else 0
            dur = max(float(s.get("duration", 3)), vd + 0.35 if vd else 0)
            sc = {"data": s, "start": t, "dur": dur, "voice": v}
            if vd:
                sc["speech"] = vd
            scenes.append(sc); t += dur
    total = t
    print(f"Rendering {len(scenes)} scenes, {total:.1f}s at {W}x{H}@{fps}")

    caps = build_captions(scenes) if sb.get("captions", True) else []
    srt_path = os.path.splitext(a.out)[0] + ".srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, cp in enumerate(caps, 1):
            f.write(f"{i}\n{srt_time(cp['start'])} --> {srt_time(cp['end'])}\n{' '.join(cp['words'])}\n\n")

    tmp = tempfile.mkdtemp()
    silent = os.path.join(tmp, "video.mp4")
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                            "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
    bg = Background(W, H, bg_colors, accent)
    u = min(W, H) / 1080; vert = H > W
    cap_y = H * (0.665 if vert else 0.86)
    col, acc = hex2rgb(theme.get("text", "#FFFFFF")), hex2rgb(accent)
    nframes = int(math.ceil(total * fps)); si = 0
    objs = {}; media = {}
    cap_cache = {}
    for fi in range(nframes):
        tt = fi / fps
        while si < len(scenes) - 1 and tt >= scenes[si]["start"] + scenes[si]["dur"]:
            if si in media:
                media.pop(si).close()
            si += 1
        sc = scenes[si]; lt = tt - sc["start"]
        if si not in objs:
            objs = {si: Scene(sc["data"], W, H, theme, sc["start"], sc["dur"])}
            if sc["data"].get("bg"):
                media[si] = MediaBG(rel(sc["data"]["bg"]), W, H, fps, sc["dur"])
        frame = media[si].frame(lt, sc["dur"]) if si in media else bg.frame(tt)
        objs[si].draw(frame, lt)
        # captions: current chunk, current word highlighted
        cp = next((c for c in caps if c["start"] <= tt < c["end"]), None)
        if cp:
            k = id(cp)
            n = len(cp["words"]); wi = min(n - 1, int((tt - cp["start"]) / max(cp["end"] - cp["start"], 0.01) * n))
            key = (k, wi)
            if key not in cap_cache:
                words = cp["words"]
                hl_phr = [words[wi]] + list(cp["hl"])
                cap_cache[key] = text_block(" ".join(words), 74 * u, W * 0.78, col, acc, hl_phr, stroke=int(7 * u))
            pop = ease_back((tt - cp["start"]) / 0.12) if wi == 0 else 1.0
            paste(frame, cap_cache[key], W / 2, cap_y, scale=0.85 + 0.15 * pop)
        if sb.get("progress_bar", True):
            d = ImageDraw.Draw(frame)
            d.rectangle([0, 0, W, int(10 * u)], fill=(255, 255, 255, 50))
            d.rectangle([0, 0, int(W * tt / total), int(10 * u)], fill=acc)
        enc.stdin.write(frame.convert("RGB").tobytes())
        if fi % (fps * 5) == 0:
            print(f"  {tt:5.1f}s / {total:.1f}s", flush=True)
    for m in media.values():
        m.close()
    enc.stdin.close(); enc.wait()

    # audio: voices + music
    inputs, chains, labels = ["-i", silent], [], []
    idx = 1
    if full_voice:
        inputs += ["-i", full_voice]; chains.append(f"[{idx}:a]aresample=48000,volume=1.0[v{idx}]"); labels.append(f"[v{idx}]"); idx += 1
    else:
        for sc in scenes:
            if sc.get("voice"):
                ms = int(sc["start"] * 1000)
                inputs += ["-i", sc["voice"]]
                chains.append(f"[{idx}:a]aresample=48000,adelay={ms}|{ms},volume=1.0[v{idx}]"); labels.append(f"[v{idx}]"); idx += 1
    music = sb.get("music", "auto")
    if music:
        mpath = os.path.join(tmp, "music.wav") if music == "auto" else rel(music)
        if music == "auto":
            make_music(mpath, total + 1)
        vol = float(sb.get("music_volume", 0.12 if labels else 0.5))
        inputs += ["-stream_loop", "-1", "-i", mpath]
        chains.append(f"[{idx}:a]aresample=48000,volume={vol}[m]"); labels.append("[m]"); idx += 1
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs]
    if labels:
        fc = ";".join(chains + [f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,"
                                f"alimiter=limit=0.95[aout]"])
        cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-map", "0:v"]
    cmd += ["-t", f"{total:.3f}", "-c:v", "copy", "-movflags", "+faststart", a.out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("ffmpeg mux failed:\n" + r.stderr[-1500:])
    print(f"Saved {a.out} ({total:.1f}s) and {srt_path}")


if __name__ == "__main__":
    main()
