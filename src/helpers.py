import base64
import json
import os
import re
import secrets
import zlib
from collections.abc import Callable
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Final, TypeVar, cast

from flask import flash, g, jsonify, redirect, request, session, url_for

from .helpers_demo import default_dashboard_state as _default_dashboard_state
from .helpers_demo import playtest_state as _playtest_state
from .helpers_shop import (
    SHOP_FILTERS,
    SHOP_ITEMS,
    _parse_coins,
    _sniff_image,
    _upload_to_blob,
    add_shop_item,
    get_sticker_files,
    load_shop_items,
    remove_shop_item,
)
from .helpers_state import award_coins_if_unprocessed
from .helpers_types import (
    Channel,
    ClubState,
    ClubStateLite,
    CoinTransaction,
    DashboardState,
    Event,
    ItemRequest,
    Member,
    Message,
    Newsletter,
    Notification,
    Order,
    OrderItem,
    Project,
    Settings,
    ShopItem,
    Workshop,
)
from .helpers_validation import (
    ADMIN_REVIEW_STATUSES,
    DEFAULT_PAGE_SIZE,
    EVENT_REPEAT_OPTIONS,
    MAX_PAGE_SIZE,
    SHOP_JSON_PATH,
    _find_club_by_project,
    _load_admin_club,
    _persist_club,
    _positive_int,
    channel_from_payload,
    clean_text,
    event_from_payload,
    find_by_id,
    json_error,
    json_payload,
    paginate,
    parse_bool,
    parse_repeat,
    workshop_from_payload,
)
from .storage import SessionStorage, make_storage

__all__ = [
    # Config constants
    'ADMIN_EMAILS',
    'COINS_PER_APPROVED_SHIP',
    'STARTER_GRANT_COINS',
    # Types
    'Channel',
    'ClubState',
    'ClubStateLite',
    'CoinTransaction',
    'DashboardState',
    'Event',
    'ItemRequest',
    'Member',
    'Message',
    'Newsletter',
    'Notification',
    'Order',
    'OrderItem',
    'Project',
    'Settings',
    'ShopItem',
    'Workshop',
    # Shop catalog
    'SHOP_FILTERS',
    'SHOP_ITEMS',
    'SHOP_JSON_PATH',
    'add_shop_item',
    'get_sticker_files',
    'load_shop_items',
    'remove_shop_item',
    # Validation / payload helpers
    'ADMIN_REVIEW_STATUSES',
    'DEFAULT_PAGE_SIZE',
    'EVENT_REPEAT_OPTIONS',
    'MAX_PAGE_SIZE',
    '_find_club_by_project',
    '_load_admin_club',
    '_persist_club',
    '_positive_int',
    'channel_from_payload',
    'clean_text',
    'feature_enabled',
    'event_from_payload',
    'find_by_id',
    'json_error',
    'json_payload',
    'paginate',
    'parse_bool',
    'parse_repeat',
    'workshop_from_payload',
    # Private-but-exported helpers
    '_parse_coins',
    '_sniff_image',
    '_upload_to_blob',
    'award_coins_if_unprocessed',
]

# ── Config constants (derived from env) ────────────────────────────────────────

ADMIN_EMAILS: Final[set[str]] = {
    email.strip().lower()
    for email in os.environ.get('ADMIN_EMAILS', '').split(',')
    if email.strip()
}

COINS_PER_APPROVED_SHIP: Final[int] = 25
STARTER_GRANT_COINS: Final[int] = 50


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
    if not isinstance(token, str) or not token:
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


def _slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', (text or '').lower()).strip('-')


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
    return _default_dashboard_state(SHOP_ITEMS)


def playtest_state() -> DashboardState:
    return _playtest_state(SHOP_ITEMS)


# ── Storage layer ──────────────────────────────────────────────────────────────


def _storage() -> Any:
    if 'storage_backend' not in g:
        g.storage_backend = make_storage(session)
    return g.storage_backend


def _club_key() -> str:
    if 'club_key' not in g:
        email = (session.get('user') or {}).get('email') or ''
        g.club_key = _storage().resolve_club_key(email)
    return cast(str, g.club_key)


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
    'ledger',
    'workshops',
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
    'dashboard': ('events', 'projects', 'newsletters', 'workshops', 'ledger'),
    'dashboard_team': (),
    'dashboard_events': ('events',),
    'dashboard_ships': ('projects',),
    'dashboard_projects': ('projects',),
    'dashboard_levels': ('projects',),
    'dashboard_tools': (),
    'dashboard_shop': ('orders', 'itemRequests'),
    'dashboard_workshops': ('workshops',),
    'dashboard_chat': ('channels', 'messages'),
    'dashboard_notifications': ('newsletters',),
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
            return cast(ClubState | None, g.club_state)
    g.club_state_loaded = True
    g.club_sections = wanted
    g.club_state = _storage().load(_club_key(), sections=sections)
    return cast(ClubState | None, g.club_state)


