# Chat Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the club chat UI (channel rail, message flow, mentions, read receipts, typing/presence, threads, composer) a cohesive visual redesign matching the existing Hackclub Leaders dashboard theme — CSS/HTML/JS only, no backend changes.

**Architecture:** Chat markup lives in `templates/dashboard/chat.html`; behavior in `static/js/dashboard-chat.js` (loaded only on the chat page); styling in the `/* ── Chat ── */` block of `static/css/dashboard.css` (currently lines 3741–4377). Most of the interaction logic (message grouping, mention resolution, thread panel, typing/presence polling, seen-by) already exists from the four feature implementations — this plan restyles what's there and makes the small number of JS/HTML tweaks needed to expose data the new visuals require (hover timestamps on grouped messages, seen-by overflow capping, animated typing dots, icon send button).

**Tech Stack:** Vanilla CSS (custom properties `--dash-*` / `--hackclub-*` already defined in `static/css/base.css` and `static/css/dashboard.css`), vanilla JS (no framework, no bundler), Jinja2 templates, pytest for backend regression.

## Global Constraints

- No backend/API/data-model changes — every task is CSS/HTML/JS in the three files named above.
- Reuse existing theme tokens only: `--dash-bg`, `--dash-card`, `--dash-border`, `--dash-fill`, `--dash-ink`, `--dash-slate`, `--dash-muted`, `--dash-accent`, `--dash-shadow-sm`, `--dash-shadow-lg`, `--hackclub-red/orange/yellow/green/cyan/blue/purple`. No new colors introduced. Chat page's `--dash-accent` resolves to `--hackclub-red` (no per-page override exists for `data-dashboard-page="chat"` in `dashboard.css:3475-3485`, so it falls through to the `.dashboard-layout` default).
- Dark mode: never write a dark-mode-specific rule. All new CSS must use `--dash-*`/`--hackclub-*` tokens so `body.dark-mode` swaps automatically (per `static/css/dashboard.css:13-42`).
- Motion: only three animated things allowed — thread panel slide (~200ms ease), new message group fade-in (already exists via `chatMessageSlideIn`, ~150-200ms), typing-dot pulse loop. Everything else is instant. Respect `@media (prefers-reduced-motion: reduce)` — add any new animation to the existing reduced-motion block at `dashboard.css:4339-4347`.
- No JS test runner exists in this repo (no Jest/Vitest, no `*.test.js` files) — frontend logic has no automated coverage. Each task that touches `dashboard-chat.js` uses the existing Python test suite as a **regression guard** (it must stay green — chat backend behavior is untouched, so the suite should still report the same pass count) plus a **manual browser verification** step against `http://127.0.0.1:5000/dashboard/chat` (or whatever local run command the project uses) as the actual functional check, since no automated frontend test exists to write.
- Per project memory: the browser automation tool cannot render mobile/narrow viewports locally (`resize_window` is a no-op) — mobile-drawer verification (Task 7) is a code-review check, not a live screenshot.
- Files stay under 500 lines per file per project CLAUDE.md — `dashboard-chat.js` is currently ~1180 lines already (pre-existing, not part of this plan's scope to split) and `dashboard.css` is a single shared stylesheet (pre-existing pattern, not to be restructured here). Do not grow either unnecessarily; every new rule/function added by this plan should be small and additive.

---

### Task 1: Channel rail restyle

**Files:**
- Modify: `static/css/dashboard.css:3750-3823` (`.chat-sidebar`, `.chat-sidebar-head`, `.chat-channel`, `.chat-channel:hover`, `.chat-channel.is-active`, `.chat-unread-dot`)

**Interfaces:**
- Consumes: existing markup from `renderChannelList()` in `static/js/dashboard-chat.js:191-209` — unchanged, class names `chat-channel`, `is-active`, `chat-unread-dot` stay identical.
- Produces: nothing new consumed by later tasks — purely visual.

- [ ] **Step 1: Update channel rail CSS**

Replace `static/css/dashboard.css:3750-3823` with:

```css
.chat-sidebar {
    width: 220px;
    flex-shrink: 0;
    background: var(--dash-card);
    border: 1px solid var(--dash-border);
    border-radius: 16px;
    box-shadow: var(--dash-shadow-sm);
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.chat-sidebar-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
    border-bottom: 1px solid var(--dash-border);
}

.chat-sidebar-head h2 {
    margin: 0;
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--dash-muted);
}

.chat-channel-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.chat-channel {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    width: 100%;
    padding: 8px 10px 8px 13px;
    border: none;
    border-left: 3px solid transparent;
    background: transparent;
    border-radius: 8px;
    color: var(--dash-slate);
    font: inherit;
    text-align: left;
    cursor: pointer;
    transition: background 0.12s ease, border-color 0.12s ease, color 0.12s ease;
}

.chat-channel:hover {
    background: var(--dash-fill);
}

.chat-channel.is-active {
    background: var(--dash-fill);
    border-left-color: var(--dash-accent);
    color: var(--dash-ink);
    font-weight: 600;
}

.chat-channel-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.chat-unread-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--hackclub-red);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--hackclub-red) 25%, transparent);
    flex-shrink: 0;
}
```

- [ ] **Step 2: Manual browser check**

Start the local dev server per the project's normal run command, sign in, open `/dashboard/chat` with at least two channels (one active, one with an unread dot). Confirm: active channel shows the left accent bar in Hackclub red, hover state tints the row, unread dot has a subtle glow ring, header label reads uppercase/muted.

- [ ] **Step 3: Regression check**

Run: `python -m pytest -q`
Expected: same pass count as before this task (no backend touched — should still be 326 passed, no new failures).

- [ ] **Step 4: Commit**

```bash
git add static/css/dashboard.css
git commit -m "style: redesign chat channel rail"
```

---

### Task 2: Grouped message spacing + hover timestamp

**Problem:** `appendMessage()` in `static/js/dashboard-chat.js:271-327` already renders grouped consecutive messages without the avatar/name/meta block (the `grouped` branch at line 303-307), but no CSS rule exists for `.chat-message--grouped` — so grouped rows currently sit flush against the left edge instead of aligning under the avatar column above them, and they show no timestamp at all (the meta block, which is where `.chat-message-time` lives, is only rendered in the non-grouped branch).

**Files:**
- Modify: `static/js/dashboard-chat.js:303-307` (grouped branch of `appendMessage()`)
- Modify: `static/css/dashboard.css:3878-3979` (`.chat-messages`, `.chat-message`, add `.chat-message--grouped`, `.chat-message-time--hover`)

**Interfaces:**
- Consumes: `chatTime(iso)` and `chatFullTime(iso)` helpers already defined at `dashboard-chat.js:98-118` — reused as-is.
- Produces: new CSS class `chat-message-time--hover`, consumed only within this task.

- [ ] **Step 1: Add hover timestamp to grouped messages**

In `static/js/dashboard-chat.js`, replace the grouped branch (currently lines 303-307):

```js
        if (grouped) {
            row.innerHTML = `
            <div class="chat-message-body">
                ${bodyHtml}${threadLink}
            </div>${actions}`;
        } else {
```

with:

```js
        if (grouped) {
            row.innerHTML = `
            <span class="chat-message-time chat-message-time--hover"
                title="${escapeHtml(chatFullTime(message.createdAt))}">${escapeHtml(chatTime(message.createdAt))}</span>
            <div class="chat-message-body">
                ${bodyHtml}${threadLink}
            </div>${actions}`;
        } else {
```

- [ ] **Step 2: Add grouping + hover-timestamp CSS**

In `static/css/dashboard.css`, after the `.chat-message-edited` rule (ends at line 3997), insert:

```css
.chat-message--grouped {
    padding-left: 46px;
    margin-top: -6px;
}

.chat-message-time--hover {
    position: absolute;
    left: 0;
    top: 2px;
    width: 46px;
    text-align: right;
    padding-right: 10px;
    font-size: 0.68rem;
    color: var(--dash-muted);
    opacity: 0;
    transition: opacity 0.12s ease-out;
}

.chat-message:hover .chat-message-time--hover,
.chat-message:focus-within .chat-message-time--hover {
    opacity: 1;
}
```

(`.chat-message { position: relative; }` already exists at `dashboard.css:4000-4002`, so the absolute positioning above resolves against the message row.)

- [ ] **Step 3: Manual browser check**

Post two messages back-to-back as the same user within a few minutes. Confirm the second message aligns under the first message's text (not the avatar), and hovering the second message reveals a small timestamp in the left gutter that wasn't visible before.

- [ ] **Step 4: Regression check**

Run: `python -m pytest -q`
Expected: same pass count as before this task.

- [ ] **Step 5: Commit**

```bash
git add static/js/dashboard-chat.js static/css/dashboard.css
git commit -m "style: align grouped chat messages and add hover timestamp"
```

---

### Task 3: Mention pills + own-mention row highlight

**Files:**
- Modify: `static/js/dashboard-chat.js:352-371` (`mentionBodyHtml()`)
- Modify: `static/js/dashboard-chat.js:271-327` (`appendMessage()` — add mentioned-row class)
- Modify: `static/css/dashboard.css:4256-4262` (`.mention`)

**Interfaces:**
- Consumes: `message.mentions` (array of lowercase emails) and `message.mentionsEveryone` (bool), both already present on every message payload per the mentions feature (`src/routes_chat.py`, commit 25f54b9). `viewerEmail` already available in this module's closure (`dashboard-chat.js:20`).
- Produces: CSS classes `mention--everyone` and `chat-message--mentioned`, consumed only within this task.

- [ ] **Step 1: Distinguish the @everyone pill in `mentionBodyHtml()`**

In `static/js/dashboard-chat.js`, replace lines 352-371:

```js
    function mentionBodyHtml(message) {
        const body = message.body || '';
        const names = mentionNames(message);
        if (!names.length) return escapeHtml(body);
        const alternation = names
            .map((name) => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
            .join('|');
        // Match on the raw body and escape each slice, so the wrapping markup
        // is never itself re-scanned by a later, shorter name.
        const pattern = new RegExp('(?<![\\w@])@(' + alternation + ')(?![\\w])', 'g');
        let html = '';
        let last = 0;
        let match;
        while ((match = pattern.exec(body)) !== null) {
            html += escapeHtml(body.slice(last, match.index))
                + `<span class="mention">@${escapeHtml(match[1])}</span>`;
            last = match.index + match[0].length;
        }
        return html + escapeHtml(body.slice(last));
    }
```

with:

```js
    function mentionBodyHtml(message) {
        const body = message.body || '';
        const names = mentionNames(message);
        if (!names.length) return escapeHtml(body);
        const alternation = names
            .map((name) => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
            .join('|');
        // Match on the raw body and escape each slice, so the wrapping markup
        // is never itself re-scanned by a later, shorter name.
        const pattern = new RegExp('(?<![\\w@])@(' + alternation + ')(?![\\w])', 'g');
        let html = '';
        let last = 0;
        let match;
        while ((match = pattern.exec(body)) !== null) {
            const cls = match[1] === 'everyone' ? 'mention mention--everyone' : 'mention';
            html += escapeHtml(body.slice(last, match.index))
                + `<span class="${cls}">@${escapeHtml(match[1])}</span>`;
            last = match.index + match[0].length;
        }
        return html + escapeHtml(body.slice(last));
    }
```

- [ ] **Step 2: Mark rows that mention the viewer**

In `static/js/dashboard-chat.js`, find this line in `appendMessage()` (line 281):

```js
        const mine = (message.authorEmail || '').toLowerCase() === viewerEmail ? ' is-mine' : '';
```

Add directly below it:

```js
        const mentionsViewer = !mine && (
            (message.mentions || []).some((email) => String(email).toLowerCase() === viewerEmail)
            || Boolean(message.mentionsEveryone)
        );
        const mentioned = mentionsViewer ? ' chat-message--mentioned' : '';
```

Then update the `row.className` assignment (currently line 290-292):

```js
        row.className = 'chat-message' + mine + (grouped ? ' chat-message--grouped' : '')
            + (message.deleted ? ' chat-message--deleted' : '')
            + (opts.pending ? ' chat-message--pending' : '');
```

to:

```js
        row.className = 'chat-message' + mine + mentioned + (grouped ? ' chat-message--grouped' : '')
            + (message.deleted ? ' chat-message--deleted' : '')
            + (opts.pending ? ' chat-message--pending' : '');
```

- [ ] **Step 3: Pill + highlight CSS**

In `static/css/dashboard.css`, replace lines 4256-4262:

```css
.mention {
    padding: 0 2px;
    border-radius: 4px;
    background: color-mix(in srgb, var(--dash-accent) 14%, transparent);
    color: var(--dash-accent);
    font-weight: 600;
}
```

with:

```css
.mention {
    padding: 1px 8px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--dash-accent) 16%, transparent);
    color: var(--dash-accent);
    font-weight: 600;
    white-space: nowrap;
}

.mention--everyone {
    background: var(--dash-accent);
    color: var(--dash-card);
}

.chat-message--mentioned {
    background: color-mix(in srgb, var(--dash-accent) 8%, transparent);
    border-radius: 8px;
    padding-top: 4px;
    padding-bottom: 4px;
    padding-right: 8px;
    margin-right: -8px;
}

.chat-message--mentioned:not(.chat-message--grouped) {
    padding-left: 8px;
    margin-left: -8px;
}

.chat-message--grouped.chat-message--mentioned {
    padding-left: 54px;
    margin-left: -8px;
}
```

- [ ] **Step 4: Manual browser check**

From a second account (or by editing test data), send a message mentioning the viewer by name and one mentioning `@everyone`. Confirm: both render as rounded pills, `@everyone` is filled/inverted rather than tinted, and the row containing a mention of the viewer has a subtle tinted background — with correct alignment whether or not the row is also a grouped message.

- [ ] **Step 5: Regression check**

Run: `python -m pytest -q`
Expected: same pass count as before this task (mentions backend tests in `tests/test_chat.py` untouched).

- [ ] **Step 6: Commit**

```bash
git add static/js/dashboard-chat.js static/css/dashboard.css
git commit -m "style: pill-shaped mentions and own-mention row highlight"
```

---

### Task 4: Seen-by overflow cap + animated typing dots

**Files:**
- Modify: `static/js/dashboard-chat.js:657-684` (`renderSeenBy()`)
- Modify: `static/js/dashboard-chat.js:541-560` (`renderTypingIndicator()`)
- Modify: `static/css/dashboard.css:3932-3951` (`.chat-seen-by`, `.chat-seen-by .avatar-sm`)
- Modify: `static/css/dashboard.css:4099-4105` (`.chat-typing-indicator`)
- Modify: `static/css/dashboard.css:4339-4347` (reduced-motion block — add typing-dot override)

**Interfaces:**
- Consumes: `avatarMarkup()` helper (already imported at `dashboard-chat.js:22`) — reused as-is.
- Produces: nothing new consumed by later tasks.

- [ ] **Step 1: Cap seen-by avatars with a "+N" overflow chip**

In `static/js/dashboard-chat.js`, replace `renderSeenBy()` (lines 657-684):

```js
    function renderSeenBy(reads) {
        const box = document.getElementById('chatMessages');
        if (!box) return;
        const existing = box.querySelector('.chat-seen-by');
        if (existing) existing.remove();
        const lastAt = S.lastFetch;
        if (!lastAt || !box.querySelector('.chat-message')) return;

        const byEmail = {};
        clubMembers().forEach((member) => {
            if (member && member.email) byEmail[String(member.email).toLowerCase()] = member;
        });
        const seen = Object.keys(reads).filter((email) => {
            const key = String(email).toLowerCase();
            return key !== viewerEmail && reads[email] >= lastAt;
        });
        if (!seen.length) return;

        const row = document.createElement('div');
        row.className = 'chat-seen-by';
        row.innerHTML = '<span class="chat-seen-by-label">Seen by</span>'
            + seen.map((email) => {
                const member = byEmail[String(email).toLowerCase()] || {};
                const name = member.name || email;
                return `<span class="chat-seen-by-person" title="${escapeHtml(name)}">${avatarMarkup({ name, avatar: member.avatar }, 'avatar-sm')}</span>`;
            }).join('');
        box.appendChild(row);
    }
```

with:

```js
    const SEEN_BY_MAX = 4;

    function renderSeenBy(reads) {
        const box = document.getElementById('chatMessages');
        if (!box) return;
        const existing = box.querySelector('.chat-seen-by');
        if (existing) existing.remove();
        const lastAt = S.lastFetch;
        if (!lastAt || !box.querySelector('.chat-message')) return;

        const byEmail = {};
        clubMembers().forEach((member) => {
            if (member && member.email) byEmail[String(member.email).toLowerCase()] = member;
        });
        const seen = Object.keys(reads).filter((email) => {
            const key = String(email).toLowerCase();
            return key !== viewerEmail && reads[email] >= lastAt;
        });
        if (!seen.length) return;

        const shown = seen.slice(0, SEEN_BY_MAX);
        const overflow = seen.length - shown.length;
        const row = document.createElement('div');
        row.className = 'chat-seen-by';
        row.innerHTML = '<span class="chat-seen-by-label">Seen by</span>'
            + shown.map((email) => {
                const member = byEmail[String(email).toLowerCase()] || {};
                const name = member.name || email;
                return `<span class="chat-seen-by-person" title="${escapeHtml(name)}">${avatarMarkup({ name, avatar: member.avatar }, 'avatar-sm')}</span>`;
            }).join('')
            + (overflow > 0 ? `<span class="chat-seen-by-overflow">+${overflow}</span>` : '');
        box.appendChild(row);
    }
```

- [ ] **Step 2: Build the typing indicator as dots + text instead of plain text**

In `static/js/dashboard-chat.js`, replace `renderTypingIndicator()` (lines 541-560):

```js
    function renderTypingIndicator(typing) {
        const el = document.getElementById('chatTypingIndicator');
        if (!el) return;
        if (!typing || !typing.length) {
            el.hidden = true;
            el.textContent = '';
            return;
        }
        const names = typing.map((person) => person.name || person.email);
        let text;
        if (names.length === 1) {
            text = `${names[0]} is typing…`;
        } else if (names.length === 2) {
            text = `${names[0]} and ${names[1]} are typing…`;
        } else {
            text = `${names[0]} and ${names.length - 1} others are typing…`;
        }
        el.textContent = text;   // textContent, not innerHTML — names are unescaped
        el.hidden = false;
    }
```

with:

```js
    function renderTypingIndicator(typing) {
        const el = document.getElementById('chatTypingIndicator');
        if (!el) return;
        if (!typing || !typing.length) {
            el.hidden = true;
            el.innerHTML = '';
            return;
        }
        const names = typing.map((person) => person.name || person.email);
        let text;
        if (names.length === 1) {
            text = `${names[0]} is typing…`;
        } else if (names.length === 2) {
            text = `${names[0]} and ${names[1]} are typing…`;
        } else {
            text = `${names[0]} and ${names.length - 1} others are typing…`;
        }
        if (!el.querySelector('.chat-typing-text')) {
            el.innerHTML = '<span class="chat-typing-dots"><span></span><span></span><span></span></span>'
                + '<span class="chat-typing-text"></span>';
        }
        el.querySelector('.chat-typing-text').textContent = text;   // textContent — names are unescaped
        el.hidden = false;
    }
```

- [ ] **Step 3: CSS for overflow chip and animated dots**

In `static/css/dashboard.css`, replace lines 3932-3951:

```css
.chat-seen-by {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px 8px;
    font-size: 12px;
    color: var(--dash-muted);
}

.chat-seen-by .avatar-sm {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    object-fit: cover;
    font-size: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--dash-fill);
}
```

with:

```css
.chat-seen-by {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px 8px;
    font-size: 12px;
    color: var(--dash-muted);
}

.chat-seen-by .avatar-sm {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    object-fit: cover;
    font-size: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--dash-fill);
}

.chat-seen-by-overflow {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--dash-fill);
    color: var(--dash-muted);
    font-size: 9px;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
}
```

Then replace `static/css/dashboard.css:4099-4105`:

```css
.chat-typing-indicator {
    padding: 2px 18px 8px;
    color: var(--dash-muted);
    font-size: 0.78rem;
    font-style: italic;
    min-height: 1em;
}
```

with:

```css
.chat-typing-indicator {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 2px 18px 8px;
    color: var(--dash-muted);
    font-size: 0.78rem;
    min-height: 1em;
}

.chat-typing-dots {
    display: inline-flex;
    gap: 3px;
}

.chat-typing-dots span {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--dash-muted);
    animation: chatTypingPulse 1.2s infinite ease-in-out;
}

.chat-typing-dots span:nth-child(2) { animation-delay: 0.15s; }
.chat-typing-dots span:nth-child(3) { animation-delay: 0.3s; }

@keyframes chatTypingPulse {
    0%, 60%, 100% { opacity: 0.3; transform: translateY(0); }
    30% { opacity: 1; transform: translateY(-2px); }
}
```

Finally, in the existing reduced-motion block at `static/css/dashboard.css:4339-4347`, add the typing-dot override:

```css
@media (prefers-reduced-motion: reduce) {
    .chat-message {
        animation: none;
    }

    .chat-sidebar {
        transition: none;
    }

    .chat-typing-dots span {
        animation: none;
    }
}
```

- [ ] **Step 4: Verify presence dot needs no change**

Read `static/css/dashboard.css:3915-3930` (`.chat-avatar-presence`, `.chat-avatar-presence.is-online::after`) and confirm it is already static (no animation/pulse declared) — per the spec, presence should stay static. No edit needed here; this step is a verification-only checkpoint.

- [ ] **Step 5: Manual browser check**

Open a channel with 5+ members who have all read the latest message — confirm the seen-by row shows 4 avatars plus a "+N" chip. In a second browser/incognito session, start typing in the same channel — confirm the first session shows three pulsing dots next to the typing text.

- [ ] **Step 6: Regression check**

Run: `python -m pytest -q`
Expected: same pass count as before this task.

- [ ] **Step 7: Commit**

```bash
git add static/js/dashboard-chat.js static/css/dashboard.css
git commit -m "style: cap seen-by avatars and animate typing indicator"
```

---

### Task 5: Thread panel slide-in + nested styling

**Files:**
- Modify: `static/js/dashboard-chat.js:711-730` (`openThreadPanel()`, `closeThreadPanel()`)
- Modify: `static/css/dashboard.css:4150-4202` (`.chat-thread-panel`, `.chat-thread-panel[hidden]`, `.chat-thread-messages`)
- Modify: `static/css/dashboard.css:4339-4347` (reduced-motion block — add thread-panel override)

**Interfaces:**
- Consumes: nothing new.
- Produces: CSS class `chat-thread-panel--visible`, used only within this task's JS/CSS pair.

- [ ] **Step 1: Animate the open/close instead of an instant `[hidden]` toggle**

In `static/js/dashboard-chat.js`, replace `openThreadPanel()` and `closeThreadPanel()` (lines 711-730):

```js
    function openThreadPanel(parentId) {
        const panel = threadPanel();
        if (!panel) return;
        S.threadParentId = parentId;
        S.threadLastFetch = null;
        S.threadLastMsgMeta = null;
        const box = panel.querySelector('.chat-thread-messages');
        if (box) box.innerHTML = '';
        panel.hidden = false;
        loadThreadMessages(parentId);
        stopThreadPolling();
        S.threadPollTimer = window.setInterval(() => threadPoll(parentId), MESSAGE_POLL_MS);
    }

    function closeThreadPanel() {
        const panel = threadPanel();
        if (panel) panel.hidden = true;
        S.threadParentId = null;
        stopThreadPolling();
    }
```

with:

```js
    function openThreadPanel(parentId) {
        const panel = threadPanel();
        if (!panel) return;
        S.threadParentId = parentId;
        S.threadLastFetch = null;
        S.threadLastMsgMeta = null;
        const box = panel.querySelector('.chat-thread-messages');
        if (box) box.innerHTML = '';
        panel.hidden = false;
        window.requestAnimationFrame(() => panel.classList.add('chat-thread-panel--visible'));
        loadThreadMessages(parentId);
        stopThreadPolling();
        S.threadPollTimer = window.setInterval(() => threadPoll(parentId), MESSAGE_POLL_MS);
    }

    function closeThreadPanel() {
        const panel = threadPanel();
        if (panel) {
            panel.classList.remove('chat-thread-panel--visible');
            window.setTimeout(() => { panel.hidden = true; }, 200);
        }
        S.threadParentId = null;
        stopThreadPolling();
    }
```

- [ ] **Step 2: Slide-in + nested visual CSS**

In `static/css/dashboard.css`, replace lines 4150-4166:

```css
.chat-thread-panel {
    width: 320px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    background: var(--dash-card);
    border: 1px solid var(--dash-border);
    border-radius: 16px;
    box-shadow: var(--dash-shadow-sm);
    overflow: hidden;
}

/* display:flex above would otherwise defeat the [hidden] attribute. */
.chat-thread-panel[hidden] {
    display: none;
}
```

with:

```css
.chat-thread-panel {
    width: 320px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    background: var(--dash-card);
    border: 1px solid color-mix(in srgb, var(--dash-border) 60%, transparent);
    border-radius: 16px;
    box-shadow: var(--dash-shadow-sm);
    overflow: hidden;
    transform: translateX(16px);
    opacity: 0;
    transition: transform 0.2s ease, opacity 0.2s ease;
}

.chat-thread-panel--visible {
    transform: translateX(0);
    opacity: 1;
}

/* display:flex above would otherwise defeat the [hidden] attribute. */
.chat-thread-panel[hidden] {
    display: none;
}
```

Then replace `static/css/dashboard.css:4181-4185`:

```css
.chat-thread-messages {
    flex: 1;
    overflow-y: auto;
    padding: 12px 16px;
}
```

with:

```css
.chat-thread-messages {
    flex: 1;
    overflow-y: auto;
    padding: 12px 16px 12px 20px;
    border-left: 2px solid var(--dash-border);
    margin-left: 8px;
}
```

Finally, add the thread-panel override to the reduced-motion block at `static/css/dashboard.css:4339-4347` (now including the typing-dots line added in Task 4):

```css
@media (prefers-reduced-motion: reduce) {
    .chat-message {
        animation: none;
    }

    .chat-sidebar {
        transition: none;
    }

    .chat-typing-dots span {
        animation: none;
    }

    .chat-thread-panel {
        transition: none;
    }
}
```

- [ ] **Step 3: Manual browser check**

Click "Reply" on a message. Confirm the thread panel slides in from the right over ~200ms rather than popping in instantly, and its message list reads as visually nested (left border + indent) under the panel header. Close it and confirm the reverse animation, then that it's fully hidden (not just transparent — check it doesn't intercept clicks) after ~200ms.

