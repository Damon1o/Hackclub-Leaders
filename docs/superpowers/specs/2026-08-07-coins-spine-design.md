# Coins Spine: Ledger, Dollar Removal, Shop Conversion

**Date:** 2026-08-07
**Source:** Brainstorm session — integrate clubs.hackclub.com features into Hackclub
Leaders, using Hack Club coins instead of dollars.
**Scope:** Spec 1 of 9. The coin ledger itself, converting the existing dollar shop to
coins, and the dashboard balance display. Workshops, the ships-review pipeline that
mints coins, the Explore feed, expanded Members/Settings/Help, and the landing page
rewrite are separate specs that build on this one.

## Context

`clubs.hackclub.com` (the real, authenticated product — inspected directly via browser,
not the marketing shell WebFetch sees) runs its whole leader experience on one economy:
ship a project → an admin approves it → the club earns **coins** → the leader redeems
coins in a shop for grants, hardware, merch. Dashboard stat tiles are `Club Coins`,
`Coins Spent`, `Members`, `Approved Ships`, `Workshops Run`, `Club Building Hours`.

This repo (Hackclub Leaders) has no coin concept anywhere — confirmed by grep across
`src/`, `static/js/`, `templates/`, `static/data/`. Its shop
(`static/data/shop.json`) prices items as USD strings (`"$3.00"`), checkout
(`src/routes_api.py:419-442`) creates an order with no price and no debit, and nothing
computes a balance. This spec replaces that with a real coin ledger and converts the
shop to coin pricing, without touching the parts of the app that don't yet exist
(workshops, ship review, Explore).

Decisions made with Damon:

- **Full ledger economy**, not a display relabel or a bare integer counter. Every
  balance change is an append-only, auditable transaction row.
- **Default per-ship award: 25 coins**, editable by the reviewer at approval time
  (clubs.hackclub.com's Help copy states there is no fixed rate — the reviewer sets the
  award based on scope and hours — so the default is a starting value, not a constant).
- Existing repo-only features (chat, notifications, 12-language i18n, club map, motion
  effects, club levels) are kept and integrated additively, not stripped to match
  clubs.hackclub.com.
- Gated clubs.hackclub.com pages were read directly through an authenticated browser
  session, not reconstructed from public copy — the shop catalog, prices, and stat
  tiles below are the real, current data.

## 1. Ledger data model

New `CoinTransaction` type in `src/helpers.py`, alongside the existing `Order`/`ShopItem`
types:

```python
class CoinTransaction(TypedDict):
    id: str
    delta: int          # positive = earned, negative = spent
    kind: str            # 'ship_approved' | 'shop_order' | 'admin_adjust' | 'starter_grant'
    ref: str              # id of the related project/order, '' for admin_adjust
    note: str
    at: str               # ISO 8601 timestamp
```

Balance and spent-to-date are **derived, never stored independently**:

```python
def coin_balance(ledger: list[CoinTransaction]) -> int:
    return sum(t['delta'] for t in ledger)

def coins_spent(ledger: list[CoinTransaction]) -> int:
    return -sum(t['delta'] for t in ledger if t['delta'] < 0)
```

This makes drift structurally impossible: there is no second number that can
disagree with the ledger.

### Why not just a `coins: int` counter

