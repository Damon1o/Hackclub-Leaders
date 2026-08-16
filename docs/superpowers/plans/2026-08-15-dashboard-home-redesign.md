# Dashboard Home Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the dashboard home page (`templates/dashboard.html`): keep the hero and level-band widgets exactly as-is, shrink the team/checklist/events widgets, and add a new "coins earned" widget (30-day total + sparkline).

**Architecture:** The home page is server-rendered (`GET /dashboard` → `templates/dashboard.html`, extends `dashboard_layout.html`) but hydrates its data client-side: `static/js/dashboard.js` fetches `/api/dashboard/state?sections=...` and calls `renderHome()`. Which state keys that fetch returns is controlled by two parallel maps that must stay in sync — `PAGE_SECTIONS` in `src/helpers.py` (server-side allow-list) and `PAGE_SECTIONS` in `static/js/dashboard.js` (client-side query-param builder). The coin ledger (`state['ledger']`, list of `{delta, kind, ref, note, at}`) already exists and is used elsewhere (shop, checkout) but isn't loaded on the home page — this plan adds it to both maps, then builds the new widget on top of it. No new backend endpoints, no charting library.

**Tech Stack:** Flask + Jinja templates, vanilla JS (no framework, no bundler), hand-rolled SVG for charts (see the existing `.donut-svg` team chart for the established pattern), pytest for backend tests.

## Global Constraints

- Keep `.home-hero` and `.level-band` markup, CSS, and JS untouched — spec requires these exactly as they are today.
- No new backend endpoints — reuse the existing ledger.
- No charting library dependency — hand-rolled SVG only.
- This repo has no JS test framework (confirmed: no `*.test.js` files exist) — JS-only changes are verified by manual browser check, not automated tests. Backend changes get pytest tests as usual.

---

### Task 1: Load the coin ledger on the home page

**Files:**
- Modify: `src/helpers.py:387` (`PAGE_SECTIONS['dashboard']` tuple)
- Modify: `static/js/dashboard.js:207` (client-side `PAGE_SECTIONS.dashboard` array)
- Modify: `static/js/dashboard.js:49-51` (add a `ledger()` accessor next to `orders()`)
- Test: `tests/test_coins.py`

**Interfaces:**
- Produces: `ledger()` in `static/js/dashboard.js` — returns `dashboardState.ledger || []`, an array of `{id, delta, kind, ref, note, at}` (same shape as `CoinTransaction` in `src/helpers_types.py`). Task 3 calls this.

- [ ] **Step 1: Write the failing backend test**

Add to `tests/test_coins.py` (follows the existing pattern at line 57-61 for `dashboard_workshops`):

```python
def test_dashboard_page_section_loads_ledger():
    from src.helpers import PAGE_SECTIONS

    assert 'ledger' in PAGE_SECTIONS['dashboard']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_coins.py::test_dashboard_page_section_loads_ledger -v`
Expected: FAIL with `assert 'ledger' in ('events', 'projects', 'newsletters', 'workshops')`

- [ ] **Step 3: Add `ledger` to the backend PAGE_SECTIONS map**

In `src/helpers.py`, change line 387 from:

```python
    'dashboard': ('events', 'projects', 'newsletters', 'workshops'),
```

to:

```python
    'dashboard': ('events', 'projects', 'newsletters', 'workshops', 'ledger'),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_coins.py::test_dashboard_page_section_loads_ledger -v`
Expected: PASS

- [ ] **Step 5: Mirror the change in the client-side map**

In `static/js/dashboard.js`, change line 207 from:

```js
        dashboard: ['events', 'projects', 'newsletters', 'workshops'],
```

to:

```js
        dashboard: ['events', 'projects', 'newsletters', 'workshops', 'ledger'],
```

- [ ] **Step 6: Add the `ledger()` accessor**

In `static/js/dashboard.js`, immediately after the `orders()` function (line 49-51):

```js
    function orders() {
        return dashboardState.orders || [];
    }

    function ledger() {
        return dashboardState.ledger || [];
    }
```

- [ ] **Step 7: Run the full backend test suite**

