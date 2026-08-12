# Settings Page Redesign (Round 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `/dashboard/settings` as a single scrolling page with a sidebar of anchor links (scrollspy) covering Club profile, Members, Your account, Appearance, Explore & privacy, Notifications, and Danger zone — each section either fully working or an honest stub, per `docs/superpowers/specs/2026-08-12-settings-page-design.md`.

**Architecture:** Server-rendered single template (`templates/dashboard/settings.html`) with one `<form>` per section that has its own Save button, same pattern as today. A small vanilla-JS `IntersectionObserver` drives the sidebar scrollspy — no new client-side state machine. Club profile's address fields replace the old free-text `location` field as the source of truth; `location` becomes a derived `"city, state"` string recomputed on every settings save, so the two existing display sites that read it (`templates/dashboard/admin.html:161`, `static/js/dashboard.js` `homeClubMeta`/`clubPreviewLocation`) keep working unchanged. "Sign out everywhere" is real and gated by `shared_backend` (`not isinstance(_storage(), SessionStorage)`), backed by a new cross-club `Users` record (`preferredName`, `sessionVersion`) on the Airtable and Mongo backends only.

**Tech Stack:** Flask 3 + Jinja2, vanilla JS (`static/js/dashboard.js`), pytest, Airtable REST backend (`src/storage.py`), MongoDB backend (`src/storage_mongo.py`), Flask signed-cookie sessions.

## Global Constraints

- No placeholders, TBDs, or fabricated data — every stub row renders literal "Not available yet" copy, never invented values (spec §3).
- `location` must keep working for existing consumers (`admin.html:161`, `dashboard.js` `homeClubMeta`/`clubPreviewLocation`) — it becomes derived, not removed.
- "Build sandbox" is dropped entirely — do not add it anywhere (spec, Context).
- "Sign out everywhere" and the cross-club `Users` record are **not** implemented on `SessionStorage` — that backend has no concept of other devices, and the feature is UI-gated off for it (spec §7).
- New markup follows the existing `data-i18n` / `data-i18n-attr` pattern used throughout `templates/dashboard/*.html` for any user-facing copy that has a matching pattern already in the template (existing sections do; new stub copy may ship English-only since no i18n keys exist for it yet — do not invent i18n keys not requested).
- CSRF: every mutating endpoint calls `require_dashboard_csrf()` first, matching every existing `/api/dashboard/*` PATCH/POST route.
- Leader-only mutations call `require_leader_api()`, matching `api_settings_update`.
- Commit after every task's tests pass, following this repo's existing commit style (`feat:`, `fix:` prefixes, no `Co-Authored-By` trailer per project CLAUDE.md).

---

## File Structure

| File | Responsibility |
|---|---|
| `src/helpers.py` | `Settings` TypedDict (add new club-profile fields), `default_dashboard_state()`/`playtest_state()` defaults |
| `src/storage.py` | `SETTINGS_FIELDS` (Airtable field mapping), new `Users` table config + `get_user_record`/`save_user_record` on `AirtableStorage`, `StorageError` reuse |
| `src/storage_mongo.py` | New `users` collection + index, `get_user_record`/`save_user_record` on `MongoStorage` |
| `src/routes_club.py` | `api_settings_update` (new fields + derived `location`), new `api_account_preferred_name_update`, new `api_account_sign_out_everywhere` |
| `src/routes_admin.py` | `api_admin_club_update` — parity for new fields |
| `src/routes_auth.py` | `hackclub_callback`, `playtest_login` — stamp `sessionVersion` into `session['user']` |
| `src/routes_web.py` | `require_club_membership` `before_request` — add session-version staleness check; `dashboard_settings` — pass `shared_backend` |
| `templates/dashboard/settings.html` | Full rebuild: scrollspy shell + all 7 sections |
| `static/css/dashboard.css` | New `.settings-shell`, `.settings-nav`, `.settings-section`, stub-row classes |
| `static/js/dashboard.js` | Scrollspy init, Your-account/Danger-zone form handlers |
| `tests/test_api.py` | Settings field coverage, derived `location`, preferred-name round-trip |
| `tests/test_auth.py` | Session-version stamping on login |
| `tests/test_storage_mongo.py` | `get_user_record`/`save_user_record` on Mongo |
| `tests/test_storage_airtable.py` (new) | `get_user_record`/`save_user_record` on Airtable, missing-table degradation |

---

### Task 1: Club profile data model — structured address + derived `location`

**Files:**
- Modify: `src/helpers.py:153-166` (`Settings` TypedDict), `src/helpers.py:596-610` (`default_dashboard_state` settings dict), `src/helpers.py:626-640` (`playtest_state` settings dict)
- Modify: `src/storage.py:144-156` (`SETTINGS_FIELDS`)
- Modify: `src/routes_club.py:100-140` (`api_settings_update`)
- Modify: `src/routes_admin.py:70-103` (`api_admin_club_update`)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: existing `clean_text()`, `parse_bool()`, `parse_language()`, `json_error()` from `src/helpers.py`.
- Produces: `Settings` TypedDict gains `venue: str`, `addressLine1: str`, `addressLine2: str`, `city: str`, `state: str`, `zip: str`, `country: str`, `meetingDay: str`, `clubBio: str`. `location: str` stays in the TypedDict (derived, not user-editable) and is recomputed by `api_settings_update`/`api_admin_club_update` as `", ".join(filter(None, [city, state]))`. Later tasks (Members, Your account, Danger zone) do not touch these fields.

- [ ] **Step 1: Write the failing test for the new fields + derived `location`**

```python
# tests/test_api.py — add at end of file

def _save_settings_v2(auth_client, monkeypatch, **overrides):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrf-token'
        sess.setdefault(
            'dashboard_state',
            {'settings': {'clubName': 'Test Club', 'location': 'Testville'}, 'members': []},
        )
    payload = {
        'clubName': 'Test Club',
        'venue': 'Lincoln High School',
        'website': '',
        'avatar': '',
        'meetingDay': 'Wednesday',
        'addressLine1': '100 Main St',
        'addressLine2': '',
        'city': 'Burlington',
        'state': 'VT',
        'zip': '05401',
        'country': 'US',
        'clubBio': 'We build cool stuff.',
    }
    payload.update(overrides)
    return auth_client.patch(
        '/api/dashboard/settings', json=payload, headers={'X-CSRF-Token': 'test-csrf-token'}
    )


def test_settings_saves_structured_address_fields(auth_client, monkeypatch):
    response = _save_settings_v2(auth_client, monkeypatch)
    assert response.status_code == 200
    settings = response.get_json()['state']['settings']
    assert settings['venue'] == 'Lincoln High School'
    assert settings['meetingDay'] == 'Wednesday'
    assert settings['addressLine1'] == '100 Main St'
    assert settings['city'] == 'Burlington'
    assert settings['state'] == 'VT'
    assert settings['zip'] == '05401'
    assert settings['country'] == 'US'
    assert settings['clubBio'] == 'We build cool stuff.'


def test_settings_derives_location_from_city_state(auth_client, monkeypatch):
    response = _save_settings_v2(auth_client, monkeypatch, city='Burlington', state='VT')
    assert response.status_code == 200
    assert response.get_json()['state']['settings']['location'] == 'Burlington, VT'


def test_settings_derives_location_with_only_city(auth_client, monkeypatch):
    response = _save_settings_v2(auth_client, monkeypatch, city='Burlington', state='')
    assert response.status_code == 200
    assert response.get_json()['state']['settings']['location'] == 'Burlington'


def test_settings_derives_empty_location_when_no_address(auth_client, monkeypatch):
    response = _save_settings_v2(auth_client, monkeypatch, city='', state='')
    assert response.status_code == 200
    assert response.get_json()['state']['settings']['location'] == ''
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_api.py -k structured_address or derives_location -v`
Expected: FAIL — `KeyError: 'venue'` (field not yet saved/returned).

- [ ] **Step 3: Implement — `helpers.py` Settings TypedDict**

```python
# src/helpers.py:153-166 — replace the Settings class
class Settings(TypedDict):
    joinCode: str
    clubName: str
    venue: str
    location: str
    addressLine1: str
    addressLine2: str
    city: str
    state: str
    zip: str
    country: str
    meetingDay: str
    clubBio: str
    website: str
    avatar: str
    publicDirectory: bool
    emailNotifications: bool
    darkModeDefault: bool
    newsletterSubscribed: bool
    language: str
    coinBalance: int
    coinsSpent: int
```

```python
# src/helpers.py — inside default_dashboard_state()'s settings dict (was lines 597-610),
# add the new keys right after 'clubName':
        'settings': {
            'joinCode': generate_join_code(),
            'clubName': f"{leader_name}'s Hack Club",
            'venue': '',
            'location': '',
            'addressLine1': '',
            'addressLine2': '',
            'city': '',
            'state': '',
            'zip': '',
            'country': '',
            'meetingDay': '',
            'clubBio': '',
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
```

```python
# src/helpers.py — inside playtest_state()'s settings dict (was lines 627-640),
# add the same new keys:
        'settings': {
            'joinCode': 'PLAYTEST',
            'clubName': 'Playtest Hack Club',
            'venue': 'Playtest High School',
            'location': 'Burlington, VT',
            'addressLine1': '',
            'addressLine2': '',
            'city': 'Burlington',
            'state': 'VT',
            'zip': '',
            'country': 'US',
            'meetingDay': 'Wednesday',
            'clubBio': '',
            'website': 'https://hackclub.com',
            'avatar': '',
            'publicDirectory': True,
            'emailNotifications': True,
            'darkModeDefault': False,
            'newsletterSubscribed': True,
            'language': 'en',
            'coinBalance': 0,
            'coinsSpent': 0,
        },
```

