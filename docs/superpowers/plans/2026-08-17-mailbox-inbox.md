# Notifications Mailbox Inbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `/dashboard/notifications` into a Gmail-style inbox — toolbar with All/Unread filters, search, select-all, and mark-all-read; flat checkboxed message rows; sender/date message view in the reading pane. Feed, APIs, and data models unchanged.

**Architecture:** Client-side only. Vanilla JS state (filter, query, selection Set) over the existing merged feed (`notificationFeedItems()`), fan-out bulk read to existing per-item PATCH endpoints. No backend changes.

**Tech Stack:** Jinja template, vanilla JS (`static/js/dashboard.js`), plain CSS (`static/css/dashboard.css`). No new dependencies.

## Global Constraints

- No backend/storage/schema changes. No new API endpoints.
- Keep every element id the existing JS/tour/tests reference: `newsletterList`, `newsletterReader`, `newsletterReadTime`, `newsletterTitle`, `newsletterDate`, `newsletterBody`, `toggleReadButton`, `notificationsMarkAllReadBtn`, `newsletterSubscribe`, `dispatchModal`.
- Keep `data-i18n`/`data-i18n-attr` coverage. New keys go in `en.js` only; other languages fall back to template English by design.
- Row clicks keep working through the existing `data-open-dispatch` delegation — checkboxes must not open rows.
- JS-rendered row strings follow the file's existing pattern (English literals + `escapeHtml`), same as current `renderNotificationFeed`.

---

### Task 1: Template — mailbox layout

**Files:**
- Modify: `templates/dashboard/notifications.html:17-55`

- [ ] **Step 1: Replace the two-card block with the mailbox shell**

Replace `.newsletter-layout` content block (lines 17-55) with:

```html
<div class="dashboard-page mailbox" data-dashboard-page="notifications">
    <div class="skeleton-block" data-skeleton="newsletters" style="padding:20px;">
      <div class="skeleton skeleton-heading"></div>
      <div class="skeleton skeleton-text medium"></div>
      <div class="skeleton skeleton-card"></div>
      <div class="skeleton skeleton-card" style="margin-top:12px;"></div>
      <div class="skeleton skeleton-card" style="margin-top:12px;"></div>
    </div>
    <section class="card-modern dashboard-panel mailbox-panel">
        <header class="mailbox-toolbar">
            <div class="mailbox-tabs" role="tablist" aria-label="Filter">
                <button class="mailbox-tab active" type="button" data-mail-filter="all" role="tab" aria-selected="true" data-i18n="newsletters.all">All</button>
                <button class="mailbox-tab" type="button" data-mail-filter="unread" role="tab" aria-selected="false" data-i18n="newsletters.unread">Unread</button>
            </div>
            <input class="mailbox-search" type="search" id="mailboxSearch" placeholder="Search messages" data-i18n-attr="placeholder:newsletters.searchPlaceholder">
            <label class="mailbox-check mailbox-check-header" title="Select all" data-i18n-attr="title:newsletters.selectAll">
                <input type="checkbox" id="mailSelectAll" aria-label="Select all" data-i18n-attr="aria-label:newsletters.selectAll">
            </label>
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
        </header>
        <div class="mailbox-bulkbar" id="mailBulkBar" hidden>
            <span id="mailBulkCount"></span>
            <button class="btn-secondary" type="button" id="mailBulkMarkRead" data-i18n="newsletters.markRead">Mark read</button>
        </div>
        <div class="mailbox-list" id="newsletterList"></div>
    </section>

    <aside class="card-modern dashboard-panel mailbox-reader" id="newsletterReader">
        <span class="badge badge-up" id="newsletterReadTime" data-i18n="newsletters.archive">Archive</span>
        <p class="mailbox-sender" id="newsletterSender"></p>
        <h2 id="newsletterTitle" data-i18n="newsletters.selectDispatch">Select a dispatch</h2>
        <p class="mailbox-date" id="newsletterDate" data-i18n="newsletters.noMessageOpen">No message open.</p>
        <p id="newsletterBody" data-i18n="newsletters.chooseDispatch">Choose a dispatch from the archive to read it here.</p>
        <button class="btn-secondary" type="button" id="toggleReadButton" hidden data-i18n="newsletters.markRead">Mark read</button>
    </aside>
</div>
```

Notes: keep the skeleton block and the dispatch modal exactly as they are;
`data-dashboard-page="notifications"` stays (routing + `removeSkeletons('newsletters')` depend on it).

### Task 2: JS — feed rendering + selection state

**Files:**
- Modify: `static/js/dashboard.js`

- [ ] **Step 1: Add mailbox state next to `selectedNewsletterId`**

Where `selectedNewsletterId` is declared (module-level let near the top of
the IIFE), add:

```javascript
let mailboxFilter = 'all';
let mailboxQuery = '';
const selectedMailIds = new Set();
```

