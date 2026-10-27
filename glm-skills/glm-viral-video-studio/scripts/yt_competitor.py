#!/usr/bin/env python3
"""YouTube competitor / outlier analysis using the free YouTube Data API v3.

Quota (default 10,000 units/day): channels.list 1, playlistItems.list 1,
videos.list 1 per call (up to 50 ids), search.list 100. Prefer --channels.

Usage:
  python3 yt_competitor.py --channels @handle1 @handle2 --per-channel 30 --out yt_report
  python3 yt_competitor.py --query "keyword" --max-results 25 --region VN --out yt_search
Outputs <out>.csv (one row per video) and <out>.md (top outliers summary).
"""
import argparse, csv, os, json, re, statistics, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

API = "https://www.googleapis.com/youtube/v3/"
units = 0



try:  # print Unicode safely on Windows consoles
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def call(endpoint, cost, **params):
    global units
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"API error {e.code} on {endpoint}: {e.read().decode()[:400]}")
    except urllib.error.URLError as e:
        sys.exit(f"Network error ({e.reason}). If the sandbox blocks googleapis.com, run this script on your own computer.")
    units += cost
    return data


def iso_duration_to_s(d):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return 0
    dd, h, mi, s = (int(x or 0) for x in m.groups())
    return dd * 86400 + h * 3600 + mi * 60 + s


def channel_info(key, ident):
    p = {"part": "snippet,statistics,contentDetails", "key": key}
    if ident.startswith("UC") and len(ident) == 24:
        p["id"] = ident
    else:
        p["forHandle"] = ident if ident.startswith("@") else "@" + ident
    items = call("channels", 1, **p).get("items", [])
    return items[0] if items else None


def upload_ids(key, playlist, n):
    ids, token = [], None
    while len(ids) < n:
        p = {"part": "contentDetails", "playlistId": playlist, "maxResults": 50, "key": key}
        if token:
            p["pageToken"] = token
        d = call("playlistItems", 1, **p)
        ids += [i["contentDetails"]["videoId"] for i in d.get("items", [])]
        token = d.get("nextPageToken")
        if not token:
            break
    return ids[:n]


def video_details(key, ids):
    out = []
    for i in range(0, len(ids), 50):
        d = call("videos", 1, part="snippet,statistics,contentDetails", id=",".join(ids[i:i + 50]), key=key)
        out += d.get("items", [])
    return out


def row(v, channel_title, subs):
    now = datetime.now(timezone.utc)
    pub = datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))
    days = max((now - pub).total_seconds() / 86400, 1)
    st = v.get("statistics", {})
    views = int(st.get("viewCount", 0))
    dur = iso_duration_to_s(v["contentDetails"].get("duration"))
    return {
        "channel": channel_title, "subscribers": subs, "title": v["snippet"]["title"],
        "url": f"https://www.youtube.com/watch?v={v['id']}", "published": pub.date().isoformat(),
        "views": views, "likes": int(st.get("likes", st.get("likeCount", 0)) or 0),
        "comments": int(st.get("commentCount", 0)), "duration_s": dur,
        "is_short": dur <= 180, "views_per_day": round(views / days),
    }


def add_outlier(rows):
    by_ch = {}
    for r in rows:
        by_ch.setdefault(r["channel"], []).append(r["views"])
    for r in rows:
        med = statistics.median(by_ch[r["channel"]]) or 1
        r["channel_median_views"] = int(med)
        r["outlier_score"] = round(r["views"] / med, 2)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-key", default=os.environ.get("YOUTUBE_API_KEY"), help="or set YOUTUBE_API_KEY")
    ap.add_argument("--channels", nargs="*", default=[], help="@handles or UC... channel ids")
    ap.add_argument("--per-channel", type=int, default=30)
    ap.add_argument("--query", help="keyword search (costs 100 units per call)")
    ap.add_argument("--max-results", type=int, default=25)
    ap.add_argument("--region", default="VN")
    ap.add_argument("--days", type=int, default=90, help="search: only videos from the last N days")
    ap.add_argument("--short-only", action="store_true")
    ap.add_argument("--out", default="yt_report")
    a = ap.parse_args()
    if not a.api_key:
        sys.exit("Missing API key: pass --api-key or set YOUTUBE_API_KEY")
    if not a.channels and not a.query:
        sys.exit("Give --channels or --query")

    rows = []
    for ident in a.channels:
        ch = channel_info(a.api_key, ident)
        if not ch:
            print(f"! Channel not found: {ident}", file=sys.stderr)
            continue
        subs = int(ch["statistics"].get("subscriberCount", 0))
        ids = upload_ids(a.api_key, ch["contentDetails"]["relatedPlaylists"]["uploads"], a.per_channel)
        rows += [row(v, ch["snippet"]["title"], subs) for v in video_details(a.api_key, ids)]

    if a.query:
        d = call("search", 100, part="snippet", q=a.query, type="video", order="viewCount",
                 regionCode=a.region, maxResults=min(a.max_results, 50), key=a.api_key,
                 publishedAfter=(datetime.now(timezone.utc) - timedelta(days=a.days))
                 .strftime("%Y-%m-%dT%H:%M:%SZ"))
        ids = [i["id"]["videoId"] for i in d.get("items", [])]
        vids = video_details(a.api_key, ids)
        ch_ids = list({v["snippet"]["channelId"] for v in vids})
        subs = {}
        for i in range(0, len(ch_ids), 50):
            for c in call("channels", 1, part="statistics", id=",".join(ch_ids[i:i + 50]), key=a.api_key).get("items", []):
                subs[c["id"]] = int(c["statistics"].get("subscriberCount", 0))
        for v in vids:
            r = row(v, v["snippet"]["channelTitle"], subs.get(v["snippet"]["channelId"], 0))
            r["views_per_sub"] = round(r["views"] / max(r["subscribers"], 1), 2)
            rows.append(r)

    if a.short_only:
        rows = [r for r in rows if r["is_short"]]
    if not rows:
        sys.exit("No videos found.")
    rows = add_outlier(rows) if a.channels else rows
    key = "outlier_score" if a.channels else "views_per_sub"
    rows.sort(key=lambda r: r.get(key, 0), reverse=True)

    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(a.out + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    with open(a.out + ".md", "w", encoding="utf-8") as f:
        f.write(f"# Top outliers ({key})\n\nQuota used: ~{units} units\n\n")
        f.write(f"| # | Channel | Title | Views | {key} | Views/day | Length | Published |\n|---|---|---|---|---|---|---|---|\n")
        for n, r in enumerate(rows[:20], 1):
            t = r["title"].replace("|", "/")[:80]
            f.write(f"| {n} | {r['channel']} | [{t}]({r['url']}) | {r['views']:,} | {r.get(key)} | "
                    f"{r['views_per_day']:,} | {r['duration_s']}s | {r['published']} |\n")
    print(f"Saved {a.out}.csv and {a.out}.md — {len(rows)} videos, ~{units} quota units used.")


if __name__ == "__main__":
    main()