- [ ] **Step 4: Implement — `storage.py` SETTINGS_FIELDS**

```python
# src/storage.py:144-156 — replace SETTINGS_FIELDS
SETTINGS_FIELDS: Final[list[tuple[str, str]]] = [
    ('clubName', 'Club Name'),
    ('venue', 'Venue'),
    ('location', 'Location'),
    ('addressLine1', 'Address Line 1'),
    ('addressLine2', 'Address Line 2'),
    ('city', 'City'),
    ('state', 'State'),
    ('zip', 'Zip'),
    ('country', 'Country'),
    ('meetingDay', 'Meeting Day'),
    ('clubBio', 'Club Bio'),
    ('website', 'Website'),
    ('avatar', 'Avatar'),
    ('joinCode', 'Join Code'),
    ('publicDirectory', 'Public Directory'),
    ('emailNotifications', 'Email Notifications'),
    ('darkModeDefault', 'Dark Mode Default'),
    ('newsletterSubscribed', 'Newsletter Subscribed'),
    ('coinBalance', 'Coin Balance'),
    ('coinsSpent', 'Coins Spent'),
]
```

(`storage_mongo.py` needs no change here — `MongoStorage.save()` persists every key in `state['settings']` verbatim, no field-name mapping or allowlist.)

- [ ] **Step 5: Implement — `routes_club.py` `api_settings_update`**

```python
# src/routes_club.py:100-140 — replace api_settings_update
    @app.patch('/api/dashboard/settings')
    @login_required
    def api_settings_update():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        payload = json_payload()
        club_name = clean_text(payload.get('clubName'))
        venue = clean_text(payload.get('venue'), max_len=120)
        website = clean_text(payload.get('website'))
        avatar = clean_text(payload.get('avatar'))
        meeting_day = clean_text(payload.get('meetingDay'), max_len=20)
        address_line1 = clean_text(payload.get('addressLine1'), max_len=120)
        address_line2 = clean_text(payload.get('addressLine2'), max_len=120)
        city = clean_text(payload.get('city'), max_len=80)
        state_field = clean_text(payload.get('state'), max_len=80)
        zip_code = clean_text(payload.get('zip'), max_len=20)
        country = clean_text(payload.get('country'), max_len=80)
        club_bio = clean_text(payload.get('clubBio'), max_len=500)

        if not club_name:
            return json_error('Club name is required.')
        if not venue:
            return json_error('School or venue is required.')
        if website and not website.startswith(('http://', 'https://')):
            return json_error('Club website must start with http:// or https://.')
        if avatar and not avatar.startswith(('http://', 'https://')):
            return json_error('Avatar URL must start with http:// or https://.')

        location = ', '.join(filter(None, [city, state_field]))

        state = get_dashboard_state()
        state['settings'].update(
            {
                'clubName': club_name,
                'venue': venue,
                'location': location,
                'addressLine1': address_line1,
                'addressLine2': address_line2,
                'city': city,
                'state': state_field,
                'zip': zip_code,
                'country': country,
                'meetingDay': meeting_day,
                'clubBio': club_bio,
                'website': website,
                'avatar': avatar,
                'publicDirectory': parse_bool(payload.get('publicDirectory')),
                'emailNotifications': parse_bool(payload.get('emailNotifications')),
                'darkModeDefault': parse_bool(payload.get('darkModeDefault')),
                'newsletterSubscribed': parse_bool(payload.get('newsletterSubscribed')),
                'language': parse_language(payload.get('language')),
            }
        )
        save_dashboard_state(state)
        return flask.jsonify({'state': state})
```

- [ ] **Step 6: Run to verify it passes**

Run: `pytest tests/test_api.py -k structured_address or derives_location -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Update `routes_admin.py` for parity**

```python
# src/routes_admin.py:70-103 — replace api_admin_club_update body from `payload = json_payload()` onward
        payload = json_payload()
        club_name = clean_text(payload.get('clubName'))
        website = clean_text(payload.get('website'))
        avatar = clean_text(payload.get('avatar'))
        venue = clean_text(payload.get('venue'), max_len=120)
        meeting_day = clean_text(payload.get('meetingDay'), max_len=20)
        address_line1 = clean_text(payload.get('addressLine1'), max_len=120)
        address_line2 = clean_text(payload.get('addressLine2'), max_len=120)
        city = clean_text(payload.get('city'), max_len=80)
        state_field = clean_text(payload.get('state'), max_len=80)
        zip_code = clean_text(payload.get('zip'), max_len=20)
        country = clean_text(payload.get('country'), max_len=80)
        club_bio = clean_text(payload.get('clubBio'), max_len=500)
        if not club_name:
            return json_error('Club name is required.')
        if website and not website.startswith(('http://', 'https://')):
            return json_error('Club website must start with http:// or https://.')
        if avatar and not avatar.startswith(('http://', 'https://')):
            return json_error('Avatar URL must start with http:// or https://.')

        settings = state.setdefault('settings', {})
        settings['clubName'] = club_name
        settings['venue'] = venue
        settings['location'] = ', '.join(filter(None, [city, state_field]))
        settings['addressLine1'] = address_line1
        settings['addressLine2'] = address_line2
        settings['city'] = city
        settings['state'] = state_field
        settings['zip'] = zip_code
        settings['country'] = country
        settings['meetingDay'] = meeting_day
        settings['clubBio'] = club_bio
        settings['website'] = website
        settings['avatar'] = avatar
        if 'publicDirectory' in payload:
            settings['publicDirectory'] = parse_bool(payload.get('publicDirectory'))
        _persist_club(backend, club_key, state)
        return flask.jsonify({'club': state})
```

- [ ] **Step 8: Run the full test suite to check nothing else broke**

Run: `pytest tests/ -v`
Expected: PASS (all tests, including the pre-existing `test_default_state_has_language`, `test_settings_persists_supported_language`, `test_settings_rejects_unsupported_language`, which still send `clubName`/`location` — verify they still pass since `location` is no longer required-and-validated directly. Note: `_save_settings()`'s existing payload has no `venue`, so re-check it against the new required-field check.)

If the old `_save_settings()` helper (test_api.py:63-80) now fails because it doesn't send `venue`, update it in the same step:

```python
# tests/test_api.py:63-80 — add venue to the default payload
def _save_settings(auth_client, monkeypatch, **overrides):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrf-token'
        sess.setdefault(
            'dashboard_state',
            {
                'settings': {'clubName': 'Test Club', 'location': 'Testville'},
                'members': [],
            },
        )
    payload = {'clubName': 'Test Club', 'venue': 'Test Venue', 'location': 'Testville'}
    payload.update(overrides)
    return auth_client.patch(
        '/api/dashboard/settings', json=payload, headers={'X-CSRF-Token': 'test-csrf-token'}
    )
```

Run: `pytest tests/ -v`
Expected: PASS (all tests)

- [ ] **Step 9: Commit**

```bash
git add src/helpers.py src/storage.py src/routes_club.py src/routes_admin.py tests/test_api.py
git commit -m "feat: split club location into structured address fields with derived location string"
```

---

### Task 2: Settings shell — scrollspy layout + sidebar nav

**Files:**
- Modify: `templates/dashboard/settings.html` (full rewrite of the shell only — sections populated in later tasks)
- Modify: `static/css/dashboard.css:1727-1734` (`.settings-layout` → new `.settings-shell` grid), append new rules after line ~2244
- Modify: `static/js/dashboard.js` — add scrollspy init near `initAvatarUploads()` (line 872) and call it from the `settings` page init path (near line 238's `initAvatarUploads()` call and the page-specific init block — see Step 5)
- Test: manual (no JS test harness in this repo — verified via the existing pytest suite still passing and a route smoke test below)

**Interfaces:**
- Consumes: `dashboard_state.settings` (Task 1's new fields), `sidebar_icon()` macro already used in `dashboard_layout.html`.
- Produces: `#settingsShell`, `#settingsNav` (sidebar with `<a href="#club-profile">` etc.), one `<section id="...">` per settings section for Tasks 3-9 to fill in. `data-settings-section` attribute on each `<section>` for the scrollspy JS.

- [ ] **Step 1: Write the failing test — route renders the new anchors**

```python
# tests/test_api.py — append

def test_settings_page_renders_all_section_anchors(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Test Club', 'venue': 'Test Venue'},
            'members': [{'id': 'm1', 'name': 'Test Leader', 'email': 'leader@test.com', 'role': 'Leader', 'avatar': '', 'status': 'Active'}],
        }
    response = auth_client.get('/dashboard/settings')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    for anchor_id in (
        'club-profile', 'members', 'your-account', 'appearance',
        'explore-privacy', 'notifications', 'danger-zone',
    ):
        assert f'id="{anchor_id}"' in body
        assert f'href="#{anchor_id}"' in body
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_api.py -k renders_all_section_anchors -v`
Expected: FAIL — current `settings.html` has none of these anchors.

- [ ] **Step 3: Rewrite `templates/dashboard/settings.html` shell**

