# Chat Typing Indicators + Presence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show "X is typing…" under the chat compose box and an online/offline dot on message-author avatars, piggybacked entirely on the polling requests the client already makes — no websocket, no new persisted schema, no new poll loop.

**Architecture:** Two new module-level, in-memory dicts in `src/routes_chat.py` (`_typing_state`, `_presence`), matching the existing `_rate_buckets` pattern. A new `POST .../typing` endpoint records a typing signal; the existing `GET .../messages` response (polled every 500ms) gains a lazily-pruned `typing` array; the existing `GET .../channels` response (polled every 5s) gains an `onlineMembers` array and doubles as the presence heartbeat. Frontend reads both fields off responses it already parses.

**Tech Stack:** Flask, Python 3, pytest, vanilla JS (`static/js/dashboard-chat.js` + `static/js/dashboard.js`), no JS test framework in this repo — frontend steps are implement + manual browser verification, not TDD.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-13-chat-typing-presence-design.md`.
- No websocket, no new poll interval — typing rides the existing 500ms message poll (`fetchMessages()`), presence rides the existing 5s channel poll (`refreshChannels()`).
- Both `_typing_state` and `_presence` use `time.monotonic()` (already imported in `routes_chat.py`), matching `_rate_limit_retry_after`'s convention — not wall-clock, immune to clock adjustments.
- `TYPING_TTL_SECONDS = 5.0`; `PRESENCE_TTL_SECONDS = 15.0` (3x the 5s channel-poll cadence) — exact values from the spec.
- `_typing_state` and `_presence` are process-global dicts, not scoped by club. `onlineMembers` MUST be intersected with the requesting club's own `state['members']` emails on every read so presence never leaks across clubs, even though the underlying dict is shared.
- The `POST .../typing` endpoint does no channel-existence check — a stale/garbage `channel_id` just creates a harmless dict entry nothing ever reads.
- Tests use `monkeypatch.setenv('STORAGE_BACKEND', 'session')` (`tests/test_chat.py:17-21`), the existing `_seed(client, role, channels=None)` and `_make_channel(client, headers, name='general')` helpers (`tests/test_chat.py:36-77`) — reuse them exactly, don't invent new fixture patterns.
- No JS test framework in this repo — frontend tasks (4, 5) are implement + manual browser verification, not automated tests.

---

### Task 1: Module-level state + `POST .../typing` endpoint

**Files:**
- Modify: `src/routes_chat.py` (add near `_rate_buckets`, after `_rate_limit_retry_after`, `routes_chat.py:72-83`; add the endpoint in the Messages section, after `api_chat_message_add`, `routes_chat.py:351-396`)
- Test: `tests/test_chat.py`

**Interfaces:**
- Produces: `_typing_state: dict[str, dict[str, float]]` (channelId -> {email: expiry_monotonic_seconds}), `TYPING_TTL_SECONDS: float`, `_presence: dict[str, float]` (email -> last_seen_monotonic_seconds), `PRESENCE_TTL_SECONDS: float`, `reset_typing_presence()`. Task 2 reads `_typing_state`/`TYPING_TTL_SECONDS`; Task 3 reads/writes `_presence`/`PRESENCE_TTL_SECONDS`. Both later tasks' tests call `reset_typing_presence()` via the new autouse fixture this task adds.
- Produces: `POST /api/dashboard/chat/channels/<channel_id>/typing` -> `{'ok': True}`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_chat.py`, add a sibling to the existing `_reset_rate_limit` fixture (right after it, `tests/test_chat.py:24-33`):

```python
@pytest.fixture(autouse=True)
def _reset_typing_presence():
    # _typing_state / _presence are process-global dicts (see routes_chat.py);
    # clear them between tests so one test's typing/presence signals don't
    # leak into the next.
    try:
        from src.routes_chat import reset_typing_presence
        reset_typing_presence()
    except ImportError:
        pass
    yield
```

Then add the tests themselves:

