# Workshops Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a club-internal workshop board — members propose topics, members apply to run them, a leader picks an applicant and schedules it (creating a linked calendar Event), and a leader later marks it run — plus a "Workshops Run" stat on the home page.

**Architecture:** A new `workshops` `STATE_SECTIONS` entry (list of `Workshop` records) follows the exact five-place registration pattern `ledger` established in the Coins Spine spec. The apply-to-run mutation reuses the same payload-key-scoping auth trick `Event.rsvp` already uses (a narrow payload shape is member-permitted; anything else needs a leader). Scheduling a workshop creates a real `Event` (`type: 'Workshop'`) so RSVP/calendar display work on it unchanged — Workshops never duplicates Event's fields, it only points at one via `eventId`.

**Tech Stack:** Flask 3.1, Python 3.10+ (mypy `--strict` in CI), vanilla JS (no bundler, no JS test runner — pytest is the only automated test tool in this repo), Jinja2, session/Airtable/MongoDB storage backends.

## Global Constraints

- Python `>=3.10`; CI runs `ruff check`, `ruff format --check`, and `mypy src/ --strict` on 3.10/3.11/3.12 — every new function in `src/helpers.py` needs full type annotations (functions added to `src/routes_api.py`, `src/notifications.py`, and `src/email.py` follow those files' own existing convention of **no** type annotations on their functions — matching, not fixing, that pre-existing inconsistency).
- `ruff format` uses single quotes, 100-char lines (`pyproject.toml`).
- Never hand-edit `static/js/i18n/<code>.js` — those are generated. Edit `static/js/i18n-data.js` and run `python scripts/split_i18n_data.py`.
- Never touch `.env`/`.env.example` (repo-wide deny rule).
- Follow the existing five-place pattern for any new `STATE_SECTIONS` key: `src/helpers.py` (`STATE_SECTIONS` + `default_dashboard_state()` + `PAGE_SECTIONS`), `src/storage.py` (`CHILD_TABLES` + a `*_FIELDS` list + `OPTIONAL_CHILD_KEYS` since this is a brand-new Airtable table existing bases won't have), `src/storage_mongo.py` (`CHILD_COLLECTIONS` + `INDEXES`), and `static/js/dashboard.js` (the client-side `PAGE_SECTIONS` mirror). Missing one of these is exactly how `notifications` and `settings.language` silently stopped persisting on Airtable previously.
- Email templates in `src/email.py` use plain f-strings with **no autoescape** — every value interpolated from user input (title, description, names) must be wrapped in `escape()` (`from markupsafe import escape`, already imported at the top of `src/email.py`).
- `viewer_role()` (`src/helpers.py:210-217`) defaults an unrecognized viewer to `'Leader'` — a test session whose email isn't in the seeded `members` list resolves as a leader. Tests that need to exercise the "ordinary member" path must seed `members` with that viewer's email and `role: 'Member'`.
- Dynamically-JS-rendered content (card grids, modal bodies built via `innerHTML`) is **not** run through the i18n system anywhere in this codebase today (confirmed: `renderEvents()`/`renderShop()`'s card text, RSVP button labels, and shop filter chip labels are all hardcoded English) — only the static Jinja-rendered page shell uses `data-i18n`. Workshops follows the same boundary: card/modal-body text is plain English in JS; only the page shell (nav label, subtitle, empty state, form labels, filter aria-label) gets i18n keys.

---

### Task 1: Workshop data model and payload validator

**Files:**
- Modify: `src/helpers.py` (types near line 58-111, `DashboardState` near line 154-166, new function near line 1117)
- Test: `tests/test_workshops.py` (new file)

**Interfaces:**
- Consumes: `clean_text(value: Any, fallback: str = '', max_len: int = 300) -> str` (existing, `src/helpers.py:1057`).
- Produces: `Workshop` TypedDict (`id`, `title`, `description`, `status`, `proposerEmail`, `proposerName`, `applicants`, `runnerEmail`, `runnerName`, `eventId`, `createdAt`); `workshop_from_payload(payload: dict[str, Any]) -> tuple[dict[str, str] | None, str | None]` — validates `title`/`description` only (the two fields a proposer submits; every other `Workshop` field is set by the route that creates the record, not by this validator).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_workshops.py`:

```python
from src.helpers import workshop_from_payload


def test_workshop_from_payload_valid():
    data, error = workshop_from_payload(
        {'title': 'Intro to Git', 'description': 'Version control basics.'}
    )
    assert error is None
    assert data == {'title': 'Intro to Git', 'description': 'Version control basics.'}


def test_workshop_from_payload_missing_title():
    data, error = workshop_from_payload({'title': '', 'description': 'Version control basics.'})
    assert data is None
    assert error == 'Workshop title is required.'


def test_workshop_from_payload_missing_description():
    data, error = workshop_from_payload({'title': 'Intro to Git', 'description': ''})
    assert data is None
    assert error == 'Workshop description is required.'


def test_workshop_from_payload_strips_whitespace():
    data, error = workshop_from_payload({'title': '  Intro to Git  ', 'description': '  Basics.  '})
    assert error is None
    assert data['title'] == 'Intro to Git'
    assert data['description'] == 'Basics.'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_workshops.py -v`
Expected: FAIL with `ImportError: cannot import name 'workshop_from_payload' from 'src.helpers'`

- [ ] **Step 3: Add the type and function**

In `src/helpers.py`, add the `Workshop` TypedDict right after `Project` and before `ShopItem` (after line 71, before line 73):

```python
class Workshop(TypedDict):
    id: str
    title: str
    description: str
    status: str            # 'Proposed' | 'Scheduled' | 'Run'
    proposerEmail: str
    proposerName: str
    applicants: list[str]  # member emails who applied to run it
    runnerEmail: str       # '' until Scheduled
    runnerName: str        # '' until Scheduled
    eventId: str           # '' until Scheduled; id of the linked Event
    createdAt: str
```

Add `workshops: list[Workshop]` to the `DashboardState` TypedDict (after `ledger`, before `settings`, around line 165):

```python
    ledger: list[CoinTransaction]
    workshops: list[Workshop]
    settings: Settings
```

Add `workshop_from_payload()` right after `event_from_payload()` (after line 1117, before the `# ── Project helpers ──` divider comment):

```python
def workshop_from_payload(payload: dict[str, Any]) -> tuple[dict[str, str] | None, str | None]:
    title = clean_text(payload.get('title'), max_len=120)
    description = clean_text(payload.get('description'), max_len=2000)
    if not title:
        return None, 'Workshop title is required.'
    if not description:
        return None, 'Workshop description is required.'
    return {'title': title, 'description': description}, None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_workshops.py -v`
Expected: 4 passed

- [ ] **Step 5: Run mypy to verify strict typing holds**

Run: `mypy src/helpers.py --strict`
Expected: same error count as before this task (26 pre-existing) — `Workshop` and `workshop_from_payload` introduce no new errors since both are fully annotated.

- [ ] **Step 6: Commit**

```bash
git add src/helpers.py tests/test_workshops.py
git commit -m "feat: add workshop data model and payload validator"
```

---

### Task 2: Register `workshops` across all three storage backends

**Files:**
- Modify: `src/helpers.py` (`STATE_SECTIONS` line 723-734, `default_dashboard_state()` seed near line 542-551, `PAGE_SECTIONS` line 745-759)
- Modify: `src/storage.py` (module docstring line 1-40, new `WORKSHOP_FIELDS`, `CHILD_TABLES`, `OPTIONAL_CHILD_KEYS`, `load()`/`_item_fields()` applicants JSON handling)
- Modify: `src/storage_mongo.py` (`CHILD_COLLECTIONS`, `INDEXES`, `load()` sort branch)
- Modify: `static/js/dashboard.js` (`PAGE_SECTIONS` client mirror, near line 201-215)
- Test: `tests/test_workshops.py` (append)

**Interfaces:**
- Consumes: `Workshop` (Task 1).
- Produces: `STATE_SECTIONS` now includes `'workshops'`; every club's default state carries an empty `workshops` list; all three backends persist and load it; both server and client `PAGE_SECTIONS` know which pages need it loaded.

- [ ] **Step 1: Write the failing registration tests**

Append to `tests/test_workshops.py`:

```python
def test_workshops_is_registered_everywhere():
    from src.helpers import STATE_SECTIONS
    from src.storage import AirtableStorage
    from src.storage_mongo import CHILD_COLLECTIONS, INDEXES

    assert 'workshops' in STATE_SECTIONS
    airtable_keys = {state_key for _s, _d, state_key, _f in AirtableStorage.CHILD_TABLES}
    assert 'workshops' in airtable_keys
    assert 'workshops' in CHILD_COLLECTIONS
    assert 'workshops' in INDEXES
    assert 'workshops' in AirtableStorage.OPTIONAL_CHILD_KEYS


def test_default_dashboard_state_seeds_empty_workshops(client):
    with client.session_transaction() as sess:
        sess['user'] = {'name': 'Test Leader', 'email': 'leader@test.com'}
    with client.application.test_request_context():
        from flask import session as flask_session

        flask_session['user'] = {'name': 'Test Leader', 'email': 'leader@test.com'}
        from src.helpers import default_dashboard_state

        state = default_dashboard_state()
        assert state['workshops'] == []


def test_dashboard_workshops_page_section_loads_workshops():
    from src.helpers import PAGE_SECTIONS

    assert PAGE_SECTIONS['dashboard_workshops'] == ('workshops',)
    assert 'workshops' in PAGE_SECTIONS['dashboard']
```

Note: `tests/test_coins.py` already has generic `test_every_state_section_has_an_airtable_table`, `test_every_state_section_has_a_mongo_collection`, and `test_every_mongo_collection_has_an_index` tests (added in the Coins Spine plan) that iterate every `STATE_SECTIONS` key — these will automatically catch a missing `workshops` registration too, so this task does not duplicate them.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_workshops.py -v`
Expected: FAIL — `'workshops' not in STATE_SECTIONS`, `KeyError: 'workshops'` (state seed), `KeyError: 'dashboard_workshops'` (`PAGE_SECTIONS`)

- [ ] **Step 3: Register `workshops` in `src/helpers.py`**

In `STATE_SECTIONS` (line 723-734), add `'workshops'`:

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
    'workshops',
)
```

In `default_dashboard_state()`, add `'workshops': []` right after `'ledger': []` (around line 551):

```python
        'notifications': [],
        'ledger': [],
        'workshops': [],
```

In `PAGE_SECTIONS` (line 745-759), add a `'dashboard_workshops'` entry and add `'workshops'` to the home page's `'dashboard'` entry (the home page's new stat tile, Task 5, needs it loaded without a second request):

```python
PAGE_SECTIONS: Final[dict[str, tuple[str, ...]]] = {
    'dashboard': ('events', 'projects', 'newsletters', 'workshops'),
    'dashboard_team': (),
    'dashboard_events': ('events',),
    'dashboard_ships': ('projects',),
    'dashboard_projects': ('projects',),
    'dashboard_levels': ('projects',),
    'dashboard_tools': (),
    'dashboard_shop': ('orders', 'itemRequests'),
    'dashboard_workshops': ('workshops',),
    'dashboard_chat': ('channels', 'messages'),
    'dashboard_newsletters': ('newsletters',),
    'dashboard_map': (),
    'dashboard_settings': (),
    'dashboard_profile': ('projects',),
}
```

- [ ] **Step 4: Register `workshops` in `src/storage.py`**

Update the module docstring's Airtable schema block: add a `Workshops` row after `Ledger` (before the closing `A "ship" is just...` paragraph):

```python
  Ledger       App Id*, Delta, Kind, Ref, Note, At, Club Email
  Workshops    App Id*, Title, Description, Status, Proposer Email, Proposer Name,
               Applicants, Runner Email, Runner Name, Event Id, Created At, Club Email
```

Update the parenthetical note just below the schema block to mention `Applicants` alongside `Items`/`Data` as JSON text:

```python
(* = used as the lookup key; "Items", "Data", and "Applicants" are JSON text. Checkbox fields:
Public Directory, Email Notifications, Dark Mode Default, Newsletter
Subscribed, RSVP, Read. Attendees, Coin Balance, and Coins Spent are numbers.)
```

Add `WORKSHOP_FIELDS` right after `LEDGER_FIELDS` (after line 107) — `applicants` is deliberately excluded here; it gets the same special-cased JSON-text-field treatment `orders.items` already gets, not a plain field mapping:

```python
WORKSHOP_FIELDS: Final[list[tuple[str, str]]] = [
    ('title', 'Title'),
    ('description', 'Description'),
    ('status', 'Status'),
    ('proposerEmail', 'Proposer Email'),
    ('proposerName', 'Proposer Name'),
    ('runnerEmail', 'Runner Email'),
    ('runnerName', 'Runner Name'),
    ('eventId', 'Event Id'),
    ('createdAt', 'Created At'),
]
```

Add a `'workshops'` entry to `AirtableStorage.CHILD_TABLES` (line 245-257), after the `LEDGER` row:

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
        ('NOTIFICATIONS', 'Notifications', 'notifications', NOTIFICATION_FIELDS),
        ('LEDGER', 'Ledger', 'ledger', LEDGER_FIELDS),
        ('WORKSHOPS', 'Workshops', 'workshops', WORKSHOP_FIELDS),
    ]
```

Add `'workshops'` to `OPTIONAL_CHILD_KEYS` (line 264-270) — this is a brand-new table, so existing Airtable bases without it must degrade to an empty list instead of erroring, exactly like `ledger` did when Coins Spine shipped:

```python
    OPTIONAL_CHILD_KEYS: Final[set[str]] = {
        'itemRequests',
        'channels',
        'messages',
        'notifications',
        'ledger',
        'workshops',
    }
```

In `load()` (around line 636-661), add an `applicants` JSON branch alongside the existing `orders`/`messages`/`notifications` special cases:

```python
                if state_key == 'orders':
                    try:
                        item['items'] = json.loads(fields.get('Items') or '[]')
                    except ValueError:
                        item['items'] = []
                if state_key == 'messages':
                    try:
                        reactions = json.loads(fields.get('Reactions') or '{}')
                    except ValueError:
                        reactions = {}
                    if reactions:
                        item['reactions'] = reactions
                if state_key == 'notifications':
                    try:
                        item['data'] = json.loads(fields.get('Data') or '{}')
                    except ValueError:
                        item['data'] = {}
                if state_key == 'workshops':
                    try:
                        item['applicants'] = json.loads(fields.get('Applicants') or '[]')
                    except ValueError:
                        item['applicants'] = []
                items.append(item)
```

In `_item_fields()` (around line 720-742), same addition:

```python
        if state_key == 'orders':
            fields['Items'] = json.dumps(item.get('items') or [])
        if state_key == 'messages':
            fields['Reactions'] = json.dumps(item.get('reactions') or {})
        if state_key == 'notifications':
            fields['Data'] = json.dumps(item.get('data') or {})
        if state_key == 'workshops':
            fields['Applicants'] = json.dumps(item.get('applicants') or [])
        return fields
```

- [ ] **Step 5: Register `workshops` in `src/storage_mongo.py`**

Add `'workshops'` to `CHILD_COLLECTIONS` (line 36-47):

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
    'workshops',
]
```

Add an `INDEXES` entry (after the `'ledger'` entry, line 89-91) — newest-first, matching `notifications`/`ledger`:

```python
    'ledger': [
        ([('clubKey', ASCENDING), ('at', DESCENDING)], False),
    ],
    'workshops': [
        ([('clubKey', ASCENDING), ('createdAt', DESCENDING)], False),
    ],
}
```

In `load()` (line 326-338), add a `workshops` case to the per-collection sort branch:

```python
        for key in wanted:
            sort = None
            if key == 'events':
                sort = [('date', ASCENDING)]
            elif key == 'messages':
                sort = [('createdAt', ASCENDING)]
            elif key == 'notifications':
                # The bell renders newest first.
                sort = [('createdAt', DESCENDING)]
            elif key == 'ledger':
                # Newest first: the bell menu's counterpart for coin history.
                sort = [('at', DESCENDING)]
            elif key == 'workshops':
                # Newest-proposed-first, matching the catalog page's default order.
                sort = [('createdAt', DESCENDING)]
            docs = self._find(key, {'clubKey': club_key}, sort=sort)
```

- [ ] **Step 6: Mirror `PAGE_SECTIONS` in `static/js/dashboard.js`**

In the `PAGE_SECTIONS` client-side object (line 201-215):

```javascript
    const PAGE_SECTIONS = {
        dashboard: ['events', 'projects', 'newsletters', 'workshops'],
        team: [],
        events: ['events'],
        ships: ['projects'],
        projects: ['projects'],
        levels: ['projects'],
        tools: [],
        shop: ['orders', 'itemRequests'],
        workshops: ['workshops'],
        chat: ['channels', 'messages'],
        newsletters: ['newsletters'],
        map: [],
        settings: [],
        profile: ['projects'],
    };
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_workshops.py -v`
Expected: 7 passed

Run: `pytest tests/test_coins.py -v -k "state_section or mongo_collection"`
Expected: all pass — confirms `workshops` didn't break the generic parity tests either.

Run: `pytest tests/ -v`
Expected: all tests pass (catches anything that constructs a `DashboardState` literal that would now be missing `workshops` under strict comparison — none expected, same reasoning as the Coins Spine plan's equivalent step).

- [ ] **Step 8: Run mypy on the three modified Python modules**

Run: `mypy src/helpers.py src/storage.py src/storage_mongo.py --strict`
Expected: same error counts as before this task (26 / 7 / 3 respectively) — pure registration, no new typed surface.

- [ ] **Step 9: Commit**

```bash
git add src/helpers.py src/storage.py src/storage_mongo.py static/js/dashboard.js tests/test_workshops.py
git commit -m "feat: register workshops across session, Airtable, and Mongo backends"
```

---

### Task 3: Propose and apply/withdraw endpoints

**Files:**
- Modify: `src/routes_api.py` (imports line 7-32, new `# ── Workshops ──` section after Events, before Cart — around line 345)
- Modify: `src/notifications.py` (one new function)
- Modify: `src/email.py` (one new render function)
- Test: `tests/test_workshops.py` (append)

**Interfaces:**
- Consumes: `workshop_from_payload` (Task 1); `_item_id`, `utc_iso`, `_viewer_email`, `find_by_id`, `parse_bool`, `clean_text`, `get_dashboard_state`, `save_dashboard_state`, `json_error`, `json_payload`, `require_dashboard_csrf`, `login_required` (all existing, already imported in this file except `utc_iso` and `workshop_from_payload`); `add_in_app_notification`, `send_email` (existing, `src/notifications.py`/`src/email.py`).
- Produces: `POST /api/dashboard/workshops` (any member proposes); `PATCH /api/dashboard/workshops/<id>` with `{applying: bool}` (any member applies/withdraws — the leader-only branches for `{status: ...}` payloads are added in Task 4, in the same function); `notify_leaders_of_workshop_application(workshop, user_email, user_name, is_applying)`; `render_workshop_application_notification(workshop, club_name, recipient_name, applicant_name, is_applying)`. Task 4's `notify_runner_of_workshop_selection` is a separate, independent function added there — this task doesn't need to anticipate it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_workshops.py`:

```python
def _seed_workshop_club(client, monkeypatch, workshops=None, members=None):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with client.session_transaction() as sess:
        sess['csrf_token'] = 'tok'
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Workshop Club'},
            'members': members if members is not None else [],
            'events': [],
            'workshops': workshops or [],
        }


HEADERS = {'X-CSRF-Token': 'tok'}


def test_propose_workshop_creates_proposed_entry(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client,
        monkeypatch,
        members=[
            {
                'id': 'm1',
                'name': 'Test Leader',
                'email': 'leader@test.com',
                'role': 'Member',
                'avatar': '',
                'status': 'Active',
            }
        ],
    )
    response = auth_client.post(
        '/api/dashboard/workshops',
        headers=HEADERS,
        json={'title': 'Intro to Git', 'description': 'Version control basics.'},
    )
    assert response.status_code == 200
    workshop = response.get_json()['workshop']
    assert workshop['title'] == 'Intro to Git'
    assert workshop['status'] == 'Proposed'
    assert workshop['proposerEmail'] == 'leader@test.com'
    assert workshop['applicants'] == []
    assert workshop['runnerEmail'] == ''
    assert workshop['eventId'] == ''
    assert workshop['id']
    assert workshop['createdAt']


def test_propose_workshop_requires_title(auth_client, monkeypatch):
    _seed_workshop_club(auth_client, monkeypatch)
    response = auth_client.post(
        '/api/dashboard/workshops',
        headers=HEADERS,
        json={'title': '', 'description': 'Version control basics.'},
    )
    assert response.status_code == 400


def _base_workshop(**overrides):
    workshop = {
        'id': 'w1',
        'title': 'Intro to Git',
        'description': 'Basics.',
        'status': 'Proposed',
        'proposerEmail': 'other@test.com',
        'proposerName': 'Other',
        'applicants': [],
        'runnerEmail': '',
        'runnerName': '',
        'eventId': '',
        'createdAt': '2026-08-09T00:00:00Z',
    }
    workshop.update(overrides)
    return workshop


def test_apply_to_workshop_adds_viewer_to_applicants(auth_client, monkeypatch):
    _seed_workshop_club(auth_client, monkeypatch, workshops=[_base_workshop()])
    response = auth_client.patch(
        '/api/dashboard/workshops/w1', headers=HEADERS, json={'applying': True}
    )
    assert response.status_code == 200
    assert 'leader@test.com' in response.get_json()['workshop']['applicants']


def test_withdraw_from_workshop_removes_viewer(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client, monkeypatch, workshops=[_base_workshop(applicants=['leader@test.com'])]
    )
    response = auth_client.patch(
        '/api/dashboard/workshops/w1', headers=HEADERS, json={'applying': False}
    )
    assert response.status_code == 200
    assert response.get_json()['workshop']['applicants'] == []


def test_apply_rejected_once_workshop_is_scheduled(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client,
        monkeypatch,
        workshops=[
            _base_workshop(
                status='Scheduled', runnerEmail='runner@test.com', runnerName='Runner', eventId='e1'
            )
        ],
    )
    response = auth_client.patch(
        '/api/dashboard/workshops/w1', headers=HEADERS, json={'applying': True}
    )
    assert response.status_code == 400


def test_apply_does_not_require_leader_role(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client,
        monkeypatch,
        members=[
            {
                'id': 'm1',
                'name': 'Test Leader',
                'email': 'leader@test.com',
                'role': 'Member',
                'avatar': '',
                'status': 'Active',
            }
        ],
        workshops=[_base_workshop()],
    )
    response = auth_client.patch(
        '/api/dashboard/workshops/w1', headers=HEADERS, json={'applying': True}
    )
    assert response.status_code == 200


def test_apply_to_missing_workshop_404s(auth_client, monkeypatch):
    _seed_workshop_club(auth_client, monkeypatch)
    response = auth_client.patch(
        '/api/dashboard/workshops/nope', headers=HEADERS, json={'applying': True}
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_workshops.py -v -k "propose or apply or withdraw"`
Expected: FAIL — 404s on `/api/dashboard/workshops` (route doesn't exist yet)

- [ ] **Step 3: Add the notification function to `src/notifications.py`**

Update the `from .email import (...)` block at the top:

```python
from .email import (
    render_event_rsvp_confirmation,
    render_project_submitted,
    render_workshop_application_notification,
    send_email,
)
```

Add the function after `notify_leaders_of_event_rsvp` (after line 69, before `notify_admins_of_project_submission`):

```python
def notify_leaders_of_workshop_application(workshop, user_email, user_name, is_applying):
    """Notify club leaders when a member applies to run (or withdraws from) a workshop."""
    state = get_dashboard_state()
    leaders = [m for m in state.get('members', []) if m.get('role') in ('Leader', 'Mentor')]
    club_name = _club_name()
    title = workshop.get('title', 'Workshop')
    if is_applying:
        subject_action = 'applied to run'
        body = f'{user_name} applied to run this workshop.'
    else:
        subject_action = 'withdrew their application for'
        body = f'{user_name} withdrew their application to run this workshop.'

    for leader in leaders:
        leader_email = leader.get('email', '').lower()
        if leader_email and leader_email != user_email:
            template = render_workshop_application_notification(
                workshop, club_name, leader.get('name', 'Leader'), user_name, is_applying
            )
            send_email(
                subject=f'🔔 {user_name} {subject_action} "{title}"',
                recipients=leader_email,
                template=template,
            )
            add_in_app_notification(
                leader_email,
                'workshop_application',
                f'{user_name} {subject_action} "{title}"',
                body,
                {'workshopId': workshop.get('id'), 'userEmail': user_email, 'isApplying': is_applying},
            )
```

- [ ] **Step 4: Add the render function to `src/email.py`**

Add after `render_event_rsvp_confirmation` (after its closing `'''`, before `render_project_submitted`):

```python
def render_workshop_application_notification(workshop, club_name, recipient_name, applicant_name, is_applying):
    """Render the email sent to leaders when a member applies to run (or withdraws from) a workshop."""
    action = 'applied to run' if is_applying else 'withdrew their application for'
    return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Workshop Application</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
        .event-card {{ background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1 style="margin: 0; font-size: 24px;">🔔 Workshop Application</h1>
        <p style="margin: 10px 0 0; opacity: 0.9;">{escape(club_name)}</p>
    </div>
    <div class="content">
        <p>Hi {escape(recipient_name)},</p>
        <p>{escape(applicant_name)} has {escape(action)} the following workshop:</p>

        <div class="event-card">
            <p style="margin: 0; font-weight: 600;">{escape(workshop.get('title', 'Untitled Workshop'))}</p>
            <p style="margin: 10px 0 0; color: #666;">{escape(workshop.get('description', ''))}</p>
        </div>

        <p style="text-align: center;">
            <a href="{os.environ.get('BASE_URL', '')}/dashboard/workshops" style="display: inline-block; background: #667eea; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">View Workshops</a>
        </p>

        <div class="footer">
            <p>You're receiving this because you're a leader of {escape(club_name)}.</p>
        </div>
    </div>
</body>
</html>
'''
```

- [ ] **Step 5: Update imports in `src/routes_api.py`**

Add `utc_iso` and `workshop_from_payload` to the `from .helpers import (...)` block (line 7-32):

```python
from .helpers import (
    STATE_SECTIONS,
    Order,
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
    utc_iso,
    viewer_is_leader,
    workshop_from_payload,
)
```

Add `notify_leaders_of_workshop_application` to the existing `from .notifications import (...)` block:

```python
from .notifications import (
    notify_admins_of_project_submission,
    notify_leaders_of_event_rsvp,
    notify_leaders_of_workshop_application,
    send_event_rsvp_confirmation,
)
```

- [ ] **Step 6: Add the Workshops section — propose and apply/withdraw**

Insert after `api_events_delete` (after line 344, before the `# ── Cart ──` divider):

```python
    # ── Workshops ──────────────────────────────────────────────────────────

    @app.post('/api/dashboard/workshops')
    @login_required
    def api_workshops_add():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        workshop_data, error = workshop_from_payload(json_payload())
        if error:
            return json_error(error)

        user = session.get('user') or {}
        state = get_dashboard_state()
        workshop = {
            'id': _item_id('workshop'),
            'title': workshop_data['title'],
            'description': workshop_data['description'],
            'status': 'Proposed',
            'proposerEmail': _viewer_email(),
            'proposerName': user.get('name', 'A member'),
            'applicants': [],
            'runnerEmail': '',
            'runnerName': '',
            'eventId': '',
            'createdAt': utc_iso(),
        }
        state['workshops'].insert(0, workshop)
        save_dashboard_state(state)
        return flask.jsonify({'workshop': workshop, 'state': state})

    @app.patch('/api/dashboard/workshops/<workshop_id>')
    @login_required
    def api_workshops_update(workshop_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        payload = json_payload()
        is_apply_only = set(payload.keys()) <= {'applying'}
        if not is_apply_only:
            role_error = require_leader_api()
            if role_error:
                return role_error

        state = get_dashboard_state()
        workshop = find_by_id(state['workshops'], workshop_id)
        if not workshop:
            return json_error('Workshop not found.', 404)

        if is_apply_only:
            if workshop['status'] != 'Proposed':
                return json_error('This workshop is no longer open to applicants.')
            applying = parse_bool(payload.get('applying'))
            viewer_email = _viewer_email()
            already_applied = viewer_email in workshop['applicants']
            if applying == already_applied:
                return flask.jsonify({'workshop': workshop, 'state': state})
            if applying:
                workshop['applicants'].append(viewer_email)
            else:
                workshop['applicants'].remove(viewer_email)
            save_dashboard_state(state)

            user = session.get('user') or {}
            try:
                notify_leaders_of_workshop_application(
                    workshop, viewer_email, user.get('name', 'A member'), applying
                )
            except Exception as e:
                current_app.logger.warning(f'Failed to send workshop application notification: {e}')
            return flask.jsonify({'workshop': workshop, 'state': state})

        return json_error('Unsupported update.')
```

Note: the `require_leader_api()`-gated branch currently just returns `json_error('Unsupported update.')` for any non-`applying` payload — Task 4 replaces that final `return json_error(...)` line with the `Scheduled`/`Run` handling.

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_workshops.py -v`
Expected: 14 passed

Run: `pytest tests/test_api.py -v`
Expected: all pass (unaffected by this addition)

- [ ] **Step 8: Run mypy**

Run: `mypy src/routes_api.py src/notifications.py src/email.py --strict`
Expected: `routes_api.py` unchanged (49 pre-existing); `notifications.py`/`email.py` gain no new error *category* — both already contain unannotated functions in the pre-existing baseline, and the new function in each file is unannotated too, matching every sibling function already there.

- [ ] **Step 9: Commit**

```bash
git add src/routes_api.py src/notifications.py src/email.py tests/test_workshops.py
git commit -m "feat: add workshop propose/apply/withdraw endpoints with notifications"
```

---

### Task 4: Schedule, mark run, delete, and the scheduling notification

**Files:**
- Modify: `src/routes_api.py` (replace the final `return json_error('Unsupported update.')` line in `api_workshops_update`; add `DELETE`)
- Modify: `src/notifications.py` (one new function)
- Modify: `src/email.py` (one new render function)
- Test: `tests/test_workshops.py` (append)

**Interfaces:**
- Consumes: `add_in_app_notification`, `send_email` (existing, `src/notifications.py`/`src/email.py`); `Event`-shaped dict construction (matches `src/helpers.py:46-55`'s fields); `notify_leaders_of_workshop_application` (Task 3, already wired — untouched by this task).
- Produces: `notify_runner_of_workshop_selection(workshop, runner_email, runner_name)`; `render_workshop_scheduled_confirmation(workshop, club_name, recipient_name)`; `PATCH /api/dashboard/workshops/<id>` now also accepts `{status: 'Scheduled', runnerEmail, date, time, location}` and `{status: 'Run'}` (both leader-only); `DELETE /api/dashboard/workshops/<id>` (leader-only, only while `status == 'Proposed'`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_workshops.py`:

```python
def test_schedule_workshop_creates_linked_event(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client,
        monkeypatch,
        members=[
            {
                'id': 'm1',
                'name': 'Runner',
                'email': 'runner@test.com',
                'role': 'Member',
                'avatar': '',
                'status': 'Active',
            }
        ],
        workshops=[_base_workshop(applicants=['runner@test.com'])],
    )
    response = auth_client.patch(
        '/api/dashboard/workshops/w1',
        headers=HEADERS,
        json={
            'status': 'Scheduled',
            'runnerEmail': 'runner@test.com',
            'date': '2026-09-01',
            'time': '15:00',
            'location': 'Room 204',
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    workshop = body['workshop']
    assert workshop['status'] == 'Scheduled'
    assert workshop['runnerEmail'] == 'runner@test.com'
    assert workshop['runnerName'] == 'Runner'
    assert workshop['eventId']
    events = body['state']['events']
    assert any(
        e['id'] == workshop['eventId']
        and e['title'] == 'Intro to Git'
        and e['type'] == 'Workshop'
        and e['location'] == 'Room 204'
        for e in events
    )


def test_schedule_workshop_rejects_non_applicant(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client, monkeypatch, workshops=[_base_workshop(applicants=['runner@test.com'])]
    )
    response = auth_client.patch(
        '/api/dashboard/workshops/w1',
        headers=HEADERS,
        json={
            'status': 'Scheduled',
            'runnerEmail': 'nobody@test.com',
            'date': '2026-09-01',
            'time': '15:00',
            'location': 'Room 204',
        },
    )
    assert response.status_code == 400


def test_schedule_workshop_rejects_invalid_date(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client, monkeypatch, workshops=[_base_workshop(applicants=['runner@test.com'])]
    )
    response = auth_client.patch(
        '/api/dashboard/workshops/w1',
        headers=HEADERS,
        json={
            'status': 'Scheduled',
            'runnerEmail': 'runner@test.com',
            'date': 'not-a-date',
            'time': '15:00',
            'location': 'Room 204',
        },
    )
    assert response.status_code == 400


def test_schedule_workshop_requires_leader(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client,
        monkeypatch,
        members=[
            {
                'id': 'm1',
                'name': 'Test Leader',
                'email': 'leader@test.com',
                'role': 'Member',
                'avatar': '',
                'status': 'Active',
            }
        ],
        workshops=[_base_workshop(applicants=['runner@test.com'])],
    )
    response = auth_client.patch(
        '/api/dashboard/workshops/w1',
        headers=HEADERS,
        json={
            'status': 'Scheduled',
            'runnerEmail': 'runner@test.com',
            'date': '2026-09-01',
            'time': '15:00',
            'location': 'Room 204',
        },
    )
    assert response.status_code == 403


def test_mark_workshop_run_requires_scheduled_status(auth_client, monkeypatch):
    _seed_workshop_club(auth_client, monkeypatch, workshops=[_base_workshop(status='Proposed')])
    response = auth_client.patch(
        '/api/dashboard/workshops/w1', headers=HEADERS, json={'status': 'Run'}
    )
    assert response.status_code == 400


def test_mark_workshop_run_succeeds_when_scheduled(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client,
        monkeypatch,
        workshops=[
            _base_workshop(
                status='Scheduled', runnerEmail='runner@test.com', runnerName='Runner', eventId='e1'
            )
        ],
    )
    response = auth_client.patch(
        '/api/dashboard/workshops/w1', headers=HEADERS, json={'status': 'Run'}
    )
    assert response.status_code == 200
    assert response.get_json()['workshop']['status'] == 'Run'


def test_delete_workshop_requires_leader(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client,
        monkeypatch,
        members=[
            {
                'id': 'm1',
                'name': 'Test Leader',
                'email': 'leader@test.com',
                'role': 'Member',
                'avatar': '',
                'status': 'Active',
            }
        ],
        workshops=[_base_workshop()],
    )
    response = auth_client.delete('/api/dashboard/workshops/w1', headers=HEADERS)
    assert response.status_code == 403


def test_delete_workshop_removes_it(auth_client, monkeypatch):
    _seed_workshop_club(auth_client, monkeypatch, workshops=[_base_workshop()])
    response = auth_client.delete('/api/dashboard/workshops/w1', headers=HEADERS)
    assert response.status_code == 200
    with auth_client.session_transaction() as sess:
        assert sess['dashboard_state']['workshops'] == []


def test_delete_workshop_rejects_once_scheduled(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client,
        monkeypatch,
        workshops=[
            _base_workshop(
                status='Scheduled', runnerEmail='runner@test.com', runnerName='Runner', eventId='e1'
            )
        ],
    )
    response = auth_client.delete('/api/dashboard/workshops/w1', headers=HEADERS)
    assert response.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_workshops.py -v -k "schedule or mark_workshop_run or delete_workshop"`
Expected: FAIL — scheduling/run/delete all currently fall through to `json_error('Unsupported update.')` (400, not the specific behavior asserted) or 404 (no `DELETE` route)

- [ ] **Step 3: Add the notification function to `src/notifications.py`**

Update the `from .email import (...)` block at the top (Task 3 already added `render_workshop_application_notification` here; this adds the second render function):

```python
from .email import (
    render_event_rsvp_confirmation,
    render_project_submitted,
    render_workshop_application_notification,
    render_workshop_scheduled_confirmation,
    send_email,
)
```

Add the function after `notify_leaders_of_workshop_application` (added in Task 3), before `notify_admins_of_project_submission`:

```python
def notify_runner_of_workshop_selection(workshop, runner_email, runner_name):
    """Notify the member picked to run a workshop once a leader schedules it."""
    club_name = _club_name()
    title = workshop.get('title', 'Workshop')
    send_email(
        subject=f'🎉 You\'re running "{title}" - {club_name}',
        recipients=runner_email,
        template=render_workshop_scheduled_confirmation(workshop, club_name, runner_name),
    )
    add_in_app_notification(
        runner_email,
        'workshop_scheduled',
        f'You\'re running "{title}"',
        'Check the Events page for the date and time.',
        {'workshopId': workshop.get('id'), 'eventId': workshop.get('eventId')},
    )
```

- [ ] **Step 4: Add the render function to `src/email.py`**

Add after `render_workshop_application_notification` (added in Task 3), before `render_project_submitted`:

```python
def render_workshop_scheduled_confirmation(workshop, club_name, recipient_name):
    """Render the email sent to a member once a leader schedules them to run a workshop."""
    return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>You're Running a Workshop</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
        .event-card {{ background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1 style="margin: 0; font-size: 24px;">🎉 You're Running a Workshop</h1>
        <p style="margin: 10px 0 0; opacity: 0.9;">{escape(club_name)}</p>
    </div>
    <div class="content">
        <p>Hi {escape(recipient_name)},</p>
        <p>A leader picked you to run the following workshop:</p>

        <div class="event-card">
            <p style="margin: 0; font-weight: 600;">{escape(workshop.get('title', 'Untitled Workshop'))}</p>
            <p style="margin: 10px 0 0; color: #666;">{escape(workshop.get('description', ''))}</p>
        </div>

        <p style="text-align: center;">
            <a href="{os.environ.get('BASE_URL', '')}/dashboard/events" style="display: inline-block; background: #667eea; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">View Event</a>
        </p>

        <div class="footer">
            <p>You're receiving this because you're a member of {escape(club_name)}.</p>
        </div>
    </div>
</body>
</html>
'''
```

- [ ] **Step 5: Import `notify_runner_of_workshop_selection` in `src/routes_api.py`**

Update the `from .notifications import (...)` block (Task 3 already added `notify_leaders_of_workshop_application` here):

```python
from .notifications import (
    notify_admins_of_project_submission,
    notify_leaders_of_event_rsvp,
    notify_leaders_of_workshop_application,
    notify_runner_of_workshop_selection,
    send_event_rsvp_confirmation,
)
```

- [ ] **Step 6: Replace the final `return json_error('Unsupported update.')` line in `api_workshops_update`**

The function now ends with three branches instead of one fallback. Replace:

```python
            return flask.jsonify({'workshop': workshop, 'state': state})

        return json_error('Unsupported update.')
```

with:

```python
            return flask.jsonify({'workshop': workshop, 'state': state})

        new_status = payload.get('status')
        if new_status == 'Scheduled':
            if workshop['status'] != 'Proposed':
                return json_error('This workshop has already been scheduled.')
            runner_email = clean_text(payload.get('runnerEmail')).lower()
            if runner_email not in workshop['applicants']:
                return json_error('Pick an applicant who actually applied to run this.')
            event_date = clean_text(payload.get('date'))
            event_time = clean_text(payload.get('time'))
            location = clean_text(payload.get('location'))
            try:
                date.fromisoformat(event_date)
            except ValueError:
                return json_error('Choose a valid date.')
            if not event_time:
                return json_error('Event time is required.')
            if not location:
                return json_error('Event location is required.')

            runner = next(
                (m for m in state['members'] if (m.get('email') or '').lower() == runner_email), None
            )
            runner_name = runner.get('name', 'A member') if runner else 'A member'

            new_event = {
                'id': _item_id('event'),
                'title': workshop['title'],
                'date': event_date,
                'time': event_time,
                'location': location,
                'type': 'Workshop',
                'repeat': '',
                'rsvp': False,
                'attendees': 0,
            }
            state['events'].append(new_event)
            state['events'].sort(key=lambda item: (item.get('date', ''), item.get('time', '')))

            workshop['status'] = 'Scheduled'
            workshop['runnerEmail'] = runner_email
            workshop['runnerName'] = runner_name
            workshop['eventId'] = new_event['id']
            save_dashboard_state(state)

            try:
                notify_runner_of_workshop_selection(workshop, runner_email, runner_name)
            except Exception as e:
                current_app.logger.warning(f'Failed to send workshop selection notification: {e}')

            return flask.jsonify({'workshop': workshop, 'state': state})

        if new_status == 'Run':
            if workshop['status'] != 'Scheduled':
                return json_error('Only a scheduled workshop can be marked as run.')
            workshop['status'] = 'Run'
            save_dashboard_state(state)
            return flask.jsonify({'workshop': workshop, 'state': state})

        return json_error('Unsupported update.')
```

`date` (from `datetime`) and `current_app` are already imported at the top of `src/routes_api.py` (used by `event_from_payload`'s callers and the RSVP notification block respectively) — no new imports needed for this step.

- [ ] **Step 7: Add the `DELETE` endpoint**

Insert right after the (now three-branch) `api_workshops_update` function, before the `# ── Cart ──` divider:

```python
    @app.delete('/api/dashboard/workshops/<workshop_id>')
    @login_required
    def api_workshops_delete(workshop_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        state = get_dashboard_state()
        workshop = find_by_id(state['workshops'], workshop_id)
        if not workshop:
            return json_error('Workshop not found.', 404)
        if workshop['status'] != 'Proposed':
            return json_error('Only a proposed (not yet scheduled) workshop can be deleted.')
        state['workshops'] = [w for w in state['workshops'] if w.get('id') != workshop_id]
        save_dashboard_state(state)
        return flask.jsonify({'state': state})
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_workshops.py -v`
Expected: 23 passed

Run: `pytest tests/ -v`
Expected: all pass

- [ ] **Step 9: Run mypy**

Run: `mypy src/routes_api.py src/notifications.py src/email.py --strict`
Expected: `routes_api.py` unchanged from its Task 3 count (49); `notifications.py`/`email.py` gain no new error *category* — both files already contain multiple unannotated functions (`no-untyped-def`) in the pre-existing baseline, and this task's one new function in each file is unannotated too, matching every sibling function already there.

- [ ] **Step 10: Commit**

```bash
git add src/routes_api.py src/notifications.py src/email.py tests/test_workshops.py
git commit -m "feat: schedule/run/delete workshops with notifications"
```

---

### Task 5: UI — nav, page, modals, and the home stat tile

**Files:**
- Modify: `templates/dashboard_layout.html` (nav link, near line 103-112)
- Modify: `templates/partials/icons.html` (new `workshop` glyph, line 19-20)
- Create: `templates/dashboard/workshops.html`
- Modify: `templates/dashboard.html` (5th sticker, line 43-47)
- Modify: `src/routes_web.py` (new page route, near line 223-227)
- Modify: `static/css/dashboard.css` (one new sticker color variant, line 762-765)
- Modify: `static/js/dashboard.js` (`workshops()` accessor, `renderWorkshops()`/`renderWorkshopFilters()`/`renderWorkshopDetail()`, modal prep, delegated click handlers, form submit handlers, `renderPage()`, `renderHome()`)
- Test: `tests/test_public.py` (append)

**Interfaces:**
- Consumes: `settings()`, `members()`, `viewerEmail`, `isLeader`, `apiRequest()`, `formObject()`, `openModal()`/`closeModal()`, `escapeHtml()`, `showToast()`, `setFormError()` (all existing client-side helpers in `static/js/dashboard.js`).
- Produces: `/dashboard/workshops` page; every dashboard page's home stat row shows a "workshops run" count.

- [ ] **Step 1: Add the `workshop` icon to `templates/partials/icons.html`**

Add a new entry to the `icons` dict (after `'coin'`, line 19):

```
    'coin': '<circle cx="12" cy="12" r="9"/><path d="M12 6.5v11"/><path d="M15 9a3 3 0 0 0-3-1h-.5a2 2 0 0 0 0 4h1a2 2 0 0 1 0 4H12a3 3 0 0 1-3-1"/>',
    'workshop': '<path d="M2 5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H2Z"/><path d="M22 5a2 2 0 0 0-2-2h-6a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h8Z"/>',
```

- [ ] **Step 2: Add the nav link to `templates/dashboard_layout.html`**

Insert between the Events link and the Ships link (after line 107, before line 108):

```html
                <a href="/dashboard/events"
                    class="dashboard-sidebar-link {% if current_path == '/dashboard/events' %}active{% endif %}"
                    title="Events" aria-label="Events" data-i18n-attr="title:side.events;aria-label:side.events">
                    {{ sidebar_icon('event-add') }}
                </a>
                <a href="/dashboard/workshops"
                    class="dashboard-sidebar-link {% if current_path == '/dashboard/workshops' %}active{% endif %}"
                    title="Workshops" aria-label="Workshops" data-i18n-attr="title:side.workshops;aria-label:side.workshops">
                    {{ sidebar_icon('workshop') }}
                </a>
                <a href="/dashboard/ships"
                    class="dashboard-sidebar-link {% if current_path == '/dashboard/ships' %}active{% endif %}"
                    title="Ships" aria-label="Ships" data-i18n-attr="title:side.ships;aria-label:side.ships">
                    {{ sidebar_icon('rocket') }}
                </a>
```

- [ ] **Step 3: Add the page route to `src/routes_web.py`**

Insert after `dashboard_events` (after line 226, before `dashboard_ships`):

```python
    @app.route('/dashboard/events')
    @login_required
    def dashboard_events():
        return flask.render_template('dashboard/events.html')

    @app.route('/dashboard/workshops')
    @login_required
    def dashboard_workshops():
        return flask.render_template('dashboard/workshops.html')

    @app.route('/dashboard/ships')
```

- [ ] **Step 4: Create `templates/dashboard/workshops.html`**

```html
{% extends "dashboard_layout.html" %}

{% block page_title %}<span data-i18n="side.workshops">Workshops</span>{% endblock %}
{% block page_subtitle %}<span data-i18n="workshops.subtitle">Propose a topic, or apply to run one someone else suggested.</span>{% endblock %}

{% block header_right %}
<button class="btn-primary" type="button" data-open-modal="workshopProposeModal">
    <span class="button-icon" aria-hidden="true">+</span>
    <span data-i18n="workshops.propose">Propose a workshop</span>
</button>
{% endblock %}

{% block content %}
<div class="dashboard-page" data-dashboard-page="workshops">
    <div class="skeleton-block" data-skeleton="workshops" style="padding:20px;">
      <div class="skeleton skeleton-heading"></div>
      <div style="display:flex; gap:8px; margin:16px 0;">
        <div class="skeleton skeleton-badge"></div>
        <div class="skeleton skeleton-badge"></div>
        <div class="skeleton skeleton-badge"></div>
      </div>
      <div style="display:flex; gap:12px; flex-wrap:wrap;">
        <div class="skeleton skeleton-card" style="width:220px;"></div>
        <div class="skeleton skeleton-card" style="width:220px;"></div>
        <div class="skeleton skeleton-card" style="width:220px;"></div>
      </div>
    </div>

    <section class="card-modern dashboard-panel dashboard-panel-full">
        <div class="panel-heading">
            <div>
                <h2 data-i18n="workshops.catalogTitle">Workshop board</h2>
                <p data-i18n="workshops.catalogDesc">Propose a topic for your club, or apply to run one that's open.</p>
            </div>
        </div>
        <div class="shop-filters" id="workshopFilters" role="tablist" aria-label="Filter workshops" data-i18n-attr="aria-label:workshops.filterAria"></div>
        <div class="item-grid" id="workshopGrid"></div>
        <div class="empty-state tight" id="workshopsEmpty" hidden>
            <h3 data-i18n="workshops.emptyTitle">No workshops yet</h3>
            <p data-i18n="workshops.emptyDesc">Be the first to propose one for your club.</p>
        </div>
    </section>
</div>

<div class="modal-backdrop" id="workshopProposeModal" aria-hidden="true">
    <section class="dashboard-modal" role="dialog" aria-modal="true" aria-labelledby="workshopProposeModalTitle">
        <header class="modal-header">
            <h2 id="workshopProposeModalTitle" data-i18n="workshops.proposeTitle">Propose a workshop</h2>
            <button class="icon-button" type="button" data-modal-close aria-label="Close" data-i18n-attr="aria-label:common.close"><span aria-hidden="true" data-i18n="common.closeX">×</span></button>
        </header>
        <form class="modal-form" id="workshopProposeForm">
            <label class="form-group">
                <span class="form-label" data-i18n="workshops.titleLabel">Title</span>
                <input class="form-input" type="text" name="title" required>
            </label>
            <label class="form-group">
                <span class="form-label" data-i18n="workshops.descriptionLabel">Description</span>
                <textarea class="form-input" name="description" rows="4" required></textarea>
            </label>
            <p class="form-error" id="workshopProposeFormError" hidden></p>
            <div class="modal-actions">
                <button class="btn-secondary" type="button" data-modal-close data-i18n="workshops.cancel">Cancel</button>
                <button class="btn-primary" type="submit" data-i18n="workshops.submitProposal">Submit proposal</button>
            </div>
        </form>
    </section>
</div>

<div class="modal-backdrop" id="workshopDetailModal" aria-hidden="true">
    <section class="dashboard-modal" role="dialog" aria-modal="true" aria-labelledby="workshopDetailTitle">
        <header class="modal-header">
            <h2 id="workshopDetailTitle"></h2>
            <button class="icon-button" type="button" data-modal-close aria-label="Close" data-i18n-attr="aria-label:common.close"><span aria-hidden="true" data-i18n="common.closeX">×</span></button>
        </header>
        <div class="modal-scroll-body" id="workshopDetailBody"></div>
        <div class="modal-actions" id="workshopDetailActions"></div>
    </section>
</div>

<div class="modal-backdrop" id="workshopScheduleModal" aria-hidden="true">
    <section class="dashboard-modal" role="dialog" aria-modal="true" aria-labelledby="workshopScheduleModalTitle">
        <header class="modal-header">
            <h2 id="workshopScheduleModalTitle" data-i18n="workshops.scheduleTitle">Schedule this workshop</h2>
            <button class="icon-button" type="button" data-modal-close aria-label="Close" data-i18n-attr="aria-label:common.close"><span aria-hidden="true" data-i18n="common.closeX">×</span></button>
        </header>
        <form class="modal-form" id="workshopScheduleForm">
            <input type="hidden" name="workshopId">
            <input type="hidden" name="runnerEmail">
            <p id="workshopScheduleRunnerName"></p>
            <div class="form-row">
                <label class="form-group">
                    <span class="form-label" data-i18n="workshops.dateLabel">Date</span>
                    <input class="form-input" type="date" name="date" required>
                </label>
                <label class="form-group">
                    <span class="form-label" data-i18n="workshops.timeLabel">Time</span>
                    <input class="form-input" type="time" name="time" required>
                </label>
            </div>
            <label class="form-group">
                <span class="form-label" data-i18n="workshops.locationLabel">Location</span>
                <input class="form-input" type="text" name="location" required>
            </label>
            <p class="form-error" id="workshopScheduleFormError" hidden></p>
            <div class="modal-actions">
                <button class="btn-secondary" type="button" data-modal-close data-i18n="workshops.cancel">Cancel</button>
                <button class="btn-primary" type="submit" data-i18n="workshops.confirmSchedule">Confirm schedule</button>
            </div>
        </form>
    </section>
</div>
{% endblock %}
```

- [ ] **Step 5: Add the 5th sticker to `templates/dashboard.html`**

After the `sticker-purple` block (line 43-46), before the closing `</div>` of `.sticker-row` (line 47):

```html
            <div class="sticker sticker-purple">
                <strong id="homeOrderTotal">0</strong>
                <span data-i18n="home.shopRequests">shop requests</span>
            </div>
            <div class="sticker sticker-red">
                <strong id="homeWorkshopTotal">0</strong>
                <span data-i18n="home.workshopsRun">workshops run</span>
            </div>
        </div>
```

- [ ] **Step 6: Add the new sticker color variant to `static/css/dashboard.css`**

After `.sticker-purple` (line 762-765):

```css
.sticker-orange { --sticker-color: var(--hackclub-orange); }
.sticker-blue   { --sticker-color: var(--hackclub-blue); }
.sticker-green  { --sticker-color: #27a37e; }
.sticker-purple { --sticker-color: var(--hackclub-purple); }
.sticker-red    { --sticker-color: var(--hackclub-red); }
```

- [ ] **Step 7: Add the `workshops()` accessor to `static/js/dashboard.js`**

Add next to the other state accessors (after `orders()`, around line 51):

```javascript
    function orders() {
        return dashboardState.orders || [];
    }

    function workshops() {
        return dashboardState.workshops || [];
    }
```

- [ ] **Step 8: Add `renderWorkshopFilters()`, `renderWorkshops()`, and `renderWorkshopDetail()`**

Add after `renderShop()` (after its closing `}`, before `renderItemRequests()`):

```javascript
    const WORKSHOP_FILTERS = ['All', 'Proposed', 'Scheduled', 'Run'];
    let workshopFilter = 'All';
    let openWorkshopId = '';

    function renderWorkshopFilters() {
        const bar = $('#workshopFilters');
        if (!bar) return;
        bar.innerHTML = WORKSHOP_FILTERS.map((filter) => {
            const active = filter === workshopFilter;
            return `
                <button class="shop-filter-chip${active ? ' is-active' : ''}" type="button" role="tab"
                    aria-selected="${active}" data-workshop-filter="${escapeHtml(filter)}">
                    <span>${escapeHtml(filter)}</span>
                </button>
            `;
        }).join('');
    }

    function renderWorkshopDetail(workshop) {
        const titleNode = $('#workshopDetailTitle');
        if (titleNode) titleNode.textContent = workshop.title;
        const body = $('#workshopDetailBody');
        const actionsNode = $('#workshopDetailActions');
        if (!body || !actionsNode) return;

        const applied = workshop.applicants.includes(viewerEmail);
        const applicantRows = workshop.applicants.map((email) => {
            const person = members().find((m) => m.email === email);
            const name = person ? person.name : email;
            return `
                <div class="order-row">
                    <span>${escapeHtml(name)}</span>
                    ${isLeader && workshop.status === 'Proposed'
                        ? `<button class="btn-secondary small" type="button" data-schedule-workshop="${escapeHtml(workshop.id)}::${escapeHtml(email)}">Schedule</button>`
                        : ''}
                </div>
            `;
        }).join('');

        const runnerLine = workshop.runnerName
            ? `<p><strong>Run by:</strong> ${escapeHtml(workshop.runnerName)}</p>`
            : '';

        body.innerHTML = `
            <span class="status-chip">${escapeHtml(workshop.status)}</span>
            <p>${escapeHtml(workshop.description)}</p>
            <p><strong>Proposed by:</strong> ${escapeHtml(workshop.proposerName)}</p>
            ${runnerLine}
            ${isLeader ? `<h3>Applicants</h3><div class="workshop-applicant-list" style="display:grid; gap:8px;">${applicantRows || '<p>No applicants yet.</p>'}</div>` : ''}
        `;

        let actionsHtml = '';
        if (workshop.status === 'Proposed') {
            actionsHtml = applied
                ? `<button class="btn-secondary" type="button" data-withdraw-workshop="${escapeHtml(workshop.id)}">Withdraw application</button>`
                : `<button class="btn-primary" type="button" data-apply-workshop="${escapeHtml(workshop.id)}">Apply to run</button>`;
            if (isLeader) {
                actionsHtml = `<button class="text-button" type="button" data-delete-workshop="${escapeHtml(workshop.id)}">Delete proposal</button>` + actionsHtml;
            }
        } else if (workshop.status === 'Scheduled' && isLeader) {
            actionsHtml = `<button class="btn-primary" type="button" data-mark-run-workshop="${escapeHtml(workshop.id)}">Mark as run</button>`;
        }
        actionsNode.innerHTML = actionsHtml;
    }

    function renderWorkshops() {
        if (page !== 'workshops') return;
        removeSkeletons('workshops');
        const grid = $('#workshopGrid');
        const empty = $('#workshopsEmpty');
        renderWorkshopFilters();

        const all = workshops();
        const visible = workshopFilter === 'All' ? all : all.filter((w) => w.status === workshopFilter);

        if (grid) {
            grid.innerHTML = visible.map((workshop, index) => `
                <article class="item-card workshop-card" style="--card-index: ${index}" data-open-workshop="${escapeHtml(workshop.id)}">
                    <span class="status-chip">${escapeHtml(workshop.status)}</span>
                    <h3>${escapeHtml(workshop.title)}</h3>
                    <p>${escapeHtml(workshop.description)}</p>
                    <div class="card-footer-line">
                        <span>${workshop.applicants.length} applicant${workshop.applicants.length === 1 ? '' : 's'}</span>
                    </div>
                </article>
            `).join('');
        }
        if (empty) empty.hidden = visible.length > 0;

        if (openWorkshopId) {
            const current = all.find((w) => w.id === openWorkshopId);
            if (current) renderWorkshopDetail(current);
            else closeModal('workshopDetailModal');
        }
    }
```

- [ ] **Step 9: Wire the propose-modal reset into the `data-open-modal` dispatcher**

Add `prepareNewWorkshop()` after `prepareEditEvent()` (after its closing `}`, before `const REPEAT_LABELS`):

```javascript
    function prepareNewWorkshop() {
        const form = $('#workshopProposeForm');
        if (!form) return;
        form.reset();
        setFormError('workshopProposeFormError', '');
    }
```

In `setupGlobalEvents()`'s `[data-open-modal]` branch (line 1635-1645), add a line for `workshopProposeModal`:

```javascript
            const openTrigger = event.target.closest('[data-open-modal]');
            if (openTrigger) {
                const modalId = openTrigger.dataset.openModal;
                if (modalId === 'memberModal') prepareNewMember();
                if (modalId === 'eventModal') prepareNewEvent();
                if (modalId === 'dispatchModal') prepareNewDispatch();
                if (modalId === 'projectModal') prepareNewProject();
                if (modalId === 'channelModal') prepareNewChannel();
                if (modalId === 'workshopProposeModal') prepareNewWorkshop();
                openModal(modalId);
                return;
            }
```

- [ ] **Step 10: Add the delegated click handlers**

In the same click listener, add these branches right after the existing `[data-shop-filter]` branch (after line 1764, before `[data-add-cart]`):

```javascript
            const workshopFilterChip = event.target.closest('[data-workshop-filter]');
            if (workshopFilterChip) {
                workshopFilter = workshopFilterChip.dataset.workshopFilter;
                renderWorkshops();
                return;
            }

            const openWorkshop = event.target.closest('[data-open-workshop]');
            if (openWorkshop) {
                openWorkshopId = openWorkshop.dataset.openWorkshop;
                const workshop = workshops().find((w) => w.id === openWorkshopId);
                if (!workshop) return;
                renderWorkshopDetail(workshop);
                openModal('workshopDetailModal');
                return;
            }

            const applyWorkshop = event.target.closest('[data-apply-workshop]');
            if (applyWorkshop) {
                try {
                    await apiRequest(`/api/dashboard/workshops/${applyWorkshop.dataset.applyWorkshop}`, {
                        method: 'PATCH',
                        body: { applying: true },
                    });
                    showToast('Applied to run this workshop.');
                } catch (error) {
                    showToast(error.message, 'error');
                }
                return;
            }

            const withdrawWorkshop = event.target.closest('[data-withdraw-workshop]');
            if (withdrawWorkshop) {
                try {
                    await apiRequest(`/api/dashboard/workshops/${withdrawWorkshop.dataset.withdrawWorkshop}`, {
                        method: 'PATCH',
                        body: { applying: false },
                    });
                    showToast('Application withdrawn.');
                } catch (error) {
                    showToast(error.message, 'error');
                }
                return;
            }

            const markRunWorkshop = event.target.closest('[data-mark-run-workshop]');
            if (markRunWorkshop) {
                try {
                    await apiRequest(`/api/dashboard/workshops/${markRunWorkshop.dataset.markRunWorkshop}`, {
                        method: 'PATCH',
                        body: { status: 'Run' },
                    });
                    showToast('Workshop marked as run.');
                } catch (error) {
                    showToast(error.message, 'error');
                }
                return;
            }

            const deleteWorkshop = event.target.closest('[data-delete-workshop]');
            if (deleteWorkshop) {
                try {
                    await apiRequest(`/api/dashboard/workshops/${deleteWorkshop.dataset.deleteWorkshop}`, { method: 'DELETE' });
                    closeModal('workshopDetailModal');
                    showToast('Proposal deleted.');
                } catch (error) {
                    showToast(error.message, 'error');
                }
                return;
            }

            const scheduleWorkshopTrigger = event.target.closest('[data-schedule-workshop]');
            if (scheduleWorkshopTrigger) {
                const [workshopId, runnerEmail] = String(scheduleWorkshopTrigger.dataset.scheduleWorkshop).split('::');
                const runner = members().find((m) => m.email === runnerEmail);
                const form = $('#workshopScheduleForm');
                if (form) {
                    form.reset();
                    form.elements.workshopId.value = workshopId;
                    form.elements.runnerEmail.value = runnerEmail;
                }
                const nameLine = $('#workshopScheduleRunnerName');
                if (nameLine) nameLine.textContent = `Running: ${runner ? runner.name : runnerEmail}`;
                setFormError('workshopScheduleFormError', '');
                openModal('workshopScheduleModal');
                return;
            }
```

- [ ] **Step 11: Add the two form submit handlers**

Add near the `#eventForm` submit handler (after its `#deleteEventButton` click handler, before the checklist-recompute comment):

```javascript
        $('#workshopProposeForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const data = formObject(form);
            setFormError('workshopProposeFormError', '');
            try {
                await apiRequest('/api/dashboard/workshops', { method: 'POST', body: data });
                closeModal('workshopProposeModal');
                showToast('Workshop proposed.');
            } catch (error) {
                setFormError('workshopProposeFormError', error.message);
            }
        });

        $('#workshopScheduleForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const data = formObject(form);
            setFormError('workshopScheduleFormError', '');
            try {
                await apiRequest(`/api/dashboard/workshops/${data.workshopId}`, {
                    method: 'PATCH',
                    body: {
                        status: 'Scheduled',
                        runnerEmail: data.runnerEmail,
                        date: data.date,
                        time: data.time,
                        location: data.location,
                    },
                });
                closeModal('workshopScheduleModal');
                closeModal('workshopDetailModal');
                showToast('Workshop scheduled.');
            } catch (error) {
                setFormError('workshopScheduleFormError', error.message);
            }
        });
```

- [ ] **Step 12: Call `renderWorkshops()` from `renderPage()` and add the home stat line to `renderHome()`**

In `renderPage()`:

```javascript
    function renderPage() {
        renderHome();
        renderTeam();
        renderEvents();
        renderWorkshops();
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

In `renderHome()`, add the new stat line next to the existing ones (after `$('#homeOrderTotal').textContent = orders().length;`):

```javascript
        $('#homeOrderTotal').textContent = orders().length;
        $('#homeWorkshopTotal').textContent = workshops().filter((w) => w.status === 'Run').length;
```

- [ ] **Step 13: Write the failing template-shell tests**

Append to `tests/test_public.py`:

```python
def test_dashboard_layout_has_workshops_nav_link(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {'settings': {'clubName': 'Nav Club'}, 'members': []}
    response = auth_client.get('/dashboard')
    assert response.status_code == 200
    assert b'/dashboard/workshops' in response.data
    assert b'id="homeWorkshopTotal"' in response.data


def test_workshops_page_has_expected_shell(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {'settings': {'clubName': 'Nav Club'}, 'members': [], 'workshops': []}
    response = auth_client.get('/dashboard/workshops')
    assert response.status_code == 200
    assert b'id="workshopGrid"' in response.data
    assert b'id="workshopProposeModal"' in response.data
    assert b'id="workshopDetailModal"' in response.data
    assert b'id="workshopScheduleModal"' in response.data
```

- [ ] **Step 14: Run tests to verify pass/fail**

Run: `pytest tests/test_public.py -v -k "workshops"`
Expected: both PASS (pure template-rendering assertions — verification, not a red/green cycle, matching the Coins Spine plan's equivalent step)

- [ ] **Step 15: Manual browser verification**

There is no JS test runner in this repo. Verify by hand:

```bash
python app.py
```

1. Sign in (or use playtest mode if `PLAYTEST_ENABLED` is set), open `/dashboard` — confirm a "workshops run" sticker renders in the home stat row (0 for a fresh club).
2. Open `/dashboard/workshops` — confirm the sidebar nav highlights, filter chips render (All/Proposed/Scheduled/Run), "Propose a workshop" opens a modal, and submitting title+description adds a card to the grid.
3. As a second member (or by editing the seeded session in playtest), apply to run the proposed workshop — confirm the applicant count updates.
4. As a leader, open the workshop's detail modal — confirm the applicant list shows with a "Schedule" button, clicking it opens the schedule modal, and submitting date/time/location flips the workshop to Scheduled and creates a matching entry on `/dashboard/events`.
5. As a leader on a Scheduled workshop, confirm "Mark as run" flips it to Run and the home page's "workshops run" count increments.
6. Open dark mode — confirm the new sticker and workshop cards are legible against the dark background.

- [ ] **Step 16: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 17: Commit**

```bash
git add templates/dashboard_layout.html templates/partials/icons.html templates/dashboard/workshops.html templates/dashboard.html src/routes_web.py static/css/dashboard.css static/js/dashboard.js tests/test_public.py
git commit -m "feat: add workshops nav, page, modals, and home stat tile"
```

---

### Task 6: i18n keys for the workshops UI

**Files:**
- Modify: `static/js/i18n-data.js` (new keys in the `en` block)
- Regenerate: `static/js/i18n/en.js` and the other 11 language files (via script, not by hand)

**Interfaces:**
- Consumes: nothing.
- Produces: `side.workshops`, `workshops.subtitle`, `workshops.propose`, `workshops.proposeTitle`, `workshops.catalogTitle`, `workshops.catalogDesc`, `workshops.titleLabel`, `workshops.descriptionLabel`, `workshops.submitProposal`, `workshops.cancel`, `workshops.filterAria`, `workshops.emptyTitle`, `workshops.emptyDesc`, `workshops.scheduleTitle`, `workshops.dateLabel`, `workshops.timeLabel`, `workshops.locationLabel`, `workshops.confirmSchedule`, `home.workshopsRun` all exist in the `en` block. English is the fallback table `i18n.js` reads for any key missing from a non-English language (per `scripts/split_i18n_data.py`'s own docstring), so these don't need to exist in the other 11 blocks.

- [ ] **Step 1: Add the new keys to the `en` block**

In `static/js/i18n-data.js`, inside the `en:` block, add near the other `side.*` keys (next to `'side.shop'`):

```javascript
            'side.workshops': 'Workshops',
```

Add near the other `shop.*`/`events.*` keys (a new block, placed after the last `shop.*` key):

```javascript
            'workshops.subtitle': 'Propose a topic, or apply to run one someone else suggested.',
            'workshops.propose': 'Propose a workshop',
            'workshops.proposeTitle': 'Propose a workshop',
            'workshops.catalogTitle': 'Workshop board',
            'workshops.catalogDesc': "Propose a topic for your club, or apply to run one that's open.",
            'workshops.titleLabel': 'Title',
            'workshops.descriptionLabel': 'Description',
            'workshops.submitProposal': 'Submit proposal',
            'workshops.cancel': 'Cancel',
            'workshops.filterAria': 'Filter workshops',
            'workshops.emptyTitle': 'No workshops yet',
            'workshops.emptyDesc': 'Be the first to propose one for your club.',
            'workshops.scheduleTitle': 'Schedule this workshop',
            'workshops.dateLabel': 'Date',
            'workshops.timeLabel': 'Time',
            'workshops.locationLabel': 'Location',
            'workshops.confirmSchedule': 'Confirm schedule',
```

Add near the other `home.*` keys:

```javascript
            'home.workshopsRun': 'workshops run',
```

- [ ] **Step 2: Regenerate the per-language files**

```bash
python scripts/split_i18n_data.py
```

Expected output: confirms it wrote `static/js/i18n-langs.js` and 12 files under `static/js/i18n/`.

- [ ] **Step 3: Verify the regenerated English file**

```bash
grep -n "side.workshops\|workshops.propose\|home.workshopsRun" static/js/i18n/en.js
```

Expected: `'side.workshops': 'Workshops',`, `'workshops.propose': 'Propose a workshop',`, `'home.workshopsRun': 'workshops run',` all present.

- [ ] **Step 4: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add static/js/i18n-data.js static/js/i18n-langs.js static/js/i18n/
git commit -m "feat: add workshops i18n keys"
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
Expected: same 1 pre-existing error as the repo's baseline (`tests/test_public.py` B905 `zip()` without `strict=`) — confirm no new errors were introduced by this feature's files.

- [ ] **Step 3: Run ruff format check**

Run: `ruff format --check .`
Expected: same pre-existing set of unformatted files as the repo's baseline — if any *new* file this plan touched needs reformatting, run `ruff format <path>` on just that file and re-verify, then commit separately: `git add -u && git commit -m "style: ruff format"`.

- [ ] **Step 4: Run mypy strict across the whole `src/` tree**

Run: `mypy src/ --strict`
Expected: error count equal to the pre-Workshops baseline (verify against a fresh clone/stash of the commit before Task 1, or by diffing per-file counts the way each task's own mypy step already tracked them) — `src/helpers.py` and `src/routes_api.py` should show **zero** new errors (both fully annotated additions there); `src/storage.py`/`src/storage_mongo.py` unchanged from their baseline; `src/notifications.py`/`src/email.py` may show a few more `no-untyped-def` instances than baseline, all matching the pre-existing unannotated style already present in those two files (not a new error *category*).

- [ ] **Step 5: Confirm the five-place registration is complete**

```bash
pytest tests/test_coins.py -v -k "state_section or mongo_collection"
pytest tests/test_workshops.py -v -k "registered_everywhere"
```

Expected: all pass — `workshops` has an `AirtableStorage.CHILD_TABLES` entry, a `storage_mongo.CHILD_COLLECTIONS` entry, and an `INDEXES` entry.

- [ ] **Step 6: Confirm i18n keys landed correctly**

```bash
grep -c "'side.workshops': 'Workshops'," static/js/i18n/en.js
grep -c "'side.workshops'" static/js/i18n/es.js
```

Expected: `1` for both — the key exists in the generated English file, and (per this repo's fallback mechanism) doesn't need to exist in `es.js` for the UI to still show correct English text there.

- [ ] **Step 7: Manual smoke test of the full propose → apply → schedule → run flow**

```bash
python app.py
```

Walk through, as two different accounts (or by editing session state directly), the complete lifecycle: propose a workshop → apply as a second member → approve/schedule as a leader (confirm it appears on `/dashboard/events`) → mark it run → confirm the home page's "workshops run" stat incremented by exactly 1. Confirm a `DELETE` attempt on a `Scheduled` workshop is rejected (400), and that deleting a still-`Proposed` one succeeds.
