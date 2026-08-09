# Workshops: Propose, Apply-to-Run, Schedule, Track

**Date:** 2026-08-09
**Source:** Brainstorm session, following directly from Spec 1 (Coins Spine).
**Scope:** Spec 2 of 9. A club-internal workshop board — members propose topics,
members apply to run them, a leader picks an applicant and schedules it (creating a
linked calendar Event), and a leader later marks it run. Ship review/coin-award, the
Explore feed, and the rest of the coins-economy specs are separate work that builds on
this one.

## Context

This repo has no Workshops feature today — confirmed by grep across `src/`,
`static/js/`, `templates/`, `static/data/`. The only "workshop" surface that exists is
an outbound link off `templates/dashboard/tools.html:31-36` to the external
`workshops.hackclub.com`, a "Workshops access" perk line in
`templates/dashboard/levels.html:46` with no data behind it, and `'Workshop'` used as
the plain default value for `Event.type` (`src/helpers.py:1089`). The real
clubs.hackclub.com product tracks a `Workshops Run` stat tile on the leader dashboard
(noted in `docs/superpowers/specs/2026-08-07-coins-spine-design.md:17`), which this
spec's data model makes possible to compute for the first time in this repo.

Decisions made with Damon:

- **Club-proposed, not an HQ-curated catalog.** Any member can post a workshop topic
  for their own club to run — this is a lightweight internal proposal board, not a
  browsable library of ready-made HQ content (the external `workshops.hackclub.com`
  link on the Tools page is untouched by this spec; it stays as a separate resource).
- **Propose → apply → leader picks → scheduled → run.** Any member proposes a topic;
  any member (including, incidentally, the proposer) can apply to run it; a leader
  picks one applicant, which requires setting a date/time/location and creates a real
  linked `Event`; a leader later marks the scheduled workshop as run. No auto-derived
  "run" state from a passed date — matches this repo's existing pattern of leaders
  manually flipping status (ship approval, item-request approval) rather than any
  date-driven background logic, of which this repo has none today.
- **No coin award.** `award_coins()` already exists (Spec 1) but this spec doesn't call
  it — a workshop-completion reward, if wanted, is a small follow-up once this ships.
  Keeps this spec's surface to proposal/apply/schedule/track only.
- **Status-only filtering** (Proposed / Scheduled / Run) for v1 — no topic/category
  taxonomy to invent or ask a proposer to classify their own idea into.
- **Title + description only** as workshop fields — no duration or materials-link
  field. Both are easy additive follow-ups; neither was asked for.
- **Detail view is a modal**, not a dedicated URL. Nothing else in this dashboard has
  a per-item page — Events' create/edit UI, the only existing multi-field editor, is
  already a `modal-backdrop` overlay on the list page. A new routed detail page would
  be new client-routing infrastructure this app doesn't have, for no functional gain.
- **Adds a 5th home-page stat tile** ("Workshops Run") to the existing
  `sticker-row` in `templates/dashboard.html:30-47`.

## 1. Data model

New `Workshop` TypedDict in `src/helpers.py`, alongside `Event`/`Project`:

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
    createdAt: str          # ISO 8601, for sort order (newest-first, matches notifications)
