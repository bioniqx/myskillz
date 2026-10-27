---
name: viral-video-studio
description: Make viral TikTok, YouTube Shorts or long-form YouTube videos at the lowest cost. Use when the user wants competitor channel analysis, video topic ideas, a video script, a finished video, thumbnail or caption, or types $viral-video-studio. Covers competitor outlier analysis, topic scoring, scripts with hooks, production in 3 modes (Gemini Pro + Canva prompts; agent renders motion-graphics video locally for free; third-party APIs such as FPT.AI, ElevenLabs, Pexels, Gemini, fal.ai), thumbnails, captions and post-publish optimization.
---

# Viral Video Studio (ZCode / GLM edition)

You run on the user's own computer inside ZCode. You can run shell commands, read/write files, and use MCP tools. Follow this file step by step. Do not skip the two approval gates.

Reply in the user's language. Write prompts for Veo / Nano Banana / other image-video models in English. Keep on-screen text, captions and voiceover in the audience's language.

## Step 0 — Locate this skill and check the machine (do this first, once per session)

1. Find the skill folder (`SKILL_DIR`). Check in this order and use the first that contains `scripts/render_storyboard.py`:
   - `<workspace>/.zcode/skills/viral-video-studio`
   - `<workspace>/.agents/skills/viral-video-studio`
   - `~/.zcode/skills/viral-video-studio`
   - `~/.agents/skills/viral-video-studio`
   - `~/.claude/skills/viral-video-studio`
   On Windows `~` is `%USERPROFILE%`. Always call scripts by their full path: `"<SKILL_DIR>/scripts/<script>.py"`.
2. Pick the Python command: try `python3 --version`; if it fails (common on Windows) use `python` or `py -3`. Call it `PY` below.
3. Run `PY "<SKILL_DIR>/scripts/setup_check.py"`.
   - If Pillow/numpy are missing: ask the user, then run it again with `--install`.
   - If ffmpeg is missing: show the user the exact install command the check printed (brew / winget / apt) and ask them to run it, or run it yourself if they agree. Then re-run the check.
   - Continue only when it prints `READY`. Stages 1–3 (research and script) do not need ffmpeg, so you can start them while the user installs it.
4. Create an output folder in the workspace: `video-output/<slug>/` (slug = short topic name, ASCII, hyphens). Put every deliverable there.

## Tools you use (ZCode)

| Need | Tool |
|---|---|
| Web search / read pages | `web-search-prime` and `web-reader` MCP servers if enabled; otherwise your built-in web tools; otherwise ask the user to paste data |
| Look at an image or video frame | Vision MCP (`@z_ai/mcp-server`): `image_analysis` for frames and thumbnails, `video_analysis` for a finished MP4 ≤ 8 MB. Pass the local file path |
| Run scripts | Shell / terminal tool |
| Ask the user | Plain chat message with numbered options; wait for the answer |
| Track progress | Your todo/plan tool if available; otherwise a short checklist in chat |

If the Vision MCP is not enabled, tell the user once that it lets you check the video visually (needs a GLM Coding Plan key, `Z_AI_API_KEY`, `Z_AI_MODE=ZAI`, Node.js 22+), then fall back to checking with ffprobe numbers and asking the user to look at the frame files.

## Three production modes (choose in Stage 0, can mix per step)

| Mode | When | Visuals | Voice | Editing + thumbnail | Reference |
|---|---|---|---|---|---|
| **A. Gemini Pro + Canva** | User has both subscriptions | Veo / Flow, Nano Banana (user pastes your prompts) | Veo or self-recorded | Canva, or `assemble_video.py` | `references/gemini-prompts.md`, `references/canva-prompts.md` |
| **B. Agent does everything** | Zero budget | Motion graphics rendered locally by `render_storyboard.py` | Self-recorded / edge-tts / FPT.AI free tier / none | `render_storyboard.py`, `make_thumbnail.py` | `references/agent-only.md` |
| **C. Third-party services** | User has API keys | Gemini Omni Flash, fal.ai (Kling, Seedance…), Pexels stock video | FPT.AI (free 100,000 chars/month), ElevenLabs, Google TTS | Same as B | `references/providers.md` |

If the user does not say, default to B and add C for any step where a key is already set (setup_check lists them).

Rules for mode C: before any paid call, tell the user how many calls and the estimated cost, and wait for "yes". Read API keys only from environment variables. Never write a key into any file, script, caption or chat output. If the user pastes a key in chat, use it only as an environment variable for that one command and suggest they rotate it later.

## Cost rules

| Task | Cheapest tool | Notes |
|---|---|---|
| YouTube competitor data | YouTube Data API v3 (free, 10,000 units/day) via `yt_competitor.py` with `YOUTUBE_API_KEY` | `search.list` = 100 units; per-channel lookups = 1 unit. Prefer channels |
| TikTok trends | TikTok Creative Center (free) + competitor profile pages | See `references/competitor-analysis.md` |
| Deep research alternative | Gemini Deep Research (Gemini Pro) | Prompt in `references/gemini-prompts.md` |
| AI footage (mode A) | Veo 3.1 in Google Flow: Lite 10 / Fast 20 / Quality 100 credits per 8s clip; Pro plan 1,000 credits/month + 50 free/day; Gemini app up to 3 Veo Fast videos/day | Draft with Lite, final with Fast, outputs per prompt = 1 |
| Images | Nano Banana Pro (Gemini app) | |
| Editing / subtitles / thumbnail | Local scripts (free) or Canva | |
| Title + thumbnail testing | YouTube Studio "Test & Compare" (up to 3 variants, winner by watch time) | |

Prices and limits change often. If web search works, re-check them before budgeting. Every script in Stage 3 must include a cost/credit budget.