```python
def test_post_typing_requires_csrf(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = c.post(f'/api/dashboard/chat/channels/{cid}/typing', json={})
    assert resp.status_code == 403


def test_post_typing_records_entry(client):
    from src.routes_chat import _typing_state

    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']

    resp = c.post(f'/api/dashboard/chat/channels/{cid}/typing', json={}, headers=h)
    assert resp.status_code == 200
    assert resp.get_json() == {'ok': True}
    assert 'leader@test.com' in _typing_state.get(cid, {})


def test_post_typing_does_not_require_existing_channel(client):
    c, h = _seed(client, 'leader')
    # A fire-and-forget ephemeral signal shouldn't 404 on a stale channel id.
    resp = c.post(
        '/api/dashboard/chat/channels/nonexistent-channel/typing', json={}, headers=h)
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chat.py -k post_typing -v`
Expected: FAIL — `test_post_typing_requires_csrf` gets 404 (route doesn't exist yet); `test_post_typing_records_entry` fails with `ImportError: cannot import name '_typing_state'`.

- [ ] **Step 3: Implement**

In `src/routes_chat.py`, add after `_rate_limit_retry_after` (line 83), before the `# ── Link previews` comment (line 86):

```python
# Typing: channelId -> {email: expiry_monotonic_seconds}. Presence:
# email -> last_seen_monotonic_seconds. Same "single-process app, module-level
# dict is enough" reasoning as _rate_buckets above — both are lost on
# restart, which is an accepted tradeoff (see spec's Error handling section).
_typing_state: dict[str, dict[str, float]] = {}
TYPING_TTL_SECONDS = 5.0

_presence: dict[str, float] = {}
PRESENCE_TTL_SECONDS = 15.0   # 3x the 5s channel-poll cadence


def reset_typing_presence():
    _typing_state.clear()
    _presence.clear()
```

Add the endpoint in `src/routes_chat.py`, in the Messages section after `api_chat_message_add` (after line 396), before `api_chat_message_delete` (line 398):

```python
    @app.post('/api/dashboard/chat/channels/<channel_id>/typing')
    @login_required
    def api_chat_typing(channel_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        _typing_state.setdefault(channel_id, {})[_viewer_email()] = (
            time.monotonic() + TYPING_TTL_SECONDS
        )
        return flask.jsonify({'ok': True})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chat.py -k post_typing -v`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/routes_chat.py tests/test_chat.py
git commit -m "feat: add chat typing-signal endpoint and ephemeral state store"
```

---

### Task 2: `typing` array on `GET .../messages`

**Files:**
- Modify: `src/routes_chat.py` (add `_typing_payload()` near `_within_window`, `routes_chat.py:211-220`; modify `api_chat_messages`, `routes_chat.py:310-349`)
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: `_typing_state`, `TYPING_TTL_SECONDS` from Task 1.
- Produces: `_typing_payload(channel_id: str, viewer_email: str, members: list[dict]) -> list[dict]` (each `{'email': str, 'name': str}`), called by both return paths of `api_chat_messages`. `GET .../messages` response gains `'typing': [...]`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_chat.py` (at the top of the file, alongside the existing `import json` / `from datetime import ...` lines, add `import time` — these tests read `time.monotonic()` directly):

```python
def test_typing_included_in_messages_excludes_self(client):
    from src.routes_chat import _typing_state

    c, h = _seed(client, 'leader')
    with c.session_transaction() as sess:
        sess['dashboard_state']['members'].append({
            'id': 'm2', 'name': 'Bob Lee', 'email': 'bob@test.com',
            'role': 'Member', 'avatar': '', 'status': 'Active',
        })
    cid = _make_channel(c, h).get_json()['channel']['id']

    c.post(f'/api/dashboard/chat/channels/{cid}/typing', json={}, headers=h)  # leader typing
    _typing_state.setdefault(cid, {})['bob@test.com'] = time.monotonic() + 5.0

    resp = c.get(f'/api/dashboard/chat/channels/{cid}/messages', headers=h)
    assert resp.status_code == 200
    # leader (the viewer) is excluded even though they also posted a typing signal
    assert resp.get_json()['typing'] == [{'email': 'bob@test.com', 'name': 'Bob Lee'}]


def test_typing_entry_expires_and_is_pruned(client, monkeypatch):
    from src.routes_chat import _typing_state

    c, h = _seed(client, 'leader')
    with c.session_transaction() as sess:
        sess['dashboard_state']['members'].append({
            'id': 'm2', 'name': 'Bob Lee', 'email': 'bob@test.com',
            'role': 'Member', 'avatar': '', 'status': 'Active',
        })
    cid = _make_channel(c, h).get_json()['channel']['id']

    fake_now = [1000.0]
    monkeypatch.setattr('src.routes_chat.time.monotonic', lambda: fake_now[0])
    _typing_state[cid] = {'bob@test.com': fake_now[0] + 5.0}   # expires at t=1005

    resp = c.get(f'/api/dashboard/chat/channels/{cid}/messages', headers=h)
    assert resp.get_json()['typing'] == [{'email': 'bob@test.com', 'name': 'Bob Lee'}]

    fake_now[0] = 1006.0   # past expiry
    resp = c.get(f'/api/dashboard/chat/channels/{cid}/messages', headers=h)
    assert resp.get_json()['typing'] == []
    assert 'bob@test.com' not in _typing_state.get(cid, {})   # lazily pruned on read
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chat.py -k typing_included_in_messages or typing_entry_expires -v`
Expected: FAIL — `KeyError: 'typing'` (the response has no such key yet)

- [ ] **Step 3: Implement**

In `src/routes_chat.py`, add after `_within_window` (line 220), before `def register(app):` (line 223):

```python
def _typing_payload(channel_id, viewer_email, members):
    """Members currently typing in `channel_id`, excluding `viewer_email`.

    Lazily prunes any entry whose TTL has passed on every read, so no
    background sweep is needed — the same pattern _rate_limit_retry_after
    uses for its own bucket.
    """
    bucket = _typing_state.get(channel_id)
    if not bucket:
        return []
    now = time.monotonic()
    expired = [email for email, expiry in bucket.items() if expiry <= now]
    for email in expired:
        del bucket[email]
    names_by_email = {
        (m.get('email') or '').strip().lower(): m.get('name') or m.get('email')
        for m in members
    }
    return [
        {'email': email, 'name': names_by_email.get(email, email)}
        for email in bucket
        if email != viewer_email
    ]
```

Replace `api_chat_messages` (`routes_chat.py:310-349`):

```python
    @app.get('/api/dashboard/chat/channels/<channel_id>/messages')
    @login_required
    def api_chat_messages(channel_id):
        """One page of a channel's thread, oldest message first.

        ?since=<iso>   everything newer than this timestamp (the poll path)
        ?before=<iso>  the page immediately older than this timestamp
        ?limit=<n>     page size, capped at MAX_MESSAGE_PAGE_SIZE

        `hasMore` reports whether older messages exist before the page
        returned, which is what the client's scroll-up loader keys off.
        `typing` reports who else is currently typing in this channel.
        """
        since = clean_text(request.args.get('since'), max_len=40)
        before = clean_text(request.args.get('before'), max_len=40)
        limit = _page_limit(request.args.get('limit'))

        backend = _storage()
        pager = getattr(backend, 'page_messages', None)
        if pager is not None:
            # Backend can page in the database — don't load the channel's
            # history into the process just to slice the tail off it.
            state = get_dashboard_state(['members', 'channels'])
            if not find_by_id(_channels(state), channel_id):
                return json_error('Channel not found.', 404)
            messages, has_more = pager(_club_key(), channel_id, limit, before, since)
            typing = _typing_payload(channel_id, _viewer_email(), state.get('members', []))
            return flask.jsonify({'messages': messages, 'hasMore': has_more, 'typing': typing})

        state = get_dashboard_state()
        if not find_by_id(_channels(state), channel_id):
            return json_error('Channel not found.', 404)

        typing = _typing_payload(channel_id, _viewer_email(), state.get('members', []))
        thread = [m for m in _messages(state) if m.get('channelId') == channel_id]
        thread.sort(key=lambda m: m.get('createdAt') or '')
        if since:
            thread = [m for m in thread if (m.get('createdAt') or '') > since]
            return flask.jsonify({'messages': thread, 'hasMore': False, 'typing': typing})
        if before:
            thread = [m for m in thread if (m.get('createdAt') or '') < before]
        has_more = len(thread) > limit
        return flask.jsonify({'messages': thread[-limit:], 'hasMore': has_more, 'typing': typing})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chat.py -v`
Expected: PASS — full file, to confirm no regression on the existing suite plus the new tests.

- [ ] **Step 5: Commit**

```bash
git add src/routes_chat.py tests/test_chat.py
git commit -m "feat: surface who else is typing on the chat messages poll"
```

---

### Task 3: `onlineMembers` array + presence heartbeat on `GET .../channels`

**Files:**
- Modify: `src/routes_chat.py:226-230` (`api_chat_channels`)
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: `_presence`, `PRESENCE_TTL_SECONDS` from Task 1.
- Produces: `GET .../channels` response gains `'onlineMembers': [email, ...]` (sorted). Every call also touches `_presence[_viewer_email()]` — this endpoint is the presence heartbeat, no separate one needed.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_chat.py`:

```python
def test_online_members_includes_viewer_after_heartbeat(client):
    c, h = _seed(client, 'leader')
    resp = c.get('/api/dashboard/chat/channels', headers=h)
    assert resp.status_code == 200
    assert resp.get_json()['onlineMembers'] == ['leader@test.com']


def test_online_members_excludes_stale_member(client, monkeypatch):
    from src.routes_chat import _presence

    c, h = _seed(client, 'leader')
    with c.session_transaction() as sess:
        sess['dashboard_state']['members'].append({
            'id': 'm2', 'name': 'Bob Lee', 'email': 'bob@test.com',
            'role': 'Member', 'avatar': '', 'status': 'Active',
        })
    fake_now = [1000.0]
    monkeypatch.setattr('src.routes_chat.time.monotonic', lambda: fake_now[0])
    _presence['bob@test.com'] = 1000.0

    resp = c.get('/api/dashboard/chat/channels', headers=h)
    assert set(resp.get_json()['onlineMembers']) == {'leader@test.com', 'bob@test.com'}

    fake_now[0] = 1000.0 + 16.0   # past PRESENCE_TTL_SECONDS (15s); bob ages out
    resp = c.get('/api/dashboard/chat/channels', headers=h)
    # leader's own heartbeat refreshes on this very call, so only bob drops off
    assert resp.get_json()['onlineMembers'] == ['leader@test.com']


def test_online_members_never_leaks_across_clubs(client):
    from src.routes_chat import _presence

    # A stale global entry left behind by some other club's viewer.
    _presence['ghost@other-club.com'] = time.monotonic()

    c, h = _seed(client, 'leader')
    resp = c.get('/api/dashboard/chat/channels', headers=h)
    assert 'ghost@other-club.com' not in resp.get_json()['onlineMembers']
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chat.py -k online_members -v`
Expected: FAIL — `KeyError: 'onlineMembers'` (the response has no such key yet)

- [ ] **Step 3: Implement**

Replace `api_chat_channels` (`routes_chat.py:226-230`):

```python
    @app.get('/api/dashboard/chat/channels')
    @login_required
    def api_chat_channels():
        state = get_dashboard_state()
        viewer = _viewer_email()
        # This poll is every member's most frequent chat request while the
        # page is open (every 5s) — it doubles as the presence heartbeat, so
        # no separate "I'm here" call is needed.
        _presence[viewer] = time.monotonic()

        member_emails = {
            (m.get('email') or '').strip().lower() for m in state.get('members', [])
        }
        now = time.monotonic()
        online_members = sorted(
            email for email in member_emails
            if email in _presence and now - _presence[email] < PRESENCE_TTL_SECONDS
        )
        return flask.jsonify({'channels': _channels(state), 'onlineMembers': online_members})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chat.py -v`
Expected: PASS — full file.

- [ ] **Step 5: Commit**

```bash
git add src/routes_chat.py tests/test_chat.py
git commit -m "feat: expose online club members on the chat channels poll"
```

---

### Task 4: Client — typing indicator under the compose box

**Files:**
- Modify: `templates/dashboard/chat.html` (add the indicator element after the composer form, line 72)
- Modify: `static/js/dashboard-chat.js` (add `TYPING_THROTTLE_MS` near line 32; add `notifyTyping()` and `renderTypingIndicator()`; call the latter from `fetchMessages()`, `dashboard-chat.js:446-483`; clear it in `closeChatThread()`, `dashboard-chat.js:221-233`; expose `notifyTyping` in the returned object, `dashboard-chat.js:753-775`)
- Modify: `static/js/dashboard.js` (add `typingThrottleUntil: 0` to `chatState`, line 1865-1877; add the `notifyTyping` forwarder near line 1929; wire it into the composer `input` listener, `dashboard.js:2483-2493`)
- Modify: `static/css/dashboard.css` (add `.chat-typing-indicator` near `.chat-composer-input:focus`, line 4056-4059)

**Interfaces:**
- Consumes: `payload.typing` from `GET .../messages` (Task 2) — `[{email, name}, ...]`; `apiRequest`, `S` (shared chat state) already available inside `dashboard-chat.js`.
- Produces: no new interface for other tasks — this is a leaf UI task, independent of Task 5.

- [ ] **Step 1: Add the indicator element to the template**

In `templates/dashboard/chat.html`, after the composer `</form>` (line 72), before `</main>` (line 73):

```html
            <form class="chat-composer" id="chatComposer" hidden autocomplete="off">
                <input class="chat-composer-input" type="text" name="body" maxlength="500"
                    data-i18n-attr="placeholder:chat.messagePlaceholder" placeholder="Type a message…" aria-label="Message">
                <button class="btn-primary" type="submit" data-i18n="chat.send">Send</button>
            </form>
            <p class="chat-typing-indicator" id="chatTypingIndicator" hidden aria-live="polite"></p>
        </main>
```

- [ ] **Step 2: Add the throttle constant, `notifyTyping()`, and `renderTypingIndicator()`**

In `static/js/dashboard-chat.js`, add after `CHAT_GROUP_MS` (line 32):

```javascript
    const CHAT_GROUP_MS = 5 * 60 * 1000;   // same-author messages within 5min render grouped
    const TYPING_THROTTLE_MS = 2000;       // client-side floor between POST .../typing calls
```

Add near `fetchMessages()` (before it, so it's defined by the time `dashboard.js` wires the composer's `input` listener in Task 4 Step 4):

```javascript
    function notifyTyping() {
        if (!S.activeId) return;
        const now = Date.now();
        if (now < S.typingThrottleUntil) return;
        S.typingThrottleUntil = now + TYPING_THROTTLE_MS;
        apiRequest(`/api/dashboard/chat/channels/${encodeURIComponent(S.activeId)}/typing`,
            { method: 'POST', body: {} }).catch(() => {
                /* fire-and-forget, same as fetchMessages()'s catch-and-continue:
                   a dropped signal just means the peer's indicator lags by up
                   to TYPING_THROTTLE_MS, nothing to recover here */
            });
    }

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
        el.textContent = text;   // textContent, not innerHTML — names come from the server unescaped
        el.hidden = false;
    }