```

`proposerName`/`runnerName` are denormalized at write time rather than looked up by
email at render time — this mirrors `Project.ownerEmail`/`ownerName`
(`src/helpers.py:58-68`), the existing precedent in this codebase for attributing a
record to a person. `applicants` stays as bare emails (not `{email, name}` pairs):
`members` is always in `ALWAYS_LOADED` (`src/helpers.py:738`), so any page rendering a
workshop already has the full roster in memory to resolve an applicant's name —
denormalizing it a second time into every workshop record would just be a second place
for the same name to go stale.

### Why not fold this into `Event`

`Event.rsvp`/`attendees` already track "who's attending" — `applicants` tracks "who
wants to *teach*," a completely different relationship on a completely different
lifecycle (a workshop can rack up applicants for weeks before any Event exists at all).
Conflating the two would mean an `Event` record with fields that are meaningless until
a workshop-specific state transition happens, and a `status` field whose values
('Proposed', 'Scheduled', 'Run') don't apply to plain meetings/demo days. A separate
entity that *creates* an `Event` once scheduled keeps both models honest and leaves
RSVP working on the resulting Event completely unchanged.

## 2. Storage registration (the five-place pattern, plus the two `PAGE_SECTIONS` mirrors)

Per `docs/superpowers/plans/2026-08-07-coins-spine.md:17`'s "five-place trap" — the
same class of bug that silently dropped `notifications` and `settings.language` on
Airtable — `workshops` must be added everywhere `ledger` was added in Spec 1:

1. `src/helpers.py` — `STATE_SECTIONS` tuple (`src/helpers.py:723-734`): add
   `'workshops'`. `default_dashboard_state()`: seed `'workshops': []`.
2. `src/helpers.py` — `PAGE_SECTIONS` dict (`src/helpers.py:745-759`): add
   `'dashboard_workshops': ('workshops',)`, and add `'workshops'` to the existing
   `'dashboard': ('events', 'projects', 'newsletters')` entry so the home page's new
   stat tile (§7) has data to count without a second request.
3. `src/storage.py` — new `WORKSHOP_FIELDS` list next to `EVENT_FIELDS`
   (`src/storage.py:63-72`) and a `('WORKSHOPS', 'Workshops', 'workshops',
   WORKSHOP_FIELDS)` row in `AirtableStorage.CHILD_TABLES`
   (`src/storage.py:245-257`). `applicants` (a list on a single record) needs the same
   special-cased JSON-text-field treatment `orders.items` already gets
   (`src/storage.py:644-648` load, `736-737` save) — not a plain field in
   `WORKSHOP_FIELDS`, but an `if state_key == 'workshops': item['applicants'] =
   json.loads(fields.get('Applicants') or '[]')` branch alongside the existing
   `orders`/`messages` special cases.
4. `src/storage_mongo.py` — `'workshops'` entry in `CHILD_COLLECTIONS`
   (`src/storage_mongo.py:36-47`) and an `INDEXES` entry indexed by club key +
   `createdAt` descending (matches the `notifications`/`ledger` shape — newest-first
   reads). Mongo is schemaless, so `applicants` needs no special handling there or in
   session-cookie mode — only Airtable's flat-field model needs the JSON encoding.
5. `static/js/dashboard.js` — mirror the `PAGE_SECTIONS` addition in the client-side
   copy (`dashboard.js:201-215`), same two entries as step 2.

A workshop this size is exactly the case the existing `STATE_SECTIONS`/
`CHILD_TABLES`/`CHILD_COLLECTIONS` cross-check tests (added in Spec 1,
`tests/test_coins.py`) are meant to catch — the implementation plan should extend those
same generic tests rather than write workshop-specific duplicates.

## 3. Endpoints

All in `src/routes_api.py`, new `# ── Workshops ──` section, alongside Events:

- **`POST /api/dashboard/workshops`** — any logged-in member (`@login_required`, no
  leader gate — matches "any member proposes"). Body: `{title, description}`, both
  required non-blank (same `clean_text()`/blank-check style as `event_from_payload`,
  no need for a dedicated `_from_payload` helper given there are only two fields and no
  partial-update case that needs an existing-value fallback — see below). Server sets
  `id`, `status: 'Proposed'`, `proposerEmail`/`proposerName` from `session['user']`,
  `applicants: []`, `runnerEmail`/`runnerName`/`eventId: ''`, `createdAt`.

