"""Convert heavyweight raster images to WebP and rewrite local references.

Targets:
  - static/images/events/*/<name>.(png|jpg|jpeg) where <name> contains
    "background" or "logo" and the file is >= 100 KB
  - static/images/Stickers/*.png >= 500 KB

Output is written alongside the source as <basename>.webp; originals are kept.
Local refs in static/js/events-data.js are rewritten to point at the .webp
files. Sticker filenames need no rewrite (get_sticker_files() globs the dir).

Usage: python scripts/convert_images.py
"""

import os
import re

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_DIR = os.path.join(ROOT, 'static', 'images', 'events')
STICKERS_DIR = os.path.join(ROOT, 'static', 'images', 'Stickers')
EVENTS_DATA_PATH = os.path.join(ROOT, 'static', 'js', 'events-data.js')

MIN_EVENT_KB = 100
MIN_STICKER_KB = 500
WEBP_QUALITY = 80


def convert_to_webp(source_path: str, min_kb: int) -> str | None:
    """Convert source_path to a sibling .webp. Returns the .webp path if
    converted, None if skipped (too small, unsupported, or already fresh)."""
    if not os.path.splitext(source_path)[1].lower() in ('.png', '.jpg', '.jpeg'):
        return None
    if os.path.getsize(source_path) < min_kb * 1024:
        return None
    target_path = os.path.splitext(source_path)[0] + '.webp'
    if os.path.exists(target_path) and os.path.getmtime(target_path) >= os.path.getmtime(source_path):
        return None
    with Image.open(source_path) as image:
        image.save(target_path, 'WEBP', quality=WEBP_QUALITY, method=6)
    if os.path.getsize(target_path) >= os.path.getsize(source_path):
        # WebP isn't always smaller (e.g. noisy JPEG) — keep the original.
        os.remove(target_path)
        return None
    return target_path


def main() -> None:
    converted: dict[str, str] = {}  # old local path -> new local path

    for directory, min_kb, pattern in (
        (EVENTS_DIR, MIN_EVENT_KB, re.compile(r'(background|logo)\.(png|jpe?g)$', re.I)),
        (STICKERS_DIR, MIN_STICKER_KB, re.compile(r'\.png$', re.I)),
    ):
        for root, _dirs, files in os.walk(directory):
            for name in sorted(files):
                if not pattern.search(name):
                    continue
                source_path = os.path.join(root, name)
                target_path = convert_to_webp(source_path, min_kb)
                if not target_path:
                    continue
                old_ref = '/' + os.path.relpath(source_path, ROOT).replace('\\', '/')
                new_ref = '/' + os.path.relpath(target_path, ROOT).replace('\\', '/')
                converted[old_ref] = new_ref
                saved_kb = (os.path.getsize(source_path) - os.path.getsize(target_path)) / 1024
                print(f'{old_ref} -> {new_ref} (saved {saved_kb:.0f} KB)')

    if not converted:
        print('Nothing to convert.')
        return

    with open(EVENTS_DATA_PATH, encoding='utf-8') as fh:
        data = fh.read()
    original = data
    for old_ref, new_ref in converted.items():
        data = data.replace(old_ref, new_ref)
    if data != original:
        with open(EVENTS_DATA_PATH, 'w', encoding='utf-8') as fh:
            fh.write(data)
        print(f'Rewrote {os.path.relpath(EVENTS_DATA_PATH, ROOT)}')
    else:
        print('events-data.js already up to date.')


if __name__ == '__main__':
    main()