## Stage 0 — Intake (one message, wait for the answer)

Ask only what is unknown, as one numbered list:
1. Niche / channel topic, target market, language.
2. Platform: TikTok, YouTube Shorts, long-form YouTube (8–15 min), or several.
3. Known competitors (links or @handles) — optional.
4. Format: on camera or faceless.
5. Monetization goal: ads revenue / TikTok Creator Rewards / affiliate / own product.
6. Production mode: Gemini Pro + Canva? Any API keys (YouTube, FPT.AI, ElevenLabs, Pexels, Gemini, fal)? 

## Stage 1 — Competitor analysis (you do it)

Read `references/competitor-analysis.md`, then:
1. Find 5–10 competitor channels/accounts.
2. Get the latest 30 videos per channel (views, date, length, title):
   - YouTube with key: `PY "<SKILL_DIR>/scripts/yt_competitor.py" --channels @a @b --per-channel 30 --out video-output/<slug>/yt_report`
   - Without key: read channel `/videos` and `/shorts` pages with web-reader or search.
   - TikTok: Creative Center trends + profile pages.
3. Outlier score = views ÷ median views of that channel's latest 30 videos. ≥ 3× = outlier.
4. Break down the top 10 outliers (hook, title formula, length, pace, thumbnail, emotion, CTA).
5. List gaps: unanswered comment questions, missing angles, formats not yet in the user's market.

If data is unreachable, say so and give the user the Gemini Deep Research prompt from `references/gemini-prompts.md`. Never invent numbers; write "no data" instead. Save the result as `video-output/<slug>/1_competitors.md`.

## Stage 2 — Topic options → APPROVAL GATE 1

Read `references/topic-selection.md`. Give 5 options, each with: working title, one-line hook, evidence (outlier links + scores), scores for Demand / Gap / Retention / Cost / Monetization (1–5 each, total /25), estimated cost. Mark the recommended one.

**STOP. Wait for the user to pick one.** Save as `2_topics.md`.

## Stage 3 — Full script → APPROVAL GATE 2

Read `references/script-template.md` and `references/platform-specs.md`. Write:
1. 3 titles + 3 hooks of different types
2. Timed table: seconds | voiceover | on-screen text | visuals | sound
3. Shot list: mode A → full Veo prompt per 8s shot; mode B → storyboard scene type per shot; mode C → stock query or AI video prompt per shot
4. Budget + cheaper alternatives
5. CTA + loop ending

Save as `3_script.md`. **STOP. Wait for approval.** Revise until approved.

## Stage 4 — Production

**Mode B (default)** — follow `references/agent-only.md`:
1. Convert the approved script to `video-output/<slug>/storyboard.json` (copy the structure of `<SKILL_DIR>/examples/storyboard_example.json`).
2. Voice (optional): user recording, or `PY "<SKILL_DIR>/scripts/providers.py" tts-storyboard video-output/<slug>/storyboard.json --engine fpt|edge|elevenlabs|google --outdir video-output/<slug>/voices`
3. Quick preview: `PY "<SKILL_DIR>/scripts/render_storyboard.py" video-output/<slug>/storyboard.json --out video-output/<slug>/preview.mp4 --preview`
4. Check it (see "Visual check" below), fix the storyboard, then render final without `--preview` to `final.mp4` (also writes `final.srt`).
5. Thumbnails: `PY "<SKILL_DIR>/scripts/make_thumbnail.py" --text "MAX 4 WORDS" --highlight "WORD" --sub "short line" --format 16x9 --out video-output/<slug>/thumb` (3 variants A/B/C; use `--format 9x16` for a TikTok/Shorts cover; add `--image photo.png` for a face/background).

**Mode C** — follow `references/providers.md`: TTS + Pexels stock (`providers.py stock`) as scene `bg`, or 1–2 AI video hook clips (`providers.py video`), then render as in mode B or join clips with `assemble_video.py`.

**Mode A** — deliver a production pack in the output folder: `veo_prompts.md` (prompt per shot, model, ratio, retry prompt), `thumbnail_prompts.md` (3 Nano Banana prompts + 3 text options + Canva prompt from `references/canva-prompts.md`), `subtitles.srt`, and editing steps. When the user drops the Veo clips into the folder, join them:
`PY "<SKILL_DIR>/scripts/assemble_video.py" --clips c1.mp4 c2.mp4 ... --voice voice.mp3 --srt subtitles.srt --format 9x16 --trim-head 0.3 --out final.mp4`

**Every mode** — also write `caption.md`: caption + hashtags per platform, YouTube description with keywords, pinned comment.

### Visual check (required before delivering)
1. Extract frames: `ffmpeg -v error -y -ss <sec> -i final.mp4 -frames:v 1 frame_<sec>.png` at 1s, the middle, and 2s before the end (plus one frame per scene type you used).
2. Check each frame with `image_analysis`: is all text fully visible, correctly spelled with diacritics, not overlapping, and outside the bottom 15% / right edge (TikTok buttons)? If the file is ≤ 8 MB you may also run `video_analysis` on the whole video.
3. Fix and re-render if anything fails. Then tell the user the file paths.

## Stage 5 — Publish and optimize

Use the "After publishing" section of `references/platform-specs.md`: Test & Compare on YouTube, check 3-second retention and the retention curve after 48 hours, log which hook won in `video-output/hook_log.md` (create it if missing) and read that log at the start of the next video.

## Quality rules

- Never invent competitor numbers or statistics; every number in `stat`/`bars` scenes needs a source cited in the caption or description.
- Never copy others' scripts, copyrighted music, characters or brands. Learn structure, make original content.
- Finance/health topics: add a short disclaimer, never promise returns.
- The hook must match the real content.
- Do not delete user files. Only write inside `video-output/`.
