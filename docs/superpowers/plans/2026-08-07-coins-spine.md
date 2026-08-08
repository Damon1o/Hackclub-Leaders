# Coins Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dollar-priced shop with a real, auditable Hack Club coin ledger — earn/spend transactions, a cached balance that rides on every dashboard page, and a shop that redeems coins instead of dollars.

**Architecture:** An append-only `ledger` list (new `STATE_SECTIONS` entry, lazily loaded) is the source of truth; `settings.coinBalance`/`coinsSpent` are a two-integer cache recomputed by `reconcile_coins()` every time `award_coins()` appends a transaction, so the cheap cache rides in `ALWAYS_LOADED` `settings` while the expensive full history stays opt-in. All three storage backends (session cookie, Airtable, MongoDB) get the new section registered in lockstep, closing the exact class of bug that already silently dropped `notifications` and `settings.language` on this repo's Airtable backend.

**Tech Stack:** Flask 3.1, Python 3.10+ (mypy `--strict` in CI), vanilla JS (no bundler, no JS test runner — pytest is the only automated test tool in this repo), Jinja2, session/Airtable/MongoDB storage backends.

## Global Constraints

- Python `>=3.10`; CI runs `ruff check`, `ruff format --check`, and `mypy src/ --strict` on 3.10/3.11/3.12 — every new function needs full type annotations.
- `ruff format` uses single quotes, 100-char lines (`pyproject.toml`).
- Never hand-edit `static/js/i18n/<code>.js` — those are generated. Edit `static/js/i18n-data.js` and run `python scripts/split_i18n_data.py`.
- Never touch `.env`/`.env.example` (repo-wide deny rule).
- Follow the existing five-place pattern for any new `STATE_SECTIONS` key: `src/helpers.py` (`STATE_SECTIONS` + `default_dashboard_state()`), `src/storage.py` (`CHILD_TABLES` + a `*_FIELDS` list), `src/storage_mongo.py` (`CHILD_COLLECTIONS` + `INDEXES`). Missing one of these is exactly how `notifications` and `settings.language` silently stopped persisting on Airtable previously.
- `COINS_PER_APPROVED_SHIP = 25` is declared in this plan for Spec 3 (ship review) to consume later; it is not called by anything in this plan — only declared, so Spec 3 doesn't have to touch `helpers.py`'s constants section again.
- No task in this plan touches workshops, ship review/approval, the Explore feed, or the landing page — those are Specs 2–9 per `docs/superpowers/specs/2026-08-07-coins-spine-design.md`.

---

### Task 1: Ledger data model and pure functions

**Files:**
- Modify: `src/helpers.py` (types near line 88-98, constants near line 20-28, new functions near line 260)
- Test: `tests/test_coins.py` (new file)

**Interfaces:**
- Consumes: `_item_id(prefix: str) -> str` (existing, `src/helpers.py:254`), `utc_iso() -> str` (existing, `src/helpers.py:258-260`).
- Produces: `CoinTransaction` TypedDict (`id`, `delta`, `kind`, `ref`, `note`, `at`); `coin_balance(ledger: list[CoinTransaction]) -> int`; `coins_spent(ledger: list[CoinTransaction]) -> int`; `reconcile_coins(state: DashboardState) -> None`; `award_coins(state: DashboardState, delta: int, kind: str, ref: str, note: str) -> CoinTransaction` — the **only** function anything should call to mutate the ledger. `COINS_PER_APPROVED_SHIP: Final[int] = 25`, `STARTER_GRANT_COINS: Final[int] = 50`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_coins.py`:

```python
from src.helpers import CoinTransaction, award_coins, coin_balance, coins_spent, reconcile_coins


def _tx(delta: int, kind: str = 'ship_approved') -> CoinTransaction:
    return {'id': 'coin-x', 'delta': delta, 'kind': kind, 'ref': '', 'note': '', 'at': '2026-08-07T00:00:00Z'}


def test_coin_balance_sums_all_deltas():
    ledger = [_tx(25), _tx(-10), _tx(50)]
    assert coin_balance(ledger) == 65


def test_coin_balance_empty_ledger_is_zero():
    assert coin_balance([]) == 0


def test_coins_spent_only_counts_negative_deltas():
    ledger = [_tx(25), _tx(-10), _tx(-5)]
    assert coins_spent(ledger) == 15


def test_coins_spent_ignores_earn_entries():
    ledger = [_tx(25), _tx(50)]
    assert coins_spent(ledger) == 0


def test_reconcile_coins_writes_cache_into_settings():
    state = {'ledger': [_tx(25), _tx(-10)], 'settings': {}}
    reconcile_coins(state)
    assert state['settings']['coinBalance'] == 15
    assert state['settings']['coinsSpent'] == 10


def test_reconcile_coins_handles_missing_ledger_key():
    state = {'settings': {}}
    reconcile_coins(state)
    assert state['settings']['coinBalance'] == 0
    assert state['settings']['coinsSpent'] == 0


def test_award_coins_appends_transaction_and_reconciles():
    state = {'ledger': [], 'settings': {}}
    tx = award_coins(state, 25, 'ship_approved', 'proj-1', 'Approved: Tide Tracker')
    assert len(state['ledger']) == 1
    assert state['ledger'][0] is tx
    assert tx['delta'] == 25
    assert tx['kind'] == 'ship_approved'
    assert tx['ref'] == 'proj-1'
    assert tx['id']
    assert tx['at']
    assert state['settings']['coinBalance'] == 25


def test_award_coins_creates_ledger_key_if_absent():
    state = {'settings': {}}
    award_coins(state, -10, 'shop_order', 'order-1', 'Order: Stickers')
    assert state['ledger'][0]['delta'] == -10
    assert state['settings']['coinBalance'] == -10


def test_award_coins_negative_delta_updates_spent_cache():
    state = {'ledger': [], 'settings': {}}
    award_coins(state, 50, 'starter_grant', '', 'Welcome grant')
    award_coins(state, -30, 'shop_order', 'order-1', 'Order: Pin')
    assert state['settings']['coinBalance'] == 20
    assert state['settings']['coinsSpent'] == 30
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_coins.py -v`
Expected: FAIL with `ImportError: cannot import name 'CoinTransaction' from 'src.helpers'`

- [ ] **Step 3: Add the type, constants, and functions**

In `src/helpers.py`, add near the other config constants (after `ADMIN_EMAILS`, line 28):

```python
COINS_PER_APPROVED_SHIP: Final[int] = 25
STARTER_GRANT_COINS: Final[int] = 50
```

Add the `CoinTransaction` TypedDict right after `OrderItem`/before `Order` (after line 90, so `Order.items` keeps referring to a type that's already defined):

```python
class CoinTransaction(TypedDict):
    id: str
    delta: int
    kind: str
    ref: str
    note: str
    at: str
```

Add the functions after `utc_iso()` (after line 260, before `generate_join_code`):

```python
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
    settings = state.setdefault('settings', {})
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
```

Add `ledger: list[CoinTransaction]` to the `DashboardState` TypedDict (after `newsletters`, before `settings`, around line 149):

```python
    newsletters: list[Newsletter]
    ledger: list[CoinTransaction]
    settings: Settings
