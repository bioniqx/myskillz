# Mode B — The agent does everything (zero cost, no Gemini/Canva)

GLM in ZCode does not generate images or video. Instead the agent renders a **faceless motion-graphics video** locally with `render_storyboard.py`: animated text, counters, charts, lists, comparisons, word-by-word highlighted captions, a progress bar and generated (copyright-free) background music. This is a common format for finance, education, facts, top lists and news niches.

Requirements: Python 3.9+, Pillow, numpy, ffmpeg (run `setup_check.py`). The bundled Inter font supports Vietnamese and other Latin-diacritic languages. For other scripts (Chinese, Thai, Arabic…) set `VVS_FONT_BOLD` / `VVS_FONT_REGULAR` to a font that supports them.

## Good / bad fit
- Good fit: personal finance, education, interesting facts, top lists, comparisons, statistics, tips, book/news summaries.
- Poor fit: product reviews that need real footage, vlogs, food, travel, fashion → film on a phone, or add Pexels stock video as scene backgrounds (mode C), or AI video.

## Workflow
1. Approved script (stage 3) → write `video-output/<slug>/storyboard.json` (format below; start from `<SKILL_DIR>/examples/storyboard_example.json`). Each scene 2–6 seconds, one idea per scene. Relative file paths inside the storyboard are resolved from the storyboard's folder.
2. Voiceover, in order of preference:
   a. The user records their own voice (per scene, or one file for the whole video) and drops it into the output folder (most trustworthy).
   b. TTS: `PY "<SKILL_DIR>/scripts/providers.py" tts-storyboard storyboard.json --engine fpt` (FPT.AI is free for 100,000 characters/month; needs `FPT_API_KEY`). Writes one mp3 per scene and adds `"voice"` to each scene.
   c. `--engine edge` (free, no key; unofficial Microsoft Edge voices, e.g. `--voice vi-VN-HoaiMyNeural`).
   d. No voice: text + music video. Increase `duration` so viewers can read (~3 words/second) and keep captions on.
3. (Optional) Real background footage per scene: `providers.py stock --query "..." --outdir video-output/<slug>/stock` downloads Pexels videos → set `"bg": "stock/pexels_123.mp4"`. Keep `stock/credits.txt` and put the attribution in the description.
4. Preview: `PY "<SKILL_DIR>/scripts/render_storyboard.py" storyboard.json --out preview.mp4 --preview` (half resolution, fast). Final: same without `--preview`, `--out final.mp4`. A `.srt` with the same name is written next to the video.
5. Thumbnails: `PY "<SKILL_DIR>/scripts/make_thumbnail.py" --text "MAIN TEXT" --highlight "WORD" --sub "secondary line" --format 16x9 --out thumb` → `thumb_A.png`, `thumb_B.png`, `thumb_C.png` for Test & Compare. Add `--image` for a face/background photo (a cut-out PNG with transparency looks best).
6. Visual check (see SKILL.md): extract frames with ffmpeg, check them with the Vision MCP `image_analysis` tool, fix, re-render.

Render speed reference: a 28-second 1080×1920 video renders in roughly 30 seconds on a normal laptop CPU; `--preview` is about 4× faster.

## storyboard.json format
```json
{
  "format": "9x16",
  "fps": 30,
  "theme": {"bg": ["#0B1026", "#1E2A78"], "accent": "#FFD400", "text": "#FFFFFF"},
  "music": "auto",
  "music_volume": 0.12,
  "captions": true,
  "progress_bar": true,
  "scenes": [
    {"type": "hook", "text": "Stop saving money", "highlight": ["saving"], "say": "Stop saving money if you want to get rich.", "duration": 3},
    {"type": "stat", "value": "90%", "label": "of young people don't know this", "say": "...", "duration": 4},
    {"type": "bullets", "title": "3 mistakes", "items": ["Low-interest savings", "No emergency fund", "Emotional spending"], "say": "...", "duration": 6},
    {"type": "bars", "title": "10 years of compounding", "data": [["Year 1", 10], ["Year 5", 16], ["Year 10", 26]], "unit": "k", "say": "...", "duration": 5},
    {"type": "compare", "left": {"title": "Saving", "items": ["5% interest"]}, "right": {"title": "Investing", "items": ["Higher potential", "Has risk"]}, "say": "...", "duration": 5},
    {"type": "quote", "text": "Compound interest is the eighth wonder", "author": "Popular saying", "say": "...", "duration": 4},
    {"type": "text", "text": "Any sentence", "highlight": ["sentence"], "say": "...", "duration": 3},
    {"type": "cta", "text": "Follow for part 2", "say": "...", "duration": 3}
  ]
}
```
Top-level options:
- `format`: `9x16` (TikTok/Shorts), `16x9` (YouTube), `1x1`
- `theme`: two background gradient colors, accent color, text color (hex)
- `music`: `"auto"` (generated, copyright-free), a file path, or `null` for none
- `voice`: one voice file for the whole video; scene durations are then split by the length of each `say`

Fields shared by every scene:
- `say`: voiceover text (used for TTS and captions)
- `voice`: an existing voice file for this scene; overrides TTS
- `bg`: background image/video (a dark overlay is added automatically for readable text)
- `duration`: minimum seconds; if the voice is longer, the scene extends automatically
- `highlight`: words/phrases shown in the accent color

Writing tips for GLM: keep `text` ≤ 6 words for hook/text scenes, ≤ 5 bullet items, ≤ 6 bars; `value` in `stat` may include a prefix/suffix (e.g. `"$2,000"`, `"90%"`) and will count up.
