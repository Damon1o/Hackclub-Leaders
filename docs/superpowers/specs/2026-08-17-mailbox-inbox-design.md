# Notifications page: mailbox inbox design

Date: 2026-08-17

## Goal

Redesign `/dashboard/notifications` from the current two-card
"dispatches + reader" layout into a Gmail-style inbox: one mailbox panel with
a toolbar (filter tabs, search, select-all, mark-all-read), a flat message
list with checkboxes, and a reading pane that shows sender, date, and body.
The existing combined feed (leader dispatches + system notifications merged
client-side) is kept; only presentation and selection affordances change.

## Unchanged

- Data models: `notifications` and `newsletters` remain separate state
  sections and storage collections. No backend/schema changes.
- API endpoints: `GET/PATCH/DELETE /api/dashboard/notifications[...]`,
  `POST/PATCH /api/dashboard/newsletters[...]`, mark-all-read, subscription
  toggle. No new endpoints in this design (bulk actions fan out client-side
  to the existing per-item PATCH endpoints).
- Row click behavior: selecting a row opens it in the reader and marks it
  read via the existing per-kind PATCH.
- Dispatch compose modal, subscribe toggle, unread badge on the sidebar nav
  link, mark-all-read flow.
- English-first i18n: new keys added to `en.js` only; other languages fall
  back to the English template text (existing `i18n.js` mechanism).

## Changes

### 1. Layout: single mailbox panel + reader

`templates/dashboard/notifications.html` replaces the two
`.card-modern` sections (`.newsletter-list-panel` + `.newsletter-reader`)
with:

```
.dashboard-page.mailbox
├── section.mailbox-panel (card-modern dashboard-panel)
│   ├── header.mailbox-toolbar
│   │   ├── .mailbox-tabs (All | Unread filter chips)
│   │   ├── .mailbox-search (text input)
│   │   ├── select-all checkbox (#mailSelectAll)
│   │   ├── mark-all-read icon button (#notificationsMarkAllReadBtn — id kept)
│   │   └── leader: subscribe toggle (#newsletterSubscribe — id kept)
│   ├── .mailbox-bulkbar (hidden; shows when rows are checked)
│   │   ├── "N selected" count
│   │   └── "Mark read" button (#mailBulkMarkRead)
│   └── #newsletterList  (flat rows, border-divided, no per-row cards)
└── aside.mailbox-reader (card-modern dashboard-panel, sticky)
    ├── #newsletterReadTime badge (kind label; kept)
    ├── #newsletterSender (new: "Leader dispatch" / type label)
    ├── #newsletterTitle
    ├── #newsletterDate
    ├── #newsletterBody
    └── #toggleReadButton (kept)
```

All existing element ids used by JS/tour/tests are preserved; the only new
id is `#newsletterSender` (plus toolbar ids above).

### 2. Row anatomy (email-like)

Each `.mailbox-row` (a `<button>` with `data-open-dispatch`, so existing
click wiring is untouched) renders:

```
[checkbox .mailbox-check] [unread dot] [kind label · title (bold when unread)]
                          [snippet (2-line clamp)]
                                              [time (relative for notifications,
                                               readTime for dispatches)]
```

- Unread rows: bold title, red unread dot, `.unread` class.
- Checkbox: `data-mail-check=<id>`, stops propagation so checking does not
  open the row. Select-all toggles all *visible* (filtered) rows.
- Kind label: dispatches → "Leader dispatch"; notifications → human label
  derived from `type` (e.g. `event_rsvp` → "Event RSVP"), fallback
  "Notification".

### 3. Toolbar state (client-side only)

- `mailboxFilter`: `'all' | 'unread'` — tab chips, default `all`.
- `mailboxQuery`: search input, live filters by title + snippet/message
  (case-insensitive substring).
- `selectedMailIds`: `Set` of checked row ids; drives select-all tri-state
  and the bulk bar visibility.
- Bulk "Mark read" fans out to the existing per-item endpoints
  (`/api/dashboard/notifications/<id>` for `kind === 'notification'`,
  `/api/dashboard/newsletters/<id>` for dispatches), then clears selection
  and re-renders. Bulk delete is explicitly out of scope (no dispatch DELETE
  endpoint exists).

### 4. Reader pane (message view)

Gains a sender line: `#newsletterSender` shows the kind label, and
`#newsletterDate` shows the full date for dispatches or the relative time
for notifications (existing behavior, now visually separated from the body).
Body rendering unchanged (`textContent`, already XSS-safe).

### 5. CSS

- Delete the `.newsletter-*` block (`dashboard.css:2593-2683`) and replace
  with `.mailbox*` styles: flat rows with `border-bottom` dividers, toolbar
  chips, search input, checkbox column, bulk bar, sticky reader.
- Update the shared two-column grid selectors (`.newsletter-layout` at
  `2087` and the `980px` media query at `3876`) to `.mailbox`.
- Mobile (`≤980px`): reader drops below list, position static — same as
  today. `≤768px`: toolbar wraps, time column hides if cramped.
- Dark/light via existing CSS variables only; no new palette tokens.

### 6. Tour + tests

- `tour-steps.js:162` target changes from `.newsletter-list-panel` to
  `.mailbox-panel`.
- `tests/test_public.py:467` asserts `id="newsletterList"` — id kept, no
  test change.

## Out of scope

- Bulk delete / per-row delete of dispatches (needs new backend endpoint).
- Folders (Sent/Archive), labels, compose-as-reply.
- Backend search/pagination; filtering is client-side over the already
  loaded feed (≤100 notifications + dispatches).