```

- [ ] **Step 3: Render it from `fetchMessages()`, and clear it on channel close**

In `fetchMessages()` (`dashboard-chat.js:446-483`), call `renderTypingIndicator` unconditionally — it must run even on polls with no new messages, so it goes before the existing `if (!incoming.length) return;` short-circuit:

```javascript
    async function fetchMessages(id, initial) {
        try {
            const query = S.lastFetch ? `?since=${encodeURIComponent(S.lastFetch)}` : '';
            const payload = await apiRequest(
                `/api/dashboard/chat/channels/${encodeURIComponent(id)}/messages${query}`);
            if (id !== S.activeId) return;   // user switched channels mid-flight
            renderTypingIndicator(payload.typing);
            const incoming = payload.messages || [];
            if (!incoming.length) return;
```

(The rest of `fetchMessages()`, lines 454-483, is unchanged.)

In `closeChatThread()` (`dashboard-chat.js:221-233`), clear the indicator so it doesn't linger when the thread closes:

```javascript
    function closeChatThread() {
        const msgs = document.getElementById('chatMessages');
        const head = document.getElementById('chatThreadHead');
        const composer = document.getElementById('chatComposer');
        const empty = document.getElementById('chatEmpty');
        if (head) head.hidden = true;
        if (msgs) { msgs.hidden = true; msgs.innerHTML = ''; }
        if (composer) composer.hidden = true;
        if (empty) empty.hidden = false;
        renderTypingIndicator([]);
        S.lastFetch = null;
        S.lastMsgMeta = null;
        resetJumpButton();
    }
```

- [ ] **Step 4: Wire the composer's `input` event and expose `notifyTyping`**

In `static/js/dashboard-chat.js`, add `notifyTyping` to the returned object (`dashboard-chat.js:753-775`), alphabetically between `markChannelRead` and `prepareEditChannel`:

```javascript
            markChannelRead: markChannelRead,
            notifyTyping: notifyTyping,
            prepareEditChannel: prepareEditChannel,
```

In `static/js/dashboard.js`, add `typingThrottleUntil: 0` to `chatState` (line 1865-1877), after `cmdMenu`:

```javascript
        cmdMenu: null,     // command autocomplete menu element (created lazily)
        typingThrottleUntil: 0,   // Date.now() ms before which notifyTyping() is a no-op
    };
```

Add the forwarder (line ~1929), alphabetically between `markChannelRead` and `prepareEditChannel`:

```javascript
    function markChannelRead(...args) { return chat && chat.markChannelRead(...args); }
    function notifyTyping(...args) { return chat && chat.notifyTyping(...args); }
    function prepareEditChannel(...args) { return chat && chat.prepareEditChannel(...args); }
```

Wire it into the composer's `input` listener in `setupForms()` (`dashboard.js:2483-2493`):

```javascript
        const chatComposerInput = $('#chatComposer')?.elements.body;
        if (chatComposerInput) {
            chatComposerInput.addEventListener('input', () => {
                updateCmdMenu(chatComposerInput.value);
                notifyTyping();
            });
            chatComposerInput.addEventListener('blur', () => window.setTimeout(hideCmdMenu, 150));
```

(The rest of `setupForms()` is unchanged.)

- [ ] **Step 5: Add the CSS**

In `static/css/dashboard.css`, add after `.chat-composer-input:focus` (line 4056-4059), before `.chat-reactions` (line 4061):

```css
.chat-typing-indicator {
    padding: 2px 18px 8px;
    color: var(--dash-muted);
    font-size: 0.78rem;
    font-style: italic;
    min-height: 1em;
}
```

- [ ] **Step 6: Manual verification**

Run the app locally (see project's `run` conventions), open the chat page in two browser sessions (or one + incognito) as two different seeded members of the same club, both viewing the same channel:

- Session A types in the composer: within ~500ms, Session B shows "Test A is typing…" under its own compose box.
- Session A stops typing for 5+ seconds without sending: the indicator clears in Session B on its next poll (no explicit "stopped typing" signal needed — server-side TTL expiry handles it).
- Three or more members typing at once shows "X and N others are typing…".
- Switching channels or navigating away from chat clears the indicator (no stale text left showing).

- [ ] **Step 7: Commit**

```bash
git add templates/dashboard/chat.html static/js/dashboard-chat.js static/js/dashboard.js static/css/dashboard.css
git commit -m "feat: show a typing indicator under the chat compose box"
```

---

### Task 5: Client — presence dot on message-author avatars

**Files:**
- Modify: `static/js/dashboard-chat.js` (add `applyPresence()`; call it from `refreshChannels()`, `dashboard-chat.js:485-498`; wrap the avatar markup in `appendMessage()`, `dashboard-chat.js:282-292`)
- Modify: `static/js/dashboard.js` (add `onlineMembers: []` to `chatState`, line 1865-1877)
- Modify: `static/css/dashboard.css` (add `.chat-avatar-presence` near `.chat-message .avatar-sm`, line 3897-3913)

**Interfaces:**
- Consumes: `payload.onlineMembers` from `GET .../channels` (Task 3) — `[email, ...]`; `S` (shared chat state), `avatarMarkup` (`ctx.avatarMarkup`, already imported in `dashboard-chat.js:22`), `escapeHtml` (`dashboard-chat.js:23`).
- Produces: no new interface for other tasks — this is a leaf UI task, independent of Task 4.

- [ ] **Step 1: Add `applyPresence()` and call it from `refreshChannels()`**

In `static/js/dashboard-chat.js`, add near `refreshChannels()`:

```javascript
    function applyPresence(onlineEmails) {
        const online = new Set((onlineEmails || []).map((email) => (email || '').toLowerCase()));
        document.querySelectorAll('#chatMessages .chat-avatar-presence[data-presence-email]')
            .forEach((el) => {
                el.classList.toggle('is-online', online.has(el.dataset.presenceEmail));
            });
    }
```

Replace `refreshChannels()` (`dashboard-chat.js:485-498`):

```javascript
    async function refreshChannels() {
        try {
            const payload = await apiRequest('/api/dashboard/chat/channels');
            S.channels = payload.channels || S.channels;
            S.onlineMembers = payload.onlineMembers || [];
            applyPresence(S.onlineMembers);
            renderChannelList();
            if (S.activeId && !S.channels.some((channel) => channel.id === S.activeId)) {
                S.activeId = null;
                closeChatThread();
                if (S.channels.length) selectChannel(S.channels[0].id);
            }
        } catch (error) {
            /* transient — retry next tick */
        }
    }
```

- [ ] **Step 2: Wrap the avatar in `appendMessage()` with a presence-tagged container**

In `appendMessage()` (`dashboard-chat.js:246-297`), the non-grouped `row.innerHTML` branch (lines 282-292) currently reads:

```javascript
        } else {
            row.innerHTML = `
            ${avatarMarkup(person, 'avatar-sm')}
            <div class="chat-message-body">
                <div class="chat-message-meta">
                    <span class="chat-message-author">${escapeHtml(message.authorName || message.authorEmail || 'Member')}</span>
                    <span class="chat-message-time" title="${escapeHtml(chatFullTime(message.createdAt))}">${escapeHtml(chatTime(message.createdAt))}</span>
                    ${edited}
                </div>
                ${bodyHtml}
            </div>${actions}`;
        }
```

Replace it with:

```javascript
        } else {
            const authorEmail = (message.authorEmail || '').toLowerCase();
            const online = (S.onlineMembers || []).includes(authorEmail) ? ' is-online' : '';
            row.innerHTML = `
            <span class="chat-avatar-presence${online}" data-presence-email="${escapeHtml(authorEmail)}">
                ${avatarMarkup(person, 'avatar-sm')}
            </span>
            <div class="chat-message-body">
                <div class="chat-message-meta">
                    <span class="chat-message-author">${escapeHtml(message.authorName || message.authorEmail || 'Member')}</span>
                    <span class="chat-message-time" title="${escapeHtml(chatFullTime(message.createdAt))}">${escapeHtml(chatTime(message.createdAt))}</span>
                    ${edited}
                </div>
                ${bodyHtml}
            </div>${actions}`;
        }