Run: `pytest -q`
Expected: all tests pass (same count as before the change, plus the one new test)

- [ ] **Step 8: Commit**

```bash
git add src/helpers.py static/js/dashboard.js tests/test_coins.py
git commit -m "feat: load coin ledger on the dashboard home page"
```

---

### Task 2: Shrink the team, checklist, and events widgets

**Files:**
- Modify: `static/css/dashboard.css` (`.home-team`, `.team-donut`, `.home-team-total`, and new scoped rules for `.home-checklist`/`.home-events` activity rows)

**Interfaces:**
- Consumes: none (CSS-only, no markup or JS changes)
- Produces: none (leaf styling task)

No template or JS changes — same elements, same IDs, same behavior, just less vertical space. This task has no automated test (pure CSS); verify visually per Step 3.

- [ ] **Step 1: Shrink the team-composition card**

In `static/css/dashboard.css`, change the `.home-team` rule (line 898-901) from:

```css
.home-team {
    grid-column: span 4;
    justify-content: flex-start;
}
```

to:

```css
.home-team {
    grid-column: span 4;
    justify-content: flex-start;
    padding: 18px 20px;
}
```

Change `.home-team-total` (line 903-911) from:

```css
.home-team-total {
    margin: 8px 0 0;
    font-family: var(--hackclub-title-font);
    font-size: 56px;
    font-weight: bold;
    line-height: 1;
    color: var(--dash-ink);
    font-variant-numeric: tabular-nums;
}
```

to:

```css
.home-team-total {
    margin: 8px 0 0;
    font-family: var(--hackclub-title-font);
    font-size: 40px;
    font-weight: bold;
    line-height: 1;
    color: var(--dash-ink);
    font-variant-numeric: tabular-nums;
}
```

Change `.team-donut` (line 915-919) from:

```css
.team-donut {
    position: relative;
    width: min(180px, 46%);
    margin: 14px auto 0;
}
```

to:

```css
.team-donut {
    position: relative;
    width: min(130px, 42%);
    margin: 10px auto 0;
}
```

- [ ] **Step 2: Shrink the checklist and events cards**

In `static/css/dashboard.css`, after the `.home-events-wide` rule (line 1172-1174), add:

```css
.home-checklist,
.home-events {
    padding: 18px 20px;
}

.home-checklist .activity-item,
.home-events .activity-item {
    padding: 7px 10px;
    gap: 10px;
}

.home-checklist .activity-icon,
.home-events .activity-icon {
    width: 34px;
    height: 34px;
    font-size: 15px;
}
```

These selectors are scoped to `.home-checklist`/`.home-events` specifically (not the bare `.activity-item`/`.activity-icon` classes) because those classes are reused on other dashboard pages (e.g. notifications) that must keep their current size.

- [ ] **Step 3: Manually verify in the browser**