def viewer_club_lite() -> ClubStateLite | None:
    if 'club_lite' in g:
        return cast(ClubStateLite | None, g.club_lite)
    if g.get('club_state_loaded') and g.get('club_state') is not None:
        g.club_lite = g.club_state
    else:
        g.club_lite = _storage().load_lite(_club_key())
    return cast(ClubStateLite | None, g.club_lite)


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
            return cast(DashboardState, g.dashboard_state)

    backend = _storage()
    raw_state = viewer_club_state(sections)
    g.dashboard_sections = wanted
    if raw_state is None:
        fresh = default_dashboard_state()
        g.dashboard_sections = None
        g.dashboard_state = fresh
        return fresh

    # Sections this request never fetched. Their keys stay absent so nothing
    # downstream mistakes "not loaded" for "empty". Session mode is exempt:
    # its state object *is* the session dict, so dropping keys from it would
    # delete them for real rather than just skip a fetch.
    omitted = (
        set()
        if wanted is None or isinstance(backend, SessionStorage)
        else {s for s in STATE_SECTIONS if s not in wanted}
    )

    state = cast(DashboardState, raw_state)
    state_dict = cast(dict[str, Any], state)
    defaults = default_dashboard_state()
    changed = False
    for key, value in defaults.items():
        if key in omitted:
            state_dict.pop(key, None)
            continue
        if key not in state_dict:
            state_dict[key] = value
            changed = True

    settings = cast(dict[str, Any], state_dict.setdefault('settings', {}))
    for key, value in defaults['settings'].items():
        if key not in settings:
            settings[key] = value
            changed = True

    # coinBalance/coinsSpent are a cache derived from `ledger`, not an
    # independent field — the loop above may have just seeded them from a
    # throwaway default_dashboard_state() call (which side-effects its own
    # STARTER_GRANT_COINS award) purely to keep `settings` complete under a
    # schemaless backend. Once `ledger` itself is known for this request
    # (present in `state`, whether loaded from storage or backfilled to []
    # above), unconditionally recompute the cache from it so it always
    # matches this specific club's real ledger and never keeps a defaulted
    # guess. `ledger` is absent only when this request's `sections` never
    # asked for it (narrow page loads) — nothing to reconcile against then,
    # so the previously-loaded/backfilled cache value is left alone.
    if 'ledger' in state:
        prev_balance = settings.get('coinBalance')
        prev_spent = settings.get('coinsSpent')
        reconcile_coins(state)
        if settings.get('coinBalance') != prev_balance or settings.get('coinsSpent') != prev_spent:
            changed = True

    state['shopItems'] = [cast(ShopItem, dict(item)) for item in SHOP_ITEMS]

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

# Same reasoning as MAX_SESSION_MESSAGES, for the coin ledger.
MAX_SESSION_LEDGER_ENTRIES: Final[int] = 100


class StateTooLarge(Exception):  # noqa: N818
    pass


def _state_cookie_size(state: DashboardState) -> int:
    raw = json.dumps(state, separators=(',', ':')).encode()
    return len(base64.urlsafe_b64encode(zlib.compress(raw)))


def save_dashboard_state(state: DashboardState) -> None:
    backend = _storage()
    if isinstance(backend, SessionStorage):
        persisted: dict[str, Any] = {key: value for key, value in state.items() if key != 'shopItems'}
        # Chat messages can grow without bound; the session cookie can't. Keep
        # only the most recent few so a busy channel doesn't blow the cookie
        # budget (Airtable mode has no cap and keeps everything).
        if persisted.get('messages'):
            persisted['messages'] = persisted['messages'][-MAX_SESSION_MESSAGES:]
        # Same reasoning as messages: the cookie can't hold unbounded history.
        # settings.coinBalance/coinsSpent were already reconciled from the
        # full ledger by award_coins() earlier in this request, so trimming
        # the persisted list here only drops old audit rows — never coins.
        if persisted.get('ledger'):
            persisted['ledger'] = persisted['ledger'][-MAX_SESSION_LEDGER_ENTRIES:]
        if _state_cookie_size(cast(DashboardState, persisted)) > MAX_STATE_COOKIE_BYTES:
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


MAX_MESSAGE_LEN: Final[int] = 500

def feature_enabled(name: str) -> bool:
    """Env-driven feature flag: on unless the env var is set to false/0/off/no."""
    return os.environ.get(name, '').strip().lower() not in ('false', '0', 'off', 'no')
