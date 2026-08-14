# Chat @mentions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect `@Full Name` and `@everyone` in chat message bodies, persist resolved recipient emails on the message, and fire in-app notifications — plus a client autocomplete dropdown and highlighted rendering.

**Architecture:** Server-side mention resolution at message-send time in `src/routes_chat.py`, matching against the club's existing `state['members']` list. Two new persisted fields on the message document (`mentions`, `mentionsEveryone`). Notification delivery reuses `notifications.add_in_app_notification()`. Client `@`-trigger autocomplete is UX only — the server is authoritative.

**Tech Stack:** Flask, Python 3, pytest, MongoDB (`pymongo`), vanilla JS (`static/js/dashboard-chat.js`), no JS test framework in this repo — frontend steps are implement + manual browser verification, not TDD.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-13-chat-mentions-design.md`.
- In-app notification only — no email (per spec, chat mentions are too frequent for email parity with other notification types).
- `@everyone` is honored only when the author passes the same leader/mentor check `require_leader_api()` uses elsewhere in this file — otherwise it's plain text, no error.
- Self-mentions never notify.
- Tests use `monkeypatch.setenv('STORAGE_BACKEND', 'session')` (session backend, not Airtable) — see `tests/test_chat.py:17-21`.
- Message body max length stays `MAX_MESSAGE_LEN` (500, `src/helpers.py:611`) — mentions are detected within that existing body, no new length budget.

---

### Task 1: Mention-resolution helper (pure function)

**Files:**
- Modify: `src/routes_chat.py` (add near the other module-level helpers, after `_within_window`, `routes_chat.py:211-220`)
- Test: `tests/test_chat.py`

**Interfaces:**
- Produces: `resolve_mentions(body: str, members: list[dict], author_email: str, author_is_leader: bool) -> tuple[list[str], bool]` — returns `(sorted list of mentioned emails excluding author, mentions_everyone: bool)`. Later tasks (2, 3) call this directly.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_chat.py`:

```python
from src.routes_chat import resolve_mentions


def test_resolve_mentions_single_match():
    members = [
        {'name': 'Jane Doe', 'email': 'jane@test.com'},
        {'name': 'Bob Lee', 'email': 'bob@test.com'},
    ]
    mentions, everyone = resolve_mentions(
        'hey @Jane Doe check this out', members, 'bob@test.com', False
    )
    assert mentions == ['jane@test.com']
    assert everyone is False


def test_resolve_mentions_multiple_matches_sorted():
    members = [
        {'name': 'Jane Doe', 'email': 'jane@test.com'},
        {'name': 'Bob Lee', 'email': 'bob@test.com'},
    ]
    mentions, _ = resolve_mentions(
        '@Bob Lee and @Jane Doe both please look', members, 'someone@test.com', False
    )
    assert mentions == ['bob@test.com', 'jane@test.com']


def test_resolve_mentions_longest_name_wins():
    # "Jane" is a prefix of "Jane Doe" — the longer name must match first so
    # a member named plain "Jane" doesn't falsely absorb "@Jane Doe" text.
    members = [
        {'name': 'Jane Doe', 'email': 'jane.doe@test.com'},
        {'name': 'Jane', 'email': 'jane@test.com'},
    ]
    mentions, _ = resolve_mentions('@Jane Doe hi', members, 'x@test.com', False)
    assert mentions == ['jane.doe@test.com']


def test_resolve_mentions_excludes_self():
    members = [{'name': 'Jane Doe', 'email': 'jane@test.com'}]
    mentions, _ = resolve_mentions('@Jane Doe talking to myself', members, 'jane@test.com', False)
    assert mentions == []


def test_resolve_mentions_duplicate_names_both_notified():
    members = [
        {'name': 'Sam Kim', 'email': 'sam1@test.com'},
        {'name': 'Sam Kim', 'email': 'sam2@test.com'},
    ]
    mentions, _ = resolve_mentions('@Sam Kim ping', members, 'x@test.com', False)
    assert mentions == ['sam1@test.com', 'sam2@test.com']


def test_resolve_mentions_no_match():
    members = [{'name': 'Jane Doe', 'email': 'jane@test.com'}]
    mentions, everyone = resolve_mentions('no mentions here', members, 'x@test.com', False)
    assert mentions == []
    assert everyone is False


def test_resolve_mentions_everyone_by_leader():
    mentions, everyone = resolve_mentions('@everyone standup in 5', [], 'leader@test.com', True)
    assert everyone is True


def test_resolve_mentions_everyone_by_non_leader_ignored():
    mentions, everyone = resolve_mentions('@everyone standup in 5', [], 'member@test.com', False)
    assert everyone is False


def test_resolve_mentions_false_positive_inside_email_avoided():
    # A bare "@Jane" substring inside an unrelated word/address shouldn't
    # match without the full display name following it.
    members = [{'name': 'Jane Doe', 'email': 'jane@test.com'}]
    mentions, _ = resolve_mentions('contact jane@test.com directly', members, 'x@test.com', False)
    assert mentions == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chat.py -k resolve_mentions -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_mentions'`