- [ ] **Step 4: Regression check**

Run: `python -m pytest -q`
Expected: same pass count as before this task.

- [ ] **Step 5: Commit**

```bash
git add static/js/dashboard-chat.js static/css/dashboard.css
git commit -m "style: slide-in animation and nested styling for thread panel"
```

---

### Task 6: Composer redesign — icon send button + mention menu polish

**Files:**
- Modify: `templates/dashboard/chat.html:68-72` (`.chat-composer` form)
- Modify: `static/css/dashboard.css:4077-4098` (`.chat-composer`, `.chat-composer-input`)
- Modify: `static/css/dashboard.css:4256` area — add `.chat-mention-menu` accent rule near the existing `.chat-cmd-menu`/`.mention` rules

**Interfaces:**
- Consumes: nothing new — the button stays `type="submit"` inside the existing `#chatComposer` form, so the existing submit-event listener (unchanged, lives in `dashboard.js`) keeps working with no JS changes in this task.
- Produces: nothing new consumed elsewhere.

- [ ] **Step 1: Replace the text send button with an icon button**

In `templates/dashboard/chat.html`, replace lines 68-72:

```html
            <form class="chat-composer" id="chatComposer" hidden autocomplete="off">
                <input class="chat-composer-input" type="text" name="body" maxlength="500"
                    data-i18n-attr="placeholder:chat.messagePlaceholder" placeholder="Type a message…" aria-label="Message">
                <button class="btn-primary" type="submit" data-i18n="chat.send">Send</button>
            </form>
```