```

Add `coinBalance: int` and `coinsSpent: int` to the `Settings` TypedDict (after `language`, around line 136):

```python
    language: str
    coinBalance: int
    coinsSpent: int
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_coins.py -v`
Expected: 9 passed

- [ ] **Step 5: Run mypy to verify strict typing holds**

Run: `mypy src/helpers.py --strict`
Expected: no errors (fix any TypedDict key-access complaints by adjusting the new functions, not by loosening types)

- [ ] **Step 6: Commit**

```bash
git add src/helpers.py tests/test_coins.py
git commit -m "feat: add coin ledger data model and pure functions"
```

---

### Task 2: Register `ledger` across all three storage backends

**Files:**
- Modify: `src/helpers.py` (`STATE_SECTIONS` line 652-662, `default_dashboard_state()` line 468-534, `save_dashboard_state()` line 820-836)
- Modify: `src/storage.py` (module docstring line 19-38, new `LEDGER_FIELDS`, `CHILD_TABLES`, `OPTIONAL_CHILD_KEYS`, `_item_fields()`/`load()` int handling)
- Modify: `src/storage_mongo.py` (`CHILD_COLLECTIONS`, `INDEXES`, `load()` sort branch)
- Test: `tests/test_coins.py` (append), `tests/test_storage_mongo.py` (append)

**Interfaces:**
- Consumes: `award_coins`, `CoinTransaction`, `STARTER_GRANT_COINS` (Task 1).
- Produces: `STATE_SECTIONS` now includes `'ledger'`; every club's default state carries a `ledger` list seeded with one `starter_grant` transaction; both shared backends persist and load it.

- [ ] **Step 1: Write the failing registration test**

Append to `tests/test_coins.py`:

```python
from src.storage import AirtableStorage
from src.storage_mongo import CHILD_COLLECTIONS, INDEXES


def test_every_state_section_has_an_airtable_table():
    from src.helpers import STATE_SECTIONS

    airtable_keys = {state_key for _s, _d, state_key, _f in AirtableStorage.CHILD_TABLES}
    missing = set(STATE_SECTIONS) - airtable_keys
    assert not missing, f'STATE_SECTIONS keys with no AirtableStorage.CHILD_TABLES entry: {missing}'


def test_every_state_section_has_a_mongo_collection():
    from src.helpers import STATE_SECTIONS

    missing = set(STATE_SECTIONS) - set(CHILD_COLLECTIONS)
    assert not missing, f'STATE_SECTIONS keys with no Mongo CHILD_COLLECTIONS entry: {missing}'


def test_every_mongo_collection_has_an_index():
    missing = set(CHILD_COLLECTIONS) - set(INDEXES)
    assert not missing, f'CHILD_COLLECTIONS with no INDEXES entry: {missing}'


def test_default_dashboard_state_seeds_a_starter_grant(client):
    with client.session_transaction() as sess:
        sess['user'] = {'name': 'Test Leader', 'email': 'leader@test.com'}
    with client.application.test_request_context():
        from flask import session as flask_session

        flask_session['user'] = {'name': 'Test Leader', 'email': 'leader@test.com'}
        from src.helpers import STARTER_GRANT_COINS, default_dashboard_state

        state = default_dashboard_state()
        assert len(state['ledger']) == 1
        assert state['ledger'][0]['kind'] == 'starter_grant'
        assert state['ledger'][0]['delta'] == STARTER_GRANT_COINS
        assert state['settings']['coinBalance'] == STARTER_GRANT_COINS
        assert state['settings']['coinsSpent'] == 0
```

This test file needs the `client` fixture — add `import pytest` and use the existing `conftest.py` fixtures (no changes needed there; `client` is already defined in `tests/conftest.py:14-17`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_coins.py -v`
Expected: FAIL — `test_every_state_section_has_an_airtable_table` and `test_every_state_section_has_a_mongo_collection` fail because `'ledger'` isn't in `STATE_SECTIONS` yet (so this specific pair can't fail on ledger — write them now anyway since they're the permanent safety net; they'll start passing once `STATE_SECTIONS` doesn't reference an unregistered key). `test_default_dashboard_state_seeds_a_starter_grant` FAILS with `KeyError: 'ledger'`.

- [ ] **Step 3: Register `ledger` in `src/helpers.py`**

In `STATE_SECTIONS` (line 652-662), add `'ledger'`:

```python
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
)
```

In `default_dashboard_state()` (line 468-534), change the function to build a local `state` variable, seed the starter grant, and return it. Replace the `return { ... }` block with:

```python
    state: DashboardState = {
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
        'ledger': [],
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
            'coinBalance': 0,
            'coinsSpent': 0,
        },
    }
    award_coins(state, STARTER_GRANT_COINS, 'starter_grant', '', 'Welcome to Hack Club — here are your first coins.')
    return state
```

`playtest_state()` (line 537-631) needs **no changes** — `get_dashboard_state()`'s existing default-backfill loop (line 776-790) already fills any top-level key a loaded state is missing (including `ledger`) and any `settings` key it's missing (including `coinBalance`/`coinsSpent`) from a fresh `default_dashboard_state()` call. This is the same mechanism that already back-fills `notifications` into `playtest_state()` today, which also never sets that key.

In `save_dashboard_state()` (line 820-836), cap the ledger the same way messages are already capped in cookie mode — the cache in `settings` was already reconciled from the full in-memory ledger by `award_coins()` earlier in the request, so truncating the *persisted* list here only trims history, never the balance:

```python
MAX_SESSION_LEDGER_ENTRIES: Final[int] = 100
```

Add this constant next to `MAX_SESSION_MESSAGES` (line 808). Then in `save_dashboard_state()`, right after the existing messages-truncation block:

```python
        if persisted.get('messages'):
            persisted['messages'] = persisted['messages'][-MAX_SESSION_MESSAGES:]
        # Same reasoning as messages: the cookie can't hold unbounded history.
        # settings.coinBalance/coinsSpent were already reconciled from the
        # full ledger by award_coins() earlier in this request, so trimming
        # the persisted list here only drops old audit rows — never coins.
        if persisted.get('ledger'):
            persisted['ledger'] = persisted['ledger'][-MAX_SESSION_LEDGER_ENTRIES:]
        if _state_cookie_size(persisted) > MAX_STATE_COOKIE_BYTES:
            raise StateTooLarge()
```

- [ ] **Step 4: Register `ledger` in `src/storage.py`**

Update the module docstring's Airtable schema block (line 19-38) to add the Ledger table:

```python
  Ledger       App Id*, Delta, Kind, Ref, Note, At, Club Email
```

(Insert this line after the `Projects` row, before the closing `A "ship" is just...` paragraph.)

Add `LEDGER_FIELDS` after `PROJECT_FIELDS` (after line 98):

