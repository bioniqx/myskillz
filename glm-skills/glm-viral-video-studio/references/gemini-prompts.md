# Prompts for Gemini Pro (mode A)

Replace the parts in <...>. Use them in the Gemini app (gemini.google.com) or Google Flow (labs.google/flow) with a Google AI Pro account.

---
## 1. Gemini Deep Research — competitor analysis (use when the agent cannot reach the data)

```
Act as a YouTube/TikTok growth analyst. Research the niche "<niche>" for the <target country / global> market on <TikTok / YouTube Shorts / YouTube long-form>, using only data published in the last 90 days.

Competitors to include (add 5 more you find with strong recent growth): <@channel1, @channel2>.

For each channel: subscriber/follower count, posting frequency, median views of the last 30 videos, and the 3 videos with the highest views relative to that median (outlier ratio = views / channel median). Give the link for every video.

For the top 10 outliers overall, break down: the first 3 seconds (exact hook words and first visual), video length, structure, title formula, thumbnail style, main emotion, and a one-line hypothesis of why it outperformed.

Then list: (a) 5 recurring patterns across outliers, (b) 5 content gaps — questions repeated in comments, angles nobody covers well, formats proven in other markets but missing in the target market, (c) 10 trending keywords/hashtags.

Output as tables. Cite every number with its source link. If a number cannot be verified, write "unverified" instead of estimating. Write the final report in <user's language>.
```
When it finishes: Export to Google Docs → paste or drop the file into the workspace so the agent can use it for stage 2.

---
## 2. Create a "Video Producer" Gem (set up once, reuse forever)
Gemini → Gems → New Gem → Instructions:
```
You turn approved video scripts into production assets. When I paste a shot list, return for each shot: (1) a Veo 3.1 prompt following this exact structure: Shot type & camera movement / Subject & action / Setting & time / Lighting & color grade / Style / Audio / Negative; (2) aspect ratio; (3) whether a still image would be enough instead of video. Keep subjects, wardrobe, colors and lighting consistent across shots by repeating the same descriptors. Never include brand logos, real celebrities or copyrighted characters. On-screen text is added later in Canva, so never ask Veo to render text.
```

---
## 3. Veo 3.1 prompt template (Flow or the Gemini app)

Cost-saving Flow settings: **Veo 3.1 Lite** to draft composition → **Fast** for the final; Outputs per prompt = **1**; 9:16 for short videos. Use Quality (100 credits) only when the hook shot truly needs it.

Structure:
```
[Shot type & camera]: <close-up / medium / wide / top-down / POV>, <static / slow push-in / handheld / orbit / dolly>.
[Subject & action]: <who/what, doing what, specific; describe characters identically in every shot>.
[Setting & time]: <location, time of day>.
[Lighting & color]: <soft window light / neon night / golden hour>, <color grade>.
[Style]: <photorealistic, shot on 35mm / cinematic documentary / clean 3D motion graphic>.
[Audio]: <ambient sound + specific SFX>; no dialogue; no music.
[Avoid]: no text, no subtitles, no logos, no watermark, no distorted hands.
Vertical 9:16.
```

Example (personal finance niche, hook shot):
```
Extreme close-up, slow push-in. A young office worker's hand drops a crumpled stack of banknotes onto a wooden desk next to a phone showing a red declining chart. Small city apartment at night, rain on the window behind. Low-key lighting, cool blue tones with a warm desk lamp accent. Photorealistic, cinematic, shallow depth of field. Audio: rain ambience, paper rustle, a soft phone notification ping; no dialogue; no music. Avoid: no readable text, no logos, no watermark. Vertical 9:16.
```

Character consistency: use "Ingredients" / reference images in Flow (create the character image with Nano Banana first), and repeat the exact same character description in every prompt.

Retry prompt when a shot fails: keep the prompt unchanged, add one specific fix line (e.g. "hands must have five fingers, keep camera fully static") — do not rewrite the whole prompt.

---
## 4. Nano Banana Pro — thumbnail backgrounds / still B-roll

YouTube thumbnail (16:9):
```
Create a 16:9 YouTube thumbnail background, 1280x720. <Main subject: e.g. a shocked young man holding a phone>, positioned on the right third, face large and expressive, looking at the camera. Left 40% of the frame is clean, uncluttered negative space with a <dark navy> gradient for headline text to be added later. High contrast, saturated <yellow and navy> palette, rim light separating the subject from the background, sharp focus, photorealistic. No text, no logos, no watermark.
```
Make 3 variants: change the emotion (shocked / confident / curious) or the background color → use them for Test & Compare.

TikTok/Shorts cover (9:16): same as above but "9:16 vertical, 1080x1920, subject in the middle third, top 25% empty for headline".

Still B-roll (replaces a Veo shot to save credits):
```
Photorealistic still, 9:16 vertical: <scene description>. Same character as the reference image: <character description>. <lighting>, <color grade>. No text, no logos.
```
Then add a slow zoom/pan in Canva (or `render_storyboard.py` with the image as `bg`) to make it move.

---
## 5. Script check with Gemini (optional, free with Pro)
```
You are a harsh short-form video editor. Here is my script: <paste>. Score the first 3 seconds 1–10 for scroll-stopping power and explain why. Mark every line where a viewer is likely to swipe away. Rewrite only those lines, keeping the total length. Answer in <user's language>.
```
