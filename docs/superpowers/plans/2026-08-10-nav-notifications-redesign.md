# Sidebar Hover-Expand + Notifications-into-Newsletters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the dashboard sidebar expand on hover to show page labels and a profile card (name, club, coins, sign-out), and fold the notification bell/popover into the Newsletters page, renamed "Notification".

**Architecture:** Pure CSS overlay expansion (no JS state) for the sidebar; a Jinja template + Flask route rename plus a client-side array merge for notifications-into-newsletters. No storage/schema changes anywhere in this plan.

**Tech Stack:** Flask/Jinja templates, vanilla JS (`static/js/dashboard.js`), plain CSS (`static/css/dashboard.css`). No new dependencies.

## Global Constraints

- No new i18n keys duplicate existing English strings — reuse `data-i18n` keys already present on the source elements (spec section 1).
- No backend/storage schema changes — `notifications` and `newsletters` stay separate state sections; only the client-side rendering merges them (spec section 2).
- Mobile (`@media max-width: 768px`) sidebar-as-bottom-bar rules are untouched.
- Every template edit must keep existing `data-i18n` / `data-i18n-attr` translation coverage intact.

---

### Task 1: Sidebar hover-expand — panel wrapper + page labels

**Files:**
- Modify: `templates/dashboard_layout.html:90-187` (sidebar markup)
- Modify: `static/css/dashboard.css` (sidebar rules, `~125-240`)

**Interfaces:**
- Produces: `.dashboard-sidebar-panel` wrapper class and `.sidebar-label` class, both consumed by Task 2 (profile card lives inside the same panel).

- [ ] **Step 1: Wrap the sidebar's two `<nav>` groups in a `.dashboard-sidebar-panel` div**

In `templates/dashboard_layout.html`, replace the `<aside class="dashboard-sidebar">...</aside>` block (currently lines 90-188) with:

```html
        <aside class="dashboard-sidebar">
          <div class="dashboard-sidebar-panel">
            <nav class="dashboard-sidebar-nav" aria-label="Dashboard" data-i18n-attr="aria-label:side.navLabel">
                {% set current_path = request.path %}
                <a href="/dashboard"
                    class="dashboard-sidebar-link {% if current_path == '/dashboard' %}active{% endif %}" title="Home"
                    aria-label="Home" data-i18n-attr="title:side.home;aria-label:side.home">
                    {{ sidebar_icon('home') }}
                    <span class="sidebar-label" data-i18n="side.home">Home</span>
                </a>
                <a href="/dashboard/team"
                    class="dashboard-sidebar-link {% if current_path == '/dashboard/team' %}active{% endif %}"
                    title="Team" aria-label="Team" data-i18n-attr="title:side.team;aria-label:side.team">
                    {{ sidebar_icon('people-3') }}
                    <span class="sidebar-label" data-i18n="side.team">Team</span>
                </a>
                <a href="/dashboard/events"
                    class="dashboard-sidebar-link {% if current_path == '/dashboard/events' %}active{% endif %}"
                    title="Events" aria-label="Events" data-i18n-attr="title:side.events;aria-label:side.events">
                    {{ sidebar_icon('event-add') }}
                    <span class="sidebar-label" data-i18n="side.events">Events</span>
                </a>
                <a href="/dashboard/workshops"
                    class="dashboard-sidebar-link {% if current_path == '/dashboard/workshops' %}active{% endif %}"
                    title="Workshops" aria-label="Workshops" data-i18n-attr="title:side.workshops;aria-label:side.workshops">
                    {{ sidebar_icon('workshop') }}
                    <span class="sidebar-label" data-i18n="side.workshops">Workshops</span>
                </a>
                <a href="/dashboard/ships"
                    class="dashboard-sidebar-link {% if current_path == '/dashboard/ships' %}active{% endif %}"
                    title="Ships" aria-label="Ships" data-i18n-attr="title:side.ships;aria-label:side.ships">
                    {{ sidebar_icon('rocket') }}
                    <span class="sidebar-label" data-i18n="side.ships">Ships</span>
                </a>
                <a href="/dashboard/projects"
                    class="dashboard-sidebar-link {% if current_path == '/dashboard/projects' %}active{% endif %}"
                    title="Projects" aria-label="Projects"
                    data-i18n-attr="title:side.projects;aria-label:side.projects">
                    {{ sidebar_icon('package') }}
                    <span class="sidebar-label" data-i18n="side.projects">Projects</span>
                </a>
                <a href="/dashboard/levels"
                    class="dashboard-sidebar-link {% if current_path == '/dashboard/levels' %}active{% endif %}"
                    title="Levels" aria-label="Levels" data-i18n-attr="title:side.levels;aria-label:side.levels">
                    {{ sidebar_icon('trophy') }}
                    <span class="sidebar-label" data-i18n="side.levels">Levels</span>
                </a>
                {% if is_leader %}
                <a href="/dashboard/shop"
                    class="dashboard-sidebar-link {% if current_path == '/dashboard/shop' %}active{% endif %}"
                    title="Shop" aria-label="Shop" data-i18n-attr="title:side.shop;aria-label:side.shop">
                    {{ sidebar_icon('bag') }}
                    <span class="sidebar-label" data-i18n="side.shop">Shop</span>
                </a>
                {% endif %}
                <a href="/dashboard/notifications"
                    class="dashboard-sidebar-link {% if current_path == '/dashboard/notifications' %}active{% endif %}"
                    title="Notification" aria-label="Notification"
                    data-i18n-attr="title:side.notifications;aria-label:side.notifications">
                    {{ sidebar_icon('email') }}
                    <span class="sidebar-label" data-i18n="side.notifications">Notification</span>
                </a>
                <a href="/dashboard/chat"
                    class="dashboard-sidebar-link {% if current_path == '/dashboard/chat' %}active{% endif %}"
                    title="Chat" aria-label="Chat" data-i18n-attr="title:side.chat;aria-label:side.chat">
                    {{ sidebar_icon('message') }}
                    <span class="sidebar-label" data-i18n="side.chat">Chat</span>
                </a>
            </nav>
            <nav class="dashboard-sidebar-nav dashboard-sidebar-bottom" aria-label="Dashboard utilities"
                data-i18n-attr="aria-label:side.utilLabel">
                <a href="/dashboard/map"
                    class="dashboard-sidebar-link {% if current_path == '/dashboard/map' %}active{% endif %}"
                    title="Club Map" aria-label="Club Map" data-i18n-attr="title:side.map;aria-label:side.map">
                    {{ sidebar_icon('map-app') }}
                    <span class="sidebar-label" data-i18n="side.map">Club Map</span>
                </a>
                {% if is_leader %}
                <a href="/dashboard/tools"
                    class="dashboard-sidebar-link {% if current_path == '/dashboard/tools' %}active{% endif %}"
                    title="Tools" aria-label="Tools" data-i18n-attr="title:side.tools;aria-label:side.tools">
                    {{ sidebar_icon('tools') }}
                    <span class="sidebar-label" data-i18n="side.tools">Tools</span>
                </a>
                <a href="/dashboard/settings"
                    class="dashboard-sidebar-link {% if current_path == '/dashboard/settings' %}active{% endif %}"
                    title="Club Settings" aria-label="Club Settings"
                    data-i18n-attr="title:side.settings;aria-label:side.settings">
                    {{ sidebar_icon('settings') }}
                    <span class="sidebar-label" data-i18n="side.settings">Club Settings</span>
                </a>
                {% endif %}
                {% if is_admin %}
                <a href="/dashboard/admin"
                    class="dashboard-sidebar-link sidebar-admin-link {% if current_path.startswith('/dashboard/admin') %}active{% endif %}"
                    title="Admin" aria-label="Admin" data-i18n-attr="title:side.admin;aria-label:side.admin">
                    {{ sidebar_icon('admin') }}
                    <span class="sidebar-label" data-i18n="side.admin">Admin</span>
                </a>
                {% endif %}
                <a href="/dashboard/profile" id="sidebarProfile"
                    class="sidebar-profile {% if current_path == '/dashboard/profile' %}active{% endif %}"
                    title="Your profile" aria-label="Your profile"
                    data-i18n-attr="title:side.profile;aria-label:side.profile">
                    {% if current_user and current_user.avatar %}
                    <img src="{{ current_user.avatar }}" alt="{{ current_user.name }}">
                    {% else %}
                    <div class="sidebar-profile-fallback">
                        {{ current_user.name[0] | upper if current_user else 'U' }}
                    </div>
                    {% endif %}
                </a>
            </nav>
          </div>
        </aside>
```

Note: the "Newsletters" link (`href="/dashboard/newsletters"`, icon `email`, key `side.newsletters`) is replaced here with the "Notification" link (`href="/dashboard/notifications"`, key `side.notifications`) — Task 3 does the matching route/i18n rename, so both land in the same commit-able state once Task 3 lands. Until Task 3 is done, this link 404s; that's fine, Task 3 is next and this file isn't shipped in between.

- [ ] **Step 2: Add the expand-on-hover CSS**

In `static/css/dashboard.css`, right after the existing `.dashboard-sidebar` rule (ends at line 140, before `body.dark-mode .dashboard-sidebar` at line 142), insert:

