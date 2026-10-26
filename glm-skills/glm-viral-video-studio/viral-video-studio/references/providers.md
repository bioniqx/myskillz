# Mode C — Third-party services

Each step is chosen independently. The three modes can be mixed, e.g. visuals rendered by the agent (B) + FPT.AI voice (C) + Canva thumbnail (A).
Prices and limits were checked in October 2026 and change often. Before the user pays for anything, re-check the official pricing page.

## 0. Where API calls run
In ZCode the scripts run on the user's own computer, so they can reach FPT.AI, ElevenLabs, Pexels, Gemini and fal directly (unless a company firewall/VPN blocks them).

Set keys as environment variables for the command only, e.g.
- macOS/Linux: `FPT_API_KEY=xxx python3 "<SKILL_DIR>/scripts/providers.py" tts ...`
- Windows PowerShell: `$env:FPT_API_KEY="xxx"; python "<SKILL_DIR>\scripts\providers.py" tts ...`
Or ask the user to add them to their shell profile / system environment once.

Always run `providers.py check` first to see which keys are set and which services are reachable.

## 1. MCP servers in ZCode (configure once in ZCode settings)
Built into the GLM Coding Plan:
- **Vision MCP** (`@z_ai/mcp-server`): `image_analysis`, `video_analysis` (≤ 8 MB MP4/MOV/M4V) and others → used for the visual check. Needs `Z_AI_API_KEY`, `Z_AI_MODE=ZAI`, Node.js 22+.
- **web-search-prime** and **web-reader**: web search and page reading for stage 1.

Optional third-party services. Some publish remote MCP servers that can be added in ZCode's MCP settings; check the vendor's docs for the current MCP URL. If there is none, the user can use the vendor's web app and paste results, or use an API key with `scripts/providers.py` where supported.

| Service | Use for | Notes |
|---|---|---|
| vidIQ | Stage 1: outliers, keyword research, trending videos, channel stats (YouTube, Instagram, TikTok) | Replaces / complements the YouTube Data API |
| Canva | Thumbnails, covers, design autofill, export | Needs a Canva account |
| HyperFrames by HeyGen | Build motion graphics / animated slides in HTML and render to video | Alternative to render_storyboard.py for more complex effects |
| TikTok for Business, AdWhispr | Research / run TikTok ads | Only with an ad budget |
| Supermetrics | Pull YouTube/TikTok analytics after publishing | Stage 5 |


## 2. Voiceover (TTS)

| Provider | Price | Command |
|---|---|---|
| FPT.AI TTS v5 (Vietnamese) | Free 100,000 characters/month (slow queue, daily request limit). Paid packs from 500,000 VND for 1.5 million characters | `providers.py tts --engine fpt --voice banmai` |
| ElevenLabs | Free 10,000 credits/month, Starter $6 / 30,000. Vietnamese is only available on `eleven_v3` and `eleven_flash_v2_5` (not on Multilingual v2) | `providers.py tts --engine elevenlabs --model eleven_flash_v2_5` |
| Google Cloud Text-to-Speech | Monthly free tier depending on voice type (see the Cloud pricing page) | `providers.py tts --engine google --voice vi-VN-Neural2-A` |
| edge-tts (Microsoft Edge voices) | Free, unofficial; needs network access to Microsoft | `providers.py tts --engine edge --voice vi-VN-HoaiMyNeural` |

Estimate: a 45-second video ≈ 120 words ≈ 550 characters → the FPT free tier covers about 180 videos/month.

## 3. AI footage (text-to-video)

| Service | Reference price | Notes |
|---|---|---|
| Gemini API — Gemini Omni Flash (`gemini-omni-1.1-flash`) | See the Gemini API pricing page | Google recommends migrating to this model because the Veo 3.1 preview models on the Gemini API were scheduled to shut down on 22 Oct 2026. Generates audio. Google has only fully evaluated English; other languages may vary → make the voiceover separately. `providers.py video --engine gemini-omni` |
| Veo 3.1 GA | On Gemini Enterprise / Vertex AI | For Google Cloud business accounts |
| Runway API | Gen-4 Turbo $0.05/second, Gen-4.5 $0.12/second | |
| Kling 3.0 | 6–8 credits/second without audio, 9–12 with audio; prepaid packs from ~$9.80 | |
| Seedance 2.0 / Hailuo | Via resellers: Seedance 720p ~$0.045–0.05/second; Hailuo 768p ~$0.04/second | Access via fal.ai: `providers.py video --engine fal --model <fal model id>` |
| Sora 2 | Not available | OpenAI removed the Videos API on 24 Sep 2026 |

Savings: use AI video only for the hook (1–2 clips). Use free stock video or the agent's motion graphics for the rest.

## 4. Free stock video/images
- **Pexels API**: free, 200 requests/hour, 20,000 requests/month. Search with `orientation=portrait` for vertical video. Attribution to Pexels is required; crediting the creator is recommended. Command: `providers.py stock --query "..." --orientation portrait --n 3` (writes `credits.txt` automatically).

## 5. Cloud video rendering (only at high volume)

| Service | Price |
|---|---|
| Shotstack | 10 free credits (30 days); pay-as-you-go $10 / 25 credits; $39/month / 200 credits; 1 credit = 1 minute of video ≤1080p; free sandbox is watermarked |
| Creatomate | 50-credit trial (capped at 480px); Essential $54/month / 2,000 credits; 1 minute of 1080p 30fps ≈ 37 credits |

For beginners: `render_storyboard.py` and `assemble_video.py` (free, run locally) are enough. Only pay for cloud rendering when making dozens of videos per day.

## 6. Automated publishing
- **TikTok Content Posting API**: unaudited apps can only post in private mode; an audit is required for public posting. Needs the `video.publish` scope. → For individuals: post manually or use a scheduling tool already approved by TikTok.
- **YouTube**: upload through YouTube Studio (fastest, and has Test & Compare). Uploading via the API needs OAuth and quota; only worth it at high volume.

## 7. API key safety rules
- Advise the user to create a dedicated key, set a low spending limit (ElevenLabs, fal and Google Cloud all allow limits), and delete/rotate the key afterwards.
- The agent passes keys as environment variables of the command and never writes keys into any file, script, caption or log.
- Never put keys in scripts, captions or artifacts.
- Before every paid call: state the number of calls and the estimated cost, and wait for the user's approval.

## Environment variables read by providers.py
`FPT_API_KEY`, `ELEVENLABS_API_KEY`, `GOOGLE_TTS_API_KEY`, `GEMINI_API_KEY`, `FAL_KEY`, `PEXELS_API_KEY`
Run `python3 scripts/providers.py check` to see which keys are set and whether each service is reachable.
