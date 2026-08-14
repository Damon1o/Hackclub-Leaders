# Chat typing indicators + presence

Date: 2026-08-13

## Summary

Show "X is typing…" under the compose box and an online/offline dot on member avatars in chat. Both are ephemeral, in-memory, piggybacked onto the existing polling requests — no websocket, no new persisted schema, no new poll loop.

## Scope

Fourth and last of the chat-gap specs. This is the one explicitly flagged during scoping as needing the most infrastructure; the design below deliberately avoids adding a realtime transport by riding the polling requests the client already makes every 500ms (messages) and 5s (channels).

## Why no websocket

The existing rate limiter (`src/routes_chat.py:62-65`) already documents the operating assumption: "This is a single-process app, so a module-level dict is enough." Typing/presence state is a natural fit for the same pattern — small, ephemeral, lost on restart, fine to be process-local. Introducing a websocket layer would mean a new dependency, a new connection-lifecycle to manage, and a departure from every other piece of chat infrastructure in this file. Piggybacking costs zero new requests: typing rides the 500ms message poll, presence rides the 5s channel poll.

## Data model

No persisted schema change. Two new module-level dicts in `src/routes_chat.py`, next to `_rate_buckets` (line 65):

```python
# channelId -> {email: expiry_monotonic_seconds}
_typing_state: dict[str, dict[str, float]] = {}
TYPING_TTL_SECONDS = 5.0

# email -> last_seen_monotonic_seconds
_presence: dict[str, float] = {}
PRESENCE_TTL_SECONDS = 15.0   # 3x the 5s channel-poll cadence
```

Both use `time.monotonic()` (already imported, used by `_rate_limit_retry_after`) — not wall-clock, consistent with the existing rate-limit bucket and immune to clock adjustments.

## Endpoints (`src/routes_chat.py`)

**`POST /api/dashboard/chat/channels/<channel_id>/typing`**
- `login_required`, `require_dashboard_csrf()`.
- No body needed. Sets `_typing_state.setdefault(channel_id, {})[_viewer_email()] = time.monotonic() + TYPING_TTL_SECONDS`.
- Returns `{'ok': True}`. No validation that the channel exists — a stale/garbage `channel_id` just creates a harmless dict entry nothing ever reads (no `find_by_id` round-trip needed for a fire-and-forget ephemeral signal).

**`GET /api/dashboard/chat/channels/<channel_id>/messages`** (existing, lines 310-349) response gains a `typing` array: every `email` in `_typing_state.get(channel_id, {})` whose expiry is still in the future and is not the viewer themself, resolved to `{email, name}` via the channel's member list already available in `state['members']`. Expired entries are lazily pruned on this same read (`del` any key whose expiry has passed) rather than needing a background sweep.

**`GET /api/dashboard/chat/channels`** (existing, lines 226-230) response gains `onlineMembers: [email, ...]`: every key in `_presence` whose `time.monotonic() - last_seen < PRESENCE_TTL_SECONDS`, intersected with the current club's `state['members']` emails (so presence never leaks across clubs — `_presence` is a single global dict but only club-member emails are ever surfaced to a club's own request). `_presence[_viewer_email()]` is also touched (`= time.monotonic()`) on every call to this endpoint, since it's already hit every 5s by any member with the chat page open — this *is* the presence heartbeat, no separate one needed.

## Frontend (`static/js/dashboard-chat.js`)

- The compose `<textarea>`'s `input` event triggers a throttled (client-side, max once per 2s) `POST .../typing` — a plain fire-and-forget `apiRequest` call, no response handling needed beyond swallowing errors (same pattern as `fetchMessages()`'s catch-and-continue, `dashboard-chat.js:480-482`).
- `fetchMessages()` (`dashboard-chat.js:446-483`), which already runs on the 500ms `messagePoll()` cadence, reads `payload.typing` from its existing response and renders "{name} is typing…" (or "{name} and N others" for 2+) in a small line under the compose box — cleared once the array is empty on a subsequent poll, no separate timeout needed client-side since the server already expires entries.
- `refreshChannels()` (`dashboard-chat.js:485-498`), which already runs on the 5s `channelPoll()` cadence, reads `payload.onlineMembers` and applies a green presence dot to any avatar currently rendered for that email — message-author avatars in the open thread (`appendMessage()`, wherever `avatarMarkup()` is called, `dashboard-chat.js:22`) get the dot toggled based on membership in the latest `onlineMembers` set. No new UI surface, no member roster panel — reuses avatars that already render.

## Error handling / edge cases

- App restart clears both dicts — everyone briefly shows offline/not-typing until their next poll tick repopulates it (≤5s for presence, ≤500ms for typing). Explicitly accepted, same tradeoff the existing rate limiter already makes.
- A member closes the tab without an explicit signal → typing entry simply expires via TTL (no cleanup call needed); presence likewise ages out within `PRESENCE_TTL_SECONDS` of their last poll.
- `_typing_state` / `_presence` grow unboundedly only in the sense that stale channel/email keys with all-expired inner entries are never removed — bounded in practice by "number of channels ever posted to" and "number of members who ever logged in," both small and already bounded elsewhere in this app; not worth adding a sweep for.

## Testing

Unit:
- `POST .../typing` sets an entry; `GET .../messages` right after includes it in `typing`, excluding the poster themself.
- Entry disappears from `typing` once its TTL (mocked via monkeypatching `time.monotonic`) has passed.
- `GET .../channels` includes a member in `onlineMembers` only after they've hit an endpoint that touches `_presence` within the TTL window, and excludes them once stale.
- `onlineMembers` never includes an email outside the requesting club's member list, even if `_presence` (global dict) has a stale entry for it from another club.

Integration:
- Two logged-in test sessions in the same channel: session A posts typing, session B's next messages poll shows A in `typing`; A stops (no more calls, TTL expires), B's next poll shows empty.
- `reset_rate_limits()`-style helper (`routes_chat.py:68-69`) gets a sibling `reset_typing_presence()` for test isolation, clearing both new dicts between tests.
