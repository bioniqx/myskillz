#!/usr/bin/env python3
"""Connect third-party services for video production. Keys come from environment variables only.

  FPT_API_KEY  ELEVENLABS_API_KEY  GOOGLE_TTS_API_KEY  GEMINI_API_KEY  FAL_KEY  PEXELS_API_KEY

Commands
  check                                   which keys are set + which services are reachable
  tts   --engine fpt|elevenlabs|google|edge --text "..." | --text-file f.txt --out voice.mp3 [--voice X]
  tts-storyboard storyboard.json --engine fpt [--outdir voices]   one voice file per scene ("say"), writes paths back
  stock --query "city night" [--orientation portrait] [--n 3] [--outdir stock]     Pexels videos + credits.txt
  video --engine gemini-omni --prompt "..." [--aspect 9:16] [--resolution 720p] --out clip.mp4
  video --engine fal --model <fal model id> --prompt "..." [--extra '{"duration":5}'] --out clip.mp4

Every paid call is the caller's responsibility: the agent must state the cost and get approval first.
"""
import argparse, base64, json, os, subprocess, sys, time, urllib.error, urllib.parse, urllib.request

UA = {"User-Agent": "viral-video-studio/1.0"}



try:  # print Unicode safely on Windows consoles
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def http(method, url, headers=None, body=None, timeout=120, raw=False):
    h = dict(UA, **(headers or {}))
    data = None
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode(); h.setdefault("Content-Type", "application/json")
        elif isinstance(body, str):
            data = body.encode("utf-8")
        else:
            data = body
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            content = r.read()
            return content if raw else json.loads(content or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} from {urllib.parse.urlsplit(url).netloc}: {e.read().decode(errors='ignore')[:500]}")
    except urllib.error.URLError as e:
        sys.exit(f"Cannot reach {urllib.parse.urlsplit(url).netloc} ({e.reason}). "
                 "Network may be blocked in this environment; run on your own computer or use another engine.")


def key(name):
    v = os.environ.get(name)
    if not v:
        sys.exit(f"Missing {name}. Set it as an environment variable for this command.")
    return v


def download(url, out, headers=None):
    with open(out, "wb") as f:
        f.write(http("GET", url, headers=headers, raw=True, timeout=600))
    return out


# ---------------- TTS ----------------
def tts_fpt(text, out, voice="banmai", speed="0"):
    r = http("POST", "https://api.fpt.ai/hmi/tts/v5", body=text,
             headers={"api_key": key("FPT_API_KEY"), "voice": voice or "banmai", "speed": str(speed), "format": "mp3"})
    if r.get("error") != 0:
        sys.exit(f"FPT.AI error: {r}")
    link = r["async"]
    for _ in range(60):  # audio ready in ~5s to 2min
        try:
            with urllib.request.urlopen(urllib.request.Request(link, headers=UA), timeout=30) as resp:
                data = resp.read()
                if len(data) > 1000:
                    open(out, "wb").write(data); return out
        except urllib.error.HTTPError:
            pass
        time.sleep(3)
    sys.exit("FPT.AI audio not ready after 3 minutes: " + link)


def tts_elevenlabs(text, out, voice=None, model="eleven_flash_v2_5"):
    voice = voice or "JBFqnCBsd6RMkjVDRZzb"  # a premade voice id from ElevenLabs docs; pick your own in the Voice Library
    body = {"text": text, "model_id": model}
    if model == "eleven_flash_v2_5":
        body["language_code"] = "vi"
    data = http("POST", f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
                headers={"xi-api-key": key("ELEVENLABS_API_KEY"), "Accept": "audio/mpeg"}, body=body, raw=True)
    open(out, "wb").write(data); return out


def tts_google(text, out, voice=None, speed=1.0):
    v = {"languageCode": "vi-VN"}
    if voice:
        v["name"] = voice
    r = http("POST", "https://texttospeech.googleapis.com/v1/text:synthesize?key=" + key("GOOGLE_TTS_API_KEY"),
             body={"input": {"text": text}, "voice": v, "audioConfig": {"audioEncoding": "MP3", "speakingRate": float(speed)}})
    open(out, "wb").write(base64.b64decode(r["audioContent"])); return out