```python
LEDGER_FIELDS: Final[list[tuple[str, str]]] = [
    ('delta', 'Delta'),
    ('kind', 'Kind'),
    ('ref', 'Ref'),
    ('note', 'Note'),
    ('at', 'At'),
]
```

Add a `'ledger'` entry to `AirtableStorage.CHILD_TABLES` (line 221-231):

```python
    CHILD_TABLES: Final[list[tuple[str, str, str, list[tuple[str, str]]]]] = [
        ('MEMBERS', 'Members', 'members', MEMBER_FIELDS),
        ('EVENTS', 'Events', 'events', EVENT_FIELDS),
        ('NEWSLETTERS', 'Newsletters', 'newsletters', NEWSLETTER_FIELDS),
        ('ORDERS', 'Orders', 'orders', ORDER_FIELDS),
        ('ITEM_REQUESTS', 'ItemRequests', 'itemRequests', ITEM_REQUEST_FIELDS),
        ('PROJECTS', 'Projects', 'projects', PROJECT_FIELDS),
        ('CHANNELS', 'Channels', 'channels', CHANNEL_FIELDS),
        ('MESSAGES', 'Messages', 'messages', MESSAGE_FIELDS),
        ('LEDGER', 'Ledger', 'ledger', LEDGER_FIELDS),
    ]
```

Add `'ledger'` to `OPTIONAL_CHILD_KEYS` (line 238) — this is a brand-new table, so existing Airtable bases without it must degrade to an empty ledger instead of erroring, exactly like `channels`/`messages` did when chat was added:

```python
    OPTIONAL_CHILD_KEYS: Final[set[str]] = {'itemRequests', 'channels', 'messages', 'ledger'}
```

In `load()` (line 549-619), the per-item field loop currently special-cases `attendees` as an int (line 601-602). Add `delta`:

```python
                for item_key, field in field_pairs:
                    value = fields.get(field)
                    if item_key in BOOL_KEYS:
                        item[item_key] = bool(value)
                    elif item_key in ('attendees', 'delta'):
                        item[item_key] = int(value or 0)
                    else:
                        item[item_key] = value or ''
```

In `_item_fields()` (line 671-691), same change:

```python
        for item_key, field in field_pairs:
            value = item.get(item_key)
            if item_key in BOOL_KEYS:
                fields[field] = bool(value)
            elif item_key in ('attendees', 'delta'):
                fields[field] = int(value or 0)
            else:
                fields[field] = value or ''
```

- [ ] **Step 5: Register `ledger` in `src/storage_mongo.py`**

Add `'ledger'` to `CHILD_COLLECTIONS` (line 36-46):

```python
CHILD_COLLECTIONS: Final[list[str]] = [
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
]
```

Add an `INDEXES` entry (after the `'notifications'` entry, line 84-87) — mirrors the notifications index shape (a future history view reads newest-first per club):

```python
    'ledger': [
        ([('clubKey', ASCENDING), ('at', DESCENDING)], False),
    ],
```

In `load()` (line 299-335), the per-collection sort branch (line 322-330) needs a `ledger` case:

```python
        for key in wanted:
            sort = None
            if key == 'events':
                sort = [('date', ASCENDING)]
            elif key == 'messages':
                sort = [('createdAt', ASCENDING)]
            elif key in ('notifications', 'ledger'):
                # Both read newest-first: the bell menu and any future coin
                # history view.
                sort = [('createdAt', DESCENDING)] if key == 'notifications' else [('at', DESCENDING)]
```

- [ ] **Step 6: Run all tests to verify they pass**

Run: `pytest tests/test_coins.py -v`
Expected: 13 passed

Run: `pytest tests/ -v`
Expected: all tests pass (this catches any existing test that constructed a `DashboardState`/`ClubState` literal missing the new `ledger`/`coinBalance`/`coinsSpent` keys and would now fail a strict comparison — none are expected here since Python dict equality in existing tests compares specific keys, not whole-dict equality, but run the full suite to be sure)

- [ ] **Step 7: Run mypy on the three modified modules**

Run: `mypy src/helpers.py src/storage.py src/storage_mongo.py --strict`
Expected: no errors

- [ ] **Step 8: Commit**

```bash
git add src/helpers.py src/storage.py src/storage_mongo.py tests/test_coins.py
git commit -m "feat: register coin ledger across session, Airtable, and Mongo backends"
```

---

### Task 3: Convert the shop from dollars to coins — types, parser, and catalog

**Files:**
- Modify: `src/helpers.py` (`ShopItem`/`OrderItem` types, `_normalize_cost`/`_shop_hours` → `_parse_coins`, `load_shop_items()`, `add_shop_item()`)
- Modify: `static/data/shop.json` (all 30 entries: dollar strings → coin ints, `hours` key removed)
- Modify: `tests/test_admin_shop.py` (assertions updated for the new int-cost model)

