import base64
import json
import os
import re
import secrets
import tempfile
import threading
import zlib
from datetime import date
from functools import wraps

import requests
from flask import flash, g, jsonify, redirect, request, session, url_for

from .storage import SessionStorage, StorageError, make_storage

# ── Config constants (derived from env) ────────────────────────────────────────

BLOB_READ_WRITE_TOKEN = os.environ.get('BLOB_READ_WRITE_TOKEN', '')

ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.environ.get('ADMIN_EMAILS', '').split(',')
    if email.strip()
}


# ── Decorators ─────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user'):
            return redirect(url_for('sign_in'))
        return f(*args, **kwargs)
    return decorated


LEADER_ROLES = {'Leader', 'Mentor'}


def viewer_role():
    user = session.get('user') or {}
    email = (user.get('email') or '').strip().lower()
    state = (viewer_club_lite() or {}) if user else {}
    for member in state.get('members', []):
        if (member.get('email') or '').strip().lower() == email:
            return member.get('role') or 'Member'
    return 'Leader'


def viewer_is_leader():
    return viewer_role() in LEADER_ROLES


def leader_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user'):
            return redirect(url_for('sign_in'))
        if not viewer_is_leader():
            flash('That page is for club leaders and mentors.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


def require_leader_api():
    if not viewer_is_leader():
        return jsonify({'error': 'Only leaders and mentors can do that.'}), 403
    return None


def is_admin():
    email = ((session.get('user') or {}).get('email') or '').strip().lower()
    return bool(email) and email in ADMIN_EMAILS


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user'):
            return redirect(url_for('sign_in'))
        if not is_admin():
            flash('That page is for site administrators.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


def require_admin_api():
    if not is_admin():
        return jsonify({'error': 'Admins only.'}), 403
    return None


# ── ID / code generation ───────────────────────────────────────────────────────

def _item_id(prefix):
    return f'{prefix}-{secrets.token_hex(4)}'


def generate_join_code():
    return secrets.token_urlsafe(9)


def unique_join_code(backend, attempts=5):
    for _ in range(attempts):
        code = generate_join_code()
        if backend.find_club_by_join_code(code) is None:
            return code
    return secrets.token_urlsafe(12)


# ── CSRF ───────────────────────────────────────────────────────────────────────

def get_csrf_token():
    token = session.get('csrf_token')
    if not token:
        token = secrets.token_urlsafe(24)
        session['csrf_token'] = token
    return token


def require_dashboard_csrf():
    token = request.headers.get('X-CSRF-Token', '')
    expected = session.get('csrf_token', '')
    if not token or not expected or not secrets.compare_digest(token, expected):
        return jsonify({'error': 'Your session token expired. Refresh and try again.'}), 403
    return None


# ── Shop catalog ───────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
SHOP_JSON_PATH = os.path.join(PROJECT_ROOT, 'static', 'data', 'shop.json')


def _slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', (text or '').lower()).strip('-')


def load_shop_items():
    try:
        with open(SHOP_JSON_PATH, encoding='utf-8-sig') as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return []
    items = []
    for entry in raw:
        name = entry.get('name', '')
        items.append({
            'id': _slugify(name),
            'name': name,
            'cost': entry.get('cost', ''),
            'image-src': entry.get('image-src', ''),
            'filter': entry.get('filter', ''),
        })
    return items


SHOP_ITEMS = load_shop_items()
_STICKER_FILES = None

# Serializes shop.json reads/writes so two admins editing at once can't
# clobber each other (the app is a single process, so a lock is enough).
_SHOP_LOCK = threading.Lock()
SHOP_FILTERS = {'Hardware', 'Swag', 'Digital'}


def get_sticker_files():
    global _STICKER_FILES
    if _STICKER_FILES is None:
        sticker_dir = os.path.join(PROJECT_ROOT, 'static', 'images', 'Stickers')
        try:
            _STICKER_FILES = sorted(
                f for f in os.listdir(sticker_dir)
                if os.path.splitext(f)[1].lower()
                in ('.png', '.svg', '.gif', '.webp', '.jpg', '.jpeg')
            )
        except OSError:
            _STICKER_FILES = []
    return _STICKER_FILES


def _read_shop_raw():
    try:
        with open(SHOP_JSON_PATH, encoding='utf-8') as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return []
    return raw if isinstance(raw, list) else []


def _write_shop_raw(raw):
    # Write to a sibling temp file, then os.replace — atomic on Windows and
    # POSIX, so a crash mid-write never leaves shop.json truncated.
    directory = os.path.dirname(SHOP_JSON_PATH)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(raw, fh, indent=2, ensure_ascii=False)
            fh.write('\n')
        os.replace(tmp, SHOP_JSON_PATH)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _normalize_cost(cost):
    """'$5', '5', '5.00' → '$5.00'; non-numeric labels ('Free', 'TBD') pass through."""
    text = (cost or '').strip()
    match = re.fullmatch(r'\$?([0-9]+(?:\.[0-9]{1,2})?)', text)
    return f'${float(match.group(1)):.2f}' if match else text


def _shop_hours(cost):
    """The 'hours' price is 1.5x the dollar cost; word labels mirror the cost."""
    match = re.fullmatch(r'\$([0-9]+(?:\.[0-9]{1,2})?)', cost or '')
    return f'${float(match.group(1)) * 1.5:.2f}' if match else (cost or '')


def add_shop_item(name, cost, image_src, item_filter):
    """Append an item to shop.json and refresh the in-memory catalog.

    Returns the catalog-shaped item dict. Raises ValueError for a blank name
    or a duplicate (same slug)."""
    global SHOP_ITEMS
    name = (name or '').strip()
    if not name:
        raise ValueError('Item name is required.')
    slug = _slugify(name)
    item_filter = item_filter if item_filter in SHOP_FILTERS else 'Swag'
    cost = _normalize_cost(cost) or 'TBD'
    entry = {
        'name': name,
        'cost': cost,
        'hours': _shop_hours(cost),
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
        'cost': cost,
        'image-src': entry['image-src'],
        'filter': item_filter,
    }


def remove_shop_item(slug):
    """Drop the item whose slug matches and refresh the catalog. Returns
    True if something was removed, False if no such item existed."""
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


# ── Default state ──────────────────────────────────────────────────────────────

def default_dashboard_state():
    user = session.get('user') or {}
    leader_name = user.get('name') or 'Club Leader'
    leader_email = user.get('email') or 'leader@hackclub.com'

    return {
        'members': [
            {
                'id': 'member-leader',
                'name': leader_name,
                'email': leader_email,
                'role': 'Leader',
                'avatar': user.get('avatar') or '',
                'status': 'Active',
            },
        ],
        'events': [],
        'shopItems': [dict(item) for item in SHOP_ITEMS],
        'cart': [],
        'orders': [],
        'itemRequests': [],
        'projects': [],
        'newsletters': [
            {
                'id': 'dispatch-hardware-grants',
                'title': 'Winter Hardware Grants are Open',
                'excerpt': 'Apply for up to $500 to buy Raspberry Pis and Arduinos for your club. Plus, check out the new Sprig game engine.',
                'body': 'Hardware grant applications are open for clubs planning electronics workshops this winter. Tell us what you want to build, how many members will participate, and what parts your club needs.',
                'date': '2026-10-12',
                'readTime': '3 min read',
                'read': False,
            },
            {
                'id': 'dispatch-hackathon-guide',
                'title': 'How to host your first hackathon',
                'excerpt': 'A step-by-step guide from leaders who just hosted an event with 50+ students at their high school.',
                'body': 'Start with a short theme, pick a realistic schedule, and recruit mentors before opening registration. The best first hackathons keep scope tight and make demo time feel celebratory.',
                'date': '2026-09-28',
                'readTime': '5 min read',
                'read': False,
            },
            {
                'id': 'dispatch-school-year',
                'title': 'Welcome to the new school year',
                'excerpt': 'Updates on Hack Club Bank, new sticker designs, and how to recruit members.',
                'body': 'The new school year kit includes updated posters, refreshed stickers, and a checklist for reaching your first ten members.',
                'date': '2026-08-15',
                'readTime': '2 min read',
                'read': False,
            },
        ],
        'settings': {
            'joinCode': generate_join_code(),
            'clubName': f"{leader_name}'s Hack Club",
            'location': '',
            'website': '',
            'avatar': '',
            'publicDirectory': True,
            'emailNotifications': True,
            'darkModeDefault': False,
            'newsletterSubscribed': True,
            'language': DEFAULT_LANGUAGE,
        },
    }


def playtest_state():
    today = date.today().isoformat()
    leader_email = 'playtest.leader@hackclub.com'
    member_email = 'playtest.member@hackclub.com'
    return {
        'settings': {
            'joinCode': 'PLAYTEST',
            'clubName': 'Playtest Hack Club',
            'location': 'Burlington, VT',
            'website': 'https://hackclub.com',
            'avatar': '',
            'publicDirectory': True,
            'emailNotifications': True,
            'darkModeDefault': False,
            'newsletterSubscribed': True,
            'language': 'en',
        },
        'members': [
            {
                'id': 'playtest-leader',
                'name': 'Test Leader',
                'email': leader_email,
                'role': 'Leader',
                'avatar': '',
                'status': 'Active',
            },
            {
                'id': 'playtest-member',
                'name': 'Test Member',
                'email': member_email,
                'role': 'Member',
                'avatar': '',
                'status': 'Active',
            },
        ],
        'events': [
            {
                'id': 'playtest-event-1',
                'title': 'First Club Meeting',
                'date': today,
                'time': '15:30',
                'location': 'Room 101',
                'repeat': '',
                'type': 'Workshop',
                'attendees': 8,
                'rsvp': True,
            },
            {
                'id': 'playtest-event-2',
                'title': 'Build Night',
                'date': today,
                'time': '18:00',
                'location': 'Library Makerspace',
                'repeat': '',
                'type': 'Hackathon',
                'attendees': 12,
                'rsvp': False,
            },
        ],
        'projects': [
            {
                'id': 'playtest-proj-1',
                'name': 'LED Blinker',
                'description': 'My first Arduino project — a blinking LED circuit.',
                'url': '',
                'repoUrl': '',
                'demoUrl': '',
                'thumbnail': '',
                'hackatimeProject': '',
                'ownerEmail': leader_email,
                'ownerName': 'Test Leader',
                'status': 'Shipped',
                'date': today,
            },
            {
                'id': 'playtest-proj-2',
                'name': 'Club Website',
                'description': 'A simple React site for club announcements.',
                'url': 'https://example.com',
                'repoUrl': 'https://github.com/playtest/club-site',
                'demoUrl': '',
                'thumbnail': '',
                'hackatimeProject': '',
                'ownerEmail': member_email,
                'ownerName': 'Test Member',
                'status': 'Submitted',
                'date': today,
            },
        ],
        'shopItems': [dict(item) for item in SHOP_ITEMS],
        'cart': [],
        'orders': [],
        'itemRequests': [],
        'newsletters': default_dashboard_state()['newsletters'],
    }


# ── Storage layer ──────────────────────────────────────────────────────────────

def _storage():
    if 'storage_backend' not in g:
        g.storage_backend = make_storage(session)
    return g.storage_backend


def _club_key():
    if 'club_key' not in g:
        email = (session.get('user') or {}).get('email') or ''
        g.club_key = _storage().resolve_club_key(email)
    return g.club_key


def viewer_club_state():
    if 'club_state_loaded' not in g:
        g.club_state_loaded = True
        g.club_state = _storage().load(_club_key())
    return g.club_state


def viewer_club_lite():
    if 'club_lite' in g:
        return g.club_lite
    if g.get('club_state_loaded') and g.get('club_state') is not None:
        g.club_lite = g.club_state
    else:
        g.club_lite = _storage().load_lite(_club_key())
    return g.club_lite


def get_dashboard_state():
    if 'dashboard_state' in g:
        return g.dashboard_state

    backend = _storage()
    state = viewer_club_state()
    if state is None:
        state = default_dashboard_state()
        g.dashboard_state = state
        return state

    defaults = default_dashboard_state()
    changed = False
    for key, value in defaults.items():
        if key not in state:
            state[key] = value
            changed = True

    settings = state.setdefault('settings', {})
    for key, value in defaults['settings'].items():
        if key not in settings:
            settings[key] = value
            changed = True

    state['shopItems'] = [dict(item) for item in SHOP_ITEMS]

    if isinstance(backend, SessionStorage):
        if changed:
            session.modified = True
    else:
        state['cart'] = session.get('cart_items') or []

    g.dashboard_state = state
    return state


MAX_STATE_COOKIE_BYTES = 2800


class StateTooLarge(Exception):  # noqa: N818
    pass


def _state_cookie_size(state):
    raw = json.dumps(state, separators=(',', ':')).encode()
    return len(base64.urlsafe_b64encode(zlib.compress(raw)))


def save_dashboard_state(state):
    backend = _storage()
    if isinstance(backend, SessionStorage):
        persisted = {key: value for key, value in state.items()
                     if key != 'shopItems'}
        if _state_cookie_size(persisted) > MAX_STATE_COOKIE_BYTES:
            raise StateTooLarge()
        backend.save(_club_key(), persisted)
    else:
        session['cart_items'] = state.get('cart') or []
        session.modified = True
        persisted = {key: value for key, value in state.items()
                     if key not in ('shopItems', 'cart')}
        backend.save(_club_key(), persisted)
    g.dashboard_state = state
    g.club_state = state
    g.club_state_loaded = True


# ── JSON API utilities ─────────────────────────────────────────────────────────

def json_payload():
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def json_error(message, status=400):
    return jsonify({'error': message}), status


# ── Image utilities ────────────────────────────────────────────────────────────

def _sniff_image(data):
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png', 'png'
    if data[:3] == b'\xff\xd8\xff':
        return 'image/jpeg', 'jpg'
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif', 'gif'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp', 'webp'
    return None, None


def _upload_to_blob(pathname, data, content_type):
    oidc_token = os.environ.get('VERCEL_OIDC_TOKEN', '').strip()
    store_id_env = os.environ.get('BLOB_STORE_ID', '').strip()
    if oidc_token and store_id_env:
        token = oidc_token
        store_id = store_id_env[6:] if store_id_env.startswith('store_') else store_id_env
    elif BLOB_READ_WRITE_TOKEN:
        token = BLOB_READ_WRITE_TOKEN
        store_id = BLOB_READ_WRITE_TOKEN.split('_')[3]
    else:
        raise StorageError('Image uploads are not configured yet '
                           '(missing BLOB_READ_WRITE_TOKEN).')
    safe_path = requests.utils.quote(pathname, safe='/')
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
        raise StorageError(f'Image upload failed ({response.status_code}){": " + detail if detail else ""}.')
    return (response.json() or {}).get('url', '')


# ── Generic utilities ──────────────────────────────────────────────────────────

def find_by_id(items, item_id):
    return next((item for item in items if item.get('id') == item_id), None)


def clean_text(value, fallback='', max_len=300):
    if value is None:
        return fallback
    return str(value).strip()[:max_len]


def parse_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() in {'1', 'true', 'yes', 'on'}


# Keep this list in sync with LANGUAGES in static/js/i18n-data.js.
# Ordered (code, native label) so the <select> can be rendered server-side —
# the control then works even if JavaScript is slow or blocked.
DASHBOARD_LANGUAGES = [
    ('en', 'English'),
    ('es', 'Español'),
    ('fr', 'Français'),
    ('de', 'Deutsch'),
    ('pt', 'Português'),
    ('it', 'Italiano'),
    ('ru', 'Русский'),
    ('hi', 'हिन्दी'),
    ('zh', '中文'),
    ('ja', '日本語'),
    ('ko', '한국어'),
    ('ar', 'العربية'),
]
SUPPORTED_LANGUAGES = {code for code, _label in DASHBOARD_LANGUAGES}
DEFAULT_LANGUAGE = 'en'


def parse_language(value):
    """Return a supported language code, defaulting to English for anything else."""
    code = str(value or '').strip().lower()
    return code if code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


# ── Event construction ─────────────────────────────────────────────────────────

# Allowed recurrence cadences for events; '' means the event does not repeat.
EVENT_REPEAT_OPTIONS = {'', 'daily', 'weekly', 'biweekly', 'monthly', 'weekdays'}


def parse_repeat(value, fallback=''):
    """Return a supported repeat cadence, or the fallback for anything else."""
    code = str(value or '').strip().lower()
    return code if code in EVENT_REPEAT_OPTIONS else fallback


def event_from_payload(payload, existing=None):
    existing = existing or {}
    title = clean_text(payload.get('title'), existing.get('title', ''))
    event_date = clean_text(payload.get('date'), existing.get('date', ''))
    event_time = clean_text(payload.get('time'), existing.get('time', ''))
    location = clean_text(payload.get('location'), existing.get('location', ''))
    event_type = clean_text(payload.get('type'), existing.get('type', 'Workshop'))
    repeat = parse_repeat(payload.get('repeat'), existing.get('repeat', ''))
    attendees = payload.get('attendees', existing.get('attendees', 0))

    if not title:
        return None, 'Event title is required.'
    try:
        date.fromisoformat(event_date)
    except ValueError:
        return None, 'Choose a valid event date.'
    if not event_time:
        return None, 'Event time is required.'
    if not location:
        return None, 'Event location is required.'
    try:
        attendees = max(0, int(attendees))
    except (TypeError, ValueError):
        attendees = existing.get('attendees', 0)

    return {
        'title': title,
        'date': event_date,
        'time': event_time,
        'location': location,
        'type': event_type,
        'repeat': repeat,
        'rsvp': parse_bool(payload.get('rsvp', existing.get('rsvp', False))),
        'attendees': attendees,
    }, None


# ── Project helpers ────────────────────────────────────────────────────────────

def _viewer_email():
    return ((session.get('user') or {}).get('email') or '').strip().lower()


def _join_missing(items):
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f'{items[0]} and {items[1]}'
    return ', '.join(items[:-1]) + ', and ' + items[-1]


def _owned_project_or_error(state, project_id):
    project = find_by_id(state.get('projects') or [], project_id)
    if not project:
        return None, json_error('Project not found.', 404)
    if (project.get('ownerEmail') or '').strip().lower() != _viewer_email():
        return None, json_error('You can only change your own projects.', 403)
    return project, None


# ── Admin helpers ──────────────────────────────────────────────────────────────

ADMIN_REVIEW_STATUSES = {'Shipped', 'Draft'}


def _persist_club(backend, club_key, state):
    if isinstance(backend, SessionStorage):
        backend.save(club_key, state)
    else:
        persisted = {key: value for key, value in state.items()
                     if key not in ('shopItems', 'cart')}
        backend.save(club_key, persisted)


def _load_admin_club(backend, club_key):
    state = backend.load(club_key)
    if state is None:
        return None, json_error('Club not found.', 404)
    return state, None


def _find_club_by_project(backend, project_id):
    for club in backend.list_clubs():
        club_key = club.get('clubKey', '')
        state = backend.load(club_key)
        if state is None:
            continue
        if find_by_id(state.get('projects') or [], project_id):
            return state, club_key
    return None, None