```css
.dashboard-sidebar-panel {
    position: absolute;
    inset: 0;
    width: 76px;
    overflow: hidden;
    border-radius: inherit;
    background: inherit;
    box-shadow: inherit;
    display: flex;
    flex-direction: column;
    align-items: stretch;
    padding: 22px 0;
    transition: width 0.22s cubic-bezier(0.22, 1, 0.36, 1);
    z-index: 1;
}

.dashboard-sidebar:hover .dashboard-sidebar-panel {
    width: 232px;
}

.sidebar-label {
    display: inline-block;
    max-width: 0;
    overflow: hidden;
    white-space: nowrap;
    opacity: 0;
    margin-left: 0;
    font-size: 14px;
    font-weight: 600;
    transition: max-width 0.22s ease 0.05s, opacity 0.18s ease 0.08s, margin-left 0.22s ease 0.05s;
}

.dashboard-sidebar:hover .sidebar-label {
    max-width: 160px;
    opacity: 1;
    margin-left: 12px;
}
```

Then change `.dashboard-sidebar-link` (line 166-177) to lay out icon+label horizontally instead of centering a single icon — replace:

```css
.dashboard-sidebar-link {
    width: 46px;
    height: 46px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #6c727c;
    text-decoration: none;
    flex-shrink: 0;
    transition: background 0.2s ease, color 0.2s ease;
}
```

with:

```css
.dashboard-sidebar-link {
    min-height: 46px;
    width: 46px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #6c727c;
    text-decoration: none;
    flex-shrink: 0;
    transition: background 0.2s ease, color 0.2s ease, width 0.22s cubic-bezier(0.22, 1, 0.36, 1);
    overflow: hidden;
}

.dashboard-sidebar:hover .dashboard-sidebar-link {
    width: 208px;
    justify-content: flex-start;
    padding-left: 12px;
}
```

Every `.dashboard-sidebar-link`'s `.sidebar-icon` (22px, set at line 179-183) keeps `flex-shrink: 0` implicitly since it's an `<svg>` with fixed `width`/`height` attributes — no change needed there.

- [ ] **Step 3: Verify in browser**