**Interfaces:**
- Consumes: nothing from Tasks 1-2.
- Produces: `ShopItem.cost: int | None` (`None` = admin hasn't priced it yet, was `'TBD'`); `OrderItem` gains `coinCost: int` (Task 4 populates it); `_parse_coins(cost: str) -> int | None` replaces `_normalize_cost`; `add_shop_item(name, cost, image_src, item_filter) -> ShopItem` keeps its signature (still takes raw admin-entered text) but now returns/stores an int-or-None `cost`.

- [ ] **Step 1: Write the failing tests**

Replace the contents of `tests/test_admin_shop.py` (the whole file — every assertion here touches the type that's changing):

```python
import json

import pytest

from src import helpers


@pytest.fixture
def shop_file(tmp_path, monkeypatch):
    """Point the shop writer at a throwaway catalog so tests never touch the
    real static/data/shop.json."""
    path = tmp_path / 'shop.json'
    path.write_text(
        json.dumps(
            [
                {
                    'name': 'Sticker Pack',
                    'cost': 0,
                    'image-src': '/static/images/shop/sticker-pack.png',
                    'filter': 'Swag',
                },
            ]
        ),
        encoding='utf-8',
    )
    monkeypatch.setattr(helpers, 'SHOP_JSON_PATH', str(path))
    return path


def _read(path):
    return json.loads(path.read_text(encoding='utf-8'))


# ── Coin parser ──────────────────────────────────────────────────────────────


def test_parse_coins_plain_digits():
    assert helpers._parse_coins('50') == 50


def test_parse_coins_dollar_prefix():
    assert helpers._parse_coins('$50') == 50


def test_parse_coins_decimal_suffix():
    assert helpers._parse_coins('50.00') == 50


def test_parse_coins_free_is_zero():
    assert helpers._parse_coins('Free') == 0
    assert helpers._parse_coins('free') == 0


def test_parse_coins_unpriced_is_none():
    assert helpers._parse_coins('TBD') is None
    assert helpers._parse_coins('') is None
    assert helpers._parse_coins('garbage') is None


# ── Shop writer (helpers) ────────────────────────────────────────────────────


def test_add_shop_item_appends_and_prices(shop_file):
    item = helpers.add_shop_item('Arduino Kit', '25', 'https://img/a.png', 'Hardware')
    raw = _read(shop_file)
    assert len(raw) == 2
    added = raw[-1]
    assert added['name'] == 'Arduino Kit'
    assert added['cost'] == 25
    assert 'hours' not in added
    assert added['filter'] == 'Hardware'
    assert item['id'] == 'arduino-kit'
    assert item['cost'] == 25


def test_add_shop_item_defaults_unpriced_and_swag(shop_file):
    item = helpers.add_shop_item('Mystery Box', '', '', 'Nonsense')
    assert item['cost'] is None
    assert item['filter'] == 'Swag'  # unknown category falls back to Swag


def test_add_shop_item_rejects_blank_name(shop_file):
    with pytest.raises(ValueError):
        helpers.add_shop_item('   ', '5', '', 'Swag')


def test_add_shop_item_rejects_duplicate(shop_file):
    with pytest.raises(ValueError):
        helpers.add_shop_item('Sticker Pack', '5', '', 'Swag')


def test_remove_shop_item(shop_file):
    assert helpers.remove_shop_item('sticker-pack') is True
    assert _read(shop_file) == []
    assert helpers.remove_shop_item('sticker-pack') is False


def test_load_shop_items_reads_int_cost(shop_file):
    items = helpers.load_shop_items()
    assert items[0]['cost'] == 0


# ── Admin API routes ─────────────────────────────────────────────────────────


def _seed(admin_client, requests=None):
    with admin_client.session_transaction() as sess:
        sess['csrf_token'] = 'tok'
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Admin Club', 'location': ''},
            'members': [],
            'itemRequests': requests if requests is not None else [],
        }


HEADERS = {'X-CSRF-Token': 'tok'}


def test_item_requests_requires_admin(auth_client):
    assert auth_client.get('/api/admin/item-requests').status_code == 403


def test_item_requests_lists_all(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed(
        admin_client,
        [
            {
                'id': 'r1',
                'name': 'Whiteboard',
                'note': 'big',
                'date': '2026-07-01',
                'status': 'Submitted',
            }
        ],
    )
    response = admin_client.get('/api/admin/item-requests')
    assert response.status_code == 200
    data = response.get_json()['itemRequests']
    assert data[0]['request']['name'] == 'Whiteboard'
    assert data[0]['clubName'] == 'Admin Club'


def test_approve_item_request_adds_to_shop_unpriced(admin_client, monkeypatch, shop_file):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed(
        admin_client,
        [
            {
                'id': 'r1',
                'name': 'Whiteboard',
                'note': '',
                'date': '2026-07-01',
                'status': 'Submitted',
            }
        ],
    )
    response = admin_client.patch(
        '/api/admin/item-requests/admin@test.com/r1', json={'status': 'approved'}, headers=HEADERS
    )
    assert response.status_code == 200
    assert response.get_json()['request']['status'] == 'Approved'
    added = next(e for e in _read(shop_file) if e['name'] == 'Whiteboard')
    assert added['cost'] is None


def test_reject_item_request_removes_it(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed(
        admin_client,
        [
            {
                'id': 'r1',
                'name': 'Whiteboard',
                'note': '',
                'date': '2026-07-01',
                'status': 'Submitted',
            }
        ],
    )
    response = admin_client.patch(
        '/api/admin/item-requests/admin@test.com/r1', json={'status': 'rejected'}, headers=HEADERS
    )
    assert response.status_code == 200
    with admin_client.session_transaction() as sess:
        assert sess['dashboard_state']['itemRequests'] == []


def test_add_shop_item_route(admin_client, monkeypatch, shop_file):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed(admin_client)
    response = admin_client.post(
        '/api/admin/shop-items',
        headers=HEADERS,
        json={'name': 'USB Drive', 'cost': '10', 'filter': 'Hardware', 'image': ''},
    )
    assert response.status_code == 200
    assert response.get_json()['shopItem']['cost'] == 10


def test_add_shop_item_route_rejects_bad_image(admin_client, monkeypatch, shop_file):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed(admin_client)
    response = admin_client.post(
        '/api/admin/shop-items',
        headers=HEADERS,
        json={'name': 'X', 'cost': '1', 'filter': 'Swag', 'image': 'javascript:alert(1)'},
    )
    assert response.status_code == 400


def test_delete_shop_item_route(admin_client, monkeypatch, shop_file):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed(admin_client)
    assert (
        admin_client.delete('/api/admin/shop-items/sticker-pack', headers=HEADERS).status_code
        == 200
    )
    assert (
        admin_client.delete('/api/admin/shop-items/sticker-pack', headers=HEADERS).status_code
        == 404
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_admin_shop.py -v`
Expected: FAIL — `AttributeError: module 'src.helpers' has no attribute '_parse_coins'`, plus assertion failures on `added['cost'] == 25` (currently `'$25.00'`)

- [ ] **Step 3: Replace `_normalize_cost`/`_shop_hours` with `_parse_coins`**

In `src/helpers.py`, delete `_normalize_cost` (line 378-382) and `_shop_hours` (line 385-388). Replace both with:

```python
def _parse_coins(cost: str) -> int | None:
    """'50', '$50', '50.00' -> 50 coins; 'free' -> 0 (case-insensitive);
    anything else ('TBD', blank, garbage) -> None, meaning the admin hasn't
    priced this item yet."""
    text = (cost or '').strip()
    if text.lower() == 'free':
        return 0
    match = re.fullmatch(r'\$?([0-9]+)(?:\.[0-9]{1,2})?', text)
    return int(match.group(1)) if match else None
```

- [ ] **Step 4: Update `ShopItem`, `OrderItem`, `load_shop_items()`, and `add_shop_item()`**

Change `ShopItem.cost` (line 73):

```python
class ShopItem(TypedDict):
    id: str
    name: str
    cost: int | None
    image_src: str
    filter: str
```

Change `OrderItem` (line 88-90) — `coinCost` is populated by Task 4's cart-add change, not here, but the type needs to exist before Task 4 can reference it:

```python
class OrderItem(TypedDict):
    id: str
    quantity: int
    coinCost: int
```

Update `load_shop_items()` (line 305-323) — `cost` now passes through as whatever JSON already has (int or `null`/`None`), no parsing at read time:

```python
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
                'cost': entry.get('cost'),
                'image_src': entry.get('image-src', ''),
                'filter': entry.get('filter', ''),
            }
        )
    return items
```

Update `add_shop_item()` (line 391-423):

```python
def add_shop_item(name: str, cost: str, image_src: str, item_filter: str) -> ShopItem:
    """Append an item to shop.json and refresh the in-memory catalog.

    Returns the catalog-shaped item dict. Raises ValueError for a blank name
    or a duplicate (same slug). `cost` is free text from an admin form;
    anything that doesn't parse to a whole coin amount (including 'TBD' or a
    blank string) leaves the item unpriced (cost: None) rather than
    rejecting the request — an admin can price it later."""
    global SHOP_ITEMS
    name = (name or '').strip()
    if not name:
        raise ValueError('Item name is required.')
    slug = _slugify(name)
    item_filter = item_filter if item_filter in SHOP_FILTERS else 'Swag'
    coins = _parse_coins(cost)
    entry = {
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
        'image-src': entry['image-src'],
        'filter': item_filter,
    }
```

Find the item-request auto-approval call site in `src/routes_admin.py` (line 169) and confirm it still reads `add_shop_item(item_request.get('name'), 'TBD', '', 'Swag')` — no change needed there; `'TBD'` still parses to `None` via `_parse_coins`.

- [ ] **Step 5: Convert `static/data/shop.json` to coin prices**

Replace the file's contents with (every dollar amount converted per the design's pricing rule: real clubs.hackclub.com price where the item matches their live catalog by product, otherwise `round(dollars * 4 / 5) * 5`; `hours` key dropped from every entry):

```json
[
  {
    "name": "Meeting Posters",
    "cost": 0,
    "image-src": "/static/images/shop/meeting-posters.png",
    "filter": "Swag"
  },
  {
    "name": "Sticker Pack",
    "cost": 0,
    "image-src": "/static/images/shop/sticker-pack.png",
    "filter": "Swag"
  },
  {
    "name": "Hot Chocolate!",
    "cost": 10,
    "image-src": "/static/images/shop/hot-chocolate.png",
    "filter": "Swag"
  },
  {
    "name": "Hack Club Pin",
    "cost": 10,
    "image-src": "/static/images/shop/hack-club-pin.png",
    "filter": "Swag"
  },
  {
    "name": "Orpheus Pico V2",
    "cost": 20,
    "image-src": "/static/images/shop/orpheus-pico-v2.png",
    "filter": "Hardware"
  },
  {
    "name": "Retro Computer Magazine",
    "cost": 20,
    "image-src": "/static/images/shop/retro-computer-magazine.png",
    "filter": "Swag"
  },
  {
    "name": "Google Play License",
    "cost": 40,
    "image-src": "/static/images/shop/google-play-license.png",
    "filter": "Digital"
  },
  {
    "name": "Hacktastical",
    "cost": 40,
    "image-src": "/static/images/shop/hacktastical.png",
    "filter": "Swag"
  },
  {
    "name": "Picoaducky",
    "cost": 40,
    "image-src": "/static/images/shop/picoaducky.png",
    "filter": "Hardware"
  },
  {
    "name": "Raspberry Pi Zero 2 W",
    "cost": 70,
    "image-src": "/static/images/shop/raspberry-pi-zero-2-w.png",
    "filter": "Hardware"
  },
  {
    "name": "Starting Plushie",
    "cost": 40,
    "image-src": "/static/images/shop/starting-plushie.png",
    "filter": "Swag"
  },
  {
    "name": "USB Drive",
    "cost": 40,
    "image-src": "/static/images/shop/usb-drive.png",
    "filter": "Hardware"
  },
  {
    "name": "GitHub Inventocat Pin",
    "cost": 45,
    "image-src": "/static/images/shop/github-inventocat-pin.png",
    "filter": "Swag"
  },
  {
    "name": "ESP32 ICE",
    "cost": 50,
    "image-src": "/static/images/shop/esp32-ice.png",
    "filter": "Hardware"
  },
  {
    "name": "Celeste",
    "cost": 80,
    "image-src": "/static/images/shop/celeste.png",
    "filter": "Digital"
  },
  {
    "name": "Hack Club CamoTee T-Shirt (Large)",
    "cost": 80,
    "image-src": "/static/images/shop/hack-club-camotee-large.png",
    "filter": "Swag"
  },
  {
    "name": "Hack Club CamoTee T-Shirt (Medium)",
    "cost": 80,
    "image-src": "/static/images/shop/hack-club-camotee-medium.png",
    "filter": "Swag"
  },
  {
    "name": "Hack Club CamoTee T-Shirt (Small)",
    "cost": 80,
    "image-src": "/static/images/shop/hack-club-camotee-small.png",
    "filter": "Swag"
  },
  {
    "name": "Hack Club CamoTee T-Shirt (X-Large)",
    "cost": 80,
    "image-src": "/static/images/shop/hack-club-camotee-xl.png",
    "filter": "Swag"
  },
  {
    "name": "Open Sauce Transit Pass",
    "cost": 80,
    "image-src": "/static/images/shop/open-sauce-transit-pass.png",
    "filter": "Swag"
  },
  {
    "name": "Startcreen T-Shirt",
    "cost": 80,
    "image-src": "/static/images/shop/startcreen-t-shirt.png",
    "filter": "Swag"
  },
  {
    "name": "Arduino Kit",
    "cost": 100,
    "image-src": "/static/images/shop/arduino-kit.png",
    "filter": "Hardware"
  },
  {
    "name": "GitHub Frisbee",
    "cost": 100,
    "image-src": "/static/images/shop/github-frisbee.png",
    "filter": "Swag"
  },
  {
    "name": "KandCard",
    "cost": 100,
    "image-src": "/static/images/shop/kandcard.png",
    "filter": "Hardware"
  },
  {
    "name": "Object from Amber's Desk",
    "cost": 100,
    "image-src": "/static/images/shop/object-from-ambers-desk.png",
    "filter": "Swag"
  },
  {
    "name": "Posthuman Cowboy Hat",
    "cost": 100,
    "image-src": "/static/images/shop/posthuman-cowboy-hat.png",
    "filter": "Swag"
  },
  {
    "name": "This is Water by David Foster-Wallace",
    "cost": 100,
    "image-src": "/static/images/shop/this-is-water.png",
    "filter": "Swag"
  },
  {
    "name": "Hack Your CPU by Julia Evans",
    "cost": 125,
    "image-src": "/static/images/shop/hack-your-cpu.png",
    "filter": "Swag"
  },
  {
    "name": "Campfire Flagship Laptop Bag",
    "cost": 190,
    "image-src": "/static/images/shop/campfire-flagship-laptop-bag.png",
    "filter": "Swag"
  },
  {
    "name": "Flantime",
    "cost": 400,
    "image-src": "/static/images/shop/flantime.png",
    "filter": "Hardware"
  }
]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_admin_shop.py -v`
Expected: 15 passed

- [ ] **Step 7: Run mypy**

Run: `mypy src/helpers.py --strict`
Expected: no errors

- [ ] **Step 8: Commit**

```bash
git add src/helpers.py static/data/shop.json tests/test_admin_shop.py
git commit -m "feat: convert shop catalog from dollars to coins"
```

---

### Task 4: Cart snapshot and checkout debit

**Files:**
- Modify: `src/routes_api.py` (`api_cart_add` line 345-372, `api_cart_checkout` line 419-442, imports line 7-29)
- Test: `tests/test_coins.py` (append)

**Interfaces:**
- Consumes: `award_coins`, `coin_balance` (Task 1); `ShopItem.cost: int | None`, `OrderItem.coinCost` (Task 3).
- Produces: cart entries always carry `coinCost` snapshotted from the shop price at add-to-cart time; checkout rejects an order that would overdraw the ledger and, on success, appends a `shop_order` transaction via `award_coins`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_coins.py`:

```python
def _seed_cart_club(client, monkeypatch, ledger=None, cart=None):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with client.session_transaction() as sess:
        sess['csrf_token'] = 'tok'
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Cart Club', 'coinBalance': 0, 'coinsSpent': 0},
            'members': [],
            'shopItems': [
                {'id': 'sticker-pack', 'name': 'Sticker Pack', 'cost': 15, 'image_src': '', 'filter': 'Swag'},
                {'id': 'mystery-box', 'name': 'Mystery Box', 'cost': None, 'image_src': '', 'filter': 'Swag'},
            ],
            'cart': cart or [],
            'orders': [],
            'ledger': ledger or [],
        }