Run: `python app.py` (or the project's existing dev-server command), sign in, open `/dashboard`.
Expected: team-composition donut and its total are visibly smaller; checklist and upcoming-events rows are more compact; no layout overflow or overlap; the hero card and level band are pixel-identical to before this task.

- [ ] **Step 4: Commit**

```bash
git add static/css/dashboard.css
git commit -m "style: shrink team, checklist, and events widgets on dashboard home"
```

---

### Task 3: Add the coins-earned widget

**Files:**
- Modify: `templates/dashboard.html:86-88` (insert new `<section>` between the level band and the checklist section)
- Modify: `static/css/dashboard.css` (new `.home-coins*` rules)
- Modify: `static/js/dashboard.js` (`renderHome()` and a new `coinsEarnedByDay()` / `renderCoinsWidget()` pair)

**Interfaces:**
- Consumes: `ledger()` from Task 1 (`static/js/dashboard.js`) — array of `{delta, at, ...}`.
- Produces: none (leaf widget)

No automated test (JS-only, no test framework in this repo — see Global Constraints). Verified manually per Step 4.

- [ ] **Step 1: Add the widget markup**

In `templates/dashboard.html`, insert this new `<section>` right after the `.level-band` section closes (line 86, `</section>`) and before the `{% if is_leader %}` checklist block (line 88):

```html
    <section class="card-modern home-coins">
        <div class="home-coins-info">
            <span class="home-coins-eyebrow" data-i18n="home.coinsEarned">Coins earned</span>
            <strong class="home-coins-value" id="homeCoinsTotal">0</strong>
            <span class="home-coins-sub" data-i18n="home.past30Days">past 30 days</span>
        </div>
        <svg class="home-coins-sparkline" id="homeCoinsSparkline" viewBox="0 0 120 32" preserveAspectRatio="none" aria-hidden="true">
            <polyline class="home-coins-line" points="" />
        </svg>
    </section>
```

- [ ] **Step 2: Add the widget CSS**

In `static/css/dashboard.css`, after the `.level-band-text` rule block (after line 1123), add:

```css
/* ── HOME: coins earned ───────────────────────────────────────────────────── */

.home-coins {
    grid-column: 1 / -1;
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    padding: 18px 26px;
}

.home-coins-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.home-coins-eyebrow {
    font-size: 12px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--hackclub-red);
}

.home-coins-value {
    font-family: var(--hackclub-title-font);
    font-size: 34px;
    line-height: 1;
    color: var(--dash-ink);
    font-variant-numeric: tabular-nums;
}

.home-coins-sub {
    font-size: 12.5px;
    color: var(--dash-muted);
}

.home-coins-sparkline {
    width: min(220px, 40%);
    height: 40px;
    flex-shrink: 0;
}

.home-coins-line {
    fill: none;
    stroke: var(--hackclub-orange);
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
    vector-effect: non-scaling-stroke;
}
```

- [ ] **Step 3: Compute and render the sparkline in `renderHome()`**

In `static/js/dashboard.js`, add these two functions right before `function renderHome()` (line 1703):

```js
    function coinsEarnedByDay(days) {
        const buckets = new Map();
        const now = new Date();
        for (let i = days - 1; i >= 0; i -= 1) {
            const d = new Date(now);
            d.setDate(d.getDate() - i);
            buckets.set(d.toISOString().slice(0, 10), 0);
        }
        ledger().forEach((tx) => {
            if (!tx || tx.delta <= 0) return;
            const day = String(tx.at || '').slice(0, 10);
            if (buckets.has(day)) buckets.set(day, buckets.get(day) + tx.delta);
        });
        return Array.from(buckets.values());
    }

    function renderCoinsWidget() {
        const days = coinsEarnedByDay(30);
        const total = days.reduce((sum, value) => sum + value, 0);
        const totalEl = $('#homeCoinsTotal');
        if (totalEl) totalEl.textContent = total;

        const line = $('#homeCoinsSparkline .home-coins-line');
        if (!line) return;
        const max = Math.max(1, ...days);
        const stepX = 120 / (days.length - 1 || 1);
        const points = days.map((value, index) => {
            const x = index * stepX;
            const y = 32 - (value / max) * 30 - 1;
            return `${x.toFixed(2)},${y.toFixed(2)}`;
        }).join(' ');
        line.setAttribute('points', points);
    }
```

Then, in `renderHome()`, add a call to `renderCoinsWidget()` right after the `renderChecklist();` line (line 1811):

```js
        renderChecklist();
        renderCoinsWidget();
    }
```

- [ ] **Step 4: Manually verify in the browser**

Run: `python app.py` (or the project's existing dev-server command), sign in, open `/dashboard`.
Expected: a new full-width card sits between the level band and the checklist/events row, showing a coin total and a small sparkline. If the signed-in test club has ledger entries (e.g. the starter grant), the total reflects them and the line is visibly non-flat; with zero ledger entries the total reads 0 and the line is flat. No console errors.

- [ ] **Step 5: Run the full backend test suite one more time**

Run: `pytest -q`
Expected: all tests pass (template/CSS/JS-only changes shouldn't affect any backend test, but this confirms nothing broke)

- [ ] **Step 6: Commit**

```bash
git add templates/dashboard.html static/css/dashboard.css static/js/dashboard.js
git commit -m "feat: add coins-earned widget to dashboard home"
```
