# Site-wide guided tour

## Goal

Give every page in the dashboard app a short, skippable spotlight tour that
walks a new leader/member through what's on the page — narrated by the
Hack Club raccoon mascot from `static/images/Stickers/find out.webp`.

One page (`/dashboard/tools`) already has this via a page-specific,
hand-rolled implementation (`static/js/tools-tour.js`). This spec replaces
it with a single shared, reusable tour engine that every dashboard page
plugs into.

## Scope: pages

All 16 pages that extend `dashboard_layout.html`:

home, tools (migrated), team, workshops, events, shop, levels, map,
projects, ships, chat, notifications, settings, profile, admin, admin-club.

Public/auth pages (landing, sign-in, join, public events) are out of scope —
there's no logged-in app chrome to tour there.

## Architecture

**Engine — `static/js/tour.js`** (replaces `tools-tour.js`): a generic
spotlight/tooltip engine, carrying forward the already-debugged positioning
logic from `tools-tour.js` (spotlight box math, tooltip clamping, the
`scrollIntoView` + reposition-after-scroll timer). Generalized so it's no
longer hardcoded to one storage key / one steps array:

- Reads the current page's key off `<body data-tour-page="...">`.
- Looks up that key in a central step map, `static/js/tour-steps.js`.
- No entry for the key, or an empty array → no-op, replay button stays
  hidden. No per-page JS required beyond the one template line below.
- Auto-starts once per page on `DOMContentLoaded` if
  `localStorage['hc_tour_seen_<pageKey>']` isn't set. Same convention as
  today's `hc_tools_tour_seen`, just parameterized per page.
- Per step: resolve `target` with `document.querySelector`. Skip to the next
  step if the target is missing **or not visible** (`offsetParent === null`,
  or a zero-size bounding rect) — the visibility check is new: several pages
  have elements that exist in the DOM but start `hidden` until data loads
  (e.g. Projects' `#hacktimeCard`, Chat's `.chat-composer`), and those must
  not be spotlighted as if they were on-screen.
- Last step "Done" or Skip → mark seen in localStorage, remove the overlay.

**Step content — `static/js/tour-steps.js`**: a single exported map,
`{ pageKey: [ {target, title, body}, ... ] }`, one entry per page. Centralizing
content here (rather than 16 inline `<script>` blocks) mirrors how this
codebase already centralizes similar per-page data (e.g. `i18n-data.js`).
Titles/bodies are plain English strings, not `data-i18n` keys — this matches
`tools-tour.js`'s existing precedent of un-internationalized tour copy, kept
for consistency rather than opening a ~150-key translation surface.

**Page identification**: `dashboard_layout.html`'s `<body>` tag gains
`data-tour-page="{% block tour_page %}{% endblock %}"`. Each of the 16 page
templates adds one line, e.g. `{% block tour_page %}workshops{% endblock %}`.

**CSS**: `.tools-tour-*` rules in `dashboard.css` (lines ~1829-1900) are
renamed to generic `.tour-*` in place — same file, no new stylesheet.

**Mascot**: every tooltip shows `static/images/Stickers/find out.webp` as a
small fixed avatar, pinned top-left inside the tooltip box, with the
title/body/action-row stacked in a column to its right (chat-bubble /
narrator layout — approved during brainstorming). Same image on every step
of every page; it's not per-step art. Displayed via `object-fit: contain`
at a small fixed box size (~56px) rather than forced into a circular crop,
since the source sticker has its own irregular die-cut outline.

**Replay trigger**: one "?" icon button added once, unconditionally, into
the currently-empty `.dashboard-header-right` div in `dashboard_layout.html`
(`templates/dashboard_layout.html:230`) — appears in the header chrome on
every dashboard page automatically, no per-template button markup needed.
`tour.js` hides it via a CSS class when the current page's step list is
empty. Clicking it always restarts from step 0, regardless of seen-state.

## Data flow

