# Publishing to Social Platforms: Finished Video → TikTok / Instagram / YouTube / LinkedIn / X …

Distribute the delivered MP4 simultaneously to TikTok, Instagram (Reels or Stories), YouTube (including Shorts), LinkedIn, Facebook, X, Threads, Pinterest, and Bluesky, either immediately or on a scheduled timer.
Script: `publish/upload_post.py`, powered by the [Upload-Post](https://upload-post.com) API, using only Python standard library (no venv / pip required).

**Trigger condition**: Run only when the user **explicitly requests** publishing the final video to social platforms (e.g. "publish this to TikTok and YouTube"). It is not a 4th recommendation outside the 1-2-3 delivery wrap-up steps; do not proactively upsell it.
Publishing is a public and difficult-to-revert action; **you must obtain explicit user confirmation of copy and platform list** before actual publishing.

> **Note**: Upload-Post is a third-party managed service. The free tier includes 10 uploads per month covering all above platforms except TikTok (TikTok requires a paid plan). Network requests are made only when the user configures their own API key.

## 1. One-Time Setup (User Action)

1. Register at https://upload-post.com, create a profile, and connect social accounts to this profile.
2. Generate an API key in the dashboard.
3. Set environment variables (or add them to shell profile):

```bash
export UPLOAD_POST_API_KEY=...
export UPLOAD_POST_USER=<profile_name>
```

When either variable is missing, inform the user of these three steps and pause waiting; do not attempt publishing.

## 2. File Selection and Copy Preparation

- **File**: Use the delivered final video. Videos with BGM come in two versions (with BGM / without BGM); default to the **with BGM version** unless specified otherwise.
- **Aspect Ratio**: TikTok, Reels, and Shorts require 9:16 vertical video. If the video is 16:9 horizontal, inform the user clearly (platforms will add black bars or crop), and suggest publishing to YouTube / LinkedIn / X / Facebook instead, or rendering a vertical cut.
- **Copy `--title`**: Acts as caption/post text on TikTok / Instagram / X / Threads; write engaging social copy (one punchy hook + 2–4 hashtags) rather than a formal YouTube title. Keep ≤100 characters when including YouTube. If the user agreed to author attribution in wrap-up step 1, include that handle.
- **Long Description `--description`**: Used by YouTube / LinkedIn / Facebook / Pinterest.
- **AI Label `--ai-generated`**: Ask the user whether to declare AI-generated content. Code-rendered videos by agents generally do not constitute "photorealistic synthetic media" and are not labeled by default; recommend labeling if AI-generated imagery or voiceovers were used.

Compile "Copy + Description + Platform List + Schedule (if any) + Privacy Settings" for user review, and **proceed only after receiving explicit confirmation**.

## 3. Run Dry-Run First (No Actual Upload)

```bash
python3 publish/upload_post.py --video out/promo.mp4 --title "<copy>" \
  --description "<long_desc>" --platforms tiktok,instagram,youtube --dry-run --json-out
```

Verify output: `authOk` is `true`. A non-empty `missingPlatforms` indicates disconnected platforms that will be skipped; notify user to connect them in dashboard or remove from target list.

## 4. Publishing

Rerun without `--dry-run`. The script waits for platform results (default timeout: 10 minutes) and outputs URLs or errors per platform.

- **Run each publish command exactly once.** Regardless of timeouts, network drops, errors, or `status: "unknown"`, **never rerun the publish command**. Rerunning generates a new `request_id`, posting duplicate videos. Only query status:
  `python3 publish/upload_post.py --status <requestId> --json-out`
- How the script discriminates: Only **400 / 401 / 403 / 422** (explicit rejection before server processing) are treated as failed; at this point nothing has been posted, and arguments can be corrected before retrying. 5xx, gateway errors, timeouts, disconnects, or 2xx without valid JSON are "indeterminate" — video may have been accepted. The script automatically polls using the same `request_id`; if confirmed, it continues; if still unconfirmed, it outputs `status: "unknown"` (exit code 2), `requestId`, and `statusCommand`, with `doNotRerun: true`.
- The script prints `request_id` and the corresponding `--status` command to stderr **before sending**. If interrupted mid-flight, use that status command to inspect instead of rerunning.
- Scheduled publishing (`--schedule 2026-10-01T09:00:00 --timezone Asia/Shanghai`) immediately returns `jobId` + `requestId` and `statusCommand`. Query scheduled jobs via **`jobId`**:
  `python3 publish/upload_post.py --status <jobId> --json-out` (`statusCommand` in output reflects this command).

## 5. Reporting to User

One line per platform: URL or error reason.

| Platform Result | Meaning |
|---|---|
| `completed` + `url` | Published. Private uploads lack public links: YouTube still provides owner-viewable link; other platforms return `postId` + `note`. |
| `skipped` | Platform not connected in profile; upload skipped. |
| `failed` / `retryable` | `error` is platform-provided reason (e.g. token expired, reconnect in dashboard); `retryable` will be automatically retried server-side. |
| TikTok `inbox: true` | TikTok placed video in creator drafts box; user must open TikTok App and tap publish. |
| Overall `status: "unknown"` | Unable to confirm acceptance. Report `requestId` as-is to user and inspect later with `statusCommand`; **never rerun publish command**. |

## 6. Options Quick Reference

| Option | Description |
|---|---|
| `--video` / `--title` | Final video path / Shared copy across platforms |
| `--description` / `--description-file` | Long description |
| `--platforms` | `tiktok,instagram,youtube,linkedin,facebook,x,threads,pinterest,bluesky` (aliases: `twitter`, `reels`, `shorts`) |
| `--user` | Profile name, defaults to `$UPLOAD_POST_USER` |
| `--schedule` + `--timezone` | Scheduled publishing (≤365 days), IANA timezone, defaults to UTC |
| `--first-comment` | Automatically post first comment after publish |
| `--ai-generated` | AI content declaration flag (TikTok / Instagram / YouTube / X) |
| `--thumbnail` | Custom thumbnail (YouTube, LinkedIn) |
| `--youtube-privacy` | `private` (default) / `unlisted` / `public` |
| `--tags` | YouTube tags, comma-separated |
| `--tiktok-privacy` / `--tiktok-draft` | TikTok privacy (defaults to account setting) / Save as draft only |
| `--instagram-story` | Post Stories instead of Reels |
| `--facebook-page-id` / `--linkedin-page-id` | Target Facebook Page / Publish as LinkedIn Organization page |
| `--pinterest-board` | Required for Pinterest |
| `--status ID` | Query previous submission: `request_id` for instant posts, `job_id` for scheduled posts |
| `--dry-run` / `--json-out` | Validate without publishing / Output single-line JSON |

Error types (`errorType`): `auth` (missing or invalid key), `validation` (invalid parameters or no platforms connected), `forbidden` (tier limitations, e.g. free tier targeting TikTok), `quota` (rate or tier limit reached), `http` (network / server error).

Offline unit tests: `python3 -m unittest publish/test_upload_post.py -v`
