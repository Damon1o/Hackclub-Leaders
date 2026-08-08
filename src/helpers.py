import base64
import json
import math
import os
import re
import secrets
import tempfile
import threading
import zlib
from collections.abc import Callable
from datetime import date, datetime, timezone
from functools import wraps
from typing import Any, Final, TypedDict, TypeVar, cast

import requests
from flask import flash, g, jsonify, redirect, request, session, url_for

from .storage import SessionStorage, StorageError, make_storage

# ── Config constants (derived from env) ────────────────────────────────────────

BLOB_READ_WRITE_TOKEN: Final[str] = os.environ.get('BLOB_READ_WRITE_TOKEN', '')

ADMIN_EMAILS: Final[set[str]] = {
    email.strip().lower()
    for email in os.environ.get('ADMIN_EMAILS', '').split(',')
    if email.strip()
}

COINS_PER_APPROVED_SHIP: Final[int] = 25
STARTER_GRANT_COINS: Final[int] = 50


# ── Type definitions ──────────────────────────────────────────────────────────


class Member(TypedDict):
    id: str
    name: str
    email: str
    role: str
    avatar: str
    status: str


class Event(TypedDict):
    id: str
    title: str
    date: str
    time: str
    location: str
    type: str
    repeat: str
    rsvp: bool
    attendees: int


class Project(TypedDict):
    id: str
    name: str
    description: str
    url: str
    repoUrl: str
    demoUrl: str
    thumbnail: str
    hackatimeProject: str
    status: str
    ownerEmail: str
    ownerName: str
    date: str


class ShopItem(TypedDict):
    id: str
    name: str
    cost: str
    image_src: str
    filter: str


class Newsletter(TypedDict):
    id: str
    title: str
    excerpt: str
    body: str
    date: str
    readTime: str
    read: bool


class OrderItem(TypedDict):
    id: str
    quantity: int


class CoinTransaction(TypedDict):
    id: str
    delta: int
    kind: str
    ref: str
    note: str
    at: str


class Order(TypedDict):
    id: str
    date: str
    status: str
    items: list[OrderItem]


class ItemRequest(TypedDict):
    id: str
    name: str
    note: str
    date: str
    status: str


class Channel(TypedDict):
    id: str
    name: str
    description: str
    createdBy: str
    lastMessageAt: str


class Message(TypedDict):
    id: str
    channelId: str
    authorEmail: str
    authorName: str
    authorAvatar: str
    body: str
    createdAt: str


class Settings(TypedDict):
    joinCode: str
    clubName: str
    location: str
    website: str
    avatar: str
    publicDirectory: bool
    emailNotifications: bool
    darkModeDefault: bool
    newsletterSubscribed: bool
    language: str
    coinBalance: int
    coinsSpent: int


class DashboardState(TypedDict, total=False):
    members: list[Member]
    events: list[Event]
    projects: list[Project]
    shopItems: list[ShopItem]
    cart: list[OrderItem]
    orders: list[Order]
    itemRequests: list[ItemRequest]
    channels: list[Channel]
    messages: list[Message]
    newsletters: list[Newsletter]
    ledger: list[CoinTransaction]
    settings: Settings


# Lite state only has settings and members
class ClubStateLite(TypedDict, total=False):
    settings: Settings
    members: list[Member]
    _lite: bool


# ClubState is the full state from Airtable load
class ClubState(TypedDict, total=False):
    settings: Settings
    members: list[Member]
    events: list[Event]
    newsletters: list[Newsletter]
    orders: list[Order]
    itemRequests: list[ItemRequest]
    projects: list[Project]
    channels: list[Channel]
    messages: list[Message]


# Type variables for decorators
F = TypeVar('F', bound=Callable[..., Any])
R = TypeVar('R')


# ── Decorators ────────────────────────────────────────────────────────────────


def login_required(f: F) -> F:
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if not session.get('user'):
            return redirect(url_for('sign_in'))
        return f(*args, **kwargs)

    return decorated  # type: ignore[return-value]


