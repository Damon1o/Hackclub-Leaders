# Chat Threads / Replies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a message be replied to instead of only appended to the main channel timeline — a reply carries `parentId`, is hidden from the main channel view, and surfaces in a per-message thread panel; the parent tracks `replyCount`/`lastReplyAt`. Single-level threading only.

**Architecture:** Server-side reply validation and parent bookkeeping in `src/routes_chat.py`'s existing message-add handler, reusing the existing paged messages endpoint with a new `?parentId=` query param rather than standing up a parallel thread endpoint. `MongoStorage.page_messages()` gains a `parent_id` parameter and a new compound index backs the thread-panel's own paging. Client thread panel reuses the existing `appendMessage()` row renderer and the existing polling lifecycle pattern, scoped to a thread instead of a channel.

**Tech Stack:** Flask, Python 3, pytest, MongoDB (`pymongo`), vanilla JS (`static/js/dashboard-chat.js`), no JS test framework in this repo — frontend steps are implement + manual browser verification, not TDD.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-13-chat-threads-design.md`.
- Single-level threading only — a reply can never itself be replied to. Enforced server-side (400) and hidden client-side (no "Reply" action on a reply row).
- `replyCount` defaults to `0`, field omitted until the first reply — same `setdefault`-on-first-use convention as `reactions` (`routes_chat.py:504`).
- Replying to a deleted parent is rejected with 409, mirroring the existing reaction handler's deleted-message check (`routes_chat.py:495-496`).
- The reply composer posts to the same `POST .../messages` endpoint and the same per-author rate-limit bucket as top-level messages — no new endpoint, no separate rate limit.
- Tests use `monkeypatch.setenv('STORAGE_BACKEND', 'session')` (`tests/test_chat.py:17-21`).
- Deleting a channel (`api_chat_channel_delete`, `src/routes_chat.py:287-306`) already drops all messages with that `channelId` regardless of `parentId` — no change needed there, but extend test coverage to confirm replies are included.

---

### Task 1: Reply validation + parent bookkeeping on message send

**Files:**
- Modify: `src/routes_chat.py:351-396` (`api_chat_message_add`)
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: `_find_message(state, channel_id, message_id)` (`routes_chat.py:195-199`, unchanged).
- Produces: message dict now optionally includes `parentId: str`; a parent message dict gains `replyCount: int` and `lastReplyAt: str` once it has at least one reply. Task 2 (GET filtering) and Task 4 (frontend) depend on these exact field names.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_chat.py`:

```python
def test_reply_sets_parent_id_and_increments_parent_count(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    parent = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'top level'}, headers=h,
    ).get_json()['message']

    resp = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'a reply', 'parentId': parent['id']}, headers=h,
    )
    assert resp.status_code == 200
    reply = resp.get_json()['message']
    assert reply['parentId'] == parent['id']

    with c.session_transaction() as sess:
        messages = sess['dashboard_state']['messages']
    stored_parent = next(m for m in messages if m['id'] == parent['id'])
    assert stored_parent['replyCount'] == 1
    assert stored_parent['lastReplyAt'] == reply['createdAt']


def test_second_reply_increments_reply_count_again(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    parent = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'top level'}, headers=h,
    ).get_json()['message']

    for _ in range(2):
        c.post(
            f'/api/dashboard/chat/channels/{cid}/messages',
            json={'body': 'a reply', 'parentId': parent['id']}, headers=h,
        )

    with c.session_transaction() as sess:
        messages = sess['dashboard_state']['messages']
    stored_parent = next(m for m in messages if m['id'] == parent['id'])
    assert stored_parent['replyCount'] == 2


def test_reply_to_missing_parent_rejected(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'a reply', 'parentId': 'nope'}, headers=h,
    )
    assert resp.status_code == 404
    assert resp.get_json()['error'] == 'Message not found.'


def test_reply_to_message_in_other_channel_rejected(client):
    c, h = _seed(client, 'leader')
    cid1 = _make_channel(c, h, 'general').get_json()['channel']['id']
    cid2 = _make_channel(c, h, 'random').get_json()['channel']['id']
    parent = c.post(
        f'/api/dashboard/chat/channels/{cid1}/messages',
        json={'body': 'top level'}, headers=h,
    ).get_json()['message']

    resp = c.post(
        f'/api/dashboard/chat/channels/{cid2}/messages',
        json={'body': 'a reply', 'parentId': parent['id']}, headers=h,
    )
    assert resp.status_code == 404


def test_reply_to_a_reply_rejected(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    parent = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'top level'}, headers=h,
    ).get_json()['message']
    reply = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'a reply', 'parentId': parent['id']}, headers=h,
    ).get_json()['message']

    resp = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'nested reply', 'parentId': reply['id']}, headers=h,
    )
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'Replies can only be added to a top-level message.'


def test_reply_to_deleted_parent_rejected(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    parent = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'top level'}, headers=h,
    ).get_json()['message']
    c.delete(
        f'/api/dashboard/chat/channels/{cid}/messages/{parent["id"]}', headers=h,
    )

    resp = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'a reply', 'parentId': parent['id']}, headers=h,
    )
    assert resp.status_code == 409
    assert resp.get_json()['error'] == 'This message was deleted.'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chat.py -k "reply" -v`
