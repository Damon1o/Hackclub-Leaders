# Motion polish implementation plan

Spec: `docs/superpowers/specs/2026-08-17-motion-polish-design.md`
Files: `static/css/dashboard.css`, `static/css/navigation.css`,
`static/js/dashboard.js`. No backend changes.

## Step 1 — dashboard.css: press feedback

After the existing `.btn-primary`/`.btn-secondary` block (~line 664), add
`:active` scale rules for all pressables listed in the spec, one grouped
block:

- shared `:active { transform: scale(0.97); }` with each element's own
  transition already present (buttons carry `transform 0.125s`); ensure
  `:active` transition timing ≤160ms where missing.

## Step 2 — dashboard.js: modal exit sequence

Rework `closeModal` (~line 365):

1. `modal.classList.add('is-closing')`
2. `setTimeout(() => { modal.classList.remove('is-open', 'is-closing'); }, 150)`
3. `openModal` removes `.is-closing` before adding `.is-open`.

## Step 3 — dashboard.css: modal exit styles

Next to `.modal-backdrop`/`.dashboard-modal` (~line 3068):

- `.dashboard-modal { transition: opacity 150ms ease-out, transform 150ms ease-out; }`
- `.modal-backdrop.is-closing { opacity: 0; }`
- `.modal-backdrop.is-closing .dashboard-modal { opacity: 0; transform: translateY(8px); }`
- Add to existing reduced-motion block: kill these transitions.

## Step 4 — navigation.css: dropdown transition

Replace `display`-only toggle (~line 240) with display + opacity/transform
start state and 180ms ease-out transition; keep `:hover`/`:focus-within`/
`.is-open` selectors as the triggers.

## Step 5 — dashboard.js + dashboard.css: toast enter

- `showToast` (~line 335): `toast.setAttribute('data-mounted', 'true')`.
- CSS: remove `animation: toast-in` and the `toast-in` keyframe; add
  `[data-mounted]` end state on the existing transition.

## Step 6 — dashboard.css: hover gating

One `@media (hover: hover) and (pointer: fine)` block wrapping the hover
transform rules listed in the spec (spec §5). Move-only, no value changes.

## Step 7 — dashboard.css: badge pop

`notification-badge-pop` `from` scale 0.4 → 0.6 (line ~3492).

## Step 8 — Verify

- Re-read each edited file section.
- `graphify update .` (AST-only).
- Manual smoke list: button press feel (desktop + touch emulation),
  modal open/close/reopen-while-closing, keyboard `Escape`, nav dropdown
  keyboard path, toast pile-up, reduced-motion block inspection.

Time estimate: ~2 hours.