HEADERS = {'X-CSRF-Token': 'tok'}


def test_cart_add_snapshots_coin_cost(auth_client, monkeypatch):
    _seed_cart_club(auth_client, monkeypatch)
    response = auth_client.post('/api/dashboard/cart', headers=HEADERS, json={'itemId': 'sticker-pack', 'quantity': 2})
    assert response.status_code == 200
    cart = response.get_json()['state']['cart']
    assert cart[0]['coinCost'] == 15
    assert cart[0]['quantity'] == 2


def test_cart_add_rejects_unpriced_item(auth_client, monkeypatch):
    _seed_cart_club(auth_client, monkeypatch)
    response = auth_client.post('/api/dashboard/cart', headers=HEADERS, json={'itemId': 'mystery-box'})
    assert response.status_code == 400


def test_checkout_debits_ledger_on_success(auth_client, monkeypatch):
    ledger = [{'id': 'c1', 'delta': 50, 'kind': 'starter_grant', 'ref': '', 'note': '', 'at': '2026-08-07T00:00:00Z'}]
    cart = [{'id': 'sticker-pack', 'quantity': 2, 'coinCost': 15}]
    _seed_cart_club(auth_client, monkeypatch, ledger=ledger, cart=cart)
    response = auth_client.post('/api/dashboard/checkout', headers=HEADERS)
    assert response.status_code == 200
    state = response.get_json()['state']
    assert state['settings']['coinBalance'] == 20  # 50 - (15*2)
    assert state['settings']['coinsSpent'] == 30
    assert any(t['kind'] == 'shop_order' for t in state['ledger'])
    assert state['cart'] == []


