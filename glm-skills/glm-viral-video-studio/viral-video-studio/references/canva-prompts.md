# Canva prompts and workflow (mode A)

Canva button/menu names change between releases; if a name doesn't match, look for the equivalent feature under Apps or the editor's search box. Write the prompt in the user's language if they prefer; on-screen text must be in the audience's language.

If a Canva MCP server is configured in ZCode, the agent can search, autofill and export designs directly instead of handing over prompts.

## 1. YouTube thumbnail (Canva AI / Magic Design)
Prompt:
```
Design a 1280x720 YouTube thumbnail for the video "<title>". Use the image I uploaded as the background, subject on the right. On the left, a big headline of at most 4 words: "<THUMBNAIL TEXT>", bold sans-serif font, white text with a thick black outline, one keyword highlighted in <yellow>. High contrast, readable at thumb size. No logos, no other text.
```
Make 3 versions (different text or colors) → export PNG ≥ 1280×720 → upload to Test & Compare.

Checklist: ≤ 4 words, don't repeat the video title, a face with a clear emotion, still understandable at 160px wide.

## 2. TikTok/Shorts cover 1080×1920
```
Design a 1080x1920 vertical video cover from the image I uploaded. Headline "<text>" in the top quarter, large bold type, inside the safe zone (at least 20% from the bottom edge, 15% from the right edge). Match the channel's brand: colors <...>, font <...>.
```

## 3. Editing the video in Canva (replaces paid editing software)
1. Create a new design → Mobile video 1080×1920 (or YouTube Video 1920×1080).
2. Upload all Veo clips, Nano Banana images and the voiceover file to Uploads.
3. Drag clips onto the timeline in shot-list order. Trim each to the seconds in the script (cut 0.3–0.5s from the start if Veo stutters).
4. Still images: add motion (Animate → slow zoom/pan).
5. Add the voiceover; background music low (about 10–20% of the voice level). Use Beat Sync if the video is mostly music.
6. Subtitles: use Canva's auto Captions, or import the .srt file the agent made if your Canva version supports it; 2–5 words per line, bold font, center of the screen above the caption zone.
7. Hook text: on the very first frame (0s), no slow typewriter effects.
8. Export MP4 1080p. Review on a phone before posting.

## 4. Canva AI prompt for promo posts (optional)
```
Create 3 square 1080x1080 images promoting the new video "<title>" from the channel <name>. Use the thumbnail I uploaded as the main image, add the line "New video" and a short hook: "<hook>". Keep the same colors and font as the thumbnail.
```