Expected: FAIL — `KeyError: 'parentId'` on the first test (field doesn't exist yet); the rejection tests fail because no `parentId` handling exists at all, so a "reply" is currently accepted as an ordinary top-level message (200 instead of 404/400/409).

- [ ] **Step 3: Implement**

In `src/routes_chat.py`, modify `api_chat_message_add` (`routes_chat.py:351-396`). Insert the parent lookup/validation after the existing rate-limit check (after line 372, before `user = session.get('user') or {}` at line 374):

```python
        parent = None
        parent_id = clean_text(json_payload().get('parentId'), max_len=40)
        if parent_id:
            parent = _find_message(state, channel_id, parent_id)
            if not parent:
                return json_error('Message not found.', 404)
            if parent.get('parentId'):
                return json_error(
                    'Replies can only be added to a top-level message.')
            if parent.get('deleted'):
                return json_error('This message was deleted.', 409)
```

Then extend the `message = {...}` dict literal (line 376-384) to set `parentId` when present, and update the parent's bookkeeping before the existing `_messages(state).append(message)` call (line 391):

```python
        user = session.get('user') or {}
        created_at = utc_iso()
        message = {
            'id': _item_id('msg'),
            'channelId': channel_id,
            'authorEmail': _viewer_email(),
            'authorName': user.get('name') or _viewer_email(),
            'authorAvatar': user.get('avatar') or '',
            'body': body,
            'createdAt': created_at,
        }
        if parent_id:
            message['parentId'] = parent_id
        if body and feature_enabled('FEATURE_CHAT_LINK_PREVIEWS'):
            url = first_url(body)
            if url:
                preview = fetch_link_preview(url)
                if preview:
                    message['linkPreview'] = preview
        _messages(state).append(message)
        if parent is not None:
            parent['replyCount'] = parent.get('replyCount', 0) + 1
            parent['lastReplyAt'] = created_at
        channel['lastMessageAt'] = created_at
        save_dashboard_state(state)
```

(The `parent` variable is the same dict object already inside `_messages(state)`'s list — from `_find_message()` — so mutating it in place is captured by the single `save_dashboard_state(state)` call already at the end of the handler; no extra write.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chat.py -v`
Expected: PASS — full file, to confirm no regression on the existing suite plus the 6 new tests.

- [ ] **Step 5: Commit**

```bash
git add src/routes_chat.py tests/test_chat.py
git commit -m "feat: add chat reply validation and parent reply-count bookkeeping"
```

---

### Task 2: Filter replies out of the top-level channel view; `?parentId=` scopes to a thread

**Files:**
- Modify: `src/routes_chat.py:310-349` (`api_chat_messages`)
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: `parentId` field on message dicts (Task 1).
- Produces: `GET .../messages` behavior change — default view excludes replies; `?parentId=<id>` returns only that thread. Task 4 (frontend) depends on `?parentId=` being honored with the same `since`/`before`/`limit` semantics as today.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_chat.py`:

```python
def test_get_messages_excludes_replies_by_default(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    parent = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'top level'}, headers=h,
    ).get_json()['message']
    c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'a reply', 'parentId': parent['id']}, headers=h,
    )

    resp = c.get(f'/api/dashboard/chat/channels/{cid}/messages')
    ids = [m['id'] for m in resp.get_json()['messages']]
    assert ids == [parent['id']]


def test_get_messages_with_parent_id_returns_only_that_thread(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    parent = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'top level'}, headers=h,
    ).get_json()['message']
    other_parent = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'another top level'}, headers=h,
    ).get_json()['message']
    reply1 = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'reply one', 'parentId': parent['id']}, headers=h,
    ).get_json()['message']
    reply2 = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'reply two', 'parentId': parent['id']}, headers=h,
    ).get_json()['message']
    c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'reply on other', 'parentId': other_parent['id']}, headers=h,
    )

    resp = c.get(
        f'/api/dashboard/chat/channels/{cid}/messages?parentId={parent["id"]}')
    ids = [m['id'] for m in resp.get_json()['messages']]
    assert ids == [reply1['id'], reply2['id']]