1. `tour.js` (now loaded from `dashboard_layout.html` instead of just
   `tools.html`) runs on `DOMContentLoaded`.
2. Reads `data-tour-page` off `<body>`, looks up steps in `tour-steps.js`.
3. No steps for this page → hide the replay button, stop.
4. Steps exist → show the replay button. Auto-start if
   `localStorage['hc_tour_seen_<pageKey>']` is unset.
5. Step loop: resolve target → missing/hidden → skip to next → else
   position spotlight + tooltip (with mascot), scroll into view, wait for
   Next/Skip.
6. End of steps or Skip clicked → set the seen flag, tear down the overlay.

## New `data-tour` markup needed

Almost every step targets an element that's already uniquely selectable
(existing `id`, or a class used once on that page). Two pages need small
additions, following the `data-tour="..."` convention `tools.html` already
uses for its featured/standard/placeholder sections:

- **Projects** (`templates/dashboard/projects.html`): the "Your projects"
  and "Submitted to your club" sections both currently share generic
  `card-modern dashboard-panel dashboard-panel-full` classes with nothing
  to disambiguate them. Add `data-tour="projects-mine"` and
  `data-tour="projects-submitted"` to their two `<section>` tags.

No other page needs new markup.

## Per-page step content

Steps are short (2-5 per page) and skippable. Targets in `` `code` `` are
CSS selectors against existing markup unless noted as new above.

**Home** (`home`, `templates/dashboard.html`)
1. `.home-hero` — *Your club HQ* — Your club's name and quick stats:
   members, events, RSVPs, ships, and shop orders.
2. `.home-team` — *Your roster at a glance* — See how your club splits
   across leaders, members, and mentors.
3. `.level-band` — *Your club's level* — Ship projects to level up and
   unlock new perks.
4. `.home-coins` — *Coins earned* — Every approved ship earns your club
   coins — track the last 30 days here.
5. `.home-events` — *What's next* — Your upcoming meetings and events,
   right on the home page.

**Tools** (`tools`, `templates/dashboard/tools.html`) — migrate the 4
existing steps from `tools-tour.js` verbatim (targets and copy unchanged):
`.dashboard-header`, `[data-tour="featured-row"]`,
`[data-tour="standard-grid"]`, `[data-tour="placeholder-card"]`.

**Team** (`team`)
1. `.dashboard-metrics` — *Your team, counted* — Members, leaders, and
   pending invites, all at a glance.