A bare counter is simpler but throws away exactly the thing coins need most —
"where did our coins go." clubs.hackclub.com's own dashboard has a dedicated `Coins
this month` panel and `/shop/orders` history; a ledger is what makes both of those
possible later without a migration.

## 2. Where the ledger lives (the always-loaded problem)

The coin balance needs to render on every dashboard page (it's in the persistent user
card). Naively that means the ledger belongs in `ALWAYS_LOADED` alongside `members` and
`notifications` — but the ledger grows without bound, and the session-cookie backend
has a hard 2.8 KB cap that this repo has already hit once with large message datasets.

Split the concern instead:

- **`ledger`** (new entry in `STATE_SECTIONS`) is lazy-loaded like `projects` or
  `orders` — only pulled in on pages that render transaction history.
- **`settings.coinBalance`** and **`settings.coinsSpent`** are a two-integer cache,
  written in the same `save_dashboard_state()` call that appends a ledger entry.
  `settings` is already in `ALWAYS_LOADED`, so the cheap cached numbers ride along for
  free on every page; the expensive full history stays opt-in.
- `reconcile_coins(state)` recomputes both cached numbers from the ledger. Called after
  every mutation in dev/test; exercised directly by a unit test that asserts the cache
  never disagrees with `coin_balance(ledger)`.

### Registration checklist (the five-place trap)

This repo has two live examples of a state section that silently doesn't persist on
the Airtable backend because it was only added in some of the required places:
`notifications` and `settings.language`. `ledger` must be added in all of:

1. `src/helpers.py` — `STATE_SECTIONS` tuple, `default_dashboard_state()` seed
   (`ledger: []`, plus one `starter_grant` transaction so a fresh club isn't stuck at
   zero, mirroring clubs.hackclub.com's "we send a starter kit... and your first
   coins" onboarding copy).
2. `src/storage.py` — `CHILD_TABLES` entry (`('LEDGER', 'Ledger', 'ledger', LEDGER_FIELDS)`)
   and the matching `LEDGER_FIELDS` list.
3. `src/storage_mongo.py` — `CHILD_COLLECTIONS` entry and its `INDEXES` entry
   (indexed by club key + `at` descending, matching the pattern already used for
   notifications).
4. `PAGE_SECTIONS` — which dashboard pages actually need `ledger` loaded (the shop page
   and a future "coin history" view; not every page).

A test asserts every key in `STATE_SECTIONS` has a corresponding `CHILD_TABLES` entry
and a corresponding `CHILD_COLLECTIONS` entry, so a future missed registration fails
CI instead of silently dropping data again.

## 3. Removing dollars

17 sites in the repo hold a dollar value or dollar-shaped code today. Each is
converted or deleted:

| # | File:line | What | Action |
|---|---|---|---|
| 1 | `static/data/shop.json` | 30 items, `cost`/`hours` dollar strings | `cost` → int coins (see §4); `hours` key dropped |
| 2 | `src/helpers.py:70-76` | `ShopItem.cost: str` | → `cost: int` |
| 3 | `src/helpers.py:378-382` | `_normalize_cost` mints `$` | → `_parse_coins`, returns `int \| None` |
| 4 | `src/helpers.py:385-388` | `_shop_hours` (1.5× dollar cost) | **delete** — dead code, `load_shop_items` never reads `hours` past this point |
| 5 | `src/helpers.py:313-322` | `load_shop_items` | passes int `cost` through unchanged |
| 6 | `src/helpers.py:88-90` | `OrderItem` has no price field | add `coinCost: int` — snapshot at purchase time so a later catalog reprice doesn't rewrite order history |
| 7 | `src/helpers.py:402` | `cost = _normalize_cost(cost) or 'TBD'` | → `_parse_coins(cost)`, `None` allowed (admin prices it later) |
| 8 | `src/helpers.py:497` | seeded newsletter: "Apply for up to $500..." | reword in coins or leave as historical flavor text — **open question, see §7** |
| 9 | `src/routes_admin.py:169` | `add_shop_item(name, 'TBD', ...)` on item-request approval | unchanged call shape, `'TBD'` still valid (unpriced) |
| 10 | `src/routes_admin.py:192` | `cost = clean_text(payload.get('cost'), max_len=20)` | validate as int string instead of free text |
| 11 | `templates/dashboard/admin.html:112-113` | label "Cost ($)", placeholder "$10.00" | → "Cost (coins)", placeholder "50" |
| 12 | `static/js/dashboard.js:1045` | shop card renders `item.cost` as-is | render int + coin glyph (§5) |
| 13 | `static/js/dashboard.js:1061` | cart line renders `item.cost` as-is | same, plus a cart **subtotal** (doesn't exist today — `dashboard.js:1025` currently sums quantities only) |
| 14 | `static/js/i18n/en.js:385` | `'admin.itemCost': 'Cost ($)'` | → `'Cost (coins)'` |
| 15 | `static/js/i18n-data.js` (12 blocks) | same key, all untranslated to "Cost ($)" | edit `i18n-data.js`, regenerate per-language files via `scripts/split_i18n_data.py` — **never hand-edit `static/js/i18n/<code>.js` directly** |
| 16 | `static/js/events-data.js:56` | "Get up to $1,000 to build hardware projects." | out of scope — this is event copy, not shop/coins. Left alone. |
| 17 | `static/js/effects.js:230` | comment example `("$1,200", "12 ships")` | cosmetic code comment, not user-facing. Left alone. |

Rows 16–17 are noted so the "every dollar removed" claim is auditable, but they're
event-page copy and a code comment respectively — not part of the coins economy this
spec touches.

## 4. Pricing the existing catalog

No official USD-to-coin rate is published anywhere. Back-solving clubs.hackclub.com's
live 16-SKU catalog against retail prices gives roughly 3.6–4.7 coins per dollar.

Rule, in priority order:

1. **If an item in `shop.json` matches a real clubs.hackclub.com catalog item by name**
   (Hack Club Pin, Stickers, Domain Grant, etc.), use their actual published coin price
   — real data beats a derived formula.
2. **Otherwise**, convert at a documented constant: `COINS_PER_DOLLAR = 4`, rounded to
   the nearest 5. This constant lives in `src/helpers.py` next to `_parse_coins`,
   commented as an unofficial estimate — never presented to users as an official Hack
   Club rate.

Worked example against the current file: `Free → 0`, `$3.00 → 10` (Hack Club's real
Stickers price, rule 1, not the derived 10 which happens to match here), `$5.00 →
20` (their real price for similar swag, not the naive `5 × 4 = 20` — verify per item),
`$10.00 → 40`, `TBD → null` (admin must price it before it's redeemable).

Every item's final coin price is enumerated as part of the implementation plan, not
guessed here — the plan step reads the live clubs.hackclub.com shop for every
name-match before falling back to the formula.

## 5. UI: coin glyph, balance, cart subtotal

- clubs.hackclub.com uses a small circular coin icon (⬤-style, orange/gold) inline
  before the number, both in the sidebar user card and every price. This repo has no
  such asset — add `static/images/coin.svg` (simple flat circular glyph, matches this
  repo's existing icon style rather than copying clubs.hackclub.com's exact art) and an
  `hc_coin_icon()` Jinja helper alongside the existing `sidebar_icon()` partial.
- Dashboard header/sidebar gets a `⬤ {{ coinBalance }}` chip, reading from
  `settings.coinBalance` — no ledger load needed on pages that don't show history.
- Shop page: every `shop-price` span renders `⬤ {cost}` instead of the raw string.
- Cart: add a subtotal row (new — `dashboard.js` cart rendering has never summed
  anything). Checkout button disables when subtotal exceeds `coinBalance`.

## 6. Checkout becomes a real debit

`src/routes_api.py:419-442` (`api_cart_checkout`) currently creates an order with no
price and no balance check. New behavior:

```python
total = sum(item['coinCost'] * item['quantity'] for item in state['cart'])
if total > coin_balance(state['ledger']):
    return json_error('Not enough coins for this order.')