def test_get_messages_parent_id_respects_limit(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    parent = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'top level'}, headers=h,
    ).get_json()['message']
    for i in range(3):
        c.post(
            f'/api/dashboard/chat/channels/{cid}/messages',
            json={'body': f'reply {i}', 'parentId': parent['id']}, headers=h,
        )

    resp = c.get(
        f'/api/dashboard/chat/channels/{cid}/messages'
        f'?parentId={parent["id"]}&limit=2')
    payload = resp.get_json()
    assert len(payload['messages']) == 2
    assert payload['hasMore'] is True


def test_full_thread_flow_reply_count_and_scoped_fetch(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    parent = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'top level'}, headers=h,
    ).get_json()['message']
    c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'reply one', 'parentId': parent['id']}, headers=h,
    )
    c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'reply two', 'parentId': parent['id']}, headers=h,
    )

    channel_view = c.get(
        f'/api/dashboard/chat/channels/{cid}/messages').get_json()['messages']
    assert len(channel_view) == 1
    assert channel_view[0]['replyCount'] == 2

    thread_view = c.get(
        f'/api/dashboard/chat/channels/{cid}/messages'
        f'?parentId={parent["id"]}').get_json()['messages']
    assert len(thread_view) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_chat.py -k "parent_id or excludes_replies or thread_flow" -v`
Expected: FAIL — the default view still includes replies (`ids == [parent['id'], reply['id']]` instead of just the parent), and `?parentId=` is silently ignored so it returns the whole channel instead of the scoped thread.

- [ ] **Step 3: Implement**

In `src/routes_chat.py`, modify `api_chat_messages` (`routes_chat.py:310-349`):

```python
    @app.get('/api/dashboard/chat/channels/<channel_id>/messages')
    @login_required
    def api_chat_messages(channel_id):
        """One page of a channel's thread, oldest message first.

        ?since=<iso>     everything newer than this timestamp (the poll path)
        ?before=<iso>    the page immediately older than this timestamp
        ?limit=<n>       page size, capped at MAX_MESSAGE_PAGE_SIZE
        ?parentId=<id>   return only replies to this message instead of the
                         channel's top-level view (replies are otherwise
                         excluded from the default, parent-less view)

        `hasMore` reports whether older messages exist before the page
        returned, which is what the client's scroll-up loader keys off.
        """
        since = clean_text(request.args.get('since'), max_len=40)
        before = clean_text(request.args.get('before'), max_len=40)
        limit = _page_limit(request.args.get('limit'))
        parent_id = clean_text(request.args.get('parentId'), max_len=40)

        backend = _storage()
        pager = getattr(backend, 'page_messages', None)
        if pager is not None:
            # Backend can page in the database — don't load the channel's
            # history into the process just to slice the tail off it.
            state = get_dashboard_state(['members', 'channels'])
            if not find_by_id(_channels(state), channel_id):
                return json_error('Channel not found.', 404)
            messages, has_more = pager(
                _club_key(), channel_id, limit, before, since, parent_id)
            return flask.jsonify({'messages': messages, 'hasMore': has_more})

        state = get_dashboard_state()
        if not find_by_id(_channels(state), channel_id):
            return json_error('Channel not found.', 404)

        if parent_id:
            thread = [m for m in _messages(state) if m.get('parentId') == parent_id]
        else:
            thread = [m for m in _messages(state)
                      if m.get('channelId') == channel_id and not m.get('parentId')]
        thread.sort(key=lambda m: m.get('createdAt') or '')
        if since:
            thread = [m for m in thread if (m.get('createdAt') or '') > since]
            return flask.jsonify({'messages': thread, 'hasMore': False})
        if before:
            thread = [m for m in thread if (m.get('createdAt') or '') < before]
        has_more = len(thread) > limit
        return flask.jsonify({'messages': thread[-limit:], 'hasMore': has_more})
```

Note: `parent_id` matching alone is sufficient to scope a thread (a reply's own `channelId` already equals its parent's, per the spec), so the channel-membership check stays as the existing `find_by_id(_channels(state), channel_id)` guard — a caller still can't fetch a thread without naming a channel they have, they just aren't re-filtered by `channelId` once `parentId` is given.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_chat.py -v`
Expected: FAIL initially on the DB-pager branch's tests (session-backend tests don't hit `page_messages`, since the session backend has no `page_messages` attribute — confirm this by checking `hasattr`/`getattr` fallback triggers the in-process branch under `STORAGE_BACKEND=session`). All in-process-path tests from Steps 1 should PASS at this point; Task 3 makes the Mongo-backed `page_messages()` path support the same `parent_id` argument so it doesn't silently break when Mongo is configured — this task's tests already pass without it because `tests/test_chat.py` runs under the session backend.

Run: `pytest tests/test_chat.py -v`
Expected: PASS — full file.

- [ ] **Step 5: Commit**

```bash
git add src/routes_chat.py tests/test_chat.py
git commit -m "feat: exclude replies from channel view, add parentId thread fetch"
```