with:

```html
            <form class="chat-composer" id="chatComposer" hidden autocomplete="off">
                <input class="chat-composer-input" type="text" name="body" maxlength="500"
                    data-i18n-attr="placeholder:chat.messagePlaceholder" placeholder="Type a message…" aria-label="Message">
                <button class="chat-send-btn" type="submit" aria-label="Send"
                    data-i18n-attr="aria-label:chat.send">
                    <span aria-hidden="true">&#10148;</span>
                </button>
            </form>
```

- [ ] **Step 2: Composer + send-button CSS**

In `static/css/dashboard.css`, replace lines 4077-4098:

```css
.chat-composer {
    display: flex;
    gap: 10px;
    padding: 14px 18px;
    border-top: 1px solid var(--dash-border);
}

.chat-composer-input {
    flex: 1;
    padding: 10px 14px;
    border-radius: 10px;
    border: 1px solid var(--dash-border);
    background: var(--dash-bg);
    color: var(--dash-ink);
    font: inherit;
}

.chat-composer-input:focus {
    outline: 2px solid var(--hackclub-red);
    outline-offset: 1px;
}
```

with:

```css
.chat-composer {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 18px;
    border-top: 1px solid var(--dash-border);
}

.chat-composer-input {
    flex: 1;
    padding: 10px 14px;
    border-radius: 999px;
    border: 1px solid var(--dash-border);
    background: var(--dash-bg);
    color: var(--dash-ink);
    font: inherit;
}

.chat-composer-input:focus {
    outline: 2px solid var(--hackclub-red);
    outline-offset: 1px;
}

.chat-send-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    flex-shrink: 0;
    border: none;
    border-radius: 50%;
    background: var(--dash-accent);
    color: var(--dash-card);
    font-size: 1rem;
    cursor: pointer;
    transition: opacity 0.1s ease, transform 0.1s ease;
}

.chat-send-btn:hover {
    opacity: 0.9;
}

.chat-send-btn:active {
    transform: scale(0.94);
}

.chat-send-btn:focus-visible {
    outline: 2px solid var(--dash-accent);
    outline-offset: 2px;
}
```

