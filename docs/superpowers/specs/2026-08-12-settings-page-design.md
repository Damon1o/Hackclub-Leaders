# Settings page redesign — round 1

## Context

Current `/dashboard/settings` is a flat two-column form (Club profile fields + a
handful of toggles). A new mockup shows a much larger settings surface: one
scrolling page with a sidebar of anchor links jumping to stacked sections —
Club profile, Members, Your account, Appearance, Explore & privacy,
Notifications, Danger zone.

The full mockup implies several subsystems that don't exist in this app yet
(join-request approval queue, Hack Club identity sync for phone/birthday/Slack/
verification, multi-theme appearance, Explore-post moderation, workshop-decision
notifications). This spec covers **round 1 only**: the settings shell plus every
section built with real, working content where the underlying feature already
exists in this codebase, and honest stubs where it doesn't. Net-new subsystems
(join-request approvals, richer identity sync) are follow-up specs.

"Build sandbox" from the mockup is dropped — not part of this app.

## Layout

One scrolling page, not tabs/separate routes. Sidebar items are anchor links
(`#club-profile`, `#members`, `#your-account`, `#appearance`,
`#explore-privacy`, `#notifications`, `#danger-zone`) to sections stacked in
that order on the same page. A small IntersectionObserver-based scrollspy
toggles an `.active` class on the sidebar item matching whichever section is
in view. No server round-trip to switch sections; no new client-side state
machine beyond the scrollspy observer.

Rationale: every other tab in this settings page reuses existing markup moved
into the new layout — there's no need for per-section page loads, and a single
page keeps Save buttons scoped to just the section they belong to (Club
profile and Your account each keep their own form + save button, matching the
mockup).

## Sections

### 1. Club profile (fully built)

Rebuilt to match the mockup:
- Logo upload — reuses the existing generic `input[name="avatar"]`
  auto-upload wiring (`initAvatarUploads` in dashboard.js already attaches an
  upload button + crop modal to any avatar input; no new JS needed).
- Club name, School/venue, Website, Meeting day
- Venue address split into: Address line 1, Address line 2, City, State, ZIP,
  Country (dropdown)
- Short bio (club-level, distinct from the personal-profile bio already on
  `current_user`)
- Save changes / Cancel, same pattern as today

**Data model change:** today `location` is a single free-text string,
referenced by the club map listing, admin table, and CSV export. New fields
replace it as the source of truth: `venue`, `addressLine1`, `addressLine2`,
`city`, `state`, `zip`, `country`, `meetingDay`, `clubBio`. `location` becomes
a derived display string (`city, state`) recomputed on save, so every
existing consumer keeps working unchanged. Touches:
- `helpers.py` — SETTINGS TypedDict + CSV header list
- `storage.py` / `storage_mongo.py` — settings read/write, derived `location`
- `routes_club.py` — `api_settings_update` validation + save
- `routes_admin.py` — admin-side settings edit, same new fields

### 2. Members (real content, partial)

Reuses the existing join-code/invite-link card verbatim (join code display,
copy-invite-link, regenerate-code — already implemented in `routes_club.py`
`api_join_code_refresh` and `dashboard.js` join-link handlers).

"Pending join requests" is a stub: static "No pending join requests right
now." text. The request/approval backend (members request to join and wait
for leader approval, instead of today's instant-join) does not exist and is
**out of scope** for this spec — follow-up spec.

### 3. Your account (new section, stubbed data)

Distinct from `/dashboard/profile` (which stays as the full personal-profile
page — this section is not a replacement).

- **Preferred name** — new field, real and editable, saved like other
  profile fields. "Shown on your profile card. Defaults to your first name."
  Own Save button, scoped to just this field.
- **Full name, Email, Slack, Verification, Phone, Birthday, Mailing address**
  — rendered read-only, labeled "synced from Hack Club and can't be edited
  here." None of this data exists anywhere in the current app (confirmed: no
  `phone`, `birthday`, `slack`, or `verified` field anywhere in `helpers.py`
  or `routes_auth.py`, and there is no persistent per-user record at all
  today — only session cookies and club roster entries). These rows render a
  placeholder ("Not available yet") rather than fabricated values. Wiring to
  Hack Club's identity API (auth.hackclub.com) is a follow-up spec.
- **Hackatime** — reuses the existing connect/manual-ID block already on
  `/dashboard/profile` verbatim.

**Data model change:** `preferredName` added to the new per-user record
described in Danger zone below (needs to persist somewhere; there is no
existing per-user table to add it to).

### 4. Appearance (real content)

Existing Dark mode default toggle, moved here from the old settings page.
The mockup's "Theme: Solid colors" dropdown (multiple background themes) is
out of scope — this app only has light/dark today.

### 5. Explore & privacy (real content)

Existing Public directory toggle, moved here. The mockup's "Require approval
before public" (Explore-post moderation) has no backing feature in this app
— omitted.

### 6. Notifications (real content)

Existing Email notifications + Newsletter subscription toggles, moved here.
The mockup's "review comes back" / "workshop decision" notification rows
have no backing feature yet — omitted, only the two existing toggles ship.

### 7. Danger zone (real content, built for real)

"Sign out everywhere" — genuinely invalidates every other signed-in session,
not just the current browser.

Current sessions are plain Flask signed cookies with no server-side session
store, so there is nothing today to invalidate against. New: a small
per-user record (keyed by lowercased email) added to storage, following the
existing table pattern in `storage.py` / `storage_mongo.py`, holding:
- `preferredName` (see Your account, above)
- `sessionVersion` (int, starts at 0)

The login flow stamps `sessionVersion` into the session cookie at sign-in.
Every authenticated request checks the cookie's stamped version against the
stored value for that email; a mismatch forces sign-out. Clicking "Sign out
everywhere" bumps the stored `sessionVersion`, which invalidates every other
cookie (different stamped version) on their next request, while the
initiating browser gets a fresh session immediately after the bump.

## Error handling

Inline `form-error` element per form section, consistent with existing forms
in this app. Club profile keeps its current required-field checks (Club
name, School/venue) and URL-prefix check (Website). Preferred name gets a
simple required/non-empty check.

## Testing

- Extend existing settings-save tests to cover the new Club profile fields
  and the derived `location` string.
- New test: `location` derivation still produces correct values for the map
  listing / admin table / CSV export.
- New test: session-version bump actually rejects a stale cookie on the next
  request (simulates a second "device").
- New test: Preferred name save round-trips through the new per-user record.
