# Sidebar redesign + notifications-into-newsletters

Date: 2026-08-10

## Summary

Two related dashboard-chrome changes:

1. The left sidebar rail expands on hover to reveal page labels, and its bottom profile avatar becomes a card showing name, club, coin balance, and sign-out.
2. The standalone notification bell + popover is removed. Notifications merge into the Newsletters page, which is renamed "Notification" and shows a single combined feed of leader dispatches and system notifications.

## 1. Sidebar hover-expand

**Mechanism.** `.dashboard-sidebar` keeps its 76px flex track permanently (no reflow of `.dashboard-main`). Its content is wrapped in a new `.dashboard-sidebar-panel` — `position: absolute; inset: 0; width: 76px; overflow: hidden` — which widens to ~232px on `.dashboard-sidebar:hover .dashboard-sidebar-panel` via a `width` transition, with `z-index` above `.dashboard-main`. Same box-shadow/rounded-corner language the rail already has (`static/css/dashboard.css:125-145`), so it floats over the page rather than pushing it.

**Labels.** Every `<a class="dashboard-sidebar-link">` in `templates/dashboard_layout.html` (both `.dashboard-sidebar-nav` groups) gets a `<span class="sidebar-label" data-i18n="...">` after its icon, reusing the exact `data-i18n` key already on that link's `title` attribute (e.g. `side.home`, `side.team`). No new i18n keys for this part. Labels are `width:0; opacity:0` collapsed, revealing past ~120px of the expand transition so text doesn't clip mid-word.

**Profile card.** `.sidebar-profile` (currently just an avatar image/fallback linking to `/dashboard/profile`) gains a sibling `.sidebar-profile-card`, revealed by the same hover expansion:

```
avatar (existing img / .sidebar-profile-fallback)
.sidebar-profile-card
  .sidebar-profile-name   → current_user.name
  .sidebar-profile-sub    → "{settings.clubName} · {viewer role}"  e.g. "Hack the Seas · Leader"
  .sidebar-profile-meta
    coin pill: <img src=".../coin.svg"> + <span id="coinBalanceAmount">   (moved here from the header)
    sign-out icon button → url_for('sign_out')   (new 'exit' icon added to templates/partials/icons.html)
```

The avatar/name area still links to `/dashboard/profile`; sign-out is a distinct small icon link so the two click targets don't fight.

**Header cleanup.** `.coin-balance-chip` is deleted from `<header class="dashboard-header">` in `dashboard_layout.html` — coin balance now lives only in the sidebar card. `#coinBalanceAmount` keeps its `id`, so `renderCoinBalance()` (`static/js/dashboard.js:1015-1018`, called from the global `renderPage()` pipeline) needs no changes.

**Mobile.** Untouched. The `@media (max-width: 768px)` rail-becomes-bottom-bar rules (`dashboard.css:3058-3103`) already exist and hover doesn't apply on touch, so mobile keeps the current icon-only bottom bar.

## 2. Notifications fold into a renamed "Notification" page

**Bell removal.** The header's notification bell button, badge, and the entire `#notificationCenter` popover + backdrop are deleted from `dashboard_layout.html`. The corresponding JS in `static/js/dashboard.js` (`loadNotifications`, `updateNotificationBadge`, `renderNotificationCenter`, `getNotificationIcon`, `openNotificationCenter`, `closeNotificationCenter`, `markNotificationRead`, `markAllNotificationsRead`, and their event wiring — roughly lines 2791-2998) is removed or repointed to the new page (see below). No nav icon is added for notifications — per your call, there's no persistent bell anywhere.

**Unread indicator.** Since the bell is gone, the unread count moves to the sidebar's Notification nav link itself: a small dot/count badge (reusing the existing `.notification-badge` CSS) anchored to that `<a class="dashboard-sidebar-link">`, shown only when `unread > 0`. It's driven by the same `dashboardState.notifications` the old badge used — just a different anchor element.

**Route rename.** `/dashboard/newsletters` becomes `/dashboard/notifications` (endpoint `dashboard_notifications` in `src/routes_web.py`), with a redirect kept at the old path in case anything still links to it. The sidebar link's `data-i18n` keys change from `side.newsletters` to `side.notifications` (new key, English: "Notification"), and `templates/dashboard/newsletters.html` → `templates/dashboard/notifications.html`, with `page_title`/`page_subtitle` blocks updated to match.

**Combined feed.** Both underlying data models stay as they are — `notifications` (`id, type, title, message, data, read, createdAt` — `src/notifications.py:40-47`) and `newsletters`/dispatches (`id, title, excerpt, body, date, readTime, read` — `src/helpers.py:568-596`) are separate state sections and separate storage collections. No backend/storage schema change. The page's JS merges the two arrays client-side into one list for display, tagging each row with `kind: 'notification' | 'dispatch'` and sorting by timestamp (`createdAt` vs `date`) descending. This reuses the existing master-detail layout already built for newsletters (`#newsletterList` roster + `#newsletterReader` detail pane, `static/js/dashboard.js:1253-1291`): clicking a row opens it in the reader pane regardless of kind, with the reader showing `message`/icon-by-`type` for a notification row and `body`/`readTime` for a dispatch row. Leaders can still compose a new dispatch via the existing "New dispatch" modal — it just appears interleaved with system notifications rather than in a separate archive.

**Read/unread actions.** The existing endpoints (`PATCH /api/dashboard/notifications/<id>`, `PATCH /api/dashboard/notifications/mark-all-read`, `DELETE /api/dashboard/notifications/<id>` in `src/routes_api.py:104-149`) and the dispatch read-toggle (`POST`-based, existing `#toggleReadButton` flow) are unchanged — only which page's markup drives them changes.

## Testing

No storage/backend schema changes. Route rename needs the redirect verified and any test referencing `/dashboard/newsletters` (`tests/test_public.py`, `tests/test_notifications.py` if any path-dependent) updated. Everything else is template/CSS/JS — verified by hand in-browser: collapsed vs hover-expanded sidebar, profile card contents in light/dark mode, combined feed ordering and read/unread state, mark-all-read, dispatch composer, and the mobile bottom-bar breakpoint (untouched, sanity-checked anyway).
