# Dashboard home page redesign

## Goal

Keep the hero (club name + stat stickers) and club-level band exactly as-is.
Shrink the other home widgets and add a new coins-earned widget.

## Unchanged

- `.home-hero` (club name, member/event/RSVP/ship/order stat stickers)
- `.level-band` (club level, progress bar, "View perks" link)

## New: coins widget

Full-width compact card, placed immediately after `.level-band` and before
the checklist/events row.

- Left: eyebrow label "Coins earned", big number = sum of positive ledger
  deltas in the last 30 days, sub-label "past 30 days"
- Right: inline SVG sparkline plotting coins earned per day for the last 30
  days (zero-filled for days with no ledger activity). Hand-rolled SVG
  polyline, consistent with the existing hand-rolled donut chart — no
  charting library.

### Data plumbing

The coin ledger (`state['ledger']`, list of `{delta, kind, ref, note, at}`)
already exists server-side but the `dashboard` (home) endpoint doesn't load
it.

- Backend: add `'ledger'` to `PAGE_SECTIONS['dashboard']` in
  `src/helpers.py` (~line 387).
- Frontend: add a `ledger()` accessor in `static/js/dashboard.js` following
  the existing `orders()`/`projects()` pattern (`dashboardState.ledger || []`).
- In `renderHome()`, bucket ledger entries with `delta > 0` by calendar day
  (from `at`) over the trailing 30 days, zero-fill missing days, render
  sparkline + total.

## Shrink existing widgets

- **Team composition card** (`.home-team`): smaller donut (180px → ~130px),
  smaller total-member number, tighter card padding. No behavior change.
- **Checklist card** (`.home-checklist`) and **Upcoming events card**
  (`.home-events`): tighter card padding and `.activity-item` row height.
  No behavior change.

## Layout order (top → bottom)

1. Hero + team row (team shrunk)
2. Level band (unchanged)
3. Coins widget (new)
4. Checklist + events row (shrunk)

## Out of scope

- No new backend endpoints — reuses the existing ledger.
- No charting library dependency.
- No changes to hero or level-band markup/behavior.