- **`PATCH /api/dashboard/workshops/<id>`** — three payload shapes on one endpoint,
  same overload-by-payload-keys trick `api_events_update` already uses for `rsvp`
  (`src/routes_api.py:286-296`):
  - **`{applying: bool}`** (keys ⊆ `{'applying'}`) — any member, no leader gate. Adds
    or removes `session['user']['email']` from `applicants` (idempotent — setting
    `applying: true` twice is a no-op, not a duplicate). Only valid while
    `status == 'Proposed'`.
  - **`{status: 'Scheduled', runnerEmail, date, time, location}`** — leader-only
    (`require_leader_api()`). `runnerEmail` must already be in `applicants` (400 if
    not — can't schedule someone who never applied). Validates `date`/`time`/`location`
    the same way `event_from_payload` does (non-blank, `date.fromisoformat`). On
    success: looks up `runnerName` from `state['members']`, builds and appends a new
    `Event` (`type: 'Workshop'`, the workshop's `title`, the supplied
    `date`/`time`/`location`, `repeat: ''`, `rsvp: False`, `attendees: 0`), sets the
    workshop's `runnerEmail`/`runnerName`/`eventId`/`status`.
  - **`{status: 'Run'}`** (keys ⊆ `{'status'}`, value `'Run'`) — leader-only. 400 if
    the workshop isn't currently `Scheduled` (can't mark an unscheduled proposal run).

  Auth check mirrors Events exactly: `is_member_apply = set(payload.keys()) <=
  {'applying'}`; if not that shape, require leader.

- **`DELETE /api/dashboard/workshops/<id>`** — leader-only, mirrors
  `api_events_delete` (`src/routes_api.py:328-...`). Lets a leader clean up an
  abandoned or spam proposal; not explicitly requested but low-cost and matches the
  delete capability every other leader-managed list in this app already has (Events,
  Projects via status, item-requests).

No dedicated paginated `GET /api/dashboard/workshops` (unlike Events'
`GET /api/dashboard/events` at `src/routes_api.py:72-78`) — Workshops behaves like a
filterable catalog (closer to Shop, which has no such endpoint either) rather than an
ever-growing chronological feed. The full list rides on the page's own state load via
`PAGE_SECTIONS`; add real pagination later if a club's proposal board actually grows
large enough to need it.

## 4. Notifications

Mirrors the existing RSVP two-channel pattern (`src/notifications.py:34-69`) exactly,
two new functions in `src/notifications.py`:

- **`notify_leaders_of_workshop_application(workshop, applicant_email, applicant_name,
  applying)`** — loops `Leader`/`Mentor` members except the actor, same shape as
  `notify_leaders_of_event_rsvp`: emails each leader and calls
  `add_in_app_notification(leader_email, 'workshop_application', ...)`. Fired from the
  `{applying: bool}` PATCH branch, wrapped in the same `try/except` +
  `current_app.logger.warning` pattern events use (`src/routes_api.py:316-324`) so a
  mail failure never 500s the apply action.
- **`notify_runner_of_workshop_selection(workshop, runner_email, runner_name)`** —
  single email + `add_in_app_notification(runner_email, 'workshop_scheduled', ...)` to
  the person just picked. Fired from the `{status: 'Scheduled', ...}` PATCH branch,
  same try/except wrapping.

Two new render functions in `src/email.py` (`render_workshop_application_notification`,
`render_workshop_scheduled_confirmation`), following whatever template shape
`render_event_rsvp_confirmation` already uses.

## 5. UI

- **Nav** — new sidebar link in `templates/dashboard_layout.html`, inserted between
  Events and Ships (workshop proposals are event-adjacent content), same markup shape
  as the existing Events link (`templates/dashboard_layout.html:103-107`): `href=
  "/dashboard/workshops"`, `data-i18n-attr="title:side.workshops;aria-label:
  side.workshops"`, a new icon. `templates/partials/icons.html` gets one new `'workshop'`
  glyph entry (same one-dict-entry addition Spec 1 made for `'coin'`,
  `templates/partials/icons.html:19`) — a simple flat stroke icon (e.g. an open book or
  presentation-board shape) matching this repo's existing icon style, not copied from
  any external source.
- **Page route** — `src/routes_web.py`: `@app.route('/dashboard/workshops')` /
  `@login_required` (not leader-gated — any member views/applies, matching the Events
  page's gate, not Shop's leader-only gate).
- **Template** — `templates/dashboard/workshops.html`, same shell as
  `templates/dashboard/shop.html`: `{% extends "dashboard_layout.html" %}`,
  `data-dashboard-page="workshops"`, a skeleton block, a status filter-chip row
  (`#workshopFilters`, same `role="tablist"` markup as `#shopFilters` in
  `templates/dashboard/shop.html:36`), a card grid (`#workshopGrid`), a "Propose a
  workshop" button opening a small modal (title + description fields only), and a
  detail `modal-backdrop` (opened on card click) showing the full description, status,
  proposer, and — leader-only — the applicant list with a per-applicant "Schedule"
  action (opens the date/time/location sub-form) or, once `Scheduled`/`Run`, a
  "Mark as run" button.