def test_checkout_rejects_when_over_budget(auth_client, monkeypatch):
    ledger = [{'id': 'c1', 'delta': 10, 'kind': 'starter_grant', 'ref': '', 'note': '', 'at': '2026-08-07T00:00:00Z'}]
    cart = [{'id': 'sticker-pack', 'quantity': 2, 'coinCost': 15}]
    _seed_cart_club(auth_client, monkeypatch, ledger=ledger, cart=cart)
    response = auth_client.post('/api/dashboard/checkout', headers=HEADERS)
    assert response.status_code == 400
    with auth_client.session_transaction() as sess:
        assert sess['dashboard_state']['cart'] == cart  # unchanged — nothing was debited
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_coins.py -v -k "cart_add or checkout"`
Expected: FAIL — `test_cart_add_rejects_unpriced_item` fails (currently accepts any item), `test_checkout_debits_ledger_on_success` fails (`KeyError: 'coinBalance'` or mismatched values), `test_checkout_rejects_when_over_budget` fails (currently always succeeds)

- [ ] **Step 3: Update imports in `src/routes_api.py`**

Add `award_coins` and `coin_balance` to the `from .helpers import (...)` block (line 7-29):

```python
from .helpers import (
    STATE_SECTIONS,
    _item_id,
    _join_missing,
    _owned_project_or_error,
    _slugify,
    _sniff_image,
    _upload_to_blob,
    _viewer_email,
    award_coins,
    clean_text,
    coin_balance,
    event_from_payload,
    find_by_id,
    get_dashboard_state,
    json_error,
    json_payload,
    login_required,
    paginate,
    parse_bool,
    require_dashboard_csrf,
    require_leader_api,
    save_dashboard_state,
    viewer_is_leader,
)
```

- [ ] **Step 4: Update `api_cart_add` (line 345-372)**

```python
    @app.post('/api/dashboard/cart')
    @login_required
    def api_cart_add():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        payload = json_payload()
        item_id = clean_text(payload.get('itemId'))
        state = get_dashboard_state()
        item = find_by_id(state['shopItems'], item_id)
        if not item:
            return json_error('Shop item not found.', 404)
        if item.get('cost') is None:
            return json_error("This item isn't priced yet.")

        try:
            quantity = max(1, int(payload.get('quantity', 1) or 1))
        except (TypeError, ValueError):
            return json_error('Cart quantity must be a number.')
        cart_item = find_by_id(state['cart'], item_id)
        if cart_item:
            cart_item['quantity'] += quantity
        else:
            state['cart'].append({'id': item_id, 'quantity': quantity, 'coinCost': item['cost']})
        save_dashboard_state(state)
        return flask.jsonify({'state': state})
```

- [ ] **Step 5: Update `api_cart_checkout` (line 419-442)**

```python
    @app.post('/api/dashboard/checkout')
    @login_required
    def api_cart_checkout():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        state = get_dashboard_state()
        if not state['cart']:
            return json_error('Add at least one item before submitting a request.')

        total = sum(item['coinCost'] * item['quantity'] for item in state['cart'])
        if total > coin_balance(state.get('ledger') or []):
            return json_error("You don't have enough coins for this order.")

        order = {
            'id': _item_id('order'),
            'date': date.today().isoformat(),
            'status': 'Requested',
            'items': [dict(item) for item in state['cart']],
        }
        state['orders'].insert(0, order)
        state['cart'] = []
        item_names = ', '.join(
            (find_by_id(state['shopItems'], item.get('id', '')) or {}).get('name') or item.get('id', '')
            for item in order['items']
        )
        award_coins(state, -total, 'shop_order', order['id'], f'Order: {item_names}')
        save_dashboard_state(state)
        return flask.jsonify({'order': order, 'state': state})
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_coins.py -v`
Expected: 17 passed

Run: `pytest tests/test_api.py -v`
Expected: all pass (existing checkout-adjacent tests, e.g. auth/CSRF checks on `/api/dashboard/cart` and `/api/dashboard/checkout`, are unaffected by this change)

- [ ] **Step 7: Run mypy**

Run: `mypy src/routes_api.py --strict`
Expected: no errors

- [ ] **Step 8: Commit**

```bash
git add src/routes_api.py tests/test_coins.py
git commit -m "feat: debit coins on checkout and snapshot cart prices"
```

---

### Task 5: Coin glyph, balance chip, and shop pricing UI

**Files:**
- Modify: `templates/partials/icons.html` (new `coin` glyph)
- Modify: `templates/dashboard_layout.html` (balance chip markup in the header)
- Modify: `templates/dashboard/shop.html` (cart subtotal element)
- Modify: `templates/dashboard/admin.html` (cost label/placeholder)
- Modify: `static/js/dashboard.js` (coin icon constant, `renderCoinBalance()`, `renderShop()` pricing + subtotal)
- Test: `tests/test_public.py` (append — template-shell assertions; there is no JS test runner in this repo)

**Interfaces:**
- Consumes: `settings().coinBalance` (client-side, populated by the `/api/dashboard/state` response once Tasks 1-4 land server-side).
- Produces: every dashboard page shows a coin balance chip in the header; the shop grid/cart show `{cost} coins` with a glyph instead of a dollar string; the cart shows a subtotal and disables checkout when it exceeds the balance (client-side UX only — the server is still authoritative per Task 4).

Note: the design spec's UI section suggested a new `static/images/coin.svg` asset plus a separate `hc_coin_icon()` Jinja helper. This task instead extends the existing `sidebar_icon()` icon registry in `templates/partials/icons.html` with one new dict entry — same visual result (a coin glyph matching this repo's existing stroke-icon style), no new image file, no new Jinja macro, no second icon-rendering mechanism to keep in sync with the first. This is an implementation-level improvement on the spec's suggestion, not a scope change.

- [ ] **Step 1: Add the `coin` icon to `templates/partials/icons.html`**

Add a new entry to the `icons` dict (after `'down-caret'`, line 18):

```python
    'down-caret': '<polyline points="6 9 12 15 18 9"/>',
    'coin': '<circle cx="12" cy="12" r="9"/><path d="M12 6.5v11"/><path d="M15 9a3 3 0 0 0-3-1h-.5a2 2 0 0 0 0 4h1a2 2 0 0 1 0 4H12a3 3 0 0 1-3-1"/>',