```html
{% extends "dashboard_layout.html" %}

{% block page_title %}<span data-i18n="settings.title">Settings</span>{% endblock %}
{% block page_subtitle %}<span data-i18n="settings.subtitle">Manage your club and account.</span>{% endblock %}

{% block content %}
{% set settings = dashboard_state.settings %}
<div class="dashboard-page settings-shell" data-dashboard-page="settings">
    <nav class="settings-nav" id="settingsNav" aria-label="Settings sections">
        <a href="#club-profile" class="settings-nav-link" data-i18n="settings.navClubProfile">Club profile</a>
        <a href="#members" class="settings-nav-link" data-i18n="settings.navMembers">Members</a>
        <a href="#your-account" class="settings-nav-link" data-i18n="settings.navYourAccount">Your account</a>
        <a href="#appearance" class="settings-nav-link" data-i18n="settings.navAppearance">Appearance</a>
        <a href="#explore-privacy" class="settings-nav-link" data-i18n="settings.navExplorePrivacy">Explore &amp; privacy</a>
        <a href="#notifications" class="settings-nav-link" data-i18n="settings.navNotifications">Notifications</a>
        <a href="#danger-zone" class="settings-nav-link settings-nav-danger" data-i18n="settings.navDangerZone">Danger zone</a>
    </nav>

    <div class="settings-sections" id="settingsSections">
        <section class="card-modern dashboard-panel settings-section" id="club-profile" data-settings-section>
            {% include "partials/settings/club_profile.html" %}
        </section>

        <section class="card-modern dashboard-panel settings-section" id="members" data-settings-section>
            {% include "partials/settings/members.html" %}
        </section>

        <section class="card-modern dashboard-panel settings-section" id="your-account" data-settings-section>
            {% include "partials/settings/your_account.html" %}
        </section>

        <section class="card-modern dashboard-panel settings-section" id="appearance" data-settings-section>
            {% include "partials/settings/appearance.html" %}
        </section>

        <section class="card-modern dashboard-panel settings-section" id="explore-privacy" data-settings-section>
            {% include "partials/settings/explore_privacy.html" %}
        </section>

        <section class="card-modern dashboard-panel settings-section" id="notifications" data-settings-section>
            {% include "partials/settings/notifications.html" %}
        </section>

        <section class="card-modern dashboard-panel settings-section" id="danger-zone" data-settings-section>
            {% include "partials/settings/danger_zone.html" %}
        </section>
    </div>
</div>
{% endblock %}
```

Create the seven partials referenced above as empty placeholders **for this task only** (each filled in by its own later task) so the route renders without a `TemplateNotFound` error:

```html
<!-- templates/partials/settings/club_profile.html -->
<h2 data-i18n="settings.clubProfile">Club profile</h2>
```

```html
<!-- templates/partials/settings/members.html -->
<h2 data-i18n="settings.members">Members</h2>
```

```html
<!-- templates/partials/settings/your_account.html -->
<h2 data-i18n="settings.yourAccount">Your account</h2>
```

```html
<!-- templates/partials/settings/appearance.html -->
<h2 data-i18n="settings.appearance">Appearance</h2>
```

```html
<!-- templates/partials/settings/explore_privacy.html -->
<h2 data-i18n="settings.explorePrivacy">Explore &amp; privacy</h2>
```

```html
<!-- templates/partials/settings/notifications.html -->
<h2 data-i18n="settings.notifications">Notifications</h2>
```

```html
<!-- templates/partials/settings/danger_zone.html -->
<h2 data-i18n="settings.dangerZone">Danger zone</h2>
```

(Note: each placeholder's `<h2>` already satisfies its section's own `id`/`href` pair via the parent `<section id="...">` wrapper in the shell above — the test only checks for `id="club-profile"` etc. on the section, which is already present.)

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_api.py -k renders_all_section_anchors -v`
Expected: PASS

- [ ] **Step 5: CSS — shell grid + nav**

```css
/* static/css/dashboard.css — replace .settings-layout rule at line 1731 with: */
.settings-shell {
    display: grid;
    grid-template-columns: 220px minmax(0, 1fr);
    gap: 28px;
    align-items: start;
}

