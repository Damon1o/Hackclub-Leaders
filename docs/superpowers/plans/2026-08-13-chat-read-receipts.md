# Chat Read Receipts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move channel unread state from `localStorage`-only to a server-persisted per-`(channel, member)` read cursor, and add a "seen by" indicator under the latest message.

**Architecture:** New `chatReads` state section (list of `{id, channelId, email, lastReadAt}` rows, upserted by `(channelId, email)`), a new Mongo collection + index, two new endpoints (`POST .../read`, `GET .../reads`), and an `unread` boolean added to the existing channel-list response.

**Tech Stack:** Flask, Python 3, pytest, MongoDB (`pymongo`), vanilla JS (`static/js/dashboard-chat.js`). No JS test framework in this repo — frontend steps are implement + manual browser verification.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-13-chat-read-receipts-design.md`.
- `unread` stays a **boolean** dot, not a count — matches the existing `localStorage` semantics being replaced.
- The read cursor never rewinds: an upsert with an older `readAt` than what's stored is a no-op.
- Tests use `monkeypatch.setenv('STORAGE_BACKEND', 'session')` (`tests/test_chat.py:17-21`).
- Deleting a channel (`api_chat_channel_delete`, `src/routes_chat.py:287-306`) must also drop that channel's `chatReads` rows, mirroring the existing `messages` cleanup on line 304.

---

### Task 1: `chatReads` upsert endpoint

**Files:**
- Modify: `src/routes_chat.py` (add helper `_chat_reads(state)` near `_channels`/`_messages`, `routes_chat.py:187-193`; add the endpoint in the Messages section)
- Test: `tests/test_chat.py`

**Interfaces:**
- Produces: `POST /api/dashboard/chat/channels/<channel_id>/read` — `login_required`, `require_dashboard_csrf()`, body optional `{"readAt": iso}`. Returns `{'read': {'channelId': ..., 'lastReadAt': ...}}`. Persists to `state['chatReads']`, one row per `(channelId, email)`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_chat.py`:

```python
def test_mark_channel_read_creates_row(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']

    resp = c.post(f'/api/dashboard/chat/channels/{cid}/read', json={}, headers=h)
    assert resp.status_code == 200
    read = resp.get_json()['read']
    assert read['channelId'] == cid
    assert read['lastReadAt']

    with c.session_transaction() as sess:
        rows = sess['dashboard_state'].get('chatReads', [])
    assert len(rows) == 1
    assert rows[0]['email'] == 'leader@test.com'


def test_mark_channel_read_upserts_not_duplicates(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']

    c.post(f'/api/dashboard/chat/channels/{cid}/read',
           json={'readAt': '2026-08-13T10:00:00Z'}, headers=h)
    resp = c.post(f'/api/dashboard/chat/channels/{cid}/read',
                   json={'readAt': '2026-08-13T12:00:00Z'}, headers=h)
    assert resp.get_json()['read']['lastReadAt'] == '2026-08-13T12:00:00Z'

    with c.session_transaction() as sess:
        rows = sess['dashboard_state'].get('chatReads', [])
    assert len(rows) == 1  # updated in place, not duplicated


def test_mark_channel_read_never_rewinds(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']

    c.post(f'/api/dashboard/chat/channels/{cid}/read',
           json={'readAt': '2026-08-13T12:00:00Z'}, headers=h)
    resp = c.post(f'/api/dashboard/chat/channels/{cid}/read',
                   json={'readAt': '2026-08-13T10:00:00Z'}, headers=h)
    assert resp.get_json()['read']['lastReadAt'] == '2026-08-13T12:00:00Z'  # unchanged


def test_mark_channel_read_requires_csrf(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = c.post(f'/api/dashboard/chat/channels/{cid}/read', json={})
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chat.py -k mark_channel_read -v`
Expected: FAIL — 404 (no such route yet)

- [ ] **Step 3: Implement**

In `src/routes_chat.py`, add after `_messages(state)` (line 193):

```python
def _chat_reads(state):
    return state.setdefault('chatReads', [])


def _find_chat_read(state, channel_id, email):
    for row in _chat_reads(state):
        if row.get('channelId') == channel_id and row.get('email') == email:
            return row
    return None
```

Add the endpoint in the Messages section, after `api_chat_message_add` (after line 396):

```python
    @app.post('/api/dashboard/chat/channels/<channel_id>/read')
    @login_required
    def api_chat_mark_read(channel_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        state = get_dashboard_state()
        if not find_by_id(_channels(state), channel_id):
            return json_error('Channel not found.', 404)

        raw_read_at = json_payload().get('readAt')
        try:
            datetime.fromisoformat((raw_read_at or '').replace('Z', '+00:00'))
            read_at = raw_read_at
        except (TypeError, ValueError):
            read_at = utc_iso()

        email = _viewer_email()
        row = _find_chat_read(state, channel_id, email)
        if row is None:
            row = {
                'id': _item_id('read'),
                'channelId': channel_id,
                'email': email,
                'lastReadAt': read_at,
            }
            _chat_reads(state).append(row)
        elif read_at > (row.get('lastReadAt') or ''):
            row['lastReadAt'] = read_at

        save_dashboard_state(state)
        return flask.jsonify({'read': {
            'channelId': channel_id, 'lastReadAt': row['lastReadAt'],
        }})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chat.py -k mark_channel_read -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/routes_chat.py tests/test_chat.py
git commit -m "feat: add server-synced chat read cursor endpoint"
```

