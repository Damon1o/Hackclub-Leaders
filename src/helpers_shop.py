"""Shop catalog loading, filtering, and management helpers."""

import json
import os
import re
import tempfile
import threading
from typing import Any, Final
from urllib.parse import quote

import requests

from .helpers_types import ShopItem
from .helpers_validation import SHOP_JSON_PATH as _DEFAULT_SHOP_JSON_PATH
from .storage import StorageError

PROJECT_ROOT: Final[str] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOB_READ_WRITE_TOKEN: Final[str] = os.environ.get('BLOB_READ_WRITE_TOKEN', '')
_SHOP_LOCK: Final[threading.Lock] = threading.Lock()
SHOP_FILTERS: Final[set[str]] = {'Hardware', 'Merch', 'Digital', 'Grants', 'Credits', 'Games'}


def _shop_json_path() -> str:
    """Resolve through src.helpers at call time so monkeypatching
    helpers.SHOP_JSON_PATH reaches the writer even though it lives here."""
    from . import helpers

    return getattr(helpers, 'SHOP_JSON_PATH', _DEFAULT_SHOP_JSON_PATH)


def _slugify(text: str) -> str:
    text = (text or '').strip().lower()
    return re.sub(r'[^a-z0-9]+', '-', text).strip('-')


def load_shop_items() -> list[ShopItem]:
    try:
        with open(_shop_json_path(), encoding='utf-8-sig') as fh:
            raw: list[dict[str, Any]] = json.load(fh)
    except (OSError, ValueError):
        return []
    items: list[ShopItem] = []
    for entry in raw:
        name = entry.get('name', '')
        items.append(
            {
                'id': _slugify(name),
                'name': name,
                'cost': entry.get('cost'),
                'image_src': entry.get('image-src', ''),
                'filter': entry.get('filter', ''),
            }
        )
    return sorted(
        items,
        key=lambda item: (
            item['cost'] is None,
            item['cost'] if item['cost'] is not None else 0,
        ),
    )


SHOP_ITEMS: list[ShopItem] = load_shop_items()
_STICKER_FILES: list[str] | None = None


def get_sticker_files() -> list[str]:
    global _STICKER_FILES
    if _STICKER_FILES is None:
        sticker_dir = os.path.join(PROJECT_ROOT, 'static', 'images', 'Stickers')
        try:
            files = os.listdir(sticker_dir)
            by_stem: dict[str, str] = {}
            for f in sorted(files):
                ext = os.path.splitext(f)[1].lower()
                if ext not in ('.png', '.svg', '.gif', '.webp', '.jpg', '.jpeg'):
                    continue
                stem = os.path.splitext(f)[0]
                if stem not in by_stem or ext == '.webp':
                    by_stem[stem] = f
            _STICKER_FILES = sorted(by_stem.values())
        except OSError:
            _STICKER_FILES = []
    return _STICKER_FILES


def _read_shop_raw() -> list[dict[str, Any]]:
    try:
        with open(_shop_json_path(), encoding='utf-8') as fh:
            raw: Any = json.load(fh)
    except (OSError, ValueError):
        return []
    return raw if isinstance(raw, list) else []


def _write_shop_raw(raw: list[dict[str, Any]]) -> None:
    path = _shop_json_path()
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(raw, fh, indent=2, ensure_ascii=False)
            fh.write('\n')
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _parse_coins(cost: str) -> int | None:
    text = (cost or '').strip()
    if text.lower() == 'free':
        return 0
    match = re.fullmatch(r'\$?([0-9]+)(?:\.[0-9]{1,2})?', text)
    return int(match.group(1)) if match else None


def add_shop_item(name: str, cost: str, image_src: str, item_filter: str) -> ShopItem:
    global SHOP_ITEMS
    name = (name or '').strip()
    if not name:
        raise ValueError('Item name is required.')
    slug = _slugify(name)
    item_filter = item_filter if item_filter in SHOP_FILTERS else 'Merch'
    coins = _parse_coins(cost)
    entry: dict[str, Any] = {
        'name': name,
        'cost': coins,
        'image-src': (image_src or '').strip(),
        'filter': item_filter,
    }
    with _SHOP_LOCK:
        raw = _read_shop_raw()
        if any(_slugify(e.get('name', '')) == slug for e in raw):
            raise ValueError('An item with that name already exists.')
        raw.append(entry)
        _write_shop_raw(raw)
        SHOP_ITEMS = load_shop_items()
    return {
        'id': slug,
        'name': name,
        'cost': coins,
        'image_src': entry['image-src'],
        'filter': item_filter,
    }


def remove_shop_item(slug: str) -> bool:
    global SHOP_ITEMS
    slug = (slug or '').strip()
    with _SHOP_LOCK:
        raw = _read_shop_raw()
        remaining = [e for e in raw if _slugify(e.get('name', '')) != slug]
        if len(remaining) == len(raw):
            return False
        _write_shop_raw(remaining)
        SHOP_ITEMS = load_shop_items()
    return True


def _sniff_image(data: bytes) -> tuple[str | None, str | None]:
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png', 'png'
    if data[:3] == b'\xff\xd8\xff':
        return 'image/jpeg', 'jpg'
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif', 'gif'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp', 'webp'
    return None, None


def _upload_to_blob(pathname: str, data: bytes, content_type: str) -> str:
    oidc_token = os.environ.get('VERCEL_OIDC_TOKEN', '').strip()
    store_id_env = os.environ.get('BLOB_STORE_ID', '').strip()
    if oidc_token and store_id_env:
        token = oidc_token
        store_id = store_id_env[6:] if store_id_env.startswith('store_') else store_id_env
    elif BLOB_READ_WRITE_TOKEN:
        token = BLOB_READ_WRITE_TOKEN
        store_id = BLOB_READ_WRITE_TOKEN.split('_')[3]
    else:
        raise StorageError('Image uploads are not configured yet (missing BLOB_READ_WRITE_TOKEN).')
    safe_path = quote(pathname, safe='/')
    try:
        response = requests.put(
            f'https://vercel.com/api/blob/?pathname={safe_path}',
            headers={
                'x-vercel-blob-access': 'public',
                'x-vercel-blob-store-id': store_id,
                'authorization': f'Bearer {token}',
                'x-api-version': '12',
                'x-content-type': content_type,
                'x-add-random-suffix': '1',
            },
            data=data,
            timeout=15,
        )
    except requests.RequestException as exc:
        raise StorageError(f'Could not reach the image store: {exc}') from exc
    if response.status_code >= 400:
        detail = ''
        try:
            detail = (response.json() or {}).get('error', {}).get('message', '')
        except (ValueError, AttributeError):
            detail = response.text[:200]
        raise StorageError(
            f'Image upload failed ({response.status_code}){": " + detail if detail else ""}.'
        )
    return str((response.json() or {}).get('url', ''))