- **Client JS** (`static/js/dashboard.js`) — `renderWorkshops()` guarded by `if (page
  !== 'workshops') return;`, following `renderShop()`'s shape
  (`static/js/dashboard.js:1030-1096`): a `WORKSHOP_FILTERS = ['All', 'Proposed',
  'Scheduled', 'Run']` client constant, `renderWorkshopFilters()` mirroring
  `renderShopFilters()` (`dashboard.js:1014-1028`), client-side array filtering (no
  network call per filter click, same as Shop), and delegated click handlers for
  `data-apply-workshop`, `data-schedule-workshop`, `data-mark-run`, `data-propose-
  workshop` in the existing single delegated-listener block (`dashboard.js:~1743`
  onward).

## 6. Home page stat tile

`templates/dashboard.html`'s existing `sticker-row` (lines 30-47) gets a 5th
`<div class="sticker">`: count of workshops with `status == 'Run'`, id
`homeWorkshopTotal`, i18n key `home.workshopsRun`. `renderHome()`
(`static/js/dashboard.js:1275-...`) gets one new line: `$('#homeWorkshopTotal')
.textContent = workshops().filter((w) => w.status === 'Run').length;` (a `workshops()`
accessor added alongside the existing `events()`/`orders()`/`shippedProjects()`
accessors). A 5th sticker color variant may need adding to CSS if only 4 exist today —
implementation-detail, confirmed when the plan touches the stylesheet.

## 7. i18n

New `workshops.*` namespace in `static/js/i18n-data.js` (English real copy; other 11
language blocks get the English fallback per this repo's existing convention — see
project memory on i18n data being mostly English placeholders). New keys: `side.
workshops`, `workshops.subtitle`, `workshops.propose`, `workshops.proposeTitle`,
`workshops.titleLabel`, `workshops.descriptionLabel`, `workshops.apply`,
`workshops.withdraw`, `workshops.applicants`, `workshops.schedule`,
`workshops.markRun`, `workshops.filterAria`, `workshops.emptyTitle`,
`workshops.statusProposed`, `workshops.statusScheduled`, `workshops.statusRun`,
`home.workshopsRun`. Edited only in `i18n-data.js`, then regenerated via
`python scripts/split_i18n_data.py` — never hand-edit `static/js/i18n/<code>.js`
directly (repeating the constraint from `docs/superpowers/plans/2026-08-07-coins-
spine.md:15`, since it bit this exact mistake category in Spec 1's Task 6 if skipped).

## Open questions

- **Can a leader un-schedule a workshop** (send it back from `Scheduled` to `Proposed`,
  e.g. the picked runner backs out)? Not asked for. Recommend leaving it out of v1 —
  a leader can `DELETE` the workshop and the proposer can re-propose it if this comes
  up; a dedicated revert path is easy to add later once it's clear how often it's
  needed.
- **Does deleting a workshop after it's `Scheduled` delete the linked `Event` too, or
  orphan it?** Recommend orphaning it (leave the Event alone) — the Event is a real
  calendar commitment independent members may have already RSVPed to; silently
  deleting it because the originating workshop record was removed would be a surprising
  side effect. `DELETE` on a `Scheduled`/`Run` workshop should probably be disallowed
  entirely rather than orphan silently — flagging for the plan to decide, since it's a
  small validation detail, not an architecture question.

## Non-goals (later specs)

- Coin award for running a workshop — a small follow-up once this ships, not part of
  Spec 3's ship-review coin award either.
- Topic/category filtering, duration field, materials/resources link field — additive,
  not requested here.
- HQ-curated workshop content library (the external `workshops.hackclub.com` link on
  the Tools page stays untouched).
- Ship submission → review → coin award UI — Spec 3.
- Explore feed, Members page expansion, Settings depth, Help center, Build editor,
  landing page rewrite — Specs 4-9.