---

### Task 3: `page_messages()` gains a `parent_id` parameter; new Mongo index

**Files:**
- Modify: `src/storage_mongo.py:83-89` (`INDEXES['messages']`)
- Modify: `src/storage_mongo.py:395-424` (`MongoStorage.page_messages`)
- Test: `tests/test_storage_mongo.py` — confirm this file exists and its test-double/fixture conventions before writing (`ls tests/test_storage*`); if no Mongo test fixture exists in this repo, this task's Step 1/2/4 become a manual verification pass instead (see Step 2 note below), consistent with how the read-receipts plan's Mongo-index task handled the same situation.

**Interfaces:**
- Consumes: `parent_id` query param plumbed through from Task 2's `api_chat_messages`.
- Produces: `page_messages(self, club_key, channel_id, limit, before='', since='', parent_id=None)` — Task 2's call site (`pager(_club_key(), channel_id, limit, before, since, parent_id)`) must match this signature exactly.

- [ ] **Step 1: Check for an existing Mongo test fixture**

Run: `ls tests/test_storage*` (or the PowerShell equivalent `Get-ChildItem tests/test_storage*`)

If a `test_storage_mongo.py` (or similarly named) file exists with a Mongo test double/fixture already wired for `page_messages`, add these tests to it, adapting to whatever fixture helper it already exposes (e.g. an in-memory Mongo double or a `mongomock`-based client) — follow that file's existing test style for `page_messages` exactly, do not invent a new fixture pattern. The behavioral assertions to cover:

```python
def test_page_messages_default_excludes_replies(mongo_storage):
    # (adapt setup to the fixture's actual seeding helper)
    mongo_storage.save('club1', {
        'settings': {}, 'channels': [{'id': 'c1'}],
        'messages': [
            {'id': 'm1', 'channelId': 'c1', 'createdAt': '2026-08-13T10:00:00Z'},
            {'id': 'm2', 'channelId': 'c1', 'createdAt': '2026-08-13T10:01:00Z',
             'parentId': 'm1'},
        ],
    })
    messages, has_more = mongo_storage.page_messages('club1', 'c1', 50)
    assert [m['id'] for m in messages] == ['m1']


def test_page_messages_parent_id_returns_only_that_thread(mongo_storage):
    mongo_storage.save('club1', {
        'settings': {}, 'channels': [{'id': 'c1'}],
        'messages': [
            {'id': 'm1', 'channelId': 'c1', 'createdAt': '2026-08-13T10:00:00Z'},
            {'id': 'm2', 'channelId': 'c1', 'createdAt': '2026-08-13T10:01:00Z',
             'parentId': 'm1'},
            {'id': 'm3', 'channelId': 'c1', 'createdAt': '2026-08-13T10:02:00Z',
             'parentId': 'm1'},
        ],
    })
    messages, has_more = mongo_storage.page_messages(
        'club1', 'c1', 50, parent_id='m1')
    assert [m['id'] for m in messages] == ['m2', 'm3']
```

If no such fixture exists anywhere in `tests/`, skip straight to Step 3 (implement) and treat Step 4 as the manual verification described there — do not invent a new Mongo test harness as part of this plan; that is a separate, larger undertaking than this task.

- [ ] **Step 2: Run tests to verify they fail (if a fixture exists)**

Run: `pytest tests/test_storage_mongo.py -k page_messages -v`
Expected: FAIL — `TypeError: page_messages() got an unexpected keyword argument 'parent_id'`, and the default-view test fails because replies aren't excluded yet.

If no fixture exists, this step is a no-op — proceed to Step 3.

- [ ] **Step 3: Implement**

In `src/storage_mongo.py`, add the new index to `INDEXES['messages']` (after line 89, i.e. modify the existing entry):

```python
    'messages': [
        ([('clubKey', ASCENDING), ('channelId', ASCENDING), ('createdAt', ASCENDING)], False),
        ([('clubKey', ASCENDING), ('createdAt', ASCENDING)], False),
        ([('clubKey', ASCENDING), ('parentId', ASCENDING), ('createdAt', ASCENDING)], False),
    ],
```

Modify `page_messages` (`storage_mongo.py:395-424`):