- [ ] **Step 3: Implement `resolve_mentions`**

Add to `src/routes_chat.py`, after `_within_window` (line 220):

```python
_EVERYONE_RE = re.compile(r'(?<![\w@])@everyone(?![\w])')


def resolve_mentions(body, members, author_email, author_is_leader):
    """Resolve @-mentions in `body` against the club's member list.

    Returns (sorted emails to notify, excluding the author; whether
    @everyone was honored). Matching is by exact display name, longest
    name first, so "Jane Doe" matches before a member literally named
    "Jane" would false-positive on a prefix of it. A name is only matched
    when preceded by a literal '@' with no other word character
    immediately before it (so "jane@test.com" does not match "@Jane").
    """
    author_email = (author_email or '').strip().lower()
    text = body or ''
    matched_emails = set()

    by_name_desc = sorted(
        (m for m in members if m.get('name') and m.get('email')),
        key=lambda m: len(m['name']),
        reverse=True,
    )
    for member in by_name_desc:
        name = member['name']
        pattern = re.compile(
            r'(?<![\w@])@' + re.escape(name) + r'(?![\w])'
        )
        if pattern.search(text):
            matched_emails.add(member['email'].strip().lower())

    matched_emails.discard(author_email)

    mentions_everyone = bool(author_is_leader and _EVERYONE_RE.search(text))
    return sorted(matched_emails), mentions_everyone
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chat.py -k resolve_mentions -v`
Expected: PASS (all 9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/routes_chat.py tests/test_chat.py
git commit -m "feat: add chat mention-resolution helper"
```

---

### Task 2: Persist mentions on message send + notify

**Files:**
- Modify: `src/routes_chat.py:351-396` (`api_chat_message_add`)
- Modify: `src/storage_mongo.py` — no schema migration needed (Mongo is schemaless; new fields just start appearing), but confirm no `_INTERNAL_KEYS`/allowlist filters them out (`storage_mongo.py:104`, `_INTERNAL_KEYS` only strips `_id`/`clubKey` — new fields pass through untouched)
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: `resolve_mentions(...)` from Task 1; `notifications.add_in_app_notification(user_email, notification_type, title, message, data=None, *, state=None)` (`src/notifications.py:25-53`).
- Produces: message dict now includes `mentions: list[str]`, `mentionsEveryone: bool`; recipients get an in-app notification of `type: 'chat_mention'`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_chat.py`:

```python
def test_message_with_mention_notifies_recipient(client):
    c, h = _seed(client, 'leader')
    # Add a second member so there's someone to mention.
    with c.session_transaction() as sess:
        sess['dashboard_state']['members'].append({
            'id': 'm2', 'name': 'Bob Lee', 'email': 'bob@test.com',
            'role': 'Member', 'avatar': '', 'status': 'Active',
        })
    cid = _make_channel(c, h).get_json()['channel']['id']

    resp = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'hey @Bob Lee check this'}, headers=h,
    )
    assert resp.status_code == 200
    message = resp.get_json()['message']
    assert message['mentions'] == ['bob@test.com']
    assert message['mentionsEveryone'] is False

    with c.session_transaction() as sess:
        notifs = sess['dashboard_state'].get('notifications', [])
    assert any(
        n['type'] == 'chat_mention' and n.get('data', {}).get('messageId') == message['id']
        for n in notifs
    )


def test_message_self_mention_not_notified(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'note to self @Test Leader'}, headers=h,
    )
    assert resp.get_json()['message']['mentions'] == []
    with c.session_transaction() as sess:
        notifs = sess['dashboard_state'].get('notifications', [])
    assert not any(n['type'] == 'chat_mention' for n in notifs)


def test_everyone_mention_by_leader_notifies_all_other_members(client):
    c, h = _seed(client, 'leader')
    with c.session_transaction() as sess:
        sess['dashboard_state']['members'].append({
            'id': 'm2', 'name': 'Bob Lee', 'email': 'bob@test.com',
            'role': 'Member', 'avatar': '', 'status': 'Active',
        })
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': '@everyone standup now'}, headers=h,
    )
    assert resp.get_json()['message']['mentionsEveryone'] is True
    with c.session_transaction() as sess:
        notifs = sess['dashboard_state'].get('notifications', [])
    assert any(n['type'] == 'chat_mention' for n in notifs)  # bob notified, leader excluded


def test_everyone_mention_by_member_not_honored(client):
    c, h = _seed(client, 'member')
    cid = _make_channel(c, h).get_json()  # member can't create channel
    assert cid.status_code == 403
    # Seed a channel directly instead, member can only post to it.
    with c.session_transaction() as sess:
        sess['dashboard_state']['channels'] = [_SEED_CHANNEL]
    resp = c.post(
        f'/api/dashboard/chat/channels/{_SEED_CHANNEL["id"]}/messages',
        json={'body': '@everyone anyone around?'}, headers=h,
    )
    assert resp.get_json()['message']['mentionsEveryone'] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chat.py -k mention -v`
Expected: FAIL — `KeyError: 'mentions'` (field doesn't exist yet)

- [ ] **Step 3: Implement**

In `src/routes_chat.py`, add the import (top of file, alongside existing `from .helpers import (...)`):

```python
from .notifications import add_in_app_notification
```

Modify `api_chat_message_add` (`routes_chat.py:351-396`) — insert after the `message = {...}` dict literal (line 384) and before the link-preview block (line 385):

```python
        mention_emails, mentions_everyone = resolve_mentions(
            body, state.get('members', []), _viewer_email(), viewer_is_leader()
        )
        message['mentions'] = mention_emails
        message['mentionsEveryone'] = mentions_everyone
```

And after `save_dashboard_state(state)` (line 393), before the `return` (line 396):

```python
        recipients = set(mention_emails)
        if mentions_everyone:
            recipients.update(
                (m.get('email') or '').strip().lower() for m in state.get('members', [])
            )
        recipients.discard(_viewer_email())
        channel_name = channel.get('name') or 'the channel'
        for recipient in recipients:
            if not recipient:
                continue
            add_in_app_notification(
                recipient,
                'chat_mention',
                f"{message['authorName']} mentioned you in #{channel_name}",
                body[:200],
                {'channelId': channel_id, 'messageId': message['id']},
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chat.py -v`
Expected: PASS — full file, to confirm no regression on the existing 56 tests plus the new ones.

- [ ] **Step 5: Commit**

```bash
git add src/routes_chat.py tests/test_chat.py
git commit -m "feat: notify mentioned members and persist mentions on chat messages"
```

---

### Task 3: Client `@` autocomplete + mention highlighting

**Files:**
- Modify: `static/js/dashboard-chat.js`
- Modify: `templates/dashboard/chat.html` (dropdown container markup, if the compose area needs a new element)
- Modify: `static/css/dashboard.css` (dropdown + `.mention` highlight styling, dark-mode-aware via existing theme variables — same convention as the rest of chat CSS)

**Interfaces:**
- Consumes: `ctx.getState().members` (already available — `dashboard.js:30`, `dashboard.js:1900`); `message.mentions` / `message.mentionsEveryone` on the message objects returned by Task 2's endpoint (both `POST` response and poll `GET` responses, since the fields are persisted).
- Produces: no new interface for other tasks — this is a leaf UI task.

- [ ] **Step 1: Add the autocomplete dropdown**

In `static/js/dashboard-chat.js`, find the compose `<textarea>`'s existing `input` event wiring (search for where the compose input is bound, near the send-message form handler). Add an `input` listener that:
1. Looks backward from the cursor for an unclosed `@` (i.e. an `@` not followed by whitespace back to the start of the current word).
2. If found, filters `ctx.getState().members` by name prefix (case-insensitive) against the text after `@`, and renders a dropdown of up to 6 matches positioned under the cursor.
3. Arrow Up/Down move a highlighted selection; Enter or click inserts `@{member.name} ` (trailing space) replacing the partial `@text`, closes the dropdown.
4. Escape or a non-matching keystroke closes the dropdown.

- [ ] **Step 2: Render mention highlighting in message bodies**

In the message-body rendering path inside `appendMessage()` (`dashboard-chat.js:246`), after the body's existing HTML-escaping (via `escapeHtml`, imported at line 23), wrap any substring matching `@{name}` for each `email` in `message.mentions` (resolve `name` by looking up `email` in `ctx.getState().members`) in `<span class="mention">…</span>`. If `message.mentionsEveryone`, also wrap the literal `@everyone` substring.

- [ ] **Step 3: Add CSS**

In `static/css/dashboard.css`, add near the other chat-specific rules:

```css
.chat-mention-dropdown {
    position: absolute;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: var(--shadow-md);
    max-height: 220px;
    overflow-y: auto;
    z-index: 20;
}
.chat-mention-dropdown-item {
    padding: 6px 10px;
    cursor: pointer;
}
.chat-mention-dropdown-item.active,
.chat-mention-dropdown-item:hover {
    background: var(--surface-hover);
}
.mention {
    color: var(--accent);
    font-weight: 600;
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    border-radius: 4px;
    padding: 0 2px;
}
```

(Reuse whatever the actual token names are in `dashboard.css` — check existing usages of `--accent`/`--surface`/`--border` near the current chat message bubble styles and match them; don't invent new tokens.)

- [ ] **Step 4: Manual verification**

Run the app locally (see project's `run` conventions), open the chat page as a seeded club with 2+ members, and verify:
- Typing `@` opens the dropdown, filters as you type, arrow keys + Enter work, click works.
- A sent message with a mention renders the mention highlighted for both sender and (in a second browser session/incognito as another member) the recipient.
- The recipient sees a `chat_mention` notification appear in the notification center.
- A non-leader typing `@everyone` sends it as plain unhighlighted text and does not mass-notify.

- [ ] **Step 5: Commit**

```bash
git add static/js/dashboard-chat.js static/css/dashboard.css templates/dashboard/chat.html
git commit -m "feat: add @ mention autocomplete and highlighting to chat"
```

---

## Self-Review Notes

- **Spec coverage:** data model (Task 2), detection algorithm (Task 1), notification delivery (Task 2), frontend autocomplete + highlighting (Task 3), error/edge cases (no-match, self-mention, non-leader `@everyone` — all covered by Task 1/2 tests) all map to a task. Ambiguous-duplicate-name behavior is exercised in Task 1's test.
- **Placeholder scan:** none — every step has real code or a concrete manual-verification checklist (frontend has no test harness in this repo, so Task 3 uses manual verification instead of automated tests, consistent with the rest of this codebase's JS).
- **Type consistency:** `resolve_mentions` signature (Task 1) matches every call site in Task 2. `message['mentions']`/`message['mentionsEveryone']` field names match what Task 3's frontend reads.