2. `.join-link-card` (leader only — step is skipped for non-leaders via the
   visibility check, since the section doesn't render for them) — *Invite
   with a link* — Share this link — anyone who opens it joins your club
   instantly.
3. `#teamRoster` — *Your roster* — Everyone in your club. Click a member to
   edit their role or status.

**Workshops** (`workshops`)
1. `#workshopFilters` — *Browse by type* — Filter the workshop board by
   category.
2. `#workshopGrid` — *Propose or run one* — Propose a topic for your club,
   or apply to run one that's already open.

**Events** (`events`)
1. `.dashboard-metrics` — *Your event stats* — Upcoming meetings, RSVPs,
   and how many people you're expecting.
2. `#eventList` — *Your schedule* — Every meeting, workshop, and demo day
   your club has planned.

**Shop** (`shop`)
1. `#shopFilters` — *Browse the shop* — Stickers, posters, and hardware —
   filter by category.
2. `#cartPanel` — *Your cart* — Add items here, then check out when you're
   ready.
3. `.request-item-block` — *Don't see it?* — Request an item and we'll
   consider adding it to the shop.

**Levels** (`levels`)
1. `.level-status-card` — *Where you stand* — Your club's current level
   and progress to the next one.
2. `.levels-grid` — *What you unlock* — See what perks each level brings.
3. `.level-cta` — *Ready to level up?* — Log a shipped project and watch
   the perks unlock.

**Map** (`map`)
1. `.map-card` — *Every Hack Club, worldwide* — Make sure your club shows
   up here too.

**Projects** (`projects`)
1. `[data-tour="projects-mine"]` *(new attr, see above)* — *Your projects*
   — Track your own projects here — only you can edit them.
2. `[data-tour="projects-submitted"]` *(new attr, see above)* — *Club
   submissions* — Once you submit a project, it lands here for a leader to
   review.

(`#hacktimeCard` is intentionally not a tour target — it's `hidden` by
default until Hackatime data loads, which the visibility-skip rule would
drop anyway; Hackatime is covered on the Profile page instead.)

**Ships** (`ships`)
1. `.dashboard-metrics` — *Your ship stats* — Total ships, current level,
   and members shipped toward the next one.
2. `#shipList` — *What's shipped* — Every approved project your club has
   shipped.

**Chat** (`chat`)
1. `.chat-sidebar` — *Your channels* — Jump between your club's channels,
   or create a new one if you're a leader.
2. `.chat-empty` — *Start chatting* — Pick a channel from the sidebar to
   join the conversation. (Visible by default before any channel is
   selected — the state a first-time visitor sees.)

**Notifications** (`notifications`)
1. `#newsletterList` — *Dispatches from HQ* — Updates from Hack Club HQ,
   plus anything you send your own club.
2. `#notificationsMarkAllReadBtn` — *Stay caught up* — Mark everything as
   read in one click.
3. `[data-open-modal="dispatchModal"]` (leader only) — *Send an update* —
   Write a dispatch to your whole club.

**Settings** (`settings`)
1. `#settingsNav` — *Jump to a section* — Club profile, members,
   appearance, privacy, notifications — organized in one place.
2. `#danger-zone` — *Careful in here* — Irreversible stuff lives in the
   danger zone — read twice before you click.

**Profile** (`profile`)
1. `#profileForm` — *Your details* — Name, email, avatar, and bio — how
   you show up across the portal.
2. `.hackatime-connect` — *Track your coding time* — Connect Hackatime to
   show your coding time on Projects.
3. `#profilePreview` — *How others see you* — A live preview of your
   profile card.

**Admin** (`admin`, admin-only page)
1. `.dashboard-metrics` — *Platform at a glance* — Total clubs, projects
   waiting on review, and members across Hack Club.
2. `.admin-review-list` — *Review queue* — Approve or reject shipped
   projects — approved ones count toward a club's level.
3. `.admin-table` — *Every club* — Browse all clubs, or open one to manage
   it directly.

**Admin Club** (`admin-club`, admin-only page)
1. `#adminClubForm` — *Edit on their behalf* — Update this club's profile
   as an admin.
2. `.timeline-list` — *Their shipped projects* — Approve, reject, or
   un-ship a project for this club.

## Error handling

- Missing or hidden target for a step → skip to the next step (extends the
  existing `tools-tour.js` missing-target fallback to also cover
  `hidden`/zero-size elements — see Architecture).
- Page with no entry in `tour-steps.js` → replay button hidden, engine
  never starts.
- `prefers-reduced-motion` → extend the existing reduced-motion block in
  `dashboard.css` to disable `scrollIntoView({behavior:'smooth'})` and any
  tooltip transition for the tour engine too (today it doesn't cover
  `.tools-tour-*` at all).

## Testing

No JS test framework in this repo (existing constraint, confirmed on the
last branch). Verified the same way: Flask route-render tests confirming
(a) the shared replay button renders in the header on a representative set
of pages, and (b) the two new `data-tour` attributes exist in
`projects.html`'s rendered output. Manual browser spot-check across a
handful of pages (home, tools, chat — the one with hidden-until-selected
elements) to confirm spotlight positioning and the mascot layout.

## Out of scope

- No i18n for tour copy (matches `tools-tour.js` precedent).
- No public/auth-page tours (landing, sign-in, join, public events).
- No per-step or per-page mascot art variation — same image everywhere.
- No backend changes — this is pure front-end.