def tts_edge(text, out, voice="vi-VN-HoaiMyNeural", speed="+0%"):
    try:
        import edge_tts  # noqa
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--break-system-packages", "edge-tts"], check=False)
    r = subprocess.run([sys.executable, "-m", "edge_tts", "--voice", voice or "vi-VN-HoaiMyNeural",
                        "--rate", speed if str(speed).endswith("%") else "+0%", "--text", text, "--write-media", out],
                       capture_output=True, text=True)
    if r.returncode or not os.path.exists(out):
        sys.exit("edge-tts failed (needs network access to Microsoft): " + r.stderr[-400:])
    return out


def tts(engine, text, out, voice=None, model=None, speed=None):
    if engine == "fpt":
        return tts_fpt(text, out, voice, speed or "0")
    if engine == "elevenlabs":
        return tts_elevenlabs(text, out, voice, model or "eleven_flash_v2_5")
    if engine == "google":
        return tts_google(text, out, voice, speed or 1.0)
    if engine == "edge":
        return tts_edge(text, out, voice, speed or "+0%")
    sys.exit("Unknown engine")


# ---------------- Stock (Pexels) ----------------
def stock(query, orientation, n, outdir):
    os.makedirs(outdir, exist_ok=True)
    q = urllib.parse.urlencode({"query": query, "orientation": orientation, "size": "medium", "per_page": max(n * 2, 5)})
    r = http("GET", "https://api.pexels.com/v1/videos/search?" + q, headers={"Authorization": key("PEXELS_API_KEY")})
    got, credits = [], []
    for v in r.get("videos", []):
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("width")]
        if not files:
            continue
        target = 1080 if orientation == "portrait" else 1920
        f = min(files, key=lambda f: abs((f["width"] if orientation != "portrait" else f["width"]) - target))
        path = os.path.join(outdir, f"pexels_{v['id']}.mp4")
        download(f["link"], path)
        got.append(path)
        credits.append(f"Video by {v.get('user', {}).get('name', 'unknown')} on Pexels: {v.get('url')}")
        if len(got) >= n:
            break
    with open(os.path.join(outdir, "credits.txt"), "a", encoding="utf-8") as fh:
        fh.write("\n".join(credits) + "\n")
    print("\n".join(got) or "No results"); print("Attribution saved to", os.path.join(outdir, "credits.txt"))


# ---------------- AI video ----------------
def find_url(obj):
    if isinstance(obj, str) and obj.startswith("http") and (".mp4" in obj or "video" in obj):
        return obj
    if isinstance(obj, dict):
        for k in ("video", "url", "videos", "output"):
            if k in obj:
                u = find_url(obj[k])
                if u:
                    return u
        for v in obj.values():
            u = find_url(v)
            if u:
                return u
    if isinstance(obj, list):
        for v in obj:
            u = find_url(v)
            if u:
                return u
    return None


def video_gemini_omni(prompt, out, aspect="9:16", resolution="720p"):
    k = key("GEMINI_API_KEY")
    r = http("POST", "https://generativelanguage.googleapis.com/v1beta/interactions",
             headers={"x-goog-api-key": k},
             body={"model": "gemini-omni-1.1-flash", "input": prompt,
                   "response_format": {"type": "video", "aspect_ratio": aspect, "resolution": resolution}},
             timeout=900)
    for step in r.get("steps", []):
        if step.get("type") == "model_output":
            for c in step.get("content", []):
                if c.get("type") == "video":
                    if c.get("data"):
                        open(out, "wb").write(base64.b64decode(c["data"])); return out
                    if c.get("uri"):
                        return download(c["uri"], out, headers={"x-goog-api-key": k})
    sys.exit("No video in response: " + json.dumps(r)[:600])


def video_fal(model, prompt, out, extra=None):
    h = {"Authorization": "Key " + key("FAL_KEY")}
    body = {"prompt": prompt}
    body.update(extra or {})
    r = http("POST", f"https://queue.fal.run/{model}", headers=h, body=body)
    status_url, response_url = r.get("status_url"), r.get("response_url")
    if not status_url:
        sys.exit("Unexpected fal response: " + json.dumps(r)[:400])
    for _ in range(240):
        s = http("GET", status_url, headers=h)
        if s.get("status") == "COMPLETED":
            break
        if s.get("status") in ("FAILED", "ERROR"):
            sys.exit("fal job failed: " + json.dumps(s)[:400])
        time.sleep(5)
    res = http("GET", response_url, headers=h)
    url = find_url(res)
    if not url:
        sys.exit("No video URL in result: " + json.dumps(res)[:600])
    return download(url, out)


