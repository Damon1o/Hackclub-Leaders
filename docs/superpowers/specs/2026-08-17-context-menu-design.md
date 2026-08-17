# Dashboard Context Menu Specification

## Status

Implemented in `static/js/dashboard.js` and `static/css/dashboard.css`.

## Summary

Add a lightweight right-click action menu to the authenticated dashboard. The menu is a progressive-disclosure layer for frequent actions; it must reuse existing dashboard controls and API flows rather than introduce parallel mutations.

## Goals

- Make common dashboard tasks discoverable without adding permanent buttons to every card.
- Put creation actions close to the page where the new record belongs.
- Keep destructive and permission-sensitive actions subject to existing role checks and API authorization.
- Preserve the playful, crisp Hack Club dashboard visual language in light and dark themes.
- Make the feature usable with a mouse, trackpad, keyboard, and reduced-motion settings.

## Non-goals

- Replacing visible buttons or modal forms.
- Adding new backend endpoints.
- Overriding browser context menus inside form controls or editable text.
- Adding right-click-only functionality that cannot be reached through the existing UI.

## Interaction model

1. A `contextmenu` event on the dashboard is intercepted unless the pointer is over `input`, `textarea`, `select`, or `[contenteditable="true"]`.
2. The target is classified from `data-context-type` and `data-context-id` attributes. Links, shop cards, and workshop cards may also be classified from their existing data attributes.
3. The menu is rendered at the pointer position and clamped inside the viewport.
4. Selecting an action closes the menu, then calls an existing preparation function, visible button, modal, or state-refresh flow.
5. Clicking elsewhere, pressing `Escape`, scrolling, or resizing closes the menu.

## Supported targets and actions

| Target | Actions | Role notes |
|---|---|---|
| Empty dashboard surface | Refresh dashboard, toggle theme, page-specific “Add new” action | Creation actions are leader-only |
| Member card | Edit member, remove member | Leader-only; server still authorizes the mutation |
| Event row | Edit, toggle RSVP, delete | Edit/delete are leader-only; RSVP follows normal member access |
| Project card | Edit, submit or move to draft, delete | Existing project ownership and API checks apply |
| Workshop card | View workshop | Proposal actions remain in the workshop detail flow |
| Shop item card | View details, add to cart | Existing cart validation and cost rules apply |
| Navigation link | Open in new tab, copy link | Uses the link’s existing `href` |

Page-specific creation shortcuts are:

| Page | Shortcut |
|---|---|
| Team | Invite member |
| Events | Schedule event |
| Workshops | Propose workshop |
| Projects | Start project |
| Notifications | Write announcement |
| Chat | Create channel |

## Accessibility and resilience

- The menu is positioned with `position: fixed` so it follows viewport coordinates instead of document layout.
- The first action receives focus after opening.
- `Escape` closes the menu without changing page state.
- Form fields retain the browser’s normal context menu and editing behavior.
- The menu includes visible focus and hover states with sufficient contrast in both themes.
- The entrance animation is disabled under `prefers-reduced-motion: reduce`.
- Copy-link uses the Clipboard API when available and does not block the rest of the dashboard if the API is unavailable.
- API failures continue to use the existing toast/error handling.

## Implementation contract

Context-aware cards should expose:

```html
<article data-context-type="project" data-context-id="project-id">
```

When adding a new target type:

1. Add `data-context-type` and a stable `data-context-id` to the rendered target.
2. Add its menu items to `contextMenuItems()`.
3. Route the action through an existing event handler or shared API helper.
4. Add the target and expected role behavior to the table above.
5. Verify keyboard dismissal, viewport clamping, light mode, dark mode, and reduced motion.

## Verification checklist

- Right-click a blank area on each create-capable page and confirm the correct “Add new” action appears.
- Right-click each supported card type and confirm actions target the correct record.
- Confirm form fields keep their native context menu.
- Confirm the menu stays inside the viewport near all four corners.
- Confirm `Escape`, outside click, scroll, and resize close the menu.
- Confirm member-level users do not receive leader-only creation/edit/delete actions.
- Confirm `node --check static/js/dashboard.js` and `git diff --check` pass.
