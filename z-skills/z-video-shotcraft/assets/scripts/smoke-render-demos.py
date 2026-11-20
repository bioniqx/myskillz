#!/usr/bin/env python3
"""smoke-render-demos.py — Demo rendering smoke tests.

Closes the loophole of "compiles but cannot run": existing CI only performs tsc
compilation without verifying whether demos can actually render. This script
scans all demos exporting duration (`_DURATION` / `_DUR`), automatically
generates a temporary Root registering all of them, renders the first frame for
each one, and asserts the output file is non-empty and rendering does not crash.

Usage (from repository root):
    python3 assets/scripts/smoke-render-demos.py [--subset a,b,c] [--list]

Prerequisites:
    - template/ has run `npm install` (remotion 4.0.484)
    - @remotion/motion-blur used by demos is installed in template (temporarily installed in CI)
    - Demos requiring textures: files in demos/_textures/ are copied to
      template/public/textures/live/ (the script automatically copies missing files)
    - Demos requiring external MP4 assets (e.g. clipcard-looping): skipped and reported, not failed

Exit codes: 0 if all pass; 1 if any demo fails to render (lists failure manifest).
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE = ROOT / 'template'
TEMPLATE_SRC = TEMPLATE / 'src'
TEXTURES_SRC = ROOT / 'demos' / '_textures'
TEXTURES_DST = TEMPLATE / 'public' / 'textures' / 'live'
DUR_PAT = re.compile(r'export const (\w+_DURATION|\w+_DUR)\s*=')

# Demos requiring external MP4 assets that cannot be synthesized (skipped with report)
MATERIAL_REQUIRED = {'ClipCardLooping'}


def find_demos():
    """Return [(path, duration_export_name, component_name)], sorted by path."""
    out = []
    for f in sorted((ROOT / 'demos').rglob('*.tsx')):
        # Legacy shots preserved for backward compatibility only
        if '_legacy' in f.relative_to(ROOT / 'demos').parts:
            continue
        src = f.read_text(encoding='utf-8')
        m = DUR_PAT.search(src)
        if not m:
            continue
        durname = m.group(1)
        stem = f.stem
        # Export must exist as React component
        # Strict regex matching to avoid false positives in comments
        if not re.search(rf'export const {re.escape(stem)}\s*:\s*React\.FC\s*=', src):
            continue
        out.append((f, durname, stem))
    return out


def write_smoke_root(demos):
    """Generate template/src/smoke-root.tsx registering all demos."""
    lines = ["import { Composition, registerRoot } from 'remotion';"]
    regs = []
    for f, durname, stem in demos:
        rel = os.path.relpath(f, TEMPLATE_SRC).replace('.tsx', '')
        lines.append(f"import {{ {stem}, {durname} }} from '{rel}';")
        regs.append(
            f'  <Composition id="{stem}" component={{{stem}}} '
            f'durationInFrames={{{durname}}} fps={{30}} width={{1920}} '
            f'height={{1080}} />'
        )
    lines.append('export const Root: React.FC = () => (<>')
    lines += regs
    lines.append('</>);')
    lines.append('registerRoot(Root);')
    (TEMPLATE_SRC / 'smoke-root.tsx').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def ensure_textures():
    """Copy image textures from demos/_textures to template/public/textures/live.
    Only copies image files (.png/.jpg/.webp), skipping data files like layout.json
    since they are imported into TS rather than used as runtime textures."""
    if not TEXTURES_SRC.exists():
        return 0
    os.makedirs(TEXTURES_DST, exist_ok=True)
    IMG_EXT = {'.png', '.jpg', '.jpeg', '.webp'}
    copied = 0
    for f in TEXTURES_SRC.iterdir():
        if f.is_file() and f.suffix.lower() in IMG_EXT and not (TEXTURES_DST / f.name).exists():
            shutil.copy2(f, TEXTURES_DST / f.name)
            copied += 1
    return copied


def render_one(stem, out_dir):
    """Render single demo first frame, returning (ok, output_path_or_error)."""
    out = out_dir / f'{stem}.png'
    r = subprocess.run(
        ['npx', 'remotion', 'still', 'src/smoke-root.tsx', stem,
         '--frame=0', str(out), '--log=error'],
        cwd=TEMPLATE,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return False, r.stderr[-400:]
    if not out.exists() or out.stat().st_size == 0:
        return False, 'rendered but empty output'
    return True, None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--subset', help='Comma-separated component names to render')
    ap.add_argument('--list', action='store_true', help='List renderable demos only')
    args = ap.parse_args()

    demos = find_demos()
    if args.list:
        for _, _, stem in demos:
            print(stem)
        return 0

    if args.subset:
        wanted = set(args.subset.split(','))
        available = {s for _, _, s in demos}
        unknown = wanted - available
        if unknown:
            print(f'error: subset contains unknown demo(s): {sorted(unknown)}')
            return 1
        demos = [(f, d, s) for f, d, s in demos if s in wanted]

    # Filter demos requiring external media
    skip = [(f, d, s) for f, d, s in demos if s in MATERIAL_REQUIRED]
    run = [(f, d, s) for f, d, s in demos if s not in MATERIAL_REQUIRED]

    print(f'Found {len(demos)} demos exporting duration; '
          f'Skipped (requires media): {len(skip)}; Rendering: {len(run)}')
    if skip:
        print(f'  Skipped: {", ".join(s for _, _, s in skip)}')

    write_smoke_root(run)
    ensure_textures()

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        failed = []
        for f, durname, stem in run:
            ok, err = render_one(stem, out_dir)
            if ok:
                print(f'  ✓ {stem}')
            else:
                print(f'  ✗ {stem}: {err}')
                failed.append(stem)

    # Clean up generated smoke-root
    (TEMPLATE_SRC / 'smoke-root.tsx').unlink(missing_ok=True)

    if failed:
        print(f'\nFailed ({len(failed)}): {failed}')
        return 1
    print(f'\nAll {len(run)} demo first frames rendered successfully ✓')
    return 0


if __name__ == '__main__':
    sys.exit(main())