LEADER_ROLES: Final[set[str]] = {'Leader', 'Mentor'}


def viewer_role() -> str:
    user = session.get('user') or {}
    email = (user.get('email') or '').strip().lower()
    state = (viewer_club_lite() or {}) if user else {}
    for member in state.get('members', []):
        if (member.get('email') or '').strip().lower() == email:
            return member.get('role') or 'Member'
    return 'Leader'


def viewer_is_leader() -> bool:
    return viewer_role() in LEADER_ROLES


def leader_required(f: F) -> F:
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if not session.get('user'):
            return redirect(url_for('sign_in'))
        if not viewer_is_leader():
            flash('That page is for club leaders and mentors.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)

    return decorated  # type: ignore[return-value]


def require_leader_api() -> tuple[Any, int] | None:
    if not viewer_is_leader():
        return jsonify({'error': 'Only leaders and mentors can do that.'}), 403
    return None


def is_admin() -> bool:
    email = ((session.get('user') or {}).get('email') or '').strip().lower()
    return bool(email) and email in ADMIN_EMAILS


def admin_required(f: F) -> F:
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if not session.get('user'):
            return redirect(url_for('sign_in'))
        if not is_admin():
            flash('That page is for site administrators.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)

    return decorated  # type: ignore[return-value]


def require_admin_api() -> tuple[Any, int] | None:
    if not is_admin():
        return jsonify({'error': 'Admins only.'}), 403
    return None


# ── ID / code generation ──────────────────────────────────────────────────────


def _item_id(prefix: str) -> str:
    return f'{prefix}-{secrets.token_hex(4)}'


def utc_iso() -> str:
    """UTC timestamp, ISO-8601 with a 'Z' suffix (e.g. 2026-07-10T22:59:00.123456Z)."""
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def coin_balance(ledger: list[CoinTransaction]) -> int:
    return sum(t['delta'] for t in ledger)


def coins_spent(ledger: list[CoinTransaction]) -> int:
    return -sum(t['delta'] for t in ledger if t['delta'] < 0)


def reconcile_coins(state: DashboardState) -> None:
    """Recompute the cached balance/spent totals in `settings` from the
    ledger. Called by award_coins() after every mutation, so the cheap
    cache in ALWAYS_LOADED settings can never drift from the ledger that
    backs it, even though the ledger itself is loaded lazily."""
    ledger = state.get('ledger') or []
    settings = state.setdefault('settings', cast(Settings, {}))
    settings['coinBalance'] = coin_balance(ledger)
    settings['coinsSpent'] = coins_spent(ledger)


def award_coins(
    state: DashboardState, delta: int, kind: str, ref: str, note: str
) -> CoinTransaction:
    """Append a ledger transaction and refresh the balance/spent cache.

    The only function that should ever mutate `state['ledger']` — every
    earn or spend path (shop checkout, ship approval, admin adjustment)
    calls this so the cache in `settings` can't fall out of sync with the
    ledger. Does not check sufficiency; callers that need to block an
    over-spend (checkout) check `coin_balance()` before calling this."""
    transaction: CoinTransaction = {
        'id': _item_id('coin'),
        'delta': delta,
        'kind': kind,
        'ref': ref,
        'note': note,
        'at': utc_iso(),
    }
    state.setdefault('ledger', []).append(transaction)
    reconcile_coins(state)
    return transaction


def generate_join_code() -> str:
    return secrets.token_urlsafe(9)


def unique_join_code(backend: Any, attempts: int = 5) -> str:
    for _ in range(attempts):
        code = generate_join_code()
        if backend.find_club_by_join_code(code) is None:
            return code
    return secrets.token_urlsafe(12)


# ── CSRF ──────────────────────────────────────────────────────────────────────


def get_csrf_token() -> str:
    token = session.get('csrf_token')
    if not token:
        token = secrets.token_urlsafe(24)
        session['csrf_token'] = token
    return token


def require_dashboard_csrf() -> tuple[Any, int] | None:
    token = request.headers.get('X-CSRF-Token', '')
    expected = session.get('csrf_token', '')
    if not token or not expected or not secrets.compare_digest(token, expected):
        return jsonify({'error': 'Your session token expired. Refresh and try again.'}), 403
    return None


# ── Shop catalog ──────────────────────────────────────────────────────────────

BASE_DIR: Final[str] = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT: Final[str] = os.path.dirname(BASE_DIR)
SHOP_JSON_PATH: Final[str] = os.path.join(PROJECT_ROOT, 'static', 'data', 'shop.json')


def _slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', (text or '').lower()).strip('-')


def load_shop_items() -> list[ShopItem]:
    try:
        with open(SHOP_JSON_PATH, encoding='utf-8-sig') as fh:
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
                'cost': entry.get('cost', ''),
                'image_src': entry.get('image-src', ''),
                'filter': entry.get('filter', ''),
            }
        )
    return items