# ---------------- check ----------------
SERVICES = {
    "YOUTUBE_API_KEY": "https://www.googleapis.com",
    "FPT_API_KEY": "https://api.fpt.ai", "ELEVENLABS_API_KEY": "https://api.elevenlabs.io",
    "GOOGLE_TTS_API_KEY": "https://texttospeech.googleapis.com", "GEMINI_API_KEY": "https://generativelanguage.googleapis.com",
    "FAL_KEY": "https://queue.fal.run", "PEXELS_API_KEY": "https://api.pexels.com",
    "(edge-tts)": "https://speech.platform.bing.com",
}


def check():
    print(f"{'service':22} {'key':6} reachable")
    for k, url in SERVICES.items():
        has = "-" if k.startswith("(") else ("yes" if os.environ.get(k) else "no")
        try:
            urllib.request.urlopen(urllib.request.Request(url, headers=UA, method="HEAD"), timeout=6); ok = "yes"
        except urllib.error.HTTPError:
            ok = "yes"  # server answered
        except Exception:
            ok = "NO (blocked/offline)"
        print(f"{k:22} {has:6} {ok}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("check")
    t = sp.add_parser("tts"); t.add_argument("--engine", required=True, choices=["fpt", "elevenlabs", "google", "edge"])
    t.add_argument("--text"); t.add_argument("--text-file"); t.add_argument("--out", required=True)
    t.add_argument("--voice"); t.add_argument("--model"); t.add_argument("--speed")
    ts = sp.add_parser("tts-storyboard"); ts.add_argument("storyboard")
    ts.add_argument("--engine", required=True, choices=["fpt", "elevenlabs", "google", "edge"])
    ts.add_argument("--outdir", default="voices"); ts.add_argument("--voice"); ts.add_argument("--model"); ts.add_argument("--speed")
    s = sp.add_parser("stock"); s.add_argument("--query", required=True)
    s.add_argument("--orientation", default="portrait", choices=["portrait", "landscape", "square"])
    s.add_argument("--n", type=int, default=3); s.add_argument("--outdir", default="stock")
    v = sp.add_parser("video"); v.add_argument("--engine", required=True, choices=["gemini-omni", "fal"])
    v.add_argument("--prompt", required=True); v.add_argument("--out", required=True)
    v.add_argument("--aspect", default="9:16"); v.add_argument("--resolution", default="720p")
    v.add_argument("--model", help="fal model id"); v.add_argument("--extra", help="JSON with extra fal input fields")
    a = ap.parse_args()

    if a.cmd == "check":
        check()
    elif a.cmd == "tts":
        text = a.text or open(a.text_file, encoding="utf-8").read()
        print("Saved", tts(a.engine, text.strip(), a.out, a.voice, a.model, a.speed))
    elif a.cmd == "tts-storyboard":
        sb = json.load(open(a.storyboard, encoding="utf-8"))
        os.makedirs(a.outdir, exist_ok=True)
        chars = sum(len(sc.get("say", "")) for sc in sb["scenes"] if not sc.get("voice"))
        print(f"Synthesizing {chars} characters with {a.engine}...")
        for i, sc in enumerate(sb["scenes"], 1):
            if sc.get("say") and not sc.get("voice"):
                out = os.path.join(a.outdir, f"scene_{i:02}.mp3")
                tts(a.engine, sc["say"], out, a.voice, a.model, a.speed)
                sc["voice"] = os.path.abspath(out); print("  scene", i, "->", out)
        json.dump(sb, open(a.storyboard, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("Updated", a.storyboard)
    elif a.cmd == "stock":
        stock(a.query, a.orientation, a.n, a.outdir)
    elif a.cmd == "video":
        if a.engine == "gemini-omni":
            print("Saved", video_gemini_omni(a.prompt, a.out, a.aspect, a.resolution))
        else:
            if not a.model:
                sys.exit("--model is required for fal (copy the model id from fal.ai/models)")
            print("Saved", video_fal(a.model, a.prompt, a.out, json.loads(a.extra) if a.extra else None))


if __name__ == "__main__":
    main()
