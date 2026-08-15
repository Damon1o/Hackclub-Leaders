# Chat Visual Redesign — Design Spec

Date: 2026-08-14

## Goal

Full visual/layout redesign of club chat (`templates/dashboard/chat.html`, `static/css/dashboard.css`, `static/js/dashboard-chat.js`). Current chat is functional but basic — mentions, read receipts, threads, and typing/presence were just implemented (commits 25f54b9, 799a36a, 223ce38, 9fed200) with minimal styling. This redesign gives the whole surface, including those four features, a cohesive visual pass.

Style direction: match existing Hackclub Leaders dashboard theme (`--dash-*` tokens in `static/css/dashboard.css`, `--hackclub-*` brand colors in `static/css/base.css`), not an external reference app. No new brand identity — level up what's there.

## Scope

- CSS/HTML/JS only. No backend or API changes — all data (mentions, receipts, threads, typing, presence) already available from existing endpoints.
- Dark mode: reuse existing `--dash-*` token swap under `body.dark-mode` / prefers-color-scheme — no separate dark-mode-specific rules needed.
- Files touched: `templates/dashboard/chat.html`, `static/css/dashboard.css` (chat section, ~line 3899+), `static/js/dashboard-chat.js` (only where DOM structure changes require new render logic).

## Layout

Discord-style 3-pane, built on the existing `.chat-layout` / `.chat-sidebar` / `.chat-main` / `.chat-thread-panel` skeleton:

- **Channel rail** (`.chat-sidebar`): slimmer width, channel rows get hover/active state with a left accent bar in `--hackclub-red` on active, unread count as a pill-shaped badge.
- **Message flow** (`.chat-main` / `#chatMessages`): grouped-by-sender rendering. Avatar + name + timestamp shown once per group; consecutive messages from the same sender within a short time window (reuse existing grouping window logic if present, else ~5 min) stack tightly with no repeated chrome. Hover on a message reveals per-message timestamp + action menu (existing reply/edit/delete affordances).
- **Thread panel** (`.chat-thread-panel`): slides in from the right (~200ms ease transition), visually nested — indented, softer border — to read as "attached to" its parent message rather than a separate pane.

## Feature-specific treatment

- **Mentions**: `@Name` renders as a pill/chip (accent-tinted background, rounded corners). `@everyone` gets a visually stronger/distinct accent pill. A message that mentions the current user gets a subtle left-border highlight + tinted row background.
- **Read receipts**: small stacked avatar cluster ("seen by") anchored bottom-right of the last message in a channel; overflow beyond N avatars collapses to a "+N" chip.
- **Typing indicator**: animated 3-dot pulse plus grammar-aware text ("Alice is typing…", "Alice and Bob are typing…", "3 people are typing…"), fades in/out rather than popping.
- **Presence**: small green dot badge on the avatar corner for online members. Static — no pulse/blink, to avoid visual noise.
- **Threads**: reply affordance appears on hover of a grouped message ("💬 3 replies" pill beneath it). Clicking opens the thread panel per the Layout section above.

## Composer

Bottom bar (`.chat-composer`) redesigned: rounded input matching dashboard form-input styling, send button converted to an icon-button (consistent with `.icon-button` used elsewhere in the dashboard). Inline @mention autocomplete dropdown floats above the input, anchored to the `@` cursor position (existing autocomplete logic from the mentions implementation, restyled).

## Empty / loading states

Keep the existing skeleton-loader markup (`[data-skeleton="chat"]`) as-is. Restyle the "select a channel" empty state (`#chatEmpty`) with an icon + friendlier copy instead of plain text.

## Motion

Subtle only:
- Thread panel slide-in/out: ~200ms ease
- New message group fade-in on arrival: ~150ms
- Typing-dot pulse: looping CSS animation
- Everything else (hover states, badges, pills) is instant/static — no motion for its own sake.

## Out of scope

- Any backend/API/data-model changes
- New brand colors or fonts beyond existing `--hackclub-*` / `--dash-*` tokens
- Mobile-specific redesign beyond what the existing responsive chat-drawer pattern already handles (verify it still works post-redesign, don't redesign it)
