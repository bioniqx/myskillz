#!/usr/bin/env python3
"""Re-sync gallery/source/*.md copies and library.json text fields from references/shots/ cards.

Run from repo root after editing any card:  python3 gallery/sync-from-cards.py
"""
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / 'references' / 'shots'
SOURCE = ROOT / 'gallery' / 'source'
LIB = ROOT / 'gallery' / 'api' / 'library.json'

# Variants with a recipe/sample but no reusable demo source get 'reference-only'
# here so the workflow does not recommend them by default. Currently empty:
# every style has demo source.
STYLE_STATUS = {}


def parse_card(path):
    text = path.read_text(encoding='utf-8')
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            if ':' in line:
                k, v = line.split(':', 1)
                fm[k.strip()] = v.strip()
    im = re.search(r'^## Intention\n(.*?)(?=\n## )', text, re.S | re.M)
    intention = re.sub(r'\s*\n\s*', ' ', im.group(1).strip()) if im else None
    return fm, intention


# Functional categories (directory name -> labels); references/shots/<category>/<card_name>.md
CATEGORIES = {
    'opening': {'zh': 'Opening & Brand', 'en': 'Opening & Brand'},
    'typography': {'zh': 'Typography & Title Cards', 'en': 'Typography & Title Cards'},
    'ui-entrance': {'zh': 'UI Entrance & Showcase', 'en': 'UI Entrance & Showcase'},
    'camera': {'zh': 'Camera & Space', 'en': 'Camera & Space'},
    'data': {'zh': 'Data & Metrics', 'en': 'Data & Metrics'},
    'interaction': {'zh': 'Interaction & Feature Demo', 'en': 'Interaction & Feature Demo'},
    'transition': {'zh': 'Transitions', 'en': 'Transitions'},
    'rhythm': {'zh': 'Rhythm & Montage', 'en': 'Rhythm & Montage'},
    'effects': {'zh': 'Light & Emphasis', 'en': 'Light & Emphasis'},
    'outro': {'zh': 'Outro', 'en': 'Outro'},
}


def main():
    cards = {p.stem: p for p in SHOTS.glob('*/*.md')}
    card_category = {p.stem: p.parent.name for p in SHOTS.glob('*/*.md')}
    unknown = sorted(set(card_category.values()) - set(CATEGORIES))
    if unknown:
        raise SystemExit(f'unknown category folders: {unknown} (add to CATEGORIES)')

    # 1. refresh gallery/source copies (drop copies whose card no longer exists).
    # A copy that differs from its card means the card was edited since the last
    # sync — bump that card's updatedAt so stats.newest / sitemap lastmod move.
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    touched = set()
    for old in SOURCE.glob('*.md'):
        if old.stem not in cards:
            old.unlink()
            print(f'removed stale copy: {old.name}')
    for name, p in cards.items():
        copy = SOURCE / p.name
        if not copy.exists() or copy.read_bytes() != p.read_bytes():
            touched.add(name)
        shutil.copyfile(p, copy)

    # 2. refresh library.json text fields
    lib = json.loads(LIB.read_text(encoding='utf-8'))
    missing = []
    for card in lib['cards']:
        p = cards.get(card['name'])
        if not p:
            missing.append(card['name'])
            continue
        fm, intention = parse_card(p)
        if fm.get('summary'):
            card['summary'] = fm.get('summary')
        if fm.get('use'):
            card['use'] = fm.get('use')
        if fm.get('duration'):
            card['duration'] = fm.get('duration')
        if fm.get('energy'):
            card['energy'] = fm.get('energy')
        if intention:
            card['intention'] = intention
        card['category'] = card_category[card['name']]
        # Multi-category tags: frontmatter "tags" lists additional matching categories
        raw_tags = fm.get('tags') or ''
        extra = [t.strip() for t in re.split(r'[,\s]+', raw_tags) if t.strip()]
        bad = [t for t in extra if t not in CATEGORIES]
        if bad:
            raise SystemExit(f"{card['name']}: unknown tags {bad} (must be CATEGORIES keys)")
        card['tags'] = [card['category']] + [t for t in extra if t != card['category']]
        card['source'] = f"references/shots/{card['category']}/{card['name']}.md"
        if card['name'] in touched:
            card['updatedAt'] = now
        # addedAt recorded when new card first enters library.json
        card.setdefault('addedAt', now)
        if len(card.get('styles', [])) == 1:
            card['styles'][0]['description'] = card['summary']
        for style in card.get('styles', []):
            status = STYLE_STATUS.get((card['name'], style['key']))
            if status:
                style['implementationStatus'] = status
            else:
                style.pop('implementationStatus', None)
    lib['categories'] = CATEGORIES
    # All view rendered flat in cards order; this is authoritative sort order
    lib['cards'].sort(key=lambda card: card['name'])

    # stats are the single source of truth every page and llms.txt reads;
    # recompute from the cards rather than trusting whatever was there
    styles = [style for card in lib['cards'] for style in card['styles']]
    lib['stats']['cardCount'] = len(lib['cards'])
    lib['stats']['styleCount'] = len(styles)
    lib['stats']['previewCount'] = sum(1 for style in styles if style.get('media'))
    lib['stats']['mediaCount'] = lib['stats']['previewCount']
    lib['stats']['newest'] = max(card['updatedAt'] for card in lib['cards'])
    LIB.write_text(json.dumps(lib, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"synced {len(lib['cards'])} cards ({lib['stats']['styleCount']} styles, "
          f"{lib['stats']['previewCount']} previews); missing card files: {missing or 'none'}")
    if missing:
        raise SystemExit(f'orphan library.json entries (card md deleted): {missing}')


if __name__ == '__main__':
    main()