Run the app (`python app.py` or the project's existing dev-server command), sign in, open `/dashboard`. Confirm:
- Collapsed sidebar looks identical to before (76px, icons only).
- Hovering the sidebar smoothly widens it to ~232px, revealing text labels next to every icon, without shifting `.dashboard-main` content.
- Un-hovering collapses it back.
- Works in both light and dark mode.

- [ ] **Step 4: Commit**

```bash
git add templates/dashboard_layout.html static/css/dashboard.css
git commit -m "feat: sidebar expands on hover to show page labels"
```

---

### Task 2: Sidebar profile card (coin balance + sign-out) + remove header coin chip

**Files:**
- Modify: `templates/dashboard_layout.html` (the `#sidebarProfile` link from Task 1's new block, and the header, `~199-213`)
- Modify: `templates/partials/icons.html` (add an `exit` icon)
- Modify: `static/css/dashboard.css` (`.sidebar-profile` rules, `~200-240`)

**Interfaces:**
- Consumes: `.dashboard-sidebar-panel` / `.dashboard-sidebar:hover` from Task 1.
- Produces: `#coinBalanceAmount` element now lives in the sidebar (same `id`, so `renderCoinBalance()` in `static/js/dashboard.js:1015-1018` needs no change).

- [ ] **Step 1: Add the `exit` icon**

In `templates/partials/icons.html`, add a new entry to the `icons` dict (after the `'workshop'` entry on line 20, before the closing `} -%}` on line 21):

```
    'workshop': '<path d="M2 5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H2Z"/><path d="M22 5a2 2 0 0 0-2-2h-6a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h8Z"/>',
    'exit': '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
} -%}
```

- [ ] **Step 2: Replace the `#sidebarProfile` block with avatar + expand-only card**

In `templates/dashboard_layout.html`, replace the `<a href="/dashboard/profile" id="sidebarProfile" ...>...</a>` block (written in Task 1 Step 1) with:

```html
                <div class="sidebar-profile-wrap">
                  <a href="/dashboard/profile" id="sidebarProfile"
                    class="sidebar-profile {% if current_path == '/dashboard/profile' %}active{% endif %}"
                    title="Your profile" aria-label="Your profile"
                    data-i18n-attr="title:side.profile;aria-label:side.profile">
                    {% if current_user and current_user.avatar %}
                    <img src="{{ current_user.avatar }}" alt="{{ current_user.name }}">
                    {% else %}
                    <div class="sidebar-profile-fallback">
                        {{ current_user.name[0] | upper if current_user else 'U' }}
                    </div>
                    {% endif %}
                  </a>
                  {% if current_user %}
                  <div class="sidebar-profile-card">
                    <p class="sidebar-profile-name">{{ current_user.name }}</p>
                    <p class="sidebar-profile-sub">{{ dashboard_state.settings.clubName if dashboard_state and dashboard_state.settings else '' }} &middot; {{ viewer_role }}</p>
                    <div class="sidebar-profile-meta">
                        <span class="sidebar-coin-pill">
                            <img src="{{ url_for('static', filename='images/hackclub-site/coin.svg') }}" alt="" class="sidebar-coin-icon">
                            <span id="coinBalanceAmount">0</span>
                        </span>
                        <a href="{{ url_for('sign_out') }}" class="icon-button sidebar-signout" aria-label="Sign out"
                            data-i18n-attr="aria-label:nav.signOut">
                            {{ sidebar_icon('exit', 16) }}
                        </a>
                    </div>
                  </div>
                  {% endif %}
                </div>
```

`dashboard_state` and `viewer_role` are both already exposed to every dashboard template by the `inject_user()` context processor in `app.py` (the same processor fixed for the StorageError redirect loop earlier this session) — no new context variable needs to be passed in from `routes_web.py`.

- [ ] **Step 3: Remove the header coin chip**

In `templates/dashboard_layout.html`, in `<header class="dashboard-header">`, delete this block (currently lines 207-212):

```html
                    {% if current_user %}
                    <div class="coin-balance-chip" id="coinBalanceChip" aria-label="Club coins balance">
                        {{ sidebar_icon('coin', 16) }}
                        <span id="coinBalanceAmount">0</span>
                    </div>
                    {% endif %}
```

(The `#coinBalanceAmount` id now only exists once, inside the sidebar card from Step 2 — removing it here avoids a duplicate-id DOM bug.)

- [ ] **Step 4: CSS for the profile card**

In `static/css/dashboard.css`, after the existing `.sidebar-profile-fallback` rule (ends line 239), insert:

```css
.sidebar-profile-wrap {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
    width: 100%;
    padding: 0 12px;
}

.sidebar-profile-card {
    max-width: 0;
    overflow: hidden;
    opacity: 0;
    white-space: nowrap;
    transition: max-width 0.22s ease 0.05s, opacity 0.18s ease 0.08s;
}

.dashboard-sidebar:hover .sidebar-profile-card {
    max-width: 200px;
    opacity: 1;
}

.sidebar-profile-name {
    margin: 0;
    font-size: 14px;
    font-weight: bold;
    color: #fff;
}

.sidebar-profile-sub {
    margin: 2px 0 8px;
    font-size: 12px;
    color: #9a9fa6;
}

.sidebar-profile-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
}

.sidebar-coin-pill {
    display: flex;
    align-items: center;
    gap: 6px;
    color: #fff;
    font-weight: bold;
    font-size: 13px;
}

.sidebar-coin-icon {
    width: 18px;
    height: 18px;
}

.sidebar-signout {
    width: 30px;
    height: 30px;
    color: #9a9fa6;
}

.sidebar-signout:hover {
    color: #fff;
}
```

- [ ] **Step 5: Verify in browser**

Hover the sidebar: confirm the avatar row now shows a card below it with your name, club name + role, coin count (matching whatever the old header chip showed), and a sign-out icon that navigates to sign-out on click. Confirm the header no longer shows a coin chip. Check dark mode.

- [ ] **Step 6: Commit**

```bash
git add templates/dashboard_layout.html templates/partials/icons.html static/css/dashboard.css
git commit -m "feat: sidebar profile card shows coin balance and sign-out on hover"
```

---

### Task 3: Rename Newsletters page to Notification (route, template, i18n key)

**Files:**
- Modify: `src/routes_web.py:263-266`
- Modify: `src/helpers.py:773` (`PAGE_SECTIONS` dict)
- Modify: `templates/dashboard/newsletters.html` → rename to `templates/dashboard/notifications.html`
- Modify: `static/js/i18n-data.js` (add `side.notifications` key to the `en` block)
- Test: `tests/test_public.py`

**Interfaces:**
- Produces: endpoint `dashboard_notifications` at `/dashboard/notifications`, template `dashboard/notifications.html`. Task 4 builds on this template; Task 1 already links to `/dashboard/notifications`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_public.py` (follow the existing pattern for other dashboard-page tests in that file — use the same `auth_client`/session-mode fixtures already used elsewhere in the file):

```python
def test_dashboard_notifications_page_loads(auth_client):
    response = auth_client.get('/dashboard/notifications')
    assert response.status_code == 200


def test_old_newsletters_path_redirects_to_notifications(auth_client):
    response = auth_client.get('/dashboard/newsletters', follow_redirects=False)
    assert response.status_code == 301
    assert response.headers['Location'].endswith('/dashboard/notifications')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_public.py -k "notifications_page_loads or newsletters_path_redirects" -v`
Expected: FAIL — `/dashboard/notifications` 404s (route doesn't exist yet), old path returns 200 not 301.

- [ ] **Step 3: Rename the route and add the redirect**

In `src/routes_web.py`, replace (lines 263-266):

```python
    @app.route('/dashboard/newsletters')
    @login_required
    def dashboard_newsletters():
        return flask.render_template('dashboard/newsletters.html')
```

with:

```python
    @app.route('/dashboard/notifications')
    @login_required
    def dashboard_notifications():
        return flask.render_template('dashboard/notifications.html')

    @app.route('/dashboard/newsletters')
    @login_required
    def dashboard_newsletters_redirect():
        return redirect(url_for('dashboard_notifications'), code=301)
```

`redirect` and `url_for` are already imported at the top of `routes_web.py` (`from flask import flash, redirect, request, session, url_for`).

- [ ] **Step 4: Update `PAGE_SECTIONS`**

In `src/helpers.py`, in the `PAGE_SECTIONS` dict (line 762-777), replace:

```python
    'dashboard_newsletters': ('newsletters',),
```

with:

```python
    'dashboard_notifications': ('newsletters',),
```

(`'notifications'` doesn't need to be listed — it's already in `ALWAYS_LOADED` at `helpers.py:755`, loaded on every dashboard page.)

- [ ] **Step 5: Rename the template and update its blocks**

Rename `templates/dashboard/newsletters.html` to `templates/dashboard/notifications.html`. In it, change lines 3-4 from:

```html
{% block page_title %}<span data-i18n="side.newsletters">Newsletters</span>{% endblock %}
{% block page_subtitle %}<span data-i18n="newsletters.subtitle">Read updates from HQ and send notes to your club.</span>{% endblock %}
```

to:

```html
{% block page_title %}<span data-i18n="side.notifications">Notification</span>{% endblock %}
{% block page_subtitle %}<span data-i18n="newsletters.subtitle">Read updates from HQ and send notes to your club.</span>{% endblock %}
```

(`newsletters.subtitle` stays — the dispatch-composing feature living on this page is unchanged, per Task 4's combined-feed design; only the page identity/nav key changes here.) Also update the `data-dashboard-page` attribute on line 16 from `data-dashboard-page="newsletters"` to `data-dashboard-page="notifications"` — Task 4's JS keys off this attribute.

- [ ] **Step 6: Add the `side.notifications` i18n key**

In `static/js/i18n-data.js`, in the `en` block, add a new line right after `'side.newsletters': 'Newsletters',` (line 93):

```js
            'side.newsletters': 'Newsletters',
            'side.notifications': 'Notification',
```

Leave the other 11 language blocks' `side.newsletters` entries untouched — `i18n.js`'s `translate()` (`static/js/i18n.js:74-80`) already falls back to English for a key missing in a non-English table, so `side.notifications` renders correctly as "Notification" in every language until someone translates it.

- [ ] **Step 7: Regenerate per-language files**

Run: `python scripts/split_i18n_data.py`
Expected: exits 0, updates files under `static/js/i18n/`.

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m pytest tests/test_public.py -k "notifications_page_loads or newsletters_path_redirects" -v`
Expected: PASS

- [ ] **Step 9: Run the full test suite**

Run: `python -m pytest -q`
Expected: no new failures (pre-existing unrelated failures noted earlier this session — `test_dashboard_redirects_to_welcome_when_no_club`, `test_welcome_page_shows_for_user_without_club`, `test_dashboard_subpages_redirect_to_welcome_when_no_club` — are fine to still see; anything newsletters/notifications-related must pass).

- [ ] **Step 10: Commit**

```bash
git add src/routes_web.py src/helpers.py templates/dashboard/notifications.html static/js/i18n-data.js static/js/i18n/ tests/test_public.py
git status  # confirm templates/dashboard/newsletters.html shows as deleted/renamed
git commit -m "feat: rename Newsletters page to Notification, redirect old path"
```

---

### Task 4: Merge notifications into the Notification page feed + unread nav badge

**Files:**
- Modify: `templates/dashboard/notifications.html` (was `newsletters.html`)
- Modify: `static/js/dashboard.js` (`renderNewsletters`/`renderNewsletterReader`, `~1253-1291`; page-name checks; `renderPage()` at `~1619-1633`)
- Modify: `templates/dashboard_layout.html` (add badge anchor to the Notification nav link)
- Modify: `static/css/dashboard.css` (badge positioning on the nav link)

**Interfaces:**
- Consumes: `dashboardState.notifications` (existing, `id/type/title/message/data/read/createdAt`) and `dashboardState.newsletters` (existing, `id/title/excerpt/body/date/readTime/read`).
- Produces: `renderNotificationFeed()` (replaces `renderNewsletters`), used only internally — no other task depends on its internals, only on it being called from `renderPage()`.

- [ ] **Step 1: Rename the page-check and function to match Task 3's renamed page**

In `static/js/dashboard.js`, `renderNewsletters()` currently opens with `if (page !== 'newsletters') return;` (line 1254) — since `data-dashboard-page` is now `"notifications"` (Task 3 Step 5), rename the function and this check. Replace the whole `renderNewsletters` function (lines 1253-1277) with:

```javascript
    function renderNotificationFeed() {
        if (page !== 'notifications') return;
        removeSkeletons('newsletters');
        const list = $('#newsletterList');
        const archive = notificationFeedItems();
        const prefs = settings();
        if (!selectedNewsletterId && archive.length) {
            selectedNewsletterId = archive[0].id;
        }
        $('#newsletterSubscribe').checked = Boolean(prefs.newsletterSubscribed);

        if (list) {
            list.innerHTML = archive.map((item, index) => `
                <button class="newsletter-row ${item.id === selectedNewsletterId ? 'active' : ''}" type="button" data-open-dispatch="${escapeHtml(item.id)}" style="--card-index: ${index}">
                    <span class="read-dot ${item.read ? 'read' : ''}" aria-hidden="true"></span>
                    <span>
                        <strong>${escapeHtml(item.title)}</strong>
                        <small>${escapeHtml(item.excerpt)}</small>
                    </span>
                    <em>${escapeHtml(item.readLabel)}</em>
                </button>
            `).join('');
        }
        renderNotificationReader();
        updateNotificationsNavBadge(archive);
    }

    // Merges the two independent state sections into one chronological feed
    // for display only — `notifications` and `newsletters` stay separate in
    // storage. `kind` tells the reader pane and the read/unread toggle which
    // shape (and which API endpoint) a given row is.
    function notificationFeedItems() {
        const dispatchRows = newsletters().map((n) => ({
            kind: 'dispatch',
            id: n.id,
            title: n.title,
            excerpt: n.excerpt,
            body: n.body,
            readLabel: n.readTime,
            read: Boolean(n.read),
            sortKey: n.date || '',
        }));
        const notificationRows = (dashboardState.notifications || []).map((n) => ({
            kind: 'notification',
            id: n.id,
            title: n.title,
            excerpt: n.message,
            body: n.message,
            readLabel: formatRelativeTime(n.createdAt),
            read: Boolean(n.read),
            sortKey: n.createdAt || '',
        }));
        return dispatchRows.concat(notificationRows).sort((a, b) => (b.sortKey || '').localeCompare(a.sortKey || ''));
    }

    function renderNotificationReader() {
        const item = notificationFeedItems().find((row) => row.id === selectedNewsletterId);
        const button = $('#toggleReadButton');
        if (!item) return;
        $('#newsletterReadTime').textContent = item.readLabel || (item.kind === 'dispatch' ? 'Dispatch' : 'Notification');
        $('#newsletterTitle').textContent = item.title || 'Untitled';
        $('#newsletterDate').textContent = item.kind === 'dispatch'
            ? formatDate(newsletters().find((n) => n.id === item.id)?.date)
            : item.readLabel;
        $('#newsletterBody').textContent = item.body || item.excerpt || '';
        if (button) {
            button.hidden = false;
            button.textContent = item.read ? 'Mark unread' : 'Mark read';
        }
    }

    function updateNotificationsNavBadge(feedItems) {
        const link = $('#sidebarNotificationsLink');
        if (!link) return;
        let badge = link.querySelector('.notification-badge');
        const unread = feedItems.filter((row) => !row.read).length;
        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'notification-badge';
            badge.setAttribute('aria-hidden', 'true');
            link.appendChild(badge);
        }
        badge.textContent = unread > 9 ? '9+' : String(unread);
        badge.style.display = unread > 0 ? 'flex' : 'none';
    }
```

`formatRelativeTime` already exists (`static/js/dashboard.js:2871-2886`, from the old notification-center code) — keep that function as-is; Task 5 does not remove it since this feed now depends on it.

- [ ] **Step 2: Update the two call sites that referenced `renderNewsletters`**

In `static/js/dashboard.js`:
- Line 1630 (inside `renderPage()`): change `renderNewsletters();` to `renderNotificationFeed();`.
- Line 2098 (inside the dispatch-submit success handler): change `renderNewsletters();` to `renderNotificationFeed();`.

- [ ] **Step 3: Give the sidebar Notification link an id for the badge**

In `templates/dashboard_layout.html`, on the Notification `<a>` added in Task 1 Step 1, add `id="sidebarNotificationsLink"`:

```html
                <a href="/dashboard/notifications" id="sidebarNotificationsLink"
                    class="dashboard-sidebar-link {% if current_path == '/dashboard/notifications' %}active{% endif %}"
                    title="Notification" aria-label="Notification"
                    data-i18n-attr="title:side.notifications;aria-label:side.notifications">
```

- [ ] **Step 4: CSS — position the badge on the nav link**

In `static/css/dashboard.css`, add after the `.dashboard-sidebar-link` rules from Task 1:

```css
#sidebarNotificationsLink {
    position: relative;
}

#sidebarNotificationsLink .notification-badge {
    top: 4px;
    right: 4px;
}
```

(`.notification-badge`'s base styling — size, color, animation — already exists at `dashboard.css:2758-2776` and is reused as-is; this just overrides its anchor position for the collapsed 46px-wide link. When the sidebar is hovered and the link widens, the badge stays pinned near the icon since `top`/`right` are relative to the link's own box, not the icon.)

- [ ] **Step 5: Add a "Mark all read" button to the page**

The old popover had `#markAllReadBtn` in its header (deleted in Task 5). Give the Notification page its own, with a different id to avoid any collision before Task 5 removes the old one. In `templates/dashboard/notifications.html`, in the `.panel-heading` div (currently just the "Leader dispatches" heading + the leader-only subscribe toggle), add the button before the closing `</div>`:

```html
        <div class="panel-heading">
            <div>
                <h2 data-i18n="newsletters.leaderDispatches">Leader dispatches</h2>
                <p data-i18n="newsletters.dispatchesDesc">Open, mark, and draft updates from one archive.</p>
            </div>
            <button class="icon-button" type="button" id="notificationsMarkAllReadBtn" aria-label="Mark all as read"
                data-i18n-attr="aria-label:notifications.markAllRead">
                {{ sidebar_icon('checkmark-all', 16) }}
            </button>
            {% if is_leader %}
            <label class="toggle-compact">
                <span data-i18n="newsletters.subscribed">Subscribed</span>
                <span class="toggle-switch">
                    <input type="checkbox" id="newsletterSubscribe">
                    <span class="toggle-slider"></span>
                </span>
            </label>
            {% endif %}
        </div>
```

In `static/js/dashboard.js`, wire it right after the existing `$('#toggleReadButton')?.addEventListener(...)` block (ends line 2496):

```javascript
        $('#notificationsMarkAllReadBtn')?.addEventListener('click', markAllNotificationsRead);
```

- [ ] **Step 6: Branch the read/unread handlers on row `kind`**

Two existing handlers assume every open/read-toggle targets a dispatch and always `PATCH /api/dashboard/newsletters/<id>` — they need to call `/api/dashboard/notifications/<id>` instead when the row is a notification. In `static/js/dashboard.js`, replace the `data-open-dispatch` branch inside the document click handler (lines 2094-2109):

```javascript
            const dispatchRow = event.target.closest('[data-open-dispatch]');
            if (dispatchRow) {
                selectedNewsletterId = dispatchRow.dataset.openDispatch;
                const feedItem = notificationFeedItems().find((row) => row.id === selectedNewsletterId);
                renderNotificationFeed();
                if (feedItem && !feedItem.read) {
                    const endpoint = feedItem.kind === 'notification'
                        ? `/api/dashboard/notifications/${feedItem.id}`
                        : `/api/dashboard/newsletters/${feedItem.id}`;
                    try {
                        await apiRequest(endpoint, { method: 'PATCH', body: { read: true } });
                    } catch (error) {
                        showToast(error.message, 'error');
                    }
                }
            }
```

And replace the `#toggleReadButton` handler (lines 2484-2496):

```javascript
        $('#toggleReadButton')?.addEventListener('click', async () => {
            const feedItem = notificationFeedItems().find((row) => row.id === selectedNewsletterId);
            if (!feedItem) return;
            const endpoint = feedItem.kind === 'notification'
                ? `/api/dashboard/notifications/${feedItem.id}`
                : `/api/dashboard/newsletters/${feedItem.id}`;
            try {
                await apiRequest(endpoint, { method: 'PATCH', body: { read: !feedItem.read } });
                showToast(feedItem.read ? 'Marked unread.' : 'Marked read.');
            } catch (error) {
                showToast(error.message, 'error');
            }
        });
```

- [ ] **Step 7: Verify in browser**

Trigger a notification (e.g. RSVP to an event, or have an admin approve a shipped project — both already call `add_in_app_notification`). Confirm:
- The badge appears on the sidebar's Notification icon (collapsed state) showing the unread count.
- Opening `/dashboard/notifications` shows both dispatches and the new notification in one list, sorted newest-first.
- Clicking a notification row opens it in the reader pane and marks it read (badge count drops); clicking a dispatch row still works the same way.
- The "Mark read/unread" button in the reader pane works for both kinds.
- "Mark all read" clears every unread row and the nav badge disappears.
- Composing a new dispatch (leader) still works and the new dispatch appears in the merged feed.

- [ ] **Step 8: Commit**

```bash
git add static/js/dashboard.js templates/dashboard_layout.html static/css/dashboard.css
git commit -m "feat: merge notifications into the Notification page feed with nav badge"
```

---

### Task 5: Remove the header notification bell and popover

**Files:**
- Modify: `templates/dashboard_layout.html` (header bell block `~199-206`, notification-center + backdrop `~246-258`)
- Modify: `static/js/dashboard.js` (delete popover-only functions)

**Interfaces:**
- Consumes: Task 4's `updateNotificationsNavBadge` (already the sole source of unread-count UI).

- [ ] **Step 1: Remove the bell button from the header**

In `templates/dashboard_layout.html`, delete this block from `<header class="dashboard-header">` (originally lines 200-206, immediately before the coin chip block Task 2 already removed):

```html
                    {% if current_user %}
                    <button class="icon-button notification-bell" id="notificationBell" type="button"
                        aria-label="Notifications" data-i18n-attr="aria-label:notifications.title">
                        {{ sidebar_icon('bell') }}
                        <span class="notification-badge" id="notificationBadge" aria-hidden="true"></span>
                    </button>
                    {% endif %}
```

- [ ] **Step 2: Remove the notification-center popover and backdrop**

In `templates/dashboard_layout.html`, delete (originally lines 246-258):

```html
    <!-- Notification Center -->
    <div class="notification-center" id="notificationCenter" aria-hidden="true" role="dialog"
        aria-label="Notifications">
        <div class="notification-center-header">
            <h2 data-i18n="notifications.title">Notifications</h2>
            <button class="icon-button" type="button" id="markAllReadBtn" aria-label="Mark all as read"
                data-i18n-attr="aria-label:notifications.markAllRead">
                {{ sidebar_icon('checkmark-all', 16) }}
            </button>
        </div>
        <div class="notification-center-list" id="notificationCenterList"></div>
    </div>
    <div class="notification-center-backdrop" id="notificationCenterBackdrop" aria-hidden="true"></div>
```

- [ ] **Step 3: Delete the popover-only JS functions**

In `static/js/dashboard.js`, delete `renderNotificationCenter`, `getNotificationIcon`, `openNotificationCenter`, `closeNotificationCenter`, `handleNotificationCenterKeydown` (roughly lines 2821-2927). Also delete `updateNotificationBadge` (lines 2805-2819) — it only ever touched `#notificationBadge`/`#notificationBell`, both deleted in Step 1; Task 4's `updateNotificationsNavBadge` already replaced its job.

`markAllNotificationsRead` (lines 2950-2975, wired to Task 4's new "Mark all read" button) currently calls the two functions just deleted. Replace its body:

```javascript
    function markAllNotificationsRead() {
        const wasUnread = new Set();
        notifications.forEach(notif => {
            if (!notif.read) {
                notif.read = true;
                wasUnread.add(notif.id);
            }
        });
        const changed = wasUnread.size > 0;

        if (!changed) return;
        renderNotificationFeed();

        apiRequest('/api/dashboard/notifications/mark-all-read', {
            method: 'PATCH',
        }).catch((error) => {
            // Put the unread flags back rather than leaving the badge lying.
            notifications.forEach((notif) => {
                if (wasUnread.has(notif.id)) notif.read = false;
            });
            renderNotificationFeed();
            showToast(error.message || 'Could not mark all as read.', 'error');
        });
    }
```

`markNotificationRead` (lines 2929-2948) is no longer called from anywhere — Task 4 Step 5's row click handler and toggle-read button do their own inline `apiRequest` calls covering both dispatch and notification rows. Delete `markNotificationRead` entirely.

Replace `initNotificationCenter` (lines 2977-3003) with a trimmed version that only loads data (no popover wiring):

```javascript
    function initNotificationData() {
        loadNotifications();
    }
```

And update its call site at line 3028 from `initNotificationCenter();` to `initNotificationData();`.

`loadNotifications` itself (lines 2797-2803) currently calls `updateNotificationBadge()` and, if the popover is open, `renderNotificationCenter()` — simplify it to just refresh the merged feed when the Notification page is the active page:

```javascript
    function loadNotifications() {
        notifications = Array.isArray(dashboardState.notifications)
            ? dashboardState.notifications
            : [];
        if (page === 'notifications') renderNotificationFeed();
    }
```

- [ ] **Step 4: Verify in browser**

Confirm the header no longer shows a bell icon anywhere. Confirm the unread badge still shows correctly on the sidebar Notification link (Task 4). Confirm no console errors from missing `#notificationBell`/`#notificationCenter` elements on any dashboard page.

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest -q`
Expected: same pass/fail set as Task 3 Step 9 (no new failures).

- [ ] **Step 6: Commit**

```bash
git add templates/dashboard_layout.html static/js/dashboard.js
git commit -m "feat: remove header notification bell, now redundant with the Notification page"
```