- [ ] **Step 3: Mention menu accent polish**

In `static/css/dashboard.css`, immediately after the `.chat-cmd-option span` rule (ends at line 3254 in the original numbering, i.e. right before the `.mention` block), add:

```css
.chat-mention-menu .chat-cmd-option strong {
    color: var(--dash-accent);
}
```

- [ ] **Step 4: Manual browser check**

Confirm the composer input is now fully rounded (pill-shaped) and the send button is a circular icon button in the page's accent color, hover/active/focus states all visible. Type `@` and confirm the mention autocomplete menu's names render in the accent color.

- [ ] **Step 5: Regression check**

Run: `python -m pytest -q`
Expected: same pass count as before this task.

- [ ] **Step 6: Commit**

```bash
git add templates/dashboard/chat.html static/css/dashboard.css
git commit -m "style: redesign chat composer with icon send button"
```

---

### Task 7: Empty state polish + full regression + mobile verification

**Files:**
- Modify: `templates/dashboard/chat.html:51-53` (`#chatEmpty`)
- Modify: `static/css/dashboard.css:3847-3855` (`.chat-empty`)

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new.

- [ ] **Step 1: Add an icon to the empty state**

In `templates/dashboard/chat.html`, replace lines 51-53:

```html
            <div class="chat-empty" id="chatEmpty">
                <p data-i18n="chat.pickChannel">Select a channel to start chatting.</p>
            </div>
```