```

(This is Jinja template source, not Python — editing the dict literal inside the `{%- set icons = {...} -%}` block.)

- [ ] **Step 2: Add the balance chip to `templates/dashboard_layout.html`**

In the header, right after the notification bell button and before `{% block header_right %}{% endblock %}` (after line 201, before line 203):

```html
                    {% endif %}
                    {% if current_user %}
                    <div class="coin-balance-chip" id="coinBalanceChip" aria-label="Club coins balance">
                        {{ sidebar_icon('coin', 16) }}
                        <span id="coinBalanceAmount">0</span>
                    </div>
                    {% endif %}
                </div>
                {% block header_right %}{% endblock %}
```

(This wraps the existing `{% if current_user %}...{% endif %}` bell block and adds a sibling `{% if current_user %}` block for the chip, both still inside `dashboard-header-right`.)

- [ ] **Step 3: Add a cart subtotal element to `templates/dashboard/shop.html`**

Between `#cartList` and `#cartEmpty` (after line 51, before line 52):

```html
        <div class="cart-list" id="cartList"></div>
        <div class="cart-subtotal" id="cartSubtotal" hidden>
            <span data-i18n="shop.cartSubtotal">Subtotal</span>
            <strong id="cartSubtotalAmount">0</strong>
        </div>
        <div class="empty-state tight" id="cartEmpty">
```

- [ ] **Step 4: Update the admin shop-item form label in `templates/dashboard/admin.html`**

Change line 112-113:

```html
                <label class="form-group">
                    <span class="form-label" data-i18n="admin.itemCost">Cost (coins)</span>
                    <input type="text" class="form-input" name="cost" maxlength="20" placeholder="50">
                </label>
```

- [ ] **Step 5: Add a coin icon constant and `renderCoinBalance()` to `static/js/dashboard.js`**

Add near `escapeHtml` (after line 135-ish, right after the `escapeHtml` function closes):

```javascript
    const COIN_ICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14" class="coin-icon" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 6.5v11"/><path d="M15 9a3 3 0 0 0-3-1h-.5a2 2 0 0 0 0 4h1a2 2 0 0 1 0 4H12a3 3 0 0 1-3-1"/></svg>';

    function coinLabel(cost) {
        if (cost === null || cost === undefined) return 'TBD';
        return `${COIN_ICON_SVG}<span>${Number(cost)}</span>`;
    }
```

Add `renderCoinBalance()` right after `renderJoinLink()` (after line 994):

```javascript
    function renderCoinBalance() {
        const amount = $('#coinBalanceAmount');
        if (amount) amount.textContent = Number(settings().coinBalance || 0);
    }
```

Call it from `renderPage()` (line 1492-1504), alongside the other unconditional per-page renders:

```javascript
    function renderPage() {
        renderHome();
        renderTeam();
        renderEvents();
        renderShips();
        renderProjects();
        renderLevels();
        renderJoinLink();
        renderCoinBalance();
        renderShop();
        renderNewsletters();
        renderChat();
        renderSettings();
    }
```

- [ ] **Step 6: Update `renderShop()`'s pricing and add the subtotal**

Replace the shop card price span (line 1044-1046):

```javascript
                    <h3>${escapeHtml(item.name)}</h3>
                    <div class="card-footer-line">
                        <span class="shop-price">${coinLabel(item.cost)}</span>
                        <button class="btn-secondary small" type="button" data-add-cart="${escapeHtml(item.id)}" ${item.cost == null ? 'disabled' : ''}>Add</button>
                    </div>
```

Replace the cart item price span (line 1058-1062):

```javascript
                    <article class="cart-item">
                        <div>
                            <strong>${escapeHtml(item.name || entry.id)}</strong>
                            <span>${coinLabel(entry.coinCost)}</span>
                        </div>
```