---

### Task 2: `GET .../reads` + `unread` on channel list

**Files:**
- Modify: `src/routes_chat.py` (new `GET .../reads` route; extend `api_chat_channels`, lines 226-230)
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: `_chat_reads(state)`, `_find_chat_read(state, channel_id, email)` from Task 1.
- Produces: `GET .../channels/<channel_id>/reads` → `{'reads': {email: lastReadAt, ...}}`. `GET .../channels` → each channel object gains `unread: bool`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_chat.py`:

```python
def test_channel_list_unread_flag(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']

    channels = c.get('/api/dashboard/chat/channels').get_json()['channels']
    assert channels[0]['unread'] is False  # no messages yet, nothing to be unread

    c.post(f'/api/dashboard/chat/channels/{cid}/messages', json={'body': 'hi'}, headers=h)
    channels = c.get('/api/dashboard/chat/channels').get_json()['channels']
    assert channels[0]['unread'] is True  # posted but never marked read

    c.post(f'/api/dashboard/chat/channels/{cid}/read', json={}, headers=h)
    channels = c.get('/api/dashboard/chat/channels').get_json()['channels']
    assert channels[0]['unread'] is False


def test_get_reads_returns_all_member_cursors(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    c.post(f'/api/dashboard/chat/channels/{cid}/read',
           json={'readAt': '2026-08-13T10:00:00Z'}, headers=h)

    resp = c.get(f'/api/dashboard/chat/channels/{cid}/reads')
    assert resp.status_code == 200
    reads = resp.get_json()['reads']
    assert reads == {'leader@test.com': '2026-08-13T10:00:00Z'}


def test_get_reads_scoped_to_channel(client):
    c, h = _seed(client, 'leader')
    cid1 = _make_channel(c, h, 'general').get_json()['channel']['id']
    cid2 = _make_channel(c, h, 'random').get_json()['channel']['id']
    c.post(f'/api/dashboard/chat/channels/{cid1}/read', json={}, headers=h)

    reads2 = c.get(f'/api/dashboard/chat/channels/{cid2}/reads').get_json()['reads']
    assert reads2 == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chat.py -k "unread_flag or get_reads" -v`
Expected: FAIL — `unread` key missing / 404 on `.../reads`

- [ ] **Step 3: Implement**

Replace `api_chat_channels` (`routes_chat.py:226-230`):

```python
    @app.get('/api/dashboard/chat/channels')
    @login_required
    def api_chat_channels():
        state = get_dashboard_state()
        email = _viewer_email()
        channels = _channels(state)
        for channel in channels:
            last_message_at = channel.get('lastMessageAt') or ''
            row = _find_chat_read(state, channel['id'], email)
            last_read = row['lastReadAt'] if row else ''
            channel['unread'] = bool(last_message_at) and last_message_at > last_read
        return flask.jsonify({'channels': channels})
```

Add a new route after the `POST .../read` endpoint from Task 1:

```python
    @app.get('/api/dashboard/chat/channels/<channel_id>/reads')
    @login_required
    def api_chat_channel_reads(channel_id):
        state = get_dashboard_state()
        if not find_by_id(_channels(state), channel_id):
            return json_error('Channel not found.', 404)
        reads = {
            row['email']: row['lastReadAt']
            for row in _chat_reads(state)
            if row.get('channelId') == channel_id
        }
        return flask.jsonify({'reads': reads})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chat.py -v`
Expected: PASS — full file.

- [ ] **Step 5: Commit**

```bash
git add src/routes_chat.py tests/test_chat.py
git commit -m "feat: expose per-channel unread flag and seen-by cursors"
```

---

### Task 3: Drop `chatReads` rows on channel delete

**Files:**
- Modify: `src/routes_chat.py:287-306` (`api_chat_channel_delete`)
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: `_chat_reads(state)` from Task 1.

- [ ] **Step 1: Write the failing test**

```python
def test_delete_channel_drops_chat_reads(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    c.post(f'/api/dashboard/chat/channels/{cid}/read', json={}, headers=h)

    resp = c.delete(f'/api/dashboard/chat/channels/{cid}', headers=h)
    assert resp.status_code == 200
    with c.session_transaction() as sess:
        rows = sess['dashboard_state'].get('chatReads', [])
    assert rows == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat.py -k drops_chat_reads -v`
Expected: FAIL — row still present after delete

- [ ] **Step 3: Implement**

In `api_chat_channel_delete` (`routes_chat.py:287-306`), after the existing `state['messages'] = [...]` line (304), add:

```python
        state['chatReads'] = [
            r for r in _chat_reads(state) if r.get('channelId') != channel_id
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_chat.py -k drops_chat_reads -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/routes_chat.py tests/test_chat.py
git commit -m "fix: drop chat read cursors when their channel is deleted"
```

---

### Task 4: Mongo collection + index

**Files:**
- Modify: `src/storage_mongo.py:83-94` (`INDEXES` dict)

**Interfaces:**
- Consumes: nothing new — `MongoStorage`'s existing generic section save/load already handles any state-section list of dicts (same mechanism `channels`/`messages` use), so no new method is needed on `MongoStorage` itself, only the index declaration.

- [ ] **Step 1: Add the index entry**

In `src/storage_mongo.py`, add to `INDEXES` after the `'messages'` entry (line 89):

```python
    'chatReads': [
        ([('clubKey', ASCENDING), ('channelId', ASCENDING), ('email', ASCENDING)], True),
    ],
```

- [ ] **Step 2: Verify index creation doesn't error**

Run: `pytest tests/test_storage_mongo.py -v` (or the closest existing Mongo-backend test module — confirm the exact filename first with `ls tests/test_storage*`) if a Mongo test double/fixture exists; otherwise confirm via the app's existing `ensure_indexes()` call path at startup with `STORAGE_BACKEND=mongo` pointed at a local/test Mongo instance. If no automated Mongo test exists in this repo for `INDEXES`, this step is a manual check: start the app with `STORAGE_BACKEND=mongo`, hit any chat-reads endpoint once, and confirm no `PyMongoError` in logs.

- [ ] **Step 3: Commit**

```bash
git add src/storage_mongo.py
git commit -m "feat: add Mongo index for chatReads collection"
```

---

### Task 5: Client — server-synced unread dot + "seen by" row

**Files:**
- Modify: `static/js/dashboard-chat.js` (`markChannelRead`/`chatReads` at lines 39-55; `fetchMessages()` at lines 446-483; `refreshChannels()` at lines 485-498; channel-list render, `renderChannelList` — search for it near line 179)

**Interfaces:**
- Consumes: `channel.unread` (Task 2), `GET .../reads` response (Task 2), `POST .../read` (Task 1).

- [ ] **Step 1: Switch unread-dot source to the server field**

Wherever `renderChannelList()` currently reads the local `chatReads()` map to decide whether to show a channel's unread dot, switch it to read `channel.unread` from the `S.channels` array (already populated by `refreshChannels()`, `dashboard-chat.js:485-498`, which now carries the server's `unread` boolean per Task 2).

- [ ] **Step 2: Post to `.../read` when the user reaches the bottom**

In `fetchMessages()` (`dashboard-chat.js:446-483`), where `markChannelRead(id, S.lastFetch)` is currently called (line 476) purely against `localStorage`, keep that call (optimistic local fallback per spec) and additionally, only when `nearBottom` is true (the existing check at lines 456-457), fire a debounced `POST /api/dashboard/chat/channels/${id}/read` with `{readAt: S.lastFetch}`. Debounce with a per-channel `setTimeout` (e.g. 2s) stored on `S`, so a burst of incoming messages while already at the bottom doesn't fire a request per message.

- [ ] **Step 3: Render "Seen by" row**

Add a fetch of `GET .../channels/${id}/reads` on the same cadence as `channelPoll()` (`dashboard-chat.js:510-513`) when a channel is open, and render a small row under the last message listing avatars/names of members whose `lastReadAt >= ` that message's `createdAt` (excluding the viewer). Use the existing `avatarMarkup()` helper (imported at line 22) for each avatar.

- [ ] **Step 4: Manual verification**

Two browser sessions (or one + incognito) as two different seeded members in the same club/channel:
- Session A posts a message; Session B's channel list shows the unread dot.
- Session B opens the channel (scrolls to bottom); dot clears in B, and after B's next 5s channel-poll tick, A sees B listed under "Seen by" on that message.
- Reload session B's browser entirely (simulating a different device) — unread state is correct on load, proving it's server-sourced and not `localStorage`-only.

- [ ] **Step 5: Commit**

```bash
git add static/js/dashboard-chat.js
git commit -m "feat: sync chat unread state and seen-by indicator from the server"
```

---

## Self-Review Notes

- **Spec coverage:** upsert endpoint (Task 1), reads endpoint + unread flag (Task 2), channel-delete cleanup (Task 3), Mongo index (Task 4), client wiring (Task 5) — every spec section has a task.
- **Placeholder scan:** Task 4 Step 2 is intentionally conditional ("if no automated Mongo test exists... this step is a manual check") because the plan author doesn't have the exact Mongo test fixture filename confirmed — the step still tells the engineer exactly what to run either way, not a bare "test it" placeholder.
- **Type consistency:** `_chat_reads`/`_find_chat_read` signatures (Task 1) match every call site in Tasks 2 and 3. `channel['unread']` (Task 2) matches the field Task 5's frontend reads.