order = {..., 'coinCost': total}   # snapshot, survives future repricing
state['ledger'].append({
    'id': _item_id('coin'), 'delta': -total, 'kind': 'shop_order',
    'ref': order['id'], 'note': f"Order: {', '.join(i['name'] for i in cart_items)}",
    'at': datetime.utcnow().isoformat(),
})
reconcile_coins(state)   # refresh settings.coinBalance / coinsSpent cache
```

This is the first real spend path. The earn path (`ship_approved` transactions minted
on admin approval) is Spec 3's job — this spec adds the ledger machinery and an
`award_coins(state, amount, kind, ref, note)` helper that Spec 3 calls, plus a stub
`admin_adjust` entry point so a leader-facing "coins are wrong, fix it" admin action has
somewhere to attach later. No admin UI for `admin_adjust` ships in this spec.

## 7. Open questions

- **Newsletter seed text** (`helpers.py:497`, "Apply for up to $500..."): reword to
  coins, or leave as flavor text describing an external (real-world, dollar-denominated)
  grant program that isn't part of this app's shop? Recommend leaving it — it's not
  reachable through any coin-priced flow — but flagging since it's a dollar string in
  scope of the original ask.
- **Exact per-item coin prices** for the 14 items that don't have a clubs.hackclub.com
  name match: use the `COINS_PER_DOLLAR = 4` formula as specified, or hold for manual
  admin pricing (ship as `null`/`TBD`)? Recommend the formula — an unpriced item is a
  worse experience than an estimated one, and the constant is documented as an
  estimate.

## Non-goals (later specs)

- Workshops catalog, filters, detail view, apply-to-run — Spec 2.
- Ship submission → review → coin award UI (the `award_coins()` call site with a
  reviewer-editable amount, defaulting to 25) — Spec 3.
- Explore feed, Members page expansion (join code, pending approvals, 4 stat tiles),
  Settings depth (themes, Hackatime link, privacy toggles), Help center, Build editor,
  landing page "How the coins work" section rewrite — Specs 4-9.
