#!/usr/bin/env python3
"""assemble-media.py — Assemble sample MP4 videos from gallery-media release into a directory.

There are two storage formats for sample videos on release, which can coexist:
  gallery-media.zip   Bulk upload for batch updates (updates a large batch of samples in one request)
  <style-key>.mp4     Individual upload for routine incremental updates
Assembly rules: Extract zip first, then download two categories of individual MP4s:
those uploaded later than the zip (new standalone additions overriding zip contents),
and those missing from the zip (which may only package a subset). Older standalone files
uploaded prior to the zip and packaged within it are automatically invalidated.
If no zip exists on the release, fallback to downloading all individual MP4s (legacy behavior).
Only downloads individual MP4s referenced in library.json (ignoring obsolete files on release).

Usage: python3 gallery/assemble-media.py <target_directory> [--repo owner/name]
Shared by deploy-pages.yml, pr-checks.yml, and fetch-media.sh; requires authenticated gh CLI (uses GH_TOKEN in CI).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile

ZIP = 'gallery-media.zip'
LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api', 'library.json')


def wanted_names():
    lib = json.load(open(LIB, encoding='utf-8'))
    out = set()
    for card in lib['cards']:
        for style in card['styles']:
            media = style.get('media')
            url = media.get('url') if isinstance(media, dict) else media
            if url:
                out.add(url.split('?')[0].rstrip('/').split('/')[-1])
    return out


def gh(*args, **kw):
    return subprocess.run(['gh', *args], check=True, text=True, capture_output=True, **kw).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dest')
    ap.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY', 'Vincentwei1021/video-shotcraft'))
    a = ap.parse_args()
    os.makedirs(a.dest, exist_ok=True)
    assets = json.loads(gh('release', 'view', 'gallery-media', '--repo', a.repo, '--json', 'assets'))['assets']
    zipped = next((x for x in assets if x['name'] == ZIP), None)
    wanted = wanted_names()
    singles = [x for x in assets if x['name'].endswith('.mp4') and x['name'] in wanted]
    from_zip, in_zip = 0, set()
    if zipped:
        with tempfile.TemporaryDirectory() as tmp:
            gh('release', 'download', 'gallery-media', '--repo', a.repo, '--dir', tmp, '--pattern', ZIP)
            with zipfile.ZipFile(os.path.join(tmp, ZIP)) as z:
                for info in z.infolist():
                    name = os.path.basename(info.filename)
                    if not name.endswith('.mp4'):
                        continue
                    with z.open(info) as src, open(os.path.join(a.dest, name), 'wb') as dst:
                        dst.write(src.read())
                    from_zip += 1
                    in_zip.add(name)
        # ISO 8601 UTC timestamp strings can be compared directly as strings
        singles = [x for x in singles if x['updatedAt'] > zipped['updatedAt'] or x['name'] not in in_zip]
    if singles:
        args = ['release', 'download', 'gallery-media', '--repo', a.repo, '--dir', a.dest, '--clobber']
        for x in singles:
            args += ['--pattern', x['name']]
        gh(*args)
    print(f'{a.dest}: {from_zip} previews from {ZIP if zipped else "(no zip)"}, '
          f'{len(singles)} single mp4 asset(s){" (newer than the zip or not in it)" if zipped else ""}')


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.exit(f'gh failed: {" ".join(e.cmd)}\n{e.stderr}')