SHOP_ITEMS: list[ShopItem] = load_shop_items()
_STICKER_FILES: list[str] | None = None

# Serializes shop.json reads/writes so two admins editing at once can't
# clobber each other (the app is a single process, so a lock is enough).
_SHOP_LOCK: Final[threading.Lock] = threading.Lock()
SHOP_FILTERS: Final[set[str]] = {'Hardware', 'Swag', 'Digital'}


def get_sticker_files() -> list[str]:
    global _STICKER_FILES
    if _STICKER_FILES is None:
        sticker_dir = os.path.join(PROJECT_ROOT, 'static', 'images', 'Stickers')
        try:
            _STICKER_FILES = sorted(
                f
                for f in os.listdir(sticker_dir)
                if os.path.splitext(f)[1].lower()
                in ('.png', '.svg', '.gif', '.webp', '.jpg', '.jpeg')
            )
        except OSError:
            _STICKER_FILES = []
    return _STICKER_FILES


def _read_shop_raw() -> list[dict[str, Any]]:
    try:
        with open(SHOP_JSON_PATH, encoding='utf-8') as fh:
            raw: Any = json.load(fh)
    except (OSError, ValueError):
        return []
    return raw if isinstance(raw, list) else []


def _write_shop_raw(raw: list[dict[str, Any]]) -> None:
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


def _normalize_cost(cost: str) -> str:
    """'$5', '5', '5.00' → '$5.00'; non-numeric labels ('Free', 'TBD') pass through."""
    text = (cost or '').strip()
    match = re.fullmatch(r'\$?([0-9]+(?:\.[0-9]{1,2})?)', text)
    return f'${float(match.group(1)):.2f}' if match else text


def _shop_hours(cost: str) -> str:
    """The 'hours' price is 1.5x the dollar cost; word labels mirror the cost."""
    match = re.fullmatch(r'\$([0-9]+(?:\.[0-9]{1,2})?)', cost or '')
    return f'${float(match.group(1)) * 1.5:.2f}' if match else (cost or '')


def add_shop_item(name: str, cost: str, image_src: str, item_filter: str) -> ShopItem:
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


def remove_shop_item(slug: str) -> bool:
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

DEFAULT_LANGUAGE: Final[str] = 'en'