.settings-nav {
    position: sticky;
    top: 104px;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.settings-nav-link {
    padding: 10px 14px;
    border-radius: 10px;
    font-size: 14px;
    font-weight: bold;
    color: var(--dash-slate);
    text-decoration: none;
    transition: background 0.15s ease, color 0.15s ease;
}

.settings-nav-link:hover {
    background: var(--dash-fill);
}

.settings-nav-link.active {
    background: var(--hackclub-red);
    color: #fff;
}

.settings-nav-danger.active {
    background: #a8122a;
}

.settings-sections {
    display: flex;
    flex-direction: column;
    gap: 24px;
    min-width: 0;
}

.settings-section {
    scroll-margin-top: 96px;
}

@media (max-width: 900px) {
    .settings-shell {
        grid-template-columns: 1fr;
    }

    .settings-nav {
        position: static;
        flex-direction: row;
        flex-wrap: wrap;
        top: auto;
    }
}
```

Also update the responsive block that currently references `.settings-layout` (`static/css/dashboard.css:3002-3017`) to reference `.settings-shell`/`.settings-section` instead — remove the now-dead `.settings-main`/`.settings-side` rules that only `profile.html` still uses (leave `.settings-layout`, `.settings-main`, `.settings-side` in place since `templates/dashboard/profile.html` still extends that layout unchanged).

- [ ] **Step 6: JS — scrollspy**

```javascript
// static/js/dashboard.js — add after initAvatarUploads() (after line ~950, its closing brace)

    function initSettingsScrollspy() {
        const nav = $('#settingsNav');
        const sections = document.querySelectorAll('[data-settings-section]');
        if (!nav || !sections.length || !window.IntersectionObserver) return;

        const links = new Map();
        nav.querySelectorAll('.settings-nav-link').forEach((link) => {
            links.set(link.getAttribute('href').slice(1), link);
        });

        const setActive = (id) => {
            links.forEach((link, sectionId) => {
                link.classList.toggle('active', sectionId === id);
            });
        };

        const observer = new IntersectionObserver(
            (entries) => {
                const visible = entries
                    .filter((entry) => entry.isIntersecting)
                    .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
                if (visible.length) setActive(visible[0].target.id);
            },
            { rootMargin: '-96px 0px -60% 0px', threshold: 0.01 }
        );
        sections.forEach((section) => observer.observe(section));

        nav.querySelectorAll('.settings-nav-link').forEach((link) => {
            link.addEventListener('click', (event) => {
                event.preventDefault();
                const target = document.getElementById(link.getAttribute('href').slice(1));
                if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        });
    }
```

Call it from the page-init path — find the block in `static/js/dashboard.js` that calls `initAvatarUploads()` once at startup (around line 238's `setState` isn't it; find the one-time init sequence — grep shows another `initAvatarUploads()` call near line 3118, which is inside the DOMContentLoaded/init bootstrap). Add the call right after that line:

```javascript
// static/js/dashboard.js — near line 3118, right after the existing initAvatarUploads() call
        initAvatarUploads();
        initSettingsScrollspy();
```

- [ ] **Step 7: Run full suite**

Run: `pytest tests/ -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add templates/dashboard/settings.html templates/partials/settings/ static/css/dashboard.css static/js/dashboard.js tests/test_api.py
git commit -m "feat: rebuild settings page as single-scroll shell with scrollspy sidebar"
```

---

### Task 3: Club profile section (fully built)

**Files:**
- Modify: `templates/partials/settings/club_profile.html` (replace placeholder)
- Test: `tests/test_api.py` (extends Task 1's tests — no new backend logic, this is markup only)

**Interfaces:**
- Consumes: `settings` (Jinja local set in `settings.html`, from `dashboard_state.settings`), Task 1's new field names, the existing generic `input[name="avatar"]` auto-upload wiring (`initAvatarUploads()` — no JS changes needed here).
- Produces: `#settingsForm` (same id as before, so no JS handler changes needed — `static/js/dashboard.js`'s existing `$('#settingsForm')` submit/input listeners at lines 2747-2780 keep working as-is since `formObject()` just serializes whatever fields exist in the form).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api.py — append

def test_club_profile_section_renders_new_fields(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {
            'settings': {
                'clubName': 'Test Club', 'venue': 'Test High', 'meetingDay': 'Wednesday',
                'addressLine1': '1 Main St', 'addressLine2': '', 'city': 'Burlington',
                'state': 'VT', 'zip': '05401', 'country': 'US', 'clubBio': 'We build stuff.',
                'website': '', 'avatar': '',
            },
            'members': [{'id': 'm1', 'name': 'Test Leader', 'email': 'leader@test.com', 'role': 'Leader', 'avatar': '', 'status': 'Active'}],
        }
    response = auth_client.get('/dashboard/settings')
    body = response.get_data(as_text=True)
    for field_name in ('venue', 'meetingDay', 'addressLine1', 'addressLine2', 'city', 'state', 'zip', 'country', 'clubBio'):
        assert f'name="{field_name}"' in body
    assert 'value="Test High"' in body
    assert 'We build stuff.' in body
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_api.py -k club_profile_section_renders_new_fields -v`
Expected: FAIL — placeholder partial has none of these fields.

- [ ] **Step 3: Implement the partial**

```html
<!-- templates/partials/settings/club_profile.html -->
<div class="panel-heading">
    <div>
        <h2 data-i18n="settings.clubProfile">Club profile</h2>
        <p data-i18n="settings.clubProfileDesc">These details show up on your club's public page and the Hack Club map.</p>
    </div>
</div>

<form class="settings-form" id="settingsForm">
    <div class="avatar-upload-row">
        <div class="club-preview-avatar" id="clubPreviewAvatar">
            {% if settings.avatar %}<img src="{{ settings.avatar }}" alt="">{% endif %}
        </div>
        <label class="form-group">
            <span class="form-label" data-i18n="settings.avatar">Club logo</span>
            <input type="text" class="form-input" name="avatar" value="{{ settings.avatar }}" hidden>
            <span class="avatar-upload-status" data-i18n="settings.avatarUploadHint">Click the logo to upload a new one.</span>
        </label>
    </div>

    <label class="form-group">
        <span class="form-label" data-i18n="settings.clubName">Club name</span>
        <input type="text" class="form-input" name="clubName" value="{{ settings.clubName }}" required>
    </label>
    <label class="form-group">
        <span class="form-label" data-i18n="settings.venue">School / venue</span>
        <input type="text" class="form-input" name="venue" value="{{ settings.venue }}" required>
    </label>
    <label class="form-group">
        <span class="form-label" data-i18n="settings.website">Club website</span>
        <input type="url" class="form-input" name="website" value="{{ settings.website }}"
            placeholder="https://..." data-i18n-attr="placeholder:common.urlPlaceholder">
    </label>
    <label class="form-group">
        <span class="form-label" data-i18n="settings.meetingDay">Meeting day</span>
        <input type="text" class="form-input" name="meetingDay" value="{{ settings.meetingDay }}"
            data-i18n-attr="placeholder:settings.meetingDayPlaceholder" placeholder="e.g. Wednesday">
    </label>

    <label class="form-group">
        <span class="form-label" data-i18n="settings.addressLine1">Address line 1</span>
        <input type="text" class="form-input" name="addressLine1" value="{{ settings.addressLine1 }}">
    </label>
    <label class="form-group">
        <span class="form-label" data-i18n="settings.addressLine2">Address line 2</span>
        <input type="text" class="form-input" name="addressLine2" value="{{ settings.addressLine2 }}">
    </label>
    <div class="form-row">
        <label class="form-group">
            <span class="form-label" data-i18n="settings.city">City</span>
            <input type="text" class="form-input" name="city" value="{{ settings.city }}">
        </label>
        <label class="form-group">
            <span class="form-label" data-i18n="settings.state">State</span>
            <input type="text" class="form-input" name="state" value="{{ settings.state }}">
        </label>
    </div>
    <div class="form-row">
        <label class="form-group">
            <span class="form-label" data-i18n="settings.zip">ZIP</span>
            <input type="text" class="form-input" name="zip" value="{{ settings.zip }}">
        </label>
        <label class="form-group">
            <span class="form-label" data-i18n="settings.country">Country</span>
            <select class="form-input" name="country">
                {% for code, label in [('US', 'United States'), ('CA', 'Canada'), ('GB', 'United Kingdom'), ('AU', 'Australia'), ('other', 'Other')] %}
                <option value="{{ code }}" {% if settings.country == code %}selected{% endif %}>{{ label }}</option>
                {% endfor %}
            </select>
        </label>
    </div>

    <label class="form-group">
        <span class="form-label" data-i18n="settings.clubBio">Short bio</span>
        <textarea class="form-input" name="clubBio" rows="3"
            data-i18n-attr="placeholder:settings.clubBioPlaceholder" placeholder="A line or two about your club...">{{ settings.clubBio }}</textarea>
    </label>

    <input type="hidden" name="language" value="{{ settings.language|default('en') }}">
    <p class="form-error" id="settingsFormError" hidden></p>
    <div class="form-actions">
        <button type="submit" class="btn-primary" data-i18n="settings.save">Save changes</button>
        <span class="save-state" id="settingsSaveState" aria-live="polite"></span>
    </div>
</form>
```

Note: the club-name-initial fallback avatar (`avatar.textContent = initials(...)` in `renderSettings()`, `static/js/dashboard.js:1746-1758`) still applies — the `<div id="clubPreviewAvatar">` markup above matches what `renderSettings()` expects to find and mutate (`textContent`/`style.backgroundImage`/`classList`), so no JS change is needed there either.

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_api.py -k club_profile_section_renders_new_fields -v`
Expected: PASS

- [ ] **Step 5: Run full suite**

Run: `pytest tests/ -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add templates/partials/settings/club_profile.html tests/test_api.py
git commit -m "feat: build out Club profile settings section with structured address fields"
```

---

### Task 4: Members section (join code reuse + pending-requests stub)

**Files:**
- Modify: `templates/partials/settings/members.html` (replace placeholder)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: existing `#joinLinkCode`/`#copyJoinLink`/`#refreshJoinLink` JS handlers already wired in `static/js/dashboard.js:2664-2685` and `renderJoinLink()` (line 1189) — reusing the exact ids from `templates/dashboard/team.html:53-61` means zero JS changes.
- Produces: nothing new consumed by later tasks.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api.py — append

def test_members_section_renders_join_link_card_and_stub(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Test Club', 'venue': 'Test High'},
            'members': [{'id': 'm1', 'name': 'Test Leader', 'email': 'leader@test.com', 'role': 'Leader', 'avatar': '', 'status': 'Active'}],
        }
    response = auth_client.get('/dashboard/settings')
    body = response.get_data(as_text=True)
    assert 'id="joinLinkCode"' in body
    assert 'id="copyJoinLink"' in body
    assert 'id="refreshJoinLink"' in body
    assert 'No pending join requests' in body
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_api.py -k members_section_renders_join_link_card_and_stub -v`
Expected: FAIL

- [ ] **Step 3: Implement the partial**

```html
<!-- templates/partials/settings/members.html -->
<div class="panel-heading">
    <div>
        <h2 data-i18n="settings.members">Members</h2>
        <p data-i18n="settings.membersDesc">Invite people to your club and review who's waiting to join.</p>
    </div>
</div>

<div class="join-link-row">
    <code class="join-link-code" id="joinLinkCode"><span data-i18n="team.joinLinkPlaceholder">leaders.example/join/…</span></code>
    <button class="btn-secondary small" type="button" id="copyJoinLink">
        <span data-hc-icon="copy" data-hc-size="16" data-hc-color="currentColor" aria-hidden="true"></span> <span data-i18n="team.copyLink">Copy link</span>
    </button>
    <button class="btn-secondary small" type="button" id="refreshJoinLink">
        <span data-hc-icon="view-reload" data-hc-size="16" data-hc-color="currentColor" aria-hidden="true"></span> <span data-i18n="team.refreshLink">Refresh link</span>
    </button>
</div>

<div class="settings-stub-block">
    <h3 data-i18n="settings.pendingRequests">Pending join requests</h3>
    <p class="settings-stub-note" data-i18n="settings.pendingRequestsEmpty">No pending join requests right now.</p>
</div>
```

Add the stub styling once, reused by every stub section in Tasks 4/7:

```css
/* static/css/dashboard.css — append after the settings block */
.settings-stub-block {
    margin-top: 20px;
    padding-top: 20px;
    border-top: 1px solid var(--dash-border);
}

.settings-stub-block h3 {
    margin: 0 0 6px;
    font-size: 15px;
}

.settings-stub-note {
    margin: 0;
    color: var(--dash-muted);
    font-size: 14px;
}

.settings-stub-row {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid var(--dash-border);
}

.settings-stub-row:last-child {
    border-bottom: none;
}

.settings-stub-row-label {
    font-weight: bold;
    color: var(--dash-slate);
}

.settings-stub-row-value {
    color: var(--dash-muted);
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_api.py -k members_section_renders_join_link_card_and_stub -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add templates/partials/settings/members.html static/css/dashboard.css tests/test_api.py
git commit -m "feat: build out Members settings section reusing join-link card"
```

---

### Task 5: Appearance / Explore & privacy / Notifications (toggle relocation)

**Files:**
- Modify: `templates/partials/settings/appearance.html`, `templates/partials/settings/explore_privacy.html`, `templates/partials/settings/notifications.html` (replace placeholders)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `settings.darkModeDefault`, `settings.publicDirectory`, `settings.emailNotifications`, `settings.newsletterSubscribed` (all pre-existing fields, untouched by Task 1). Every `<input type="checkbox">` keeps `form="settingsForm"` so the existing single `#settingsForm` submit handler (`static/js/dashboard.js:2756-2780`) saves them together with Club profile — matching current behavior exactly.
- Produces: nothing new.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api.py — append

def test_appearance_privacy_notifications_sections_render_toggles(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {
            'settings': {
                'clubName': 'Test Club', 'venue': 'Test High',
                'darkModeDefault': True, 'publicDirectory': False,
                'emailNotifications': True, 'newsletterSubscribed': False,
            },
            'members': [{'id': 'm1', 'name': 'Test Leader', 'email': 'leader@test.com', 'role': 'Leader', 'avatar': '', 'status': 'Active'}],
        }
    response = auth_client.get('/dashboard/settings')
    body = response.get_data(as_text=True)
    assert 'name="darkModeDefault"' in body and 'form="settingsForm"' in body
    assert 'name="publicDirectory"' in body
    assert 'name="emailNotifications"' in body
    assert 'name="newsletterSubscribed"' in body
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_api.py -k appearance_privacy_notifications_sections_render_toggles -v`
Expected: FAIL

- [ ] **Step 3: Implement the three partials**

```html
<!-- templates/partials/settings/appearance.html -->
<div class="panel-heading">
    <div>
        <h2 data-i18n="settings.appearance">Appearance</h2>
        <p data-i18n="settings.appearanceDesc">Choose how the dashboard looks when you sign in.</p>
    </div>
</div>
<label class="toggle-row">
    <span>
        <strong data-i18n="settings.darkMode">Dark mode default</strong>
        <small data-i18n="settings.darkModeDesc">Load this dashboard in the dark theme.</small>
    </span>
    <span class="toggle-switch">
        <input type="checkbox" name="darkModeDefault" form="settingsForm" {% if settings.darkModeDefault %}checked{% endif %}>
        <span class="toggle-slider"></span>
    </span>
</label>
```

```html
<!-- templates/partials/settings/explore_privacy.html -->
<div class="panel-heading">
    <div>
        <h2 data-i18n="settings.explorePrivacy">Explore &amp; privacy</h2>
        <p data-i18n="settings.explorePrivacyDesc">Control what other Hack Clubbers can see about your club.</p>
    </div>
</div>
<label class="toggle-row">
    <span>
        <strong data-i18n="settings.publicDirectory">Public directory</strong>
        <small data-i18n="settings.publicDirectoryDesc">Show the club on the Hack Club map.</small>
    </span>
    <span class="toggle-switch">
        <input type="checkbox" name="publicDirectory" form="settingsForm" {% if settings.publicDirectory %}checked{% endif %}>
        <span class="toggle-slider"></span>
    </span>
</label>
```

```html
<!-- templates/partials/settings/notifications.html -->
<div class="panel-heading">
    <div>
        <h2 data-i18n="settings.notifications">Notifications</h2>
        <p data-i18n="settings.notificationsDesc">Choose what you hear about.</p>
    </div>
</div>
<label class="toggle-row">
    <span>
        <strong data-i18n="settings.emailNotifications">Email notifications</strong>
        <small data-i18n="settings.emailNotificationsDesc">Receive HQ dispatches and reminders.</small>
    </span>
    <span class="toggle-switch">
        <input type="checkbox" name="emailNotifications" form="settingsForm" {% if settings.emailNotifications %}checked{% endif %}>
        <span class="toggle-slider"></span>
    </span>
</label>
<label class="toggle-row">
    <span>
        <strong data-i18n="settings.newsletter">Newsletter subscription</strong>
        <small data-i18n="settings.newsletterDesc">Keep leader dispatches enabled.</small>
    </span>
    <span class="toggle-switch">
        <input type="checkbox" name="newsletterSubscribed" form="settingsForm" {% if settings.newsletterSubscribed %}checked{% endif %}>
        <span class="toggle-slider"></span>
    </span>
</label>
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_api.py -k appearance_privacy_notifications_sections_render_toggles -v`
Expected: PASS

- [ ] **Step 5: Run full suite, then commit**

Run: `pytest tests/ -v` — Expected: PASS

```bash
git add templates/partials/settings/appearance.html templates/partials/settings/explore_privacy.html templates/partials/settings/notifications.html tests/test_api.py
git commit -m "feat: relocate Appearance, Explore & privacy, Notifications toggles into settings sections"
```

---

### Task 6: Cross-club Users storage — `get_user_record`/`save_user_record`

**Files:**
- Modify: `src/storage.py` — add `USERS_TABLE` config to `AirtableStorage.__init__` (near line 294), add `get_user_record`/`save_user_record` methods (near line 750, end of class), module docstring update
- Modify: `src/storage_mongo.py` — add `USERS_COLLECTION` constant, index entry in `INDEXES`, `get_user_record`/`save_user_record` methods on `MongoStorage`
- Test: `tests/test_storage_mongo.py`, new `tests/test_storage_airtable.py`

**Interfaces:**
- Produces (both backends, same signature):
  - `get_user_record(email: str) -> dict` → always returns `{'preferredName': str, 'sessionVersion': int}`, defaulting to `{'preferredName': '', 'sessionVersion': 0}` when no row exists.
  - `save_user_record(email: str, fields: dict) -> None` → `fields` may contain `preferredName` and/or `sessionVersion`; merges onto the existing record (upsert). Raises `StorageError` on the Airtable backend specifically when the `Users` table doesn't exist in the base.
- Consumes: `StorageError` (already defined in `src/storage.py:178`), `requests`/`PyMongoError` plumbing already present in each module.

- [ ] **Step 1: Write the failing Mongo test**

```python
# tests/test_storage_mongo.py — append (see existing file for the mongomock/fixture pattern already used there; reuse whatever fixture name that file already defines for a MongoStorage instance, e.g. `storage`)

def test_get_user_record_defaults_when_missing(storage):
    record = storage.get_user_record('nobody@example.com')
    assert record == {'preferredName': '', 'sessionVersion': 0}


def test_save_and_get_user_record_round_trips(storage):
    storage.save_user_record('leader@example.com', {'preferredName': 'Ada', 'sessionVersion': 1})
    record = storage.get_user_record('leader@example.com')
    assert record == {'preferredName': 'Ada', 'sessionVersion': 1}


def test_save_user_record_merges_partial_update(storage):
    storage.save_user_record('leader@example.com', {'preferredName': 'Ada'})
    storage.save_user_record('leader@example.com', {'sessionVersion': 2})
    record = storage.get_user_record('leader@example.com')
    assert record == {'preferredName': 'Ada', 'sessionVersion': 2}


def test_get_user_record_lowercases_email(storage):
    storage.save_user_record('Leader@Example.com', {'preferredName': 'Ada'})
    record = storage.get_user_record('leader@example.com')
    assert record['preferredName'] == 'Ada'
```

(If `tests/test_storage_mongo.py` doesn't already have a `storage` fixture, inspect its existing tests first and reuse the exact fixture name/setup it uses to build a `MongoStorage` against `mongomock` — do not introduce a second fixture pattern.)

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_storage_mongo.py -k user_record -v`
Expected: FAIL — `AttributeError: 'MongoStorage' object has no attribute 'get_user_record'`

- [ ] **Step 3: Implement on `MongoStorage`**

```python
# src/storage_mongo.py:32 — add alongside CLUBS_COLLECTION
USERS_COLLECTION: Final[str] = 'users'
```

```python
# src/storage_mongo.py — add to INDEXES dict (after the CLUBS_COLLECTION entry, before 'members')
    # get_user_record()/save_user_record() look a user up by their own email —
    # _id IS the lowercased email, so no extra index is needed beyond the
    # default _id index Mongo always creates.
```

```python
# src/storage_mongo.py — add two new methods to MongoStorage, after page_messages()

    def get_user_record(self, email: str) -> dict[str, Any]:
        """Cross-club record for `email` — preferred display name and the
        session-invalidation counter. Defaults if no row exists yet."""
        email = (email or '').strip().lower()
        defaults = {'preferredName': '', 'sessionVersion': 0}
        if not email:
            return defaults
        docs = self._find(USERS_COLLECTION, {'_id': email}, limit=1)
        if not docs:
            return defaults
        doc = docs[0]
        return {
            'preferredName': doc.get('preferredName') or '',
            'sessionVersion': int(doc.get('sessionVersion') or 0),
        }

    def save_user_record(self, email: str, fields: dict[str, Any]) -> None:
        """Upsert `fields` (preferredName and/or sessionVersion) onto the
        user's cross-club record, merging onto whatever's already there."""
        email = (email or '').strip().lower()
        if not email:
            raise StorageError('Cannot save a user record without an email.')
        update: dict[str, Any] = {}
        if 'preferredName' in fields:
            update['preferredName'] = str(fields['preferredName'] or '')
        if 'sessionVersion' in fields:
            update['sessionVersion'] = int(fields['sessionVersion'] or 0)
        try:
            self.db[USERS_COLLECTION].update_one(
                {'_id': email}, {'$set': update}, upsert=True
            )
        except PyMongoError as exc:
            raise StorageError(f'MongoDB write on {USERS_COLLECTION} failed: {exc}') from exc
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_storage_mongo.py -k user_record -v`
Expected: PASS

- [ ] **Step 5: Write the failing Airtable test**

Inspect the existing Airtable test setup first — this repo currently has no `tests/test_storage_airtable.py`, so check how `AirtableStorage` is exercised elsewhere (likely mocked via `responses` or `monkeypatch` on `requests`). If no existing pattern for mocking `AirtableStorage._request`, use `monkeypatch` directly on the instance:

```python
# tests/test_storage_airtable.py — new file

import pytest

from src.storage import AirtableStorage, StorageError


@pytest.fixture
def storage(monkeypatch):
    monkeypatch.setenv('AIRTABLE_TOKEN', 'test-token')
    monkeypatch.setenv('AIRTABLE_BASE_ID', 'test-base')
    return AirtableStorage()


def test_get_user_record_defaults_when_table_missing(storage, monkeypatch):
    def fake_request(method, table, **kwargs):
        raise StorageError('Airtable request failed (404): Table not found')

    monkeypatch.setattr(storage, '_request', fake_request)
    record = storage.get_user_record('nobody@example.com')
    assert record == {'preferredName': '', 'sessionVersion': 0}


def test_get_user_record_reads_existing_row(storage, monkeypatch):
    def fake_list(table, **kwargs):
        return [
            {
                'id': 'rec1',
                'fields': {'Email': 'leader@example.com', 'Preferred Name': 'Ada', 'Session Version': 3},
            }
        ]

    monkeypatch.setattr(storage, '_list', fake_list)
    record = storage.get_user_record('leader@example.com')
    assert record == {'preferredName': 'Ada', 'sessionVersion': 3}


def test_save_user_record_raises_when_table_missing(storage, monkeypatch):
    def fake_request(method, table, **kwargs):
        raise StorageError('Airtable request failed (404): Table not found')

    monkeypatch.setattr(storage, '_request', fake_request)
    monkeypatch.setattr(storage, '_list', lambda table, **kwargs: (_ for _ in ()).throw(
        StorageError('Airtable request failed (404): Table not found')
    ))
    with pytest.raises(StorageError, match='Users table'):
        storage.save_user_record('leader@example.com', {'preferredName': 'Ada'})
```

(Before writing these, read `src/storage.py`'s existing `_request`/`_list` helper signatures in full — lines 307-330 and the `_list`/`_paged` helpers further down — to match the mock's call signature exactly. Adjust the fake functions above to match those exact signatures if they differ from what's assumed here.)

- [ ] **Step 6: Run to verify it fails**

Run: `pytest tests/test_storage_airtable.py -v`
Expected: FAIL — `AttributeError: 'AirtableStorage' object has no attribute 'get_user_record'`

- [ ] **Step 7: Implement on `AirtableStorage`**

```python
# src/storage.py:294 — add alongside self.clubs_table in __init__
        self.users_table = os.environ.get('AIRTABLE_TABLE_USERS', 'Users')
```

```python
# src/storage.py — add two new methods to AirtableStorage, at the end of the class (after the last existing method)

    def get_user_record(self, email: str) -> dict[str, Any]:
        """Cross-club record for `email` — preferred display name and the
        session-invalidation counter. Defaults if the Users table is missing
        from this base, or the user has no row in it yet."""
        email = (email or '').strip().lower()
        defaults = {'preferredName': '', 'sessionVersion': 0}
        if not email:
            return defaults
        try:
            rows = self._list(
                self.users_table,
                params={'filterByFormula': f"LOWER({{Email}})='{email}'", 'maxRecords': 1},
            )
        except StorageError:
            return defaults
        if not rows:
            return defaults
        fields = rows[0].get('fields', {})
        return {
            'preferredName': fields.get('Preferred Name') or '',
            'sessionVersion': int(fields.get('Session Version') or 0),
        }

    def save_user_record(self, email: str, fields: dict[str, Any]) -> None:
        """Upsert `fields` (preferredName and/or sessionVersion) onto the
        user's Users-table row. Raises StorageError (surfaced by the route as
        a setup instruction) if this base has no Users table yet."""
        email = (email or '').strip().lower()
        if not email:
            raise StorageError('Cannot save a user record without an email.')
        airtable_fields: dict[str, Any] = {}
        if 'preferredName' in fields:
            airtable_fields['Preferred Name'] = str(fields['preferredName'] or '')
        if 'sessionVersion' in fields:
            airtable_fields['Session Version'] = int(fields['sessionVersion'] or 0)
        try:
            existing = self._list(
                self.users_table,
                params={'filterByFormula': f"LOWER({{Email}})='{email}'", 'maxRecords': 1},
            )
        except StorageError as exc:
            raise StorageError(
                'This club uses Airtable but has no Users table yet. '
                'Ask your Airtable base owner to add a Users table first.'
            ) from exc
        if existing:
            record_id = existing[0]['id']
            self._request(
                'patch',
                self.users_table,
                record_path=record_id,
                json={'fields': airtable_fields},
            )
        else:
            airtable_fields.setdefault('Email', email)
            self._request('post', self.users_table, json={'fields': airtable_fields})
```

- [ ] **Step 8: Run to verify it passes**

Run: `pytest tests/test_storage_airtable.py -v`
Expected: PASS (adjust mock call signatures per Step 5's note if `_list`/`_request` differ from what's assumed — re-run until green)

- [ ] **Step 9: Document the new table in the module docstring**

Read `src/storage.py`'s top-of-file docstring (lines 1-30ish, not yet quoted here) and add one line documenting the new `Users` table (`Email*`, `Preferred Name`, `Session Version`) alongside the existing schema list, following whatever format the existing docstring uses for `Clubs`/`Members`/etc.

- [ ] **Step 10: Run full suite, then commit**

Run: `pytest tests/ -v` — Expected: PASS

```bash
git add src/storage.py src/storage_mongo.py tests/test_storage_mongo.py tests/test_storage_airtable.py
git commit -m "feat: add cross-club Users record (preferredName, sessionVersion) to Airtable and Mongo backends"
```

---

### Task 7: Your account section — Preferred name (real) + stubbed identity fields

**Files:**
- Modify: `templates/partials/settings/your_account.html` (replace placeholder)
- Modify: `src/routes_club.py` — new `api_account_preferred_name_update` endpoint
- Modify: `src/routes_web.py:278-283` (`dashboard_settings`) — pass `preferred_name` and `shared_backend` into the template context
- Modify: `src/helpers.py` — new `_storage()`-aware helper `get_preferred_name(email: str) -> str` used by both the route and the template context
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `get_user_record`/`save_user_record` from Task 6 (shared backends), `session['user']` (session backend — preferred name round-trips through `session['user']['preferredName']`, same pattern as `name`/`bio`/`hackatimeId` in `api_profile_update`).
- Produces: `POST /api/dashboard/account/preferred-name` (PATCH), body `{preferredName: str}` → `{preferredName: str}`. `dashboard_settings` template context gains `preferred_name: str` and `shared_backend: bool` (the latter reused verbatim by Task 9's Danger zone section, defined once here since both sections need it).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api.py — append

def test_preferred_name_round_trips_on_session_backend(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrf-token'
        sess['dashboard_state'] = {'settings': {'clubName': 'Test Club'}, 'members': []}
    response = auth_client.patch(
        '/api/dashboard/account/preferred-name',
        json={'preferredName': 'Ada'},
        headers={'X-CSRF-Token': 'test-csrf-token'},
    )
    assert response.status_code == 200
    assert response.get_json()['preferredName'] == 'Ada'
    with auth_client.session_transaction() as sess:
        assert sess['user']['preferredName'] == 'Ada'


def test_preferred_name_rejects_blank(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrf-token'
        sess['dashboard_state'] = {'settings': {'clubName': 'Test Club'}, 'members': []}
    response = auth_client.patch(
        '/api/dashboard/account/preferred-name',
        json={'preferredName': '  '},
        headers={'X-CSRF-Token': 'test-csrf-token'},
    )
    assert response.status_code == 400


def test_your_account_section_renders_stub_rows(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Test Club', 'venue': 'Test High'},
            'members': [{'id': 'm1', 'name': 'Test Leader', 'email': 'leader@test.com', 'role': 'Leader', 'avatar': '', 'status': 'Active'}],
        }
    response = auth_client.get('/dashboard/settings')
    body = response.get_data(as_text=True)
    assert 'name="preferredName"' in body
    for label in ('Full name', 'Slack', 'Verification', 'Phone', 'Birthday', 'Mailing address'):
        assert label in body
    assert 'Not available yet' in body
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_api.py -k preferred_name or your_account_section_renders_stub_rows -v`
Expected: FAIL — no such route, placeholder partial has no fields.

- [ ] **Step 3: Implement `get_preferred_name` helper**

```python
# src/helpers.py — add near _club_key() (after line 734)

def get_preferred_name() -> str:
    """The viewer's preferred display name. Session backend: round-trips
    through session['user']['preferredName'] (same pattern as name/bio/
    hackatimeId in api_profile_update). Shared backends: the cross-club
    Users record."""
    backend = _storage()
    if isinstance(backend, SessionStorage):
        return (session.get('user') or {}).get('preferredName') or ''
    email = (session.get('user') or {}).get('email') or ''
    return backend.get_user_record(email).get('preferredName') or ''
```

- [ ] **Step 4: Implement the API endpoint**

```python
# src/routes_club.py — add to the "── Profile ──" section, after api_profile_update

    @app.patch('/api/dashboard/account/preferred-name')
    @login_required
    def api_account_preferred_name_update():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        preferred_name = clean_text(json_payload().get('preferredName'), max_len=80)
        if not preferred_name:
            return json_error('Preferred name is required.')

        backend = _storage()
        if isinstance(backend, SessionStorage):
            user = dict(session.get('user') or {})
            user['preferredName'] = preferred_name
            session['user'] = user
        else:
            email = (session.get('user') or {}).get('email') or ''
            backend.save_user_record(email, {'preferredName': preferred_name})

        return flask.jsonify({'preferredName': preferred_name})
```

Add `_storage` and `SessionStorage` to `routes_club.py`'s imports (`_storage` is already imported; add `SessionStorage`):

```python
# src/routes_club.py:1-22 — add to the import block
from .storage import SessionStorage
```

- [ ] **Step 5: Wire `dashboard_settings` route context**

```python
# src/routes_web.py:278-283 — replace dashboard_settings
    @app.route('/dashboard/settings')
    @leader_required
    def dashboard_settings():
        backend = _storage()
        return flask.render_template(
            'dashboard/settings.html',
            dashboard_state=get_dashboard_state(sections_for_request()),
            preferred_name=get_preferred_name(),
            shared_backend=not isinstance(backend, SessionStorage),
        )
```

Add `get_preferred_name` to `routes_web.py`'s imports from `.helpers`:

```python
# src/routes_web.py:6-19 — add get_preferred_name to the import list
from .helpers import (
    _item_id,
    _storage,
    clean_text,
    default_dashboard_state,
    get_dashboard_state,
    get_preferred_name,
    is_admin,
    json_error,
    leader_required,
    login_required,
    save_dashboard_state,
    sections_for_request,
    viewer_club_lite,
)
```

- [ ] **Step 6: Implement the partial**

```html
<!-- templates/partials/settings/your_account.html -->
<div class="panel-heading">
    <div>
        <h2 data-i18n="settings.yourAccount">Your account</h2>
        <p data-i18n="settings.yourAccountDesc">Personal details tied to you, not your club.</p>
    </div>
</div>

<form class="settings-form" id="preferredNameForm">
    <label class="form-group">
        <span class="form-label" data-i18n="settings.preferredName">Preferred name</span>
        <input type="text" class="form-input" name="preferredName" value="{{ preferred_name }}" required>
        <small class="form-hint" data-i18n="settings.preferredNameHint">Shown on your profile card. Defaults to your first name.</small>
    </label>
    <p class="form-error" id="preferredNameFormError" hidden></p>
    <div class="form-actions">
        <button type="submit" class="btn-primary" data-i18n="settings.save">Save changes</button>
        <span class="save-state" id="preferredNameSaveState" aria-live="polite"></span>
    </div>
</form>

<div class="settings-stub-block">
    <h3 data-i18n="settings.syncedFromHackClub">Synced from Hack Club</h3>
    <p class="settings-stub-note" data-i18n="settings.syncedFromHackClubDesc">These can't be edited here.</p>
    <div class="settings-stub-row">
        <span class="settings-stub-row-label" data-i18n="settings.fullName">Full name</span>
        <span class="settings-stub-row-value">{{ current_user.name or 'Not available yet' }}</span>
    </div>
    <div class="settings-stub-row">
        <span class="settings-stub-row-label" data-i18n="settings.email">Email</span>
        <span class="settings-stub-row-value">{{ current_user.email or 'Not available yet' }}</span>
    </div>
    <div class="settings-stub-row">
        <span class="settings-stub-row-label" data-i18n="settings.slack">Slack</span>
        <span class="settings-stub-row-value" data-i18n="common.notAvailableYet">Not available yet</span>
    </div>
    <div class="settings-stub-row">
        <span class="settings-stub-row-label" data-i18n="settings.verification">Verification</span>
        <span class="settings-stub-row-value" data-i18n="common.notAvailableYet">Not available yet</span>
    </div>
    <div class="settings-stub-row">
        <span class="settings-stub-row-label" data-i18n="settings.phone">Phone</span>
        <span class="settings-stub-row-value" data-i18n="common.notAvailableYet">Not available yet</span>
    </div>
    <div class="settings-stub-row">
        <span class="settings-stub-row-label" data-i18n="settings.birthday">Birthday</span>
        <span class="settings-stub-row-value" data-i18n="common.notAvailableYet">Not available yet</span>
    </div>
    <div class="settings-stub-row">
        <span class="settings-stub-row-label" data-i18n="settings.mailingAddress">Mailing address</span>
        <span class="settings-stub-row-value" data-i18n="common.notAvailableYet">Not available yet</span>
    </div>
</div>

<div class="settings-stub-block">
    <h3 data-i18n="profile.hackatime">Hackatime</h3>
    <div class="hackatime-connect">
        {% if current_user.hackatimeId %}
        <span class="hackatime-connected">
            <span class="hackatime-dot" aria-hidden="true"></span>
            <span data-i18n="profile.connected">Connected · ID {{ current_user.hackatimeId }}</span>
        </span>
        {% if hackatime_connect_enabled %}
        <a class="btn-secondary small" href="{{ url_for('hackatime_login') }}" data-i18n="profile.reconnect">Reconnect</a>
        {% endif %}
        {% elif hackatime_connect_enabled %}
        <a class="btn-primary small" href="{{ url_for('hackatime_login') }}">
            <span class="button-icon" aria-hidden="true"><span data-hc-icon="bolt" data-hc-size="16" data-hc-color="currentColor" aria-hidden="true"></span></span> <span data-i18n="profile.connectHackatime">Connect Hackatime</span>
        </a>
        {% endif %}
    </div>
</div>
```

Note: `hackatime_connect_enabled` is not currently passed to `dashboard_settings` — add it in Step 5 alongside `preferred_name`/`shared_backend`:

```python
# src/routes_web.py — dashboard_settings, final version (supersedes Step 5's version)
    @app.route('/dashboard/settings')
    @leader_required
    def dashboard_settings():
        backend = _storage()
        return flask.render_template(
            'dashboard/settings.html',
            dashboard_state=get_dashboard_state(sections_for_request()),
            preferred_name=get_preferred_name(),
            shared_backend=not isinstance(backend, SessionStorage),
            hackatime_connect_enabled=bool(HACKATIME_CLIENT_ID),
        )
```

(`HACKATIME_CLIENT_ID` is already a parameter of `register(app, HACKATIME_CLIENT_ID)` in `routes_web.py:23` — confirm it's in scope at this point in the file; it is, since `dashboard_profile` at the bottom of the same file already uses it identically.)

- [ ] **Step 7: JS — preferred name form handler**

```javascript
// static/js/dashboard.js — add near the #profileForm submit handler (after line ~2823)

        $('#preferredNameForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const stateLabel = $('#preferredNameSaveState');
            setFormError('preferredNameFormError', '');
            if (stateLabel) stateLabel.textContent = 'Saving...';
            try {
                await apiRequest('/api/dashboard/account/preferred-name', {
                    method: 'PATCH',
                    body: formObject(event.currentTarget),
                });
                if (stateLabel) stateLabel.textContent = 'Saved';
                showToast('Preferred name saved.');
            } catch (error) {
                setFormError('preferredNameFormError', error.message);
                if (stateLabel) stateLabel.textContent = '';
            }
        });
```

- [ ] **Step 8: Run to verify it passes**

Run: `pytest tests/test_api.py -k preferred_name or your_account_section_renders_stub_rows -v`
Expected: PASS

- [ ] **Step 9: Run full suite, then commit**

Run: `pytest tests/ -v` — Expected: PASS

```bash
git add src/helpers.py src/routes_club.py src/routes_web.py templates/partials/settings/your_account.html static/js/dashboard.js tests/test_api.py
git commit -m "feat: build out Your account settings section with real Preferred name and stubbed identity fields"
```

---

### Task 8: Session-version stamping on login + staleness check

**Files:**
- Modify: `src/routes_auth.py:114-120` (`hackclub_callback`), `src/routes_auth.py:153-179` (`playtest_login`)
- Modify: `src/routes_web.py:58-73` (`require_club_membership` before_request)
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: `get_user_record` from Task 6 (shared backends only).
- Produces: `session['user']['sessionVersion']: int`, stamped at login. `require_club_membership` now also clears a stale session (`session.clear()` + redirect to sign-in) when `shared_backend` is true and the cookie's stamped version no longer matches the stored one.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_auth.py — append (inspect the existing file first for its import/fixture style and match it; this assumes `app` and a way to monkeypatch STORAGE_BACKEND are already used elsewhere in the file, as they are in test_api.py)

def test_before_request_clears_stale_session_on_shared_backend(client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    # Session backend never triggers the staleness check (no shared_backend) —
    # this test only verifies the check is skipped, not that it fires, since
    # exercising the Airtable/Mongo path requires mocking get_user_record.
    with client.session_transaction() as sess:
        sess['user'] = {'id': 'u1', 'name': 'Test', 'email': 'leader@test.com', 'sessionVersion': 5}
        sess['dashboard_state'] = {'settings': {'clubName': 'Test'}, 'members': []}
    response = client.get('/dashboard')
    assert response.status_code == 200


def test_before_request_clears_stale_session_when_version_mismatches(client, monkeypatch):
    import src.routes_web as routes_web_module

    class FakeSharedBackend:
        def resolve_club_key(self, email):
            return email

        def load_lite(self, club_key):
            return {'settings': {'clubName': 'Test'}, 'members': [{'email': 'leader@test.com', 'role': 'Leader'}]}

        def get_user_record(self, email):
            return {'preferredName': '', 'sessionVersion': 99}

    monkeypatch.setattr(routes_web_module, '_storage', lambda: FakeSharedBackend())
    with client.session_transaction() as sess:
        sess['user'] = {'id': 'u1', 'name': 'Test', 'email': 'leader@test.com', 'sessionVersion': 1}
    response = client.get('/dashboard', follow_redirects=False)
    assert response.status_code in (301, 302)
    assert '/sign-in' in response.headers['Location']
    with client.session_transaction() as sess:
        assert 'user' not in sess
```

(If `tests/test_auth.py` uses a different monkeypatch pattern for swapping `_storage()` than the class-based fake above — check the file first — match its existing convention instead of introducing a new one.)

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_auth.py -k stale_session -v`
Expected: FAIL — second test currently passes through with no staleness check (i.e. the redirect assertion fails, response is 200).

- [ ] **Step 3: Implement — stamp `sessionVersion` at login**

```python
# src/routes_auth.py:114-120 — replace inside hackclub_callback
        backend = make_storage(session)
        session_version = 0
        if not isinstance(backend, SessionStorage):
            session_version = backend.get_user_record(user_data.get('email') or '').get('sessionVersion', 0)

        session['user'] = {
            'id': user_data.get('sub'),
            'name': user_data.get('name'),
            'email': user_data.get('email'),
            'avatar': user_data.get('picture'),
            'provider': 'hackclub',
            'sessionVersion': session_version,
        }
```

```python
# src/routes_auth.py:1-9 — add imports
from .helpers import clean_text, login_required, playtest_state
from .storage import SessionStorage, make_storage
```

```python
# src/routes_auth.py:154-165 — playtest_login leader branch, add sessionVersion
        session['user'] = {
            'id': 'playtest-leader',
            'name': 'Test Leader',
            'email': 'playtest.leader@hackclub.com',
            'avatar': '',
            'provider': 'playtest',
            'hackatimeId': 'playtest',
            'sessionVersion': 0,
        }
```

```python
# src/routes_auth.py:167-174 — playtest_login member branch, add sessionVersion
        session['user'] = {
            'id': 'playtest-member',
            'name': 'Test Member',
            'email': 'playtest.member@hackclub.com',
            'avatar': '',
            'provider': 'playtest',
            'hackatimeId': 'playtest',
            'sessionVersion': 0,
        }
```

(Playtest always uses `STORAGE_BACKEND` however the app is configured, but its accounts are synthetic and never have a real Users row — stamping `0` is correct since `get_user_record` would also default to `0` for these emails; no need to call the backend for playtest.)

- [ ] **Step 4: Run to verify hackclub_callback logic doesn't break existing auth tests**

Run: `pytest tests/test_auth.py -v`
Expected: PASS (pre-existing tests), new staleness test for the session-backend case (Step 1's first test) also PASS.

- [ ] **Step 5: Implement — staleness check in `require_club_membership`**

```python
# src/routes_web.py:58-73 — replace require_club_membership
    @app.before_request
    def require_club_membership():
        path = request.path
        if not (path.startswith('/dashboard') or path.startswith('/api/dashboard')):
            return None
        if path.startswith('/dashboard/welcome'):
            return None
        if path.startswith('/dashboard/admin') or path.startswith('/api/admin'):
            return None
        user = session.get('user')
        if not user:
            return None

        backend = _storage()
        if not isinstance(backend, SessionStorage):
            stored_version = backend.get_user_record(user.get('email') or '').get('sessionVersion', 0)
            if int(user.get('sessionVersion', 0)) != int(stored_version):
                session.clear()
                if path.startswith('/api/'):
                    return json_error('Your session was signed out from another device. Please sign in again.', 401)
                return redirect(url_for('sign_in'))

        if is_admin() or viewer_club_lite() is not None:
            return None
        if path.startswith('/api/'):
            return json_error('Join or create a club first.', 403)
        return redirect(url_for('dashboard_welcome'))
```

- [ ] **Step 6: Run to verify it passes**

Run: `pytest tests/test_auth.py -k stale_session -v`
Expected: PASS

- [ ] **Step 7: Run full suite, then commit**

Run: `pytest tests/ -v` — Expected: PASS (watch for any existing test in `tests/test_api.py`/`tests/test_auth.py` that sets `session['user']` without `sessionVersion` while running against a *shared* backend mock — those would now hit the staleness branch. Grep for `STORAGE_BACKEND.*airtable\|mongo` across `tests/` to confirm none exist against a real/mocked shared backend without this field; if any do, add `'sessionVersion': 0` to their fixture's `session['user']` dict to match what a real stored default (`0`) would be.)

```bash
git add src/routes_auth.py src/routes_web.py tests/test_auth.py
git commit -m "feat: stamp and verify sessionVersion on login for cross-device sign-out"
```

---

### Task 9: Danger zone — "Sign out everywhere"

**Files:**
- Modify: `templates/partials/settings/danger_zone.html` (replace placeholder)
- Modify: `src/routes_club.py` — new `api_account_sign_out_everywhere` endpoint
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `save_user_record` (Task 6), `shared_backend` template context (Task 7).
- Produces: `POST /api/dashboard/account/sign-out-everywhere` → `{'signedOut': true}`, then clears the initiating browser's own session (it must re-authenticate too, per spec).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api.py — append

def test_sign_out_everywhere_requires_shared_backend(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrf-token'
        sess['dashboard_state'] = {'settings': {'clubName': 'Test Club'}, 'members': []}
    response = auth_client.post(
        '/api/dashboard/account/sign-out-everywhere',
        headers={'X-CSRF-Token': 'test-csrf-token'},
    )
    assert response.status_code == 400
    assert 'demo mode' in response.get_json()['error'].lower()


def test_sign_out_everywhere_bumps_session_version_and_clears_session(auth_client, monkeypatch):
    import src.routes_club as routes_club_module

    class FakeSharedBackend:
        def __init__(self):
            self.saved = None

        def get_user_record(self, email):
            return {'preferredName': '', 'sessionVersion': 3}

        def save_user_record(self, email, fields):
            self.saved = (email, fields)

    fake_backend = FakeSharedBackend()
    monkeypatch.setattr(routes_club_module, '_storage', lambda: fake_backend)
    with auth_client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrf-token'
        sess['user']['sessionVersion'] = 3

    response = auth_client.post(
        '/api/dashboard/account/sign-out-everywhere',
        headers={'X-CSRF-Token': 'test-csrf-token'},
    )
    assert response.status_code == 200
    assert response.get_json()['signedOut'] is True
    assert fake_backend.saved == ('leader@test.com', {'sessionVersion': 4})
    with auth_client.session_transaction() as sess:
        assert 'user' not in sess
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_api.py -k sign_out_everywhere -v`
Expected: FAIL — `404 NOT FOUND` (route doesn't exist)

- [ ] **Step 3: Implement the endpoint**

```python
# src/routes_club.py — add at the end of the file, new "── Account danger zone ──" section

    # ── Account danger zone ──────────────────────────────────────────────────

    @app.post('/api/dashboard/account/sign-out-everywhere')
    @login_required
    def api_account_sign_out_everywhere():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        backend = _storage()
        if isinstance(backend, SessionStorage):
            return json_error(
                'This site is running in local demo mode, so signing out other '
                'devices is not available here.'
            )

        email = (session.get('user') or {}).get('email') or ''
        current_version = backend.get_user_record(email).get('sessionVersion', 0)
        backend.save_user_record(email, {'sessionVersion': current_version + 1})
        session.clear()
        return flask.jsonify({'signedOut': True})
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_api.py -k sign_out_everywhere -v`
Expected: PASS

- [ ] **Step 5: Implement the partial**

```html
<!-- templates/partials/settings/danger_zone.html -->
<div class="panel-heading">
    <div>
        <h2 class="danger-heading" data-i18n="settings.dangerZone">Danger zone</h2>
    </div>
</div>

{% if shared_backend %}
<div class="danger-row">
    <div>
        <strong data-i18n="settings.signOutEverywhere">Sign out everywhere</strong>
        <p data-i18n="settings.signOutEverywhereDesc">Sign out of every device where you're currently signed in, including this one.</p>
    </div>
    <button class="btn-danger" type="button" id="signOutEverywhereBtn" data-i18n="settings.signOutEverywhereBtn">Sign out everywhere</button>
</div>
{% else %}
<p class="settings-stub-note" data-i18n="settings.signOutEverywhereDemoMode">
    This site is running in local demo mode, so signing out other devices isn't available here.
</p>
{% endif %}
```

Add `.danger-row`/`.btn-danger`/`.danger-heading` CSS (check `static/css/dashboard.css` first for any existing danger/destructive button style to reuse — e.g. `#deleteMemberButton` in `team.html` likely already has one; if `.btn-danger` doesn't exist, add it):

```css
/* static/css/dashboard.css — append if no .btn-danger already exists (grep first) */
.danger-heading {
    color: #a8122a;
}

.danger-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
}

.btn-danger {
    font-family: inherit;
    font-size: 14px;
    font-weight: bold;
    padding: 10px 18px;
    border-radius: 10px;
    border: 1.5px solid #a8122a;
    background: transparent;
    color: #a8122a;
    cursor: pointer;
    transition: background 0.15s ease, color 0.15s ease;
}

.btn-danger:hover {
    background: #a8122a;
    color: #fff;
}
```

- [ ] **Step 6: JS handler**

```javascript
// static/js/dashboard.js — add near the #refreshJoinLink handler (after line ~2685)

        $('#signOutEverywhereBtn')?.addEventListener('click', async () => {
            const ok = window.confirm(
                'Sign out of every device, including this one? '
                + "You'll need to sign in again."
            );
            if (!ok) return;
            try {
                await apiRequest('/api/dashboard/account/sign-out-everywhere', { method: 'POST' });
                window.location.href = '/sign-in';
            } catch (error) {
                showToast(error.message, 'error');
            }
        });
```

- [ ] **Step 7: Run full suite**

Run: `pytest tests/ -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/routes_club.py templates/partials/settings/danger_zone.html static/css/dashboard.css static/js/dashboard.js tests/test_api.py
git commit -m "feat: build out Danger zone with real, shared-backend-gated Sign out everywhere"
```

---

## Post-plan cleanup (housekeeping, not a task)

The spec file `docs/superpowers/specs/2026-08-12-settings-page-design.md` has two uncommitted edits from before this plan was written (the Your-account and Danger-zone sections were revised after discovering the storage.py architecture nuance). Commit them separately before or alongside Task 1:

```bash
git add docs/superpowers/specs/2026-08-12-settings-page-design.md
git commit -m "docs: finalize Danger zone architecture in settings page spec"
```

---

## Self-Review Notes

**Spec coverage:** All 7 sections (Club profile, Members, Your account, Appearance, Explore & privacy, Notifications, Danger zone) map to Tasks 2-9. The `location` derivation, avatar-upload reuse, join-code-card reuse, and `shared_backend` gating are each covered in Tasks 1, 3, 4, and 7/9 respectively. "Build sandbox" is explicitly not built anywhere in this plan.

**Correction from the original spec draft:** the spec's Testing section mentioned a CSV export as a `location` consumer — investigation during planning (Task 1) found no CSV export exists anywhere in this codebase. The real consumers are `templates/dashboard/admin.html:161` and `static/js/dashboard.js`'s `homeClubMeta`/`clubPreviewLocation` strings, both covered by keeping `location` derived rather than removed.

**Known one-time transition gap:** existing clubs saved under the old single-`location` field will show a blank `city`/`state`/derived `location` until a leader next saves the Club profile form (Task 1 adds no backfill/migration script — YAGNI, not requested by spec).
