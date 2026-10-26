# viral-video-studio — ZCode (Z.ai, GLM) skill

Competitor analysis → topic options → script → finished video, thumbnails and captions for TikTok / YouTube Shorts / YouTube.

## Install
- macOS / Linux: `./install.sh` (all workspaces) or `./install.sh /path/to/project` (one project)
- Windows: `powershell -ExecutionPolicy Bypass -File .\install.ps1` (or add a project path)
- Manual: copy the `viral-video-studio` folder into `~/.zcode/skills/` (Windows: `%USERPROFILE%\.zcode\skills\`) or `<project>/.zcode/skills/`.

Then in ZCode: **Settings → Skills → Refresh**, check the skill is enabled, and type `$viral-video-studio` in chat (or just describe what you want; it triggers automatically).

## Requirements
- Python 3.9+ with Pillow and numpy (`setup_check.py --install` installs them)
- ffmpeg (macOS: `brew install ffmpeg`; Windows: `winget install --id Gyan.FFmpeg -e`; Linux: `sudo apt install ffmpeg`)
- Recommended MCP servers (GLM Coding Plan): Vision MCP (`@z_ai/mcp-server`, Node.js 22+) for checking frames; web-search-prime and web-reader for research.
- Optional API keys as environment variables: `YOUTUBE_API_KEY`, `FPT_API_KEY`, `ELEVENLABS_API_KEY`, `GOOGLE_TTS_API_KEY`, `GEMINI_API_KEY`, `FAL_KEY`, `PEXELS_API_KEY`.

## Contents
- `SKILL.md` — the workflow the agent follows
- `references/` — detailed guides (competitor analysis, topics, scripts, platform specs, Gemini/Canva prompts, agent-only rendering, third-party providers)
- `scripts/` — `setup_check.py`, `yt_competitor.py`, `render_storyboard.py`, `make_thumbnail.py`, `assemble_video.py`, `providers.py`, `fonts.py`
- `assets/fonts/` — Inter (SIL Open Font License 1.1, see OFL.txt)
- `examples/storyboard_example.json`