DASHBOARD_LANGUAGES: Final[list[tuple[str, str]]] = [
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
SUPPORTED_LANGUAGES: Final[set[str]] = {code for code, _label in DASHBOARD_LANGUAGES}


def parse_language(value: str) -> str:
    """Return a supported language code, defaulting to English for anything else."""
    code = str(value or '').strip().lower()
    return code if code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def default_dashboard_state() -> DashboardState:
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
        'channels': [],
        'messages': [],
        'notifications': [],
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


def playtest_state() -> DashboardState:
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


def _storage() -> Any:
    if 'storage_backend' not in g:
        g.storage_backend = make_storage(session)
    return g.storage_backend


def _club_key() -> str:
    if 'club_key' not in g:
        email = (session.get('user') or {}).get('email') or ''
        g.club_key = _storage().resolve_club_key(email)
    return g.club_key


# The state keys a backend stores per club. A page can ask for a subset of
# these; anything outside the list (shopItems, cart) is filled in locally.
STATE_SECTIONS: Final[tuple[str, ...]] = (
    'members',
    'events',
    'newsletters',
    'orders',
    'itemRequests',
    'projects',
    'channels',
    'messages',
    'notifications',
)

# Sections every page needs regardless of what it renders: the roster drives
# viewer_role(), and the notification bell lives in the shared layout.
ALWAYS_LOADED: Final[frozenset[str]] = frozenset({'members', 'notifications'})

# Which sections each dashboard page actually renders, keyed by Flask
# endpoint. Endpoints not listed here get the full state. Keeping this map
# next to the loader (rather than in the routes) is what makes it safe:
# get_dashboard_state() drops the unlisted keys, and both shared backends
# treat a missing key as "leave this section alone" on save.
PAGE_SECTIONS: Final[dict[str, tuple[str, ...]]] = {
    'dashboard': ('events', 'projects', 'newsletters'),
    'dashboard_team': (),
    'dashboard_events': ('events',),
    'dashboard_ships': ('projects',),
    'dashboard_projects': ('projects',),
    'dashboard_levels': ('projects',),
    'dashboard_tools': (),
    'dashboard_shop': ('orders', 'itemRequests'),
    'dashboard_chat': ('channels', 'messages'),
    'dashboard_newsletters': ('newsletters',),
    'dashboard_map': (),
    'dashboard_settings': (),
    'dashboard_profile': ('projects',),
}


def sections_for_page(page: str) -> list[str] | None:
    """The sections the given endpoint needs, or None for "everything"."""
    if page not in PAGE_SECTIONS:
        return None
    return sorted(ALWAYS_LOADED | set(PAGE_SECTIONS[page]))


def sections_for_request() -> list[str] | None:
    """Sections needed by the endpoint currently being served.

    Pages outside the dashboard (landing, sign-in, join) render no club data
    at all, so they get the cheapest useful slice rather than a full load.
    """
    endpoint = (request.endpoint or '') if request else ''
    if endpoint in PAGE_SECTIONS:
        return sections_for_page(endpoint)
    if endpoint.startswith('dashboard') or endpoint.startswith('api_'):
        return None
    return sorted(ALWAYS_LOADED)


def viewer_club_state(sections: list[str] | None = None) -> ClubState | None:
    """The club's stored state. `sections` limits which parts are fetched;
    None means all of them.

    A request that first asks for a subset and later asks for more reloads —
    the cached partial isn't silently passed off as complete.
    """
    wanted = None if sections is None else set(sections) | ALWAYS_LOADED
    if 'club_state_loaded' in g:
        loaded = g.get('club_sections')
        if loaded is None or (wanted is not None and wanted <= loaded):
            return g.club_state
    g.club_state_loaded = True
    g.club_sections = wanted
    g.club_state = _storage().load(_club_key(), sections=sections)
    return g.club_state


def viewer_club_lite() -> ClubStateLite | None:
    if 'club_lite' in g:
        return g.club_lite
    if g.get('club_state_loaded') and g.get('club_state') is not None:
        g.club_lite = g.club_state
    else:
        g.club_lite = _storage().load_lite(_club_key())
    return g.club_lite


def get_dashboard_state(sections: list[str] | None = None) -> DashboardState:
    """The viewer's dashboard state.

    `sections` names the state keys the caller will read; None loads
    everything. A partial state deliberately omits the keys it didn't fetch
    instead of defaulting them to empty — save_dashboard_state() treats a
    missing key as "leave alone", so an omitted section can't be erased by a
    page that never loaded it.
    """
    # A caller naming only the sections it reads still gets ALWAYS_LOADED —
    # otherwise the role check and the notification bell would break on any
    # endpoint that asked for a narrow slice.
    wanted = None if sections is None else set(sections) | ALWAYS_LOADED
    if 'dashboard_state' in g:
        loaded = g.get('dashboard_sections')
        if loaded is None or (wanted is not None and wanted <= loaded):
            return g.dashboard_state

    backend = _storage()
    state = viewer_club_state(sections)
    g.dashboard_sections = wanted
    if state is None:
        state = default_dashboard_state()
        g.dashboard_sections = None
        g.dashboard_state = state
        return state

    # Sections this request never fetched. Their keys stay absent so nothing
    # downstream mistakes "not loaded" for "empty". Session mode is exempt:
    # its state object *is* the session dict, so dropping keys from it would
    # delete them for real rather than just skip a fetch.
    omitted = (
        set()
        if wanted is None or isinstance(backend, SessionStorage)
        else {s for s in STATE_SECTIONS if s not in wanted}
    )

    defaults = default_dashboard_state()
    changed = False
    for key, value in defaults.items():
        if key in omitted:
            state.pop(key, None)
            continue
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


MAX_STATE_COOKIE_BYTES: Final[int] = 2800

# In session (cookie) mode, keep only this many recent chat messages so a busy
# channel can't overrun the cookie. Airtable mode keeps the full history.
MAX_SESSION_MESSAGES: Final[int] = 30


class StateTooLarge(Exception):  # noqa: N818
    pass


def _state_cookie_size(state: DashboardState) -> int:
    raw = json.dumps(state, separators=(',', ':')).encode()
    return len(base64.urlsafe_b64encode(zlib.compress(raw)))


def save_dashboard_state(state: DashboardState) -> None:
    backend = _storage()
    if isinstance(backend, SessionStorage):
        persisted = {key: value for key, value in state.items() if key != 'shopItems'}
        # Chat messages can grow without bound; the session cookie can't. Keep
        # only the most recent few so a busy channel doesn't blow the cookie
        # budget (Airtable mode has no cap and keeps everything).
        if persisted.get('messages'):
            persisted['messages'] = persisted['messages'][-MAX_SESSION_MESSAGES:]
        if _state_cookie_size(persisted) > MAX_STATE_COOKIE_BYTES:
            raise StateTooLarge()
        backend.save(_club_key(), persisted)
    else:
        session['cart_items'] = state.get('cart') or []
        session.modified = True
        persisted = {key: value for key, value in state.items() if key not in ('shopItems', 'cart')}
        backend.save(_club_key(), persisted)
    g.dashboard_state = state
    g.club_state = state
    g.club_state_loaded = True


# ── JSON API utilities ─────────────────────────────────────────────────────────


DEFAULT_PAGE_SIZE: Final[int] = 25
MAX_PAGE_SIZE: Final[int] = 200


def _positive_int(raw: Any, default: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, min(value, maximum))


def paginate(
    items: list[Any],
    page: int | None = None,
    per_page: int | None = None,
) -> dict[str, Any]:
    """One page of `items` plus the counts a pager needs to render.

    Reads ?page= and ?per_page= from the request when not passed explicitly.
    Both are clamped, so a hostile or buggy client can't ask for page
    -1 or a million rows at once.
    """
    args = request.args if request else {}
    per_page = per_page or _positive_int(args.get('per_page'), DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE)
    total = len(items)
    pages = max(1, math.ceil(total / per_page))
    page = page or _positive_int(args.get('page'), 1, pages)
    page = min(page, pages)
    start = (page - 1) * per_page
    return {
        'items': items[start : start + per_page],
        'page': page,
        'perPage': per_page,
        'total': total,
        'pages': pages,
        'hasMore': start + per_page < total,
    }


def json_payload() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def json_error(message: str, status: int = 400) -> tuple[Any, int]:
    return jsonify({'error': message}), status


# ── Image utilities ────────────────────────────────────────────────────────────


def _sniff_image(data: bytes) -> tuple[str | None, str | None]:
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png', 'png'
    if data[:3] == b'\xff\xd8\xff':
        return 'image/jpeg', 'jpg'
    if data[:6] in (b'GIF87a', 'GIF89a'):
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
        raise StorageError(
            f'Image upload failed ({response.status_code}){": " + detail if detail else ""}.'
        )
    return (response.json() or {}).get('url', '')


# ── Generic utilities ──────────────────────────────────────────────────────────

T = TypeVar('T', bound=dict[str, Any])


def find_by_id(items: list[T], item_id: str) -> T | None:
    return next((item for item in items if item.get('id') == item_id), None)


def clean_text(value: Any, fallback: str = '', max_len: int = 300) -> str:
    if value is None:
        return fallback
    return str(value).strip()[:max_len]


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {'1', 'true', 'yes', 'on'}


# ── Event construction ─────────────────────────────────────────────────────────

# Allowed recurrence cadences for events; '' means the event does not repeat.
EVENT_REPEAT_OPTIONS: Final[set[str]] = {'', 'daily', 'weekly', 'biweekly', 'monthly', 'weekdays'}


def parse_repeat(value: Any, fallback: str = '') -> str:
    """Return a supported repeat cadence, or the fallback for anything else."""
    code = str(value or '').strip().lower()
    return code if code in EVENT_REPEAT_OPTIONS else fallback


def event_from_payload(
    payload: dict[str, Any], existing: dict[str, Any] | None = None
) -> tuple[Event | None, str | None]:
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


def _viewer_email() -> str:
    return ((session.get('user') or {}).get('email') or '').strip().lower()


def _join_missing(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f'{items[0]} and {items[1]}'
    return ', '.join(items[:-1]) + ', and ' + items[-1]


def _owned_project_or_error(
    state: DashboardState, project_id: str
) -> tuple[Project | None, tuple[Any, int] | None]:
    project = find_by_id(state.get('projects') or [], project_id)
    if not project:
        return None, json_error('Project not found.', 404)
    if (project.get('ownerEmail') or '').strip().lower() != _viewer_email():
        return None, json_error('You can only change your own projects.', 403)
    return project, None


# ── Chat helpers ───────────────────────────────────────────────────────────────

MAX_MESSAGE_LEN: Final[int] = 500


def channel_from_payload(
    payload: dict[str, Any], existing: dict[str, Any] | None = None
) -> tuple[dict[str, str] | None, str | None]:
    """Validate a channel create/edit payload. Returns (fields, error)."""
    existing = existing or {}
    name = clean_text(payload.get('name'), existing.get('name', ''), max_len=60).lstrip('#').strip()
    description = clean_text(
        payload.get('description'), existing.get('description', ''), max_len=140
    )
    if not name:
        return None, 'Channel name is required.'
    return {'name': name, 'description': description}, None


# ── Admin helpers ──────────────────────────────────────────────────────────────

ADMIN_REVIEW_STATUSES: Final[set[str]] = {'Shipped', 'Draft'}


def _persist_club(backend: Any, club_key: str, state: ClubState) -> None:
    if isinstance(backend, SessionStorage):
        backend.save(club_key, state)
    else:
        persisted = {key: value for key, value in state.items() if key not in ('shopItems', 'cart')}
        backend.save(club_key, persisted)


def _load_admin_club(
    backend: Any, club_key: str
) -> tuple[ClubState | None, tuple[Any, int] | None]:
    state = backend.load(club_key)
    if state is None:
        return None, json_error('Club not found.', 404)
    return state, None


def _find_club_by_project(backend: Any, project_id: str) -> tuple[ClubState | None, str | None]:
    for club in backend.list_clubs():
        club_key = club.get('clubKey', '')
        state = backend.load(club_key)
        if state is None:
            continue
        if find_by_id(state.get('projects') or [], project_id):
            return state, club_key
    return None, None