Add a subtotal calculation and render it, right after the `list.innerHTML = ...` block in `renderShop()` (after line 1072, before line 1074's `if (empty) ...`):

```javascript
        const subtotal = cart().reduce((total, entry) => total + Number(entry.coinCost || 0) * Number(entry.quantity || 0), 0);
        const subtotalNode = $('#cartSubtotal');
        const subtotalAmount = $('#cartSubtotalAmount');
        if (subtotalNode) subtotalNode.hidden = cart().length === 0;
        if (subtotalAmount) subtotalAmount.innerHTML = coinLabel(subtotal);

        if (empty) empty.hidden = cart().length > 0;
        if (checkoutButton) checkoutButton.disabled = cart().length === 0 || subtotal > Number(settings().coinBalance || 0);
```

(This replaces the existing `if (checkoutButton) checkoutButton.disabled = cart().length === 0;` line — the new version keeps that condition and adds the over-budget check.)

- [ ] **Step 7: Write the failing template-shell test**

Append to `tests/test_public.py`:

```python
def test_dashboard_layout_has_coin_balance_chip(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Chip Club', 'coinBalance': 0, 'coinsSpent': 0},
            'members': [],
        }
    response = auth_client.get('/dashboard')
    assert response.status_code == 200
    assert b'id="coinBalanceChip"' in response.data
    assert b'id="coinBalanceAmount"' in response.data


def test_shop_page_has_cart_subtotal_shell(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Chip Club', 'coinBalance': 0, 'coinsSpent': 0},
            'members': [],
        }
    response = auth_client.get('/dashboard/shop')
    assert response.status_code == 200
    assert b'id="cartSubtotal"' in response.data
```

- [ ] **Step 8: Run tests to verify pass/fail**

Run: `pytest tests/test_public.py -v -k "coin_balance_chip or cart_subtotal"`
Expected: both PASS once Steps 1-4 are in place (these are pure template-rendering assertions, so they should already pass by this point in the task — this step is verification, not a red/green cycle like the Python-logic tasks)

- [ ] **Step 9: Manual browser verification**

There is no JS test runner in this repo (confirmed: no `package.json`, pytest is the only automated test tool). Verify by hand:

```bash
python app.py
```

1. Sign in (or use playtest mode if `PLAYTEST_ENABLED` is set), open `/dashboard` — confirm a coin balance chip renders in the header next to the notification bell, showing `50` (the starter grant) after the initial `/api/dashboard/state` fetch resolves.
2. Open `/dashboard/shop` — confirm every priced item shows a coin count with the glyph instead of a dollar string, the one unpriced item (if any test data has one) shows "TBD" with a disabled Add button, adding an item shows a subtotal above the cart-empty message, and the checkout button disables when the subtotal exceeds the balance.
3. Open dark mode — confirm the coin glyph and chip are legible against the dark background (they inherit `currentColor`, so this should be automatic, but check for contrast).

- [ ] **Step 10: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 11: Commit**

```bash
git add templates/partials/icons.html templates/dashboard_layout.html templates/dashboard/shop.html templates/dashboard/admin.html static/js/dashboard.js tests/test_public.py
git commit -m "feat: show coin balance and shop prices in coins instead of dollars"
```

---

### Task 6: i18n keys for the coin UI

**Files:**
- Modify: `static/js/i18n-data.js` (12 occurrences of `admin.itemCost`, new keys in the `en` block)
- Regenerate: `static/js/i18n/en.js` and the other 11 language files (via script, not by hand)

**Interfaces:**
- Consumes: nothing.
- Produces: `admin.itemCost` reads "Cost (coins)" in all 12 language blocks (was untranslated English "Cost ($)" everywhere per this repo's existing i18n state — see `i18n-data-mostly-english-placeholders` in project memory); new keys `shop.cartSubtotal`, `shop.notEnoughCoins`, `shop.itemUnpriced`, `common.coinBalance` exist in the `en` block (English is the fallback table `i18n.js` reads for any key missing from a non-English language, per `scripts/split_i18n_data.py`'s own docstring, so these don't need to exist in the other 11 blocks).

- [ ] **Step 1: Update `admin.itemCost` in all 12 language blocks**

In `static/js/i18n-data.js`, every one of these 12 lines currently reads `'admin.itemCost': 'Cost ($)',` — change each to `'admin.itemCost': 'Cost (coins)',`:

Lines: 400, 917, 1434, 1951, 2468, 2985, 3502, 4019, 4536, 5053, 5570, 6087.

Verify the count before and after:

```bash
grep -c "'admin.itemCost': 'Cost (\$)'," static/js/i18n-data.js   # expect 12 before the edit
```

After editing all 12 lines:

```bash
grep -c "'admin.itemCost': 'Cost (coins)'," static/js/i18n-data.js   # expect 12
grep -c "'admin.itemCost': 'Cost (\$)'," static/js/i18n-data.js      # expect 0
```

- [ ] **Step 2: Add new keys to the `en` block only**

In `static/js/i18n-data.js`, right after the `'shop.submitRequest': 'Submit request',` line (line 268, inside the `en:` block only):

```javascript
            'shop.submitRequest': 'Submit request',
            'shop.cartSubtotal': 'Subtotal',
            'shop.notEnoughCoins': "You don't have enough coins for this order.",
            'shop.itemUnpriced': 'Not priced yet',
            'common.coinBalance': 'Club coins',
```

- [ ] **Step 3: Regenerate the per-language files**

```bash
python scripts/split_i18n_data.py
```

Expected output: confirms it wrote `static/js/i18n-langs.js` and 12 files under `static/js/i18n/`.

- [ ] **Step 4: Verify the regenerated English file**

```bash
grep -n "admin.itemCost\|shop.cartSubtotal\|common.coinBalance" static/js/i18n/en.js
```

Expected: `'admin.itemCost': 'Cost (coins)',`, `'shop.cartSubtotal': 'Subtotal',`, `'common.coinBalance': 'Club coins',` all present.

- [ ] **Step 5: Verify a non-English file picked up the shared key change**

```bash
grep -n "admin.itemCost" static/js/i18n/es.js
```

Expected: `'admin.itemCost': 'Cost (coins)',` (still untranslated English text, per this repo's existing i18n state, but the stale dollar sign is gone from every language, not just English).

- [ ] **Step 6: Run the full test suite (i18n has no dedicated Python tests, but this confirms nothing else broke)**

Run: `pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add static/js/i18n-data.js static/js/i18n-langs.js static/js/i18n/
git commit -m "feat: update shop/admin i18n copy from dollars to coins"
```

---

### Task 7: Final verification gate

**Files:** none (verification only)

**Interfaces:** none.

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all tests pass, 0 failures

- [ ] **Step 2: Run ruff lint**

Run: `ruff check .`
Expected: no errors

- [ ] **Step 3: Run ruff format check**

Run: `ruff format --check .`
Expected: no reformatting needed (if it reports files needing formatting, run `ruff format .` and re-verify, then amend the affected task's commit is NOT the move — instead make a new small commit: `git add -u && git commit -m "style: ruff format"`)

- [ ] **Step 4: Run mypy strict across the whole `src/` tree**

Run: `mypy src/ --strict`
Expected: no errors

- [ ] **Step 5: Confirm every dollar site the spec called out is gone**

```bash
grep -n '\$[0-9]' static/data/shop.json src/helpers.py src/routes_admin.py templates/dashboard/admin.html static/js/dashboard.js
```

Expected: no matches inside the shop/coins code paths. (This may still match unrelated strings like `static/js/events-data.js`'s "$1,000" hardware-grant copy and `static/js/effects.js`'s comment example — both are explicitly out of scope per the design spec §3, rows 16-17, since they're event-page copy and a code comment, not shop/coin data.)

- [ ] **Step 6: Confirm no placeholder/TBD leakage into required fields**

```bash
grep -rn "TBD" src/helpers.py src/routes_admin.py static/data/shop.json
```

Expected: no matches — `'TBD'` was the OLD string sentinel for an unpriced item; the new model uses `None`/`null`, so a literal `"TBD"` string anywhere in these files means a leftover from the conversion was missed.

- [ ] **Step 7: Confirm the one deliberately-untouched dollar site is still there**

```bash
grep -n '\$500' src/helpers.py
```

Expected: one match — the seeded newsletter excerpt at `default_dashboard_state()` ("Apply for up to $500 to buy Raspberry Pis and Arduinos..."). Per the design spec §7 open question, this is flavor text for an external, real-world grant program that isn't reachable through any coin-priced flow in this app, and was deliberately left as dollars rather than reworded to coins. If this grep finds nothing, someone changed it outside this plan — leave it alone unless the user asks otherwise.