```python
    def page_messages(
        self,
        club_key: str,
        channel_id: str,
        limit: int,
        before: str = '',
        since: str = '',
        parent_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        """One page of messages, oldest-first, plus whether older messages
        remain. `parent_id` set scopes to that thread's replies (matched by
        `parentId` alone — a reply's own `channelId` already equals its
        parent's, so `parentId` uniquely scopes a thread); `parent_id` unset
        returns the channel's top-level view, excluding replies. Served
        entirely by one of two (clubKey, ..., createdAt) indexes — the app
        never loads a whole channel or thread to slice the tail off it.
        """
        self._ensure_indexes_once()
        if parent_id:
            query: dict[str, Any] = {'clubKey': club_key, 'parentId': parent_id}
        else:
            query = {
                'clubKey': club_key,
                'channelId': channel_id,
                'parentId': {'$exists': False},
            }
        if since:
            query['createdAt'] = {'$gt': since}
            docs = self._find('messages', query, sort=[('createdAt', ASCENDING)])
            return [self._to_item(doc) for doc in docs], False

        if before:
            query['createdAt'] = {'$lt': before}
        # Walk backwards from the newest, take one extra to detect "has more",
        # then flip to chronological for the client.
        docs = self._find(
            'messages', query, sort=[('createdAt', DESCENDING)], limit=limit + 1
        )
        has_more = len(docs) > limit
        page = list(reversed(docs[:limit]))
        return [self._to_item(doc) for doc in page], has_more
```

Update the call site in `src/routes_chat.py` (Task 2) — confirm it now reads:

```python
            messages, has_more = pager(
                _club_key(), channel_id, limit, before, since, parent_id)
```

