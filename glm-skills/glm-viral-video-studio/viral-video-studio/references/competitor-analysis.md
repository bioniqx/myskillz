# Competitor analysis — detailed method

## A. YouTube

### Option 1: YouTube Data API v3 (free, most accurate)
The user creates an API key once (5 minutes, free):
1. console.cloud.google.com → create a project
2. APIs & Services → Library → enable "YouTube Data API v3"
3. Credentials → Create credentials → API key

Quota: 10,000 units/day per project. Cost per call:
- `search.list`: 100 units (expensive — use sparingly)
- `channels.list`, `playlistItems.list`, `videos.list`: 1 unit (videos.list fetches up to 50 videos per call)

→ Analyzing 10 channels × 30 videos costs only about 30–50 units when going per channel instead of using search.

Run:
```
PY "<SKILL_DIR>/scripts/yt_competitor.py" --channels @handle1 @handle2 --per-channel 30 --out video-output/<slug>/yt_report
PY "<SKILL_DIR>/scripts/yt_competitor.py" --query "investing for beginners" --max-results 25 --region VN --out video-output/<slug>/yt_search
```
The key is read from the `YOUTUBE_API_KEY` environment variable (or `--api-key`). Never write the key into a file.
Output: `yt_report.csv` (one row per video, with outlier score, views/day, duration, is_short) and `yt_report.md` (top outliers).

If googleapis.com is unreachable (firewall/VPN): tell the user and switch to option 2 or 3.

### Option 2: vidIQ
If a vidIQ MCP server is configured in ZCode, use its outlier, trending-video, channel-stats and keyword-research tools instead of (or alongside) the API.

### Option 3: Web reader / search
- Read `youtube.com/@handle/videos` and `/shorts`, sort by "Popular", read titles + views.
- Take the median views of the 30 "Latest" videos to compute the outlier score.
- Read the top 50 comments of the 3 biggest outliers: look for repeated questions, complaints, requests for a follow-up.

## B. TikTok

1. **TikTok Creative Center** (ads.tiktok.com/creative/creativeCenter — free, basic browsing needs no login; best on desktop):
   - Trends → Hashtags: filter Country = target market, industry, 7/30 days. Note rising hashtags.
   - Trends → Songs: rising songs (business accounts may only use commercially licensed music).
   - Top Ads: hooks and structures of winning ads in the industry — very useful for sales/affiliate videos.
   - Keyword Insights: phrases to use in captions.
2. **Competitor profiles**: `tiktok.com/@handle` → read views of the latest 30 videos, compute outliers the same way as YouTube.
3. TikTok search bar: type niche keywords and look at autocomplete suggestions (shows what people are searching for).

## C. Breaking down an outlier video (fill in for each of the top 10)

| Field | What to record |
|---|---|
| Hook 0–3s | First spoken words / on-screen text + first visual. Which hook type (see script-template.md) |
| Promise | What the viewer gets if they watch to the end |
| Structure | List / story / before-after / contrarian / tutorial |
| Length & pace | Total seconds, average seconds between scene/text changes |
| Title / caption | Formula (number, question, curiosity, contrast) |
| Thumbnail (YouTube) | Face? How many words? Dominant colors? |
| Main emotion | Curiosity / FOMO / anger / admiration / humor |
| Why it won (hypothesis) | One sentence |

## D. Required output of stage 1
1. Top 10 outlier table (link, views, outlier score, hook, why it won)
2. 3–5 recurring patterns across outliers
3. 3–5 gaps (with evidence: comments, searches, other markets)
4. List of sources used; state explicitly where no data could be obtained