- [ ] **Step 2: Add a kind label helper + notification type label map**

Next to `notificationFeedItems()` (currently line 1723), add:

```javascript
const NOTIFICATION_TYPE_LABELS = {
    event_rsvp: 'Event RSVP',
    workshop_application: 'Workshop application',
    workshop_scheduled: 'Workshop scheduled',
    project_submitted: 'Project submitted',
    project_reviewed: 'Project reviewed',
    order_placed: 'Order placed',
};

function mailboxKindLabel(item) {
    if (item.kind === 'dispatch') return 'Leader dispatch';
    return NOTIFICATION_TYPE_LABELS[item.type] || 'Notification';
}
```

`notificationFeedItems()` must pass `type` through for notification rows
(add `type: n.type` to the notification row mapping).

- [ ] **Step 3: Rewrite `renderNotificationFeed()` (lines 1692-1717)**

New behavior:
1. Compute `archive = notificationFeedItems()`, then `visible` = rows
   matching `mailboxFilter` (`'unread'` → `!row.read`) and `mailboxQuery`
   (case-insensitive match on `title`/`excerpt`).
2. Default-select first *visible* row when `selectedNewsletterId` isn't in
   `visible` and `visible.length > 0`.
3. Render toolbar state: `#mailSelectAll.checked` tri-state
   (`checked` when all visible selected, `indeterminate` when some).
4. Render rows:

```html
<button class="mailbox-row [active] [unread]" type="button"
    data-open-dispatch="<id>" style="--card-index: i">
  <span class="mailbox-check" role="checkbox"?><input type="checkbox"
      data-mail-check="<id>" aria-label="Select message"></span>
  <span class="read-dot" aria-hidden="true"></span>
  <span class="mailbox-row-main">
    <strong><kind label> · <title></strong>
    <small><snippet></small>
  </span>
  <em class="mailbox-row-time"><time label></em>
</button>
```

Checkbox gets `checked` when id ∈ `selectedMailIds`. Row gets `.active`
when selected-for-reading, `.unread` when `!item.read` (replaces the
old `read-dot.read` toggling — keep the dot element for visual parity).
5. Show/hide `#mailBulkBar` + set `#mailBulkCount` ("N selected") when
   `selectedMailIds.size > 0` (prune ids no longer in `visible` first).
6. Keep `renderNotificationReader()` call and
   `updateNotificationsNavBadge(archive)` at the end (badge uses the full
   unfiltered archive).

- [ ] **Step 4: Update `renderNotificationReader()` (lines 1747-1761)**

Set `#newsletterSender` to `mailboxKindLabel(item)` and hide it while the
placeholder state is showing (i.e. when no item, clear it). Rest unchanged.

- [ ] **Step 5: Guard the row-click delegation (line 3164)**

At the top of the `dispatchRow` branch (before selecting), add:

```javascript
if (event.target.closest('[data-mail-check]')) return;
```

- [ ] **Step 6: Wire new toolbar events (near the existing handlers, ~line 3605)**

```javascript
$$('.mailbox-tab').forEach((tab) => tab.addEventListener('click', () => {
    $$('.mailbox-tab').forEach((t) => { t.classList.toggle('active', t === tab); t.setAttribute('aria-selected', t === tab ? 'true' : 'false'); });
    mailboxFilter = tab.dataset.mailFilter;
    renderNotificationFeed();
}));

$('#mailboxSearch')?.addEventListener('input', (event) => {
    mailboxQuery = event.currentTarget.value.trim().toLowerCase();
    renderNotificationFeed();
});

$('#mailSelectAll')?.addEventListener('change', (event) => {
    const checked = event.currentTarget.checked;
    visibleMailItems().forEach((row) => {
        if (checked) selectedMailIds.add(row.id); else selectedMailIds.delete(row.id);
    });
    renderNotificationFeed();
});

$('#newsletterList')?.addEventListener('change', (event) => {
    const checkbox = event.target.closest('[data-mail-check]');
    if (!checkbox) return;
    if (checkbox.checked) selectedMailIds.add(checkbox.dataset.mailCheck);
    else selectedMailIds.delete(checkbox.dataset.mailCheck);
    renderNotificationFeed();
});

$('#mailBulkMarkRead')?.addEventListener('click', bulkMarkSelectedRead);
```

- [ ] **Step 7: Add `visibleMailItems()` + `bulkMarkSelectedRead()`**