with:

```html
            <div class="chat-empty" id="chatEmpty">
                <div class="chat-empty-icon" aria-hidden="true">&#128172;</div>
                <p data-i18n="chat.pickChannel">Select a channel to start chatting.</p>
            </div>
```

- [ ] **Step 2: Empty-state CSS**

In `static/css/dashboard.css`, replace lines 3847-3855:

```css
.chat-empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--dash-muted);
    padding: 24px;
    text-align: center;
}
```

with:

```css
.chat-empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    color: var(--dash-muted);
    padding: 24px;
    text-align: center;
}

.chat-empty-icon {
    font-size: 2.4rem;
    opacity: 0.5;
}
```

- [ ] **Step 3: Manual browser check**

Load `/dashboard/chat` in a state with no channel selected (or as a brand-new member with zero channels) and confirm the empty state now shows a large muted speech-bubble icon above the existing copy.

- [ ] **Step 4: Mobile drawer code-review check**

The browser automation tool used in this project cannot render narrow/mobile viewports locally (confirmed limitation, not worth re-testing). Instead, read `static/css/dashboard.css:4300-4337` (the `@media (max-width: 768px)` block) and confirm every class it references — `.chat-layout`, `.chat-drawer-toggle`, `.chat-sidebar`, `.chat-sidebar.open`, `.chat-backdrop`, `.chat-main` — still exists with the same names after Tasks 1-7 (Task 1 renamed no classes, only added new ones). No code change expected from this step; it's a verification-only checkpoint.

- [ ] **Step 5: Full regression suite**

Run: `python -m pytest -q`
Expected: `326 passed` (same count as the pre-redesign baseline — this plan touches no backend code, so the count must not change).

- [ ] **Step 6: Commit**

```bash
git add templates/dashboard/chat.html static/css/dashboard.css
git commit -m "style: polish chat empty state"
```