(This is already what Task 2 wrote — this step is just the cross-check that the positional argument order matches `page_messages`'s new signature: `club_key, channel_id, limit, before, since, parent_id`.)

- [ ] **Step 4: Run tests to verify they pass**

If a Mongo test fixture exists:
Run: `pytest tests/test_storage_mongo.py -k page_messages -v`
Expected: PASS

If no Mongo test fixture exists, this is a manual check instead: start the app with `STORAGE_BACKEND=mongo` pointed at a local/test Mongo instance, exercise `POST .../messages` with and without `parentId`, then `GET .../messages` and `GET .../messages?parentId=<id>`, and confirm via `mongosh` (or Compass) that:
- The `messages` collection now has three indexes on `clubKey`-prefixed keys (`db.messages.getIndexes()`).
- A reply document has `parentId` set; a top-level document does not have the key at all.
- No `PyMongoError` appears in the app logs.

Also run the full suite to confirm nothing else regressed:
Run: `pytest tests/test_chat.py -v`
Expected: PASS (session backend, unaffected by this task's Mongo-only changes).

- [ ] **Step 5: Commit**

```bash
git add src/storage_mongo.py tests/test_storage_mongo.py
git commit -m "feat: scope Mongo message paging by parentId and add its index"
```

(Omit `tests/test_storage_mongo.py` from the `git add` if Step 1 found no such file to add tests to.)

---

### Task 4: Frontend — reply affordance, thread panel, scoped polling, reply composer

**Files:**
- Modify: `static/js/dashboard-chat.js`
- Modify: `templates/dashboard/chat.html` — thread panel container markup, if the chat page layout needs a new element for it (check the file first for an existing empty panel slot before adding one)
- Modify: `static/css/dashboard.css` — thread panel + reply-count affordance styling, matching existing chat CSS tokens

**Interfaces:**
- Consumes: `message.replyCount` / `message.parentId` (Task 1), `GET .../messages?parentId=<id>` (Task 2), `POST .../messages` with `{body, parentId}` (Task 1), `appendMessage(message, opts)` (`dashboard-chat.js:246`, unchanged signature — reused, not duplicated), `MESSAGE_POLL_MS` (`dashboard-chat.js:30`, unchanged).
- Produces: no new interface for other tasks — this is a leaf UI task.

- [ ] **Step 1: Render the reply-count affordance on top-level messages**

In `appendMessage()` (`dashboard-chat.js:246-297`), a reply row never needs this affordance (it's not rendered on rows that are themselves replies — those never reach the main channel view per Task 2's filtering, so no `message.parentId` guard is needed inside `appendMessage()` itself). Add a thread-affordance element after `messageActionsMarkup()` is computed and rendered — insert into the non-grouped and grouped `row.innerHTML` templates, right after `${bodyHtml}` and before `${actions}`:

```javascript
        const threadLink = message.deleted ? '' : threadAffordanceMarkup(message);
```

Add `threadLink` into both `row.innerHTML` template literals (grouped and non-grouped branches) immediately after `${bodyHtml}`:

```javascript
        if (grouped) {
            row.innerHTML = `
            <div class="chat-message-body">
                ${bodyHtml}${threadLink}
            </div>${actions}`;
        } else {
            row.innerHTML = `
            ${avatarMarkup(person, 'avatar-sm')}
            <div class="chat-message-body">
                <div class="chat-message-meta">
                    <span class="chat-message-author">${escapeHtml(message.authorName || message.authorEmail || 'Member')}</span>
                    <span class="chat-message-time" title="${escapeHtml(chatFullTime(message.createdAt))}">${escapeHtml(chatTime(message.createdAt))}</span>
                    ${edited}
                </div>
                ${bodyHtml}${threadLink}
            </div>${actions}`;
        }
```

Add the `threadAffordanceMarkup()` function near `reactionsMarkup()` (after line 310):

```javascript
    function threadAffordanceMarkup(message) {
        const count = message.replyCount || 0;
        if (!count) return '';
        const label = count === 1 ? '1 reply' : `${count} replies`;
        return `<button class="chat-thread-open" type="button" data-open-thread="${escapeHtml(String(message.id))}">
            💬 ${escapeHtml(label)}</button>`;
    }
```

Add a "Reply" action to `messageActionsMarkup()` (`dashboard-chat.js:314-325`) — only on messages that are not themselves a reply (so replying to a reply is never offered):

```javascript
    function messageActionsMarkup(message, mine) {
        if (message.deleted) return '';
        const reactBtns = REACTION_EMOJI.map((emoji) =>
            `<button class="chat-msg-action" type="button" data-react="${emoji}" aria-label="React ${emoji}">${emoji}</button>`).join('');
        const replyBtn = message.parentId ? '' :
            `<button class="chat-msg-action" type="button" data-open-thread="${escapeHtml(String(message.id))}" aria-label="Reply in thread">Reply</button>`;
        const editBtn = mine
            ? '<button class="chat-msg-action" type="button" data-edit-msg aria-label="Edit message">Edit</button>'
            : '';
        const deleteBtn = (mine || isLeader)
            ? '<button class="chat-msg-action" type="button" data-delete-msg aria-label="Delete message">Delete</button>'
            : '';
        return `<span class="chat-message-actions">${reactBtns}${replyBtn}${editBtn}${deleteBtn}</span>`;
    }
```

- [ ] **Step 2: Add thread panel state and open/close lifecycle**

Near the other `S`-scoped chat constants (`dashboard-chat.js:29-33`), no new module-level constant is needed — the thread panel reuses `MESSAGE_POLL_MS`. Add thread panel functions after `stopChatPolling()` (`dashboard-chat.js:521-530`):

```javascript
    function openThreadPanel(parentId) {
        const panel = document.getElementById('chatThreadPanel');
        if (!panel) return;
        S.threadParentId = parentId;
        S.threadLastFetch = null;
        panel.querySelector('.chat-thread-messages').innerHTML = '';
        panel.hidden = false;
        loadThreadMessages(parentId, true);
        stopThreadPolling();
        S.threadPollTimer = window.setInterval(() => threadPoll(parentId), MESSAGE_POLL_MS);
    }

    function closeThreadPanel() {
        const panel = document.getElementById('chatThreadPanel');
        if (panel) panel.hidden = true;
        S.threadParentId = null;
        stopThreadPolling();
    }

    function stopThreadPolling() {
        if (S.threadPollTimer) {
            window.clearInterval(S.threadPollTimer);
            S.threadPollTimer = null;
        }
    }

    async function threadPoll(parentId) {
        if (document.hidden || page !== 'chat' || S.threadParentId !== parentId || S.threadPollBusy) return;
        S.threadPollBusy = true;
        try {
            await loadThreadMessages(parentId, false);
        } finally {
            S.threadPollBusy = false;
        }
    }

    async function loadThreadMessages(parentId, initial) {
        try {
            const query = (!initial && S.threadLastFetch)
                ? `?parentId=${encodeURIComponent(parentId)}&since=${encodeURIComponent(S.threadLastFetch)}`
                : `?parentId=${encodeURIComponent(parentId)}`;
            const payload = await apiRequest(
                `/api/dashboard/chat/channels/${encodeURIComponent(S.activeId)}/messages${query}`);
            if (S.threadParentId !== parentId) return;   // panel switched threads mid-flight
            const incoming = payload.messages || [];
            if (!incoming.length) return;
            const panel = document.getElementById('chatThreadPanel');
            const box = panel && panel.querySelector('.chat-thread-messages');
            if (!box) return;
            const savedLastMsgMeta = S.lastMsgMeta;
            S.lastMsgMeta = S.threadLastMsgMeta || null;
            incoming.forEach((message) => {
                const row = appendMessage(message);
                if (row) box.appendChild(row);
            });
            S.threadLastMsgMeta = S.lastMsgMeta;
            S.lastMsgMeta = savedLastMsgMeta;
            S.threadLastFetch = incoming[incoming.length - 1].createdAt || S.threadLastFetch;
            box.scrollTop = box.scrollHeight;
        } catch (error) {
            /* keep showing what we have; the next poll retries */
        }
    }
```

Note: `appendMessage()` appends to `#chatMessages` internally (`dashboard-chat.js:248-249, 294`) — since the thread panel uses a different container (`.chat-thread-messages`), `appendMessage()` needs its target container to be an argument rather than hardcoded, OR (simpler, avoids touching every existing call site) the thread panel accepts the row `appendMessage()` already appended to `#chatMessages` and *moves* it into the thread panel's container:

Replace the row-handling loop above with the simpler move-based approach, since it requires zero changes to `appendMessage()` itself:

```javascript
            incoming.forEach((message) => {
                const row = appendMessage(message);
                if (row) box.appendChild(row);   // moves the row from #chatMessages into the thread panel
            });
```

(`Node.appendChild()` on an element already in the DOM moves it rather than cloning it, so this is correct as written above — no further change needed. This note exists so the implementer doesn't "fix" it into a duplicate-render bug.)

- [ ] **Step 3: Wire up the open/close/reply-send click handlers**

Find the chat page's existing delegated click handler for `#chatMessages` (search for where `data-react`, `data-edit-msg`, `data-delete-msg` are currently handled) and add `data-open-thread` to the same delegation:

```javascript
        const threadBtn = event.target.closest('[data-open-thread]');
        if (threadBtn) {
            openThreadPanel(threadBtn.dataset.openThread);
            return;
        }
```

Add a close button handler for the thread panel (wherever the chat page's other one-time DOM bindings are set up, e.g. near `bindChatVisibility()`):

```javascript
    function bindThreadPanel() {
        if (S.threadPanelBound) return;
        S.threadPanelBound = true;
        const panel = document.getElementById('chatThreadPanel');
        if (!panel) return;
        const closeBtn = panel.querySelector('[data-close-thread]');
        if (closeBtn) closeBtn.addEventListener('click', closeThreadPanel);
        const form = panel.querySelector('.chat-thread-reply-form');
        if (form) {
            form.addEventListener('submit', async (event) => {
                event.preventDefault();
                const input = form.querySelector('.chat-thread-reply-input');
                const body = (input.value || '').trim();
                if (!body || !S.activeId || !S.threadParentId) return;
                const submitBtn = form.querySelector('[type="submit"]');
                if (submitBtn) submitBtn.disabled = true;
                try {
                    await apiRequest(
                        `/api/dashboard/chat/channels/${encodeURIComponent(S.activeId)}/messages`,
                        { method: 'POST', body: { body, parentId: S.threadParentId } });
                    input.value = '';
                } catch (error) {
                    if (error && error.status === 409) {
                        showToast('This message was deleted.', 'error');
                        closeThreadPanel();
                    } else {
                        showToast(error.message, 'error');
                    }
                } finally {
                    if (submitBtn) submitBtn.disabled = false;
                }
            });
        }
    }
```

Call `bindThreadPanel()` from wherever the chat page's other one-time bind functions (e.g. `bindChatVisibility()`) are invoked during chat page setup.

Also close the thread panel when the active channel changes, so stale thread state can't leak across channels — find `selectChannel()` (referenced at `dashboard-chat.js:493`) and add `closeThreadPanel();` at its start.

- [ ] **Step 4: Add the thread panel markup**

In `templates/dashboard/chat.html`, add the panel container (hidden by default) near the existing `#chatMessages` container. First read the file to find the right insertion point and match existing markup conventions (class naming, ARIA attributes already used elsewhere in the template), then add:

```html
<aside id="chatThreadPanel" class="chat-thread-panel" hidden aria-label="Thread">
    <div class="chat-thread-header">
        <span>Thread</span>
        <button type="button" data-close-thread aria-label="Close thread">&times;</button>
    </div>
    <div class="chat-thread-messages"></div>
    <form class="chat-thread-reply-form">
        <input class="chat-thread-reply-input" type="text" maxlength="500"
               placeholder="Reply..." aria-label="Reply message">
        <button class="btn-primary small" type="submit">Send</button>
    </form>
</aside>
```

- [ ] **Step 5: Add CSS**

In `static/css/dashboard.css`, add near the other chat-specific rules (check existing usages of `--surface`/`--border`/`--accent` near the current chat message bubble and dropdown styles first, and match those exact token names rather than inventing new ones):

```css
.chat-thread-open {
    display: block;
    margin-top: 4px;
    padding: 2px 8px;
    font-size: 0.85em;
    color: var(--accent);
    background: color-mix(in srgb, var(--accent) 8%, transparent);
    border: none;
    border-radius: 6px;
    cursor: pointer;
}
.chat-thread-open:hover {
    background: color-mix(in srgb, var(--accent) 16%, transparent);
}
.chat-thread-panel {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: 340px;
    background: var(--surface);
    border-left: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    z-index: 30;
}
.chat-thread-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
}
.chat-thread-messages {
    flex: 1;
    overflow-y: auto;
    padding: 8px 16px;
}
.chat-thread-reply-form {
    display: flex;
    gap: 8px;
    padding: 12px 16px;
    border-top: 1px solid var(--border);
}
.chat-thread-reply-input {
    flex: 1;
}
```

- [ ] **Step 6: Manual verification**

Run the app locally (see project's `run` conventions), open the chat page as a seeded club with 2+ members, and verify:
- Posting a top-level message shows no thread affordance (0 replies).
- Clicking "Reply" on that message opens the thread panel, empty.
- Sending a reply from the panel's composer shows it in the panel; closing and reopening the panel (or reloading the page) shows the same reply persisted via `GET ?parentId=`.
- Back in the main channel view, the parent message now shows "💬 1 reply"; the reply itself does **not** appear inline in the main channel.
- Opening the thread panel on a message with existing replies loads them in order.
- In a second browser session (or incognito) as another member, opening the same thread while the first session posts a new reply shows the new reply appear via the panel's independent poll, without needing to refresh.
- The "Reply" action is not shown on a message that is itself a reply (open a thread, confirm no reply button on the rows inside the panel).
- Deleting the parent message from the main channel, then trying to send from an already-open thread panel for it, surfaces a toast ("This message was deleted.") and closes the panel.
- Switching to a different channel while a thread panel is open closes the panel (no stale thread bleeding into the new channel).

- [ ] **Step 7: Commit**

```bash
git add static/js/dashboard-chat.js static/css/dashboard.css templates/dashboard/chat.html
git commit -m "feat: add chat thread panel with reply affordance and scoped polling"
```

---

### Task 5: Extend channel-delete test coverage to replies

**Files:**
- Modify: `tests/test_chat.py`

**Interfaces:**
- Consumes: nothing new — exercises the existing `api_chat_channel_delete` (`routes_chat.py:287-306`), which already drops every message with the deleted `channelId` regardless of `parentId` since replies carry the same `channelId` as their parent.

- [ ] **Step 1: Write the test**

Add to `tests/test_chat.py`:

```python
def test_delete_channel_drops_replies_too(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    parent = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'top level'}, headers=h,
    ).get_json()['message']
    c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'a reply', 'parentId': parent['id']}, headers=h,
    )

    resp = c.delete(f'/api/dashboard/chat/channels/{cid}', headers=h)
    assert resp.status_code == 200

    with c.session_transaction() as sess:
        messages = sess['dashboard_state']['messages']
    assert messages == []
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `pytest tests/test_chat.py -k drops_replies_too -v`
Expected: PASS immediately — this is coverage-only, not a behavior change; `api_chat_channel_delete`'s existing `state['messages'] = [m for m in _messages(state) if m.get('channelId') != channel_id]` (`routes_chat.py:304`) already filters by `channelId`, which every reply shares with its parent, so no implementation change is needed for this test to pass. If it fails, that indicates channel-delete regressed during Tasks 1-4 and must be fixed before proceeding.

- [ ] **Step 3: Run the full suite**

Run: `pytest tests/test_chat.py -v`
Expected: PASS — full file, confirming the whole feature plus all pre-existing tests are green together.

- [ ] **Step 4: Commit**

```bash
git add tests/test_chat.py
git commit -m "test: confirm channel delete drops thread replies alongside top-level messages"
```

---

## Self-Review Notes

- **Spec coverage:** data model — `parentId`/`replyCount`/`lastReplyAt` (Task 1), Mongo index (Task 3); reply validation — missing parent, reply-to-reply, deleted parent (Task 1); `?parentId=` GET behavior change (Task 2); `page_messages()` `parent_id` param (Task 3); frontend affordance, panel, scoped polling, reply composer, no-reply-on-reply (Task 4); channel-delete cleanup (Task 5, coverage-only since the existing code already handles it, per the spec's own "no change needed there" note). Every spec section maps to a task.
- **Placeholder scan:** Task 3's Steps 1/2/4 are conditionally worded ("if a fixture exists... otherwise this is a manual check") because this plan doesn't have confirmed knowledge of whether `tests/test_storage_mongo.py` exists or what fixture it uses — same pattern the read-receipts plan used for its own Mongo-index task, and each branch still tells the implementer exactly what to run. No other step is conditional or vague; every step has real code.
- **Type consistency:** `page_messages(self, club_key, channel_id, limit, before='', since='', parent_id=None)` (Task 3) matches the positional call `pager(_club_key(), channel_id, limit, before, since, parent_id)` written in Task 2. `message['parentId']`/`message['replyCount']`/`message['lastReplyAt']` (Task 1) match the fields Task 2's filtering and Task 4's frontend (`message.replyCount`, `message.parentId`) read. `openThreadPanel(parentId)` / `closeThreadPanel()` / `loadThreadMessages(parentId, initial)` (Task 4) are used consistently across the click-delegation, `selectChannel()` hook, and reply-composer submit handler within the same task.
