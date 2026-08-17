# Motion & interaction polish (Emil Kowalski principles)

## Goal

Make every pressable, dropdown, and modal feel responsive: consistent press
feedback, exit animations where entries exist, and touch-safe hover states.
No visual redesign; markup changes limited to class/attribute additions.

## Unchanged

- Color tokens, layout, typography, existing custom easing
  `cubic-bezier(0.22, 1, 0.36, 1)`
- Sidebar width expansion, tour spotlight positioning, progress-bar width
  animation (documented tradeoffs — layout props are the semantics there)
- All existing reduced-motion blocks (extended only, never rewritten)

## Changes

### 1. Press feedback

`:active { transform: scale(0.97) }`, 160ms ease-out, on every pressable:

- `.btn-primary`, `.btn-secondary`, `.btn-ghost-light`, `.btn-danger`
  (hover keeps its existing scale-up)
- `.icon-button`, `.text-button`
- `.shop-filter-chip`, `.checklist-toggle`
- `.activity-item`, dashboard sidebar links
- `.nav-links a`, `.apply-now-link`, `.sign-in-link` (navigation bar)

Mirrors the existing `.chat-send-btn:active { transform: scale(0.94) }`
(dashboard.css:4485). Press scale must not be gated behind hover media —
touch presses need it most.

### 2. Modal exit

Today: open = keyframe `modal-pop`, close = instant `display` flip
(dashboard.js:365-372). Add exit:

- JS: `closeModal` adds `.is-closing`, keeps `aria-hidden="true"` immediate,
  removes `.is-open` + `.is-closing` after 150ms.
- CSS: `.modal-backdrop.is-closing .dashboard-modal` →
  `opacity: 0; transform: translateY(8px)` with 150ms ease-out transition;
  backdrop itself fades 150ms.
- Reopen during exit must be safe: `openModal` clears `.is-closing`.

Exit faster than enter (150ms vs 220ms) per asymmetric timing.

### 3. Nav dropdown

Today: `display:none → flex` toggle (navigation.css:240-252), zero animation.

- Keep display toggle for a11y (menu stays hidden from AT), add
  `transform: translateY(-4px) scale(0.98); opacity: 0` start state,
  transition 180ms ease-out, `transform-origin: top left`.
- `:focus-within` and `.is-open` paths keep working unchanged.

### 4. Toast enter

Today: enter via keyframe `toast-in`, exit via `.toast-leaving` transition
(dashboard.css:3444-3467) — mixed model, enter not interruptible.

- JS: `showToast` sets `data-mounted="true"` on the element.
- CSS: toast base state `opacity: 0; transform: translateY(8px)`;
  `[data-mounted]` → `opacity: 1; transform: none` with existing
  `transition: opacity 0.2s ease, transform 0.2s ease`; drop the keyframe.

### 5. Touch gating

No `@media (hover: hover) and (pointer: fine)` anywhere today. Gate these
hover-only transforms (one media block each, keeping non-transform hover
styling like color/background ungated):

- `.metric-tile`, `.sticker`, `.item-card`, `a.tool-card`, `.activity-item`,
  `.legend-item`, `.timeline-item`, `.level-card`, `.sidebar-profile`,
  `.dashboard-title`, `.checklist-toggle`, `.donut-svg`

### 6. Notification badge pop

`notification-badge-pop` starts `scale(0.4)` → start `scale(0.6)`.
Nothing should materialize from (near) nothing.

## Out of scope

- New easing/duration token system
- Layout redesign
- Reduced-motion coverage rewrite (already in 6 files)
- Keyboard-action animations (none found to remove)
