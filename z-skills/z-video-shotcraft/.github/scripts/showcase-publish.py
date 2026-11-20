#!/usr/bin/env python3
"""Publish an approved showcase submission (run by showcase-publish.yml).

Workflow: parse submission issue form body -> download video ->
normalize to h264 mp4 via ffmpeg + extract poster -> store in showcase-media release ->
update showcase.json on release -> trigger deploy-pages redeploy -> comment and close
issue. Submission media and showcase.json are stored only in release assets, not git.

Field parsing anchors match issue form labels (rendered as '### <label>'),
mapped 1:1 with .github/ISSUE_TEMPLATE/showcase.yml.

Environment variables (injected by workflow): GH_TOKEN GH_REPO ISSUE_NUMBER ISSUE_BODY
ISSUE_USER ISSUE_CREATED_AT RUN_ID
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

RELEASE_TAG = 'showcase-media'
MAX_BYTES = 300 * 1024 * 1024  # Max 300MB per submission
SHOWCASE_URL = 'https://vincentwei1021.github.io/video-shotcraft/showcase.html'

# Matches showcase.yml field labels
FIELD_TITLE = 'Video Title'
FIELD_DESC = 'One-line Description'
FIELD_CARDS = 'Shot Cards Used (optional)'
FIELD_FILE = 'Video File (≤10MB drag-and-drop upload)'
FIELD_URL = 'External Video URL (for larger files)'
FIELD_X = 'X Handle (optional)'
FIELD_YOUTUBE = 'YouTube (optional)'
FIELD_XHS = 'Xiaohongshu (optional)'
FIELD_DY = 'Douyin (optional)'

ATTACHMENT_RE = re.compile(
    r'https://github\.com/user-attachments/(?:assets/[\w-]+|files/\d+/\S+?)(?=[)\s"\']|$)'
    r'|https://user-images\.githubusercontent\.com/\S+?(?=[)\s"\']|$)')
URL_RE = re.compile(r'https?://\S+?(?=[)\s"\']|$)')
YOUTUBE_RE = re.compile(r'^https?://(?:www\.)?(?:youtube\.com|youtu\.be)/', re.I)


def run(cmd, **kw):
    print('+', ' '.join(str(c) for c in cmd), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def parse_form(body):
    """Split issue form body by '### <label>' into dict of section text."""
    sections = {}
    current = None
    for line in body.replace('\r\n', '\n').split('\n'):
        if line.startswith('### '):
            current = line[4:].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    fields = {}
    for key, lines in sections.items():
        value = '\n'.join(lines).strip()
        fields[key] = '' if value == '_No response_' else value
    return fields


def pick_video_url(fields):
    attachment = ATTACHMENT_RE.search(fields.get(FIELD_FILE, ''))
    if attachment:
        return attachment.group(0)
    external = URL_RE.search(fields.get(FIELD_URL, ''))
    if external:
        return external.group(0)
    sys.exit('Submission contains neither video attachment nor external link; cannot publish')


def probe_codec(path):
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'stream=codec_name', '-of', 'csv=p=0', str(path)],
        capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        sys.exit(f'ffprobe failed to recognize downloaded file as valid video: {result.stderr.strip()}')
    return result.stdout.strip().splitlines()[0]


def normalize_video(raw, out_mp4):
    """Remux h264 directly (lossless + faststart); transcode other codecs to 1080p h264."""
    codec = probe_codec(raw)
    if codec == 'h264':
        remux = subprocess.run(
            ['ffmpeg', '-y', '-i', str(raw), '-c', 'copy',
             '-movflags', '+faststart', str(out_mp4)])
        if remux.returncode == 0:
            return
    run(['ffmpeg', '-y', '-i', str(raw),
         '-vf', "scale='min(1920,iw)':-2",
         '-c:v', 'libx264', '-crf', '20', '-preset', 'veryfast',
         '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
         '-movflags', '+faststart', str(out_mp4)])


def extract_poster(video, poster):
    for seek in ('1', '0'):
        result = subprocess.run(
            ['ffmpeg', '-y', '-ss', seek, '-i', str(video), '-frames:v', '1',
             '-vf', "scale='min(960,iw)':-2", str(poster)])
        if result.returncode == 0 and poster.exists() and poster.stat().st_size > 0:
            return
    sys.exit('Failed to extract poster frame from video')


def main():
    env = os.environ
    issue = int(env['ISSUE_NUMBER'])
    fields = parse_form(env.get('ISSUE_BODY', ''))
    title = fields.get(FIELD_TITLE, '').strip()
    description = fields.get(FIELD_DESC, '').strip()
    if not title or not description:
        sys.exit('Submission missing title or description; please complete before approving')

    video_url = pick_video_url(fields)
    work = Path(tempfile.mkdtemp(prefix='showcase-'))
    raw = work / 'raw-video'
    # -A browser UA: some direct links return 403 on empty UA
    run(['curl', '-fSL', '--retry', '3', '--max-time', '600',
         '--max-filesize', str(MAX_BYTES),
         '-A', 'Mozilla/5.0 (video-shotcraft showcase bot)',
         '-o', str(raw), video_url])
    if raw.stat().st_size > MAX_BYTES:
        sys.exit(f'Video exceeds {MAX_BYTES // 1024 // 1024}MB limit')

    mp4 = work / f'showcase-{issue}.mp4'
    poster = work / f'showcase-{issue}.jpg'
    normalize_video(raw, mp4)
    extract_poster(mp4, poster)

    # Release is auto-created on first submission
    exists = subprocess.run(['gh', 'release', 'view', RELEASE_TAG],
                            capture_output=True)
    if exists.returncode != 0:
        run(['gh', 'release', 'create', RELEASE_TAG,
             '--title', 'Showcase media assets',
             '--notes', 'User-submitted showcase videos + showcase.json '
                        '(published by showcase-publish.yml, not tracked in git).'])

    manifest_path = work / 'showcase.json'
    fetched = subprocess.run(
        ['gh', 'release', 'download', RELEASE_TAG, '--pattern', 'showcase.json',
         '--dir', str(work), '--clobber'], capture_output=True)
    if fetched.returncode == 0 and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    else:
        manifest = {'items': []}

    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    youtube = fields.get(FIELD_YOUTUBE, '').strip()
    xiaohongshu = fields.get(FIELD_XHS, '').strip()
    # Backward compatibility for earlier submissions
    if not youtube and YOUTUBE_RE.match(xiaohongshu):
        youtube, xiaohongshu = xiaohongshu, ''
    entry = {
        'id': issue,
        'title': title,
        'description': description,
        'cards': fields.get(FIELD_CARDS, '').strip(),
        'author': {
            'github': env.get('ISSUE_USER', ''),
            'x': fields.get(FIELD_X, '').strip(),
            'youtube': youtube,
            'xiaohongshu': xiaohongshu,
            'douyin': fields.get(FIELD_DY, '').strip(),
        },
        # ?v= cache busting for CDN
        'video': f'./showcase-media/showcase-{issue}.mp4?v={env.get("RUN_ID", "0")}',
        'poster': f'./showcase-media/showcase-{issue}.jpg?v={env.get("RUN_ID", "0")}',
        'submittedAt': env.get('ISSUE_CREATED_AT', ''),
        'approvedAt': now,
    }
    manifest['items'] = ([entry]
                         + [item for item in manifest['items'] if item.get('id') != issue])
    manifest['updatedAt'] = now
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    run(['gh', 'release', 'upload', RELEASE_TAG, str(mp4), str(poster),
         str(manifest_path), '--clobber'])
    # Explicit workflow_dispatch trigger
    run(['gh', 'workflow', 'run', 'deploy-pages.yml'])
    run(['gh', 'issue', 'comment', str(issue), '--body',
         f'🎉 Published! Your video will appear on the [Showcase page]({SHOWCASE_URL}) in a few minutes.\n\n'
         f'To edit or delist, feel free to comment here or open an issue. Thank you!'])
    run(['gh', 'issue', 'close', str(issue), '--reason', 'completed'])


if __name__ == '__main__':
    main()