```javascript
function visibleMailItems() {
    const q = mailboxQuery.trim().toLowerCase();
    return notificationFeedItems().filter((row) => {
        if (mailboxFilter === 'unread' && row.read) return false;
        if (q && !`${row.title} ${row.excerpt}`.toLowerCase().includes(q)) return false;
        return true;
    });
}

async function bulkMarkSelectedRead() {
    const items = visibleMailItems().filter((row) => selectedMailIds.has(row.id));
    const requests = items.map((item) => {
        const endpoint = item.kind === 'notification'
            ? `/api/dashboard/notifications/${item.id}`
            : `/api/dashboard/newsletters/${item.id}`;
        return apiRequest(endpoint, { method: 'PATCH', body: { read: true } });
    });
    try {
        await Promise.all(requests);
        selectedMailIds.clear();
        renderNotificationFeed();
        showToast(items.length ? `${items.length} message(s) marked read.` : 'Nothing selected.');
    } catch (error) {
        showToast(error.message, 'error');
    }
}
```

Place both near `markAllNotificationsRead()` (~line 3975).

- [ ] **Step 8: Clear selection when filters/search hide rows**

`renderNotificationFeed()` prunes `selectedMailIds` against `visible`
(Step 3.5) — the only cleanup needed. No other state migration.

### Task 3: CSS — mailbox styles

**Files:**
- Modify: `static/css/dashboard.css`

- [ ] **Step 1: Replace the newsletters block (lines 2593-2683)**

Delete `.newsletter-list`, `.newsletter-row*`, `.read-dot*`,
`.newsletter-reader*` rules and add (variables only, no hard-coded palette):

- `.mailbox` → reuse the existing shared two-column grid.
- `.mailbox-panel` → `grid-column: 1; min-width: 0`.
- `.mailbox-toolbar` → flex, wrap, gap 8-10px, padding, bottom border.
- `.mailbox-tabs` / `.mailbox-tab` → pill chips; `.active` uses
  `--hackclub-red` + white text.
- `.mailbox-search` → form-input-like, flex-grow, min-width ~160px.
- `.mailbox-check` → checkbox column, 18px input, centered.
- `.mailbox-list` → no gap; rows divide with `border-bottom`.
- `.mailbox-row` → grid `24px 12px minmax(0,1fr) auto`, flat background,
  hover/active tint via `--dash-fill`/`--dash-card`, no translate/box-shadow
  card effect. `.unread strong` bold + full `--dash-ink`; read rows get
  muted title weight.
- `.mailbox-row small` → 2-line clamp (keep existing clamp code).
- `.mailbox-row-time` → muted, nowrap, 12px.
- `.mailbox-bulkbar` → sticky under toolbar, flex, gap, red-tinted
  background, `[hidden]` respected.
- `.mailbox-reader` → `grid-column: 2; position: sticky; top: 104px;`
  gap 14px; `h2` keeps the existing reader typography (28px title font).
- `.mailbox-sender` → small caps/bold muted label; `.mailbox-date` → muted
  13px.
- `.read-dot` rules → keep class name (used by rows + reader) but restyle as
  a unread-only indicator: red when parent `.unread`, transparent/gone when
  read.

- [ ] **Step 2: Update shared grid selectors**

`dashboard.css:2087` `.shop-layout, .newsletter-layout, .settings-layout` →
replace `.newsletter-layout` with `.mailbox`; `2094`
`.newsletter-list-panel` → `.mailbox-panel`; `2100` `.newsletter-reader` →
`.mailbox-reader`. Same three renames inside the `@media (max-width: 980px)`
block at `3876-3892`.

- [ ] **Step 3: Responsive pass**

In the `980px` block the reader already drops to `grid-column: 1` and
static positioning. Add at `≤768px` (existing breakpoint block): toolbar
search full-width wrap, hide `.mailbox-check-header`/time column if needed
(simple: `.mailbox-row { grid-template-columns: 22px 12px minmax(0,1fr); }`
and `.mailbox-row-time { display:none; }` — verify against the existing
768px block before adding).

### Task 4: Tour + i18n

**Files:**
- Modify: `static/js/tour-steps.js:162`
- Modify: `static/js/i18n/en.js` (newsletters section)

- [ ] **Step 1: Tour target** — `.newsletter-list-panel` → `.mailbox-panel`.

- [ ] **Step 2: en.js keys** — add next to the existing `newsletters.*` keys:

```javascript
'newsletters.all': "All",
'newsletters.unread': "Unread",
'newsletters.searchPlaceholder': "Search messages",
'newsletters.selectAll': "Select all",
'newsletters.selected': "{count} selected",
```

Other language files intentionally untouched — `i18n.js` falls back to the
English template text for missing keys.

### Task 5: Verification

- [ ] `pytest tests/test_notifications.py tests/test_public.py -q`
- [ ] Ruff on touched Python files (none — backend untouched; skip if no py
      changes).
- [ ] Manual browser pass: load `/dashboard/notifications` in light+dark,
      leader + member roles; verify filters, search, select-all tri-state,
      bulk mark-read toast + badge update, row click opens reader + marks
      read, compose modal still works, mobile ≤980px stacking, ≤768px row
      compacting, tour step still highlights the panel.
