# Chat threads / replies

Date: 2026-08-13

## Summary

Let a message be replied to instead of only appended to the main channel timeline. A reply is a message with a `parentId`; replies are hidden from the main channel view and surface only in a per-message thread panel, with a reply-count affordance on the parent. Single-level threading only — a reply cannot itself be replied to (no nested threads).

## Scope

Third of the chat-gap specs. Touches the same `messages` collection as mentions and read receipts but through orthogonal fields (`parentId`, `replyCount`, `lastReplyAt`) — no field overlap, can ship independently and in any order relative to the other two.

## Data model

`src/storage_mongo.py` message documents gain:

- `parentId: str | None` — set only on a reply; absent/`None` on a top-level message.
- `replyCount: int` — maintained on the **parent** message, incremented each time a reply is posted. Defaults to `0`, field omitted until the first reply (consistent with how `reactions` is only added via `setdefault` in `routes_chat.py:504`).
- `lastReplyAt: iso timestamp` — maintained on the parent alongside `replyCount`, so the thread affordance can show recency without a separate query.

`INDEXES['messages']` (`storage_mongo.py:86-89`) gains a third index for the thread-panel's own paging:

```python
([('clubKey', ASCENDING), ('parentId', ASCENDING), ('createdAt', ASCENDING)], False),
```

## Backend changes (`src/routes_chat.py`)

**`POST /api/dashboard/chat/channels/<channel_id>/messages`** (existing, lines 351-396) accepts an optional `parentId` in the JSON body:
1. If present, look up the parent via `_find_message(state, channel_id, parent_id)`. 404 (`'Message not found.'`) if missing or in a different channel.
2. Reject replying to a reply: if the parent itself has a `parentId`, return `json_error('Replies can only be added to a top-level message.')`. This is what keeps threading single-level.
3. Reject replying to a deleted parent: `if parent.get('deleted'): return json_error('This message was deleted.', 409)` — mirrors the existing reaction handler's same check (`routes_chat.py:495-496`).
4. On success, set `message['parentId'] = parent_id`, then `parent['replyCount'] = parent.get('replyCount', 0) + 1` and `parent['lastReplyAt'] = created_at`. Both the reply and the mutated parent are part of the same `save_dashboard_state(state)` call already at the end of the handler — no extra write.

**`GET /api/dashboard/chat/channels/<channel_id>/messages`** (existing, lines 310-349) gains a `?parentId=` query param:
- Absent (default) → **only top-level messages**: filter becomes `not m.get('parentId')`, applied in both the DB-pager branch and the in-process fallback branch. This is the behavior change that removes replies from the main channel view.
- Present → returns that thread's replies, chronological, with the same `since`/`before`/`limit` semantics already implemented — just scoped by `parentId == <value>` instead of `channelId == <value>` at the top level (channel is still checked so a caller can't fetch a thread from a channel they don't have, but replies are matched by `parentId` alone since a reply's own `channelId` already equals its parent's).

`MongoStorage.page_messages()` (`storage_mongo.py:395-424`) gains a `parent_id: str | None = None` parameter: when set, the query becomes `{'clubKey': club_key, 'parentId': parent_id}` (dropping `channelId` from the query, since `parentId` alone uniquely scopes a thread) instead of `{'clubKey': club_key, 'channelId': channel_id}`; when unset, add `'parentId': {'$exists': False}` to the existing top-level query so the DB path matches the in-process fallback's behavior change above.

No new endpoint needed — reusing the existing paged messages endpoint with a query param avoids a parallel implementation of paging, filtering, and the `hasMore` cursor logic.

## Frontend (`static/js/dashboard-chat.js`)

- Each top-level message row that has `replyCount > 0` renders a "💬 N repl{y,ies}" affordance below it (near where `.chat-message-actions` renders, `dashboard-chat.js:442-443`).
- Clicking it (or a "Reply" action on any top-level message, including ones with zero replies yet) opens a thread side panel: fetches `GET .../messages?parentId=<id>`, renders using the same message-row rendering `appendMessage()` (`dashboard-chat.js:246`) already builds, reused rather than duplicated.
- While the thread panel is open, it polls independently at the same `MESSAGE_POLL_MS` (500ms) cadence as the main channel (`messagePoll()`, `dashboard-chat.js:500-508`), scoped to `?parentId=<id>` — paused/cleared when the panel closes, same start/stop lifecycle pattern as `startChatPolling()`/`stopChatPolling()` (lines 515-530).
- The reply composer posts to the same `POST .../messages` endpoint with `parentId` set; it does not get its own endpoint or its own rate-limit bucket (replies count against the same per-author `_rate_buckets` as top-level messages — no reason to special-case it).
- Replying is disabled on a message that is itself a reply (parent already 1-level deep) — the "Reply" action is simply not rendered on rows where `message.parentId` is set.

## Error handling / edge cases

- Reply to a message that gets deleted between panel-open and send → 409 from the parent-deleted check, surfaced as a toast (`showToast`, already imported into the module, `dashboard-chat.js:26`), thread panel stays open so the user can retry against a different message.
- Reply to a message in a channel that gets deleted entirely → existing `api_chat_channel_delete` (`routes_chat.py:287-306`) already drops all `messages` with that `channelId` regardless of `parentId`, so replies are cleaned up automatically — no change needed there.
- A parent's `replyCount`/`lastReplyAt` update and the reply's own insert are not atomic under concurrent posts in the Airtable/session backends (whole-state read-modify-write, same as every other chat mutation today) — accepted, consistent with the rest of this file's existing concurrency model.

## Testing

Unit:
- Posting a reply sets `parentId` on the child and increments `replyCount`/`lastReplyAt` on the parent.
- Posting a reply to a reply is rejected.
- Posting a reply to a deleted parent is rejected with 409.
- `GET .../messages` with no `parentId` excludes replies; with `parentId=<id>` returns only that thread, oldest-first, respecting `limit`/`before`/`since`.

Integration:
- Full flow: post top-level message → post two replies → `GET` channel view shows the parent with `replyCount: 2` and no replies inline → `GET ?parentId=<id>` returns both replies in order.
- Deleting the channel removes both parent and replies (existing clear/delete behavior, extended coverage).
