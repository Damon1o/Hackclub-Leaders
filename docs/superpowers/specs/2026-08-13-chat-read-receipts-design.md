# Server-synced chat read receipts

Date: 2026-08-13

## Summary

Move "have I read this channel" from client-only (`localStorage` key `hcl:chatReads`, `static/js/dashboard-chat.js:39-55`) to a server-persisted per-member, per-channel read cursor. This makes unread state cross-device and adds a "seen by" row under the latest message showing which members have read it — neither exists today.

## Scope

Second of the chat-gap specs (after `2026-08-13-chat-mentions-design.md`). Independent of mentions, threads, and typing/presence — no shared code paths besides the existing channel/message endpoints in `src/routes_chat.py`.

## Data model

New state section `chatReads`, one row per `(channelId, email)` pair, upserted (never duplicated):

```python
{
    'id': 'read_...',
    'channelId': channel_id,
    'email': viewer_email,       # lowercased, matches _viewer_email()
    'lastReadAt': iso_timestamp,
}
```

`src/storage_mongo.py`: new collection `chatReads`, added to `INDEXES` (`storage_mongo.py:83-94`):

```python
'chatReads': [
    ([('clubKey', ASCENDING), ('channelId', ASCENDING), ('email', ASCENDING)], True),
],
```

Unique index on `(clubKey, channelId, email)` — the collection is small (members × channels), so an upsert-by-query is cheap and never needs the DB-side pager `page_messages()` uses for `messages`.

## Endpoints (`src/routes_chat.py`)

**`POST /api/dashboard/chat/channels/<channel_id>/read`**
- `login_required`, `require_dashboard_csrf()` — same guards every other chat mutation uses.
- Body optional: `{"readAt": iso}`; defaults to `utc_iso()` if omitted or unparseable (reuse the `_within_window` file's `datetime.fromisoformat` pattern for validation, not reuse of the function itself).
- Upserts the viewer's `chatReads` row for this channel: find existing by `(channelId, email)`, update `lastReadAt` if the new value is newer (monotonic — a stale client retry should never rewind the cursor), else insert.
- Returns `{'read': {'channelId': ..., 'lastReadAt': ...}}`.

**`GET /api/dashboard/chat/channels/<channel_id>/reads`**
- `login_required` only (no CSRF on a read).
- Returns every member's cursor for this channel: `{'reads': {email: lastReadAt, ...}}`. Members not yet in `chatReads` (never opened the channel) are simply absent — client treats absence as "unread everything."
- No leader gate — read receipts are visible to all channel members, consistent with the "seen by" pattern in mainstream chat apps.

**`GET /api/dashboard/chat/channels`** (existing, `routes_chat.py:226-230`) gains a per-channel `unread: bool` in the response, computed server-side: `channel.lastMessageAt > viewer's chatReads row for that channel` (or `True` if the viewer has no row and `lastMessageAt` is non-empty). This is the same boolean-dot semantics the current localStorage implementation already has — not a switch to unread *counts*.

## Frontend (`static/js/dashboard-chat.js`)

- `markChannelRead()`/`chatReads()` (lines 39-55) stop being the source of truth. Reads still happen locally for instant optimistic UI (dot disappears the moment you open a channel, no round-trip wait), but the authoritative unread dot comes from the `unread` field on the channel-list poll response (`refreshChannels()`, `routes_chat.py` channel list → `dashboard-chat.js:485-498`).
- The client posts `POST .../read` when the user is actually at the bottom of a channel's history (same `nearBottom` check already computed in `fetchMessages()`, `dashboard-chat.js:454-457`), debounced to at most once per few seconds per channel switch/scroll — not on every poll tick, to avoid write-amplifying a 500ms loop.
- A "Seen by {avatars}" row renders under the last message in the open channel, sourced from `GET .../reads`, refreshed on the same `CHANNEL_POLL_MS` (5s) cadence as `channelPoll()` (`dashboard-chat.js:510-513`) — no new interval. Only members whose `lastReadAt >= ` the last message's `createdAt` are shown as having seen it.
- `hcl:chatReads` localStorage key is kept (not removed) purely as the optimistic pre-server-response fallback described above; it is no longer read as the unread-dot source.

## Error handling / edge cases

- Viewer with no `chatReads` row for a channel they're a member of → treated as fully unread, no error.
- `POST .../read` with an older `readAt` than what's stored → no-op (cursor never rewinds).
- Channel deleted while a stale `chatReads` row still references it → orphaned rows are harmless (never queried outside their own channel scope) and are cleaned up incidentally by the existing channel-delete handler if extended (see Testing) — not required for correctness since `GET .../reads` is always scoped to a channel ID the caller already validated exists.

## Testing

Unit:
- Upsert creates a row on first read, updates `lastReadAt` on a second call with a later timestamp, no-ops on an older one.
- Channel list `unread` flag is `True` for no-row-yet, `False` once a read at/after `lastMessageAt` exists.
- `GET .../reads` returns only rows for the requested channel.

Integration:
- `POST` a message → `GET` channel list as a different member → `unread: True`. That member `POST`s `.../read` → subsequent `GET` channel list → `unread: False`.
- `GET .../reads` after two members read → both present with correct timestamps; a third member who never opened the channel → absent.

Extend `api_chat_channel_delete` (`routes_chat.py:287-306`) to also drop `chatReads` rows for the deleted channel, mirroring how it already drops `messages` (line 304) — add this as an explicit test rather than leaving it to the "harmless orphan" fallback above.