```

(The dot is set at initial render from `S.onlineMembers`, already populated by the last `refreshChannels()` tick, so a message appended between two 5s channel-polls still shows the right state immediately rather than waiting for the next poll.)

- [ ] **Step 3: Initialize `S.onlineMembers`**

In `static/js/dashboard.js`, add `onlineMembers: []` to `chatState` (line 1865-1877), after `typingThrottleUntil` (added in Task 4 Step 4):

```javascript
        typingThrottleUntil: 0,   // Date.now() ms before which notifyTyping() is a no-op
        onlineMembers: [],        // emails online per the last GET .../channels poll
    };
```

- [ ] **Step 4: Add the CSS**

In `static/css/dashboard.css`, add after the `.chat-message .avatar-sm` block (line 3897-3913):

```css
.chat-avatar-presence {
    position: relative;
    display: inline-flex;
}

.chat-avatar-presence.is-online::after {
    content: '';
    position: absolute;
    right: -1px;
    bottom: -1px;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--hackclub-green);
    border: 2px solid var(--dash-bg);
}
```

- [ ] **Step 5: Manual verification**

With the same two-session setup as Task 4:

- Session A opens the chat page and posts a message. Once Session B's next 5s channel-poll lands, Session B sees a green dot on Session A's avatar next to that message.
- Session A closes its tab (or navigates away from chat entirely). Within `PRESENCE_TTL_SECONDS` (15s) of A's last channel-poll, Session B's dot for A disappears on a subsequent poll.
- A member who has never opened chat (no presence entry at all) shows no dot, not an error.
- Reload Session B's page entirely — the dot state is correct immediately after the first `refreshChannels()` poll (proving it isn't relying on any stale client-side cache).

- [ ] **Step 6: Commit**

```bash
git add static/js/dashboard-chat.js static/js/dashboard.js static/css/dashboard.css
git commit -m "feat: show an online presence dot on chat message avatars"
```

---

## Self-Review Notes

- **Spec coverage:** data model / TTL constants (Task 1), `POST .../typing` endpoint (Task 1), `typing` on `GET .../messages` with lazy pruning and self-exclusion (Task 2), `onlineMembers` on `GET .../channels` with the presence heartbeat and club-scoping (Task 3), frontend typing indicator (Task 4), frontend presence dot (Task 5), `reset_typing_presence()` test helper (Task 1) — every spec section maps to a task. The spec's edge cases (app restart clears state, no explicit "stopped typing" signal, unbounded-but-small dict growth) are accepted tradeoffs documented in the spec itself and don't need dedicated tests beyond the TTL-expiry tests already in Task 2/3.
- **Placeholder scan:** none — every backend step has real code with a concrete failing/passing test; frontend steps (4, 5) use manual-verification checklists instead of automated tests, consistent with the rest of this codebase's JS (no JS test framework), matching the same convention used in the mentions and read-receipts plans.
- **Type consistency:** `_typing_payload(channel_id, viewer_email, members)` (Task 2) matches its only call sites, both added in the same task. `_presence`/`PRESENCE_TTL_SECONDS` (Task 1) match the read/write sites in Task 3. `payload.typing` (Task 2's response shape) matches what `renderTypingIndicator()` reads in Task 4. `payload.onlineMembers` (Task 3's response shape) matches what `applyPresence()` and `appendMessage()` read in Task 5. `S.typingThrottleUntil` and `S.onlineMembers` are each initialized in `chatState` (Task 4 Step 4, Task 5 Step 3) before any code path reads them.
