# Chat @mentions + notification

Date: 2026-08-13

## Summary

Add `@name` mentions to chat messages. Mentioning a club member notifies them in-app; leaders/mentors can additionally use `@everyone` to notify all channel members. Mention resolution is server-side and authoritative — the client's `@` autocomplete is a typing aid only, not the source of truth for who gets notified.

## Scope

This is the first of several chat gaps identified in a broader review (typing indicators, server-synced read receipts, threads/replies, search, and presence are out of scope — each would get its own spec). Mentions was picked first because it needs no new realtime transport: it slots into the existing polling + in-app notification infrastructure.

## Data model

`src/storage_mongo.py` message documents gain two fields, both computed once at send time and persisted (not re-derived on read):

- `mentions: [email, ...]` — resolved recipient emails.
- `mentionsEveryone: bool` — true only when the author is a leader/mentor and typed the literal token `@everyone`.

No schema change to `channels`. No new collection.

## Detection algorithm

In `api_chat_message_add` (`src/routes_chat.py:351-396`), after `body` is cleaned and before the message dict is appended:

1. Load the club's `members` from `state` (already loaded for the request).
2. Sort members by display-name length descending (so a longer name matches before a shorter name that's a substring of it, e.g. "Jane Doe" before "Jane").
3. Scan `body` case-insensitively for `@<full name>` occurrences; collect matched member emails into a set.
4. Remove the author's own email from the set (self-mentions never notify).
5. Separately check for the literal, word-bounded token `@everyone`. Honor it (set `mentionsEveryone = True`) only if the author passes the same leader/mentor check `require_leader_api()` already uses elsewhere in this file. For a non-leader author, `@everyone` is left as plain text — no error, no special handling.
6. Persist `mentions` (sorted list) and `mentionsEveryone` on the message dict alongside the existing fields.

Ambiguous duplicate display names (two members with the same name) notify all matching members — accepted at club scale, not resolved further.

Substring false positives (a member's name appearing incidentally inside a URL, email address, or unrelated word) are an accepted risk of exact-name matching; not solved further per YAGNI.

## Notification delivery

Reuses `notifications.add_in_app_notification()` (`src/notifications.py:25-53`) — in-app only, no email, matching how a mention should read at chat's message frequency (all other notification types here also send email, but those are low-frequency lifecycle events; chat is not).

For each resolved recipient (individual `mentions`, or all other channel members when `mentionsEveryone`):

```python
add_in_app_notification(
    recipient_email,
    'chat_mention',
    f'{author_name} mentioned you in #{channel_name}',
    truncated_body,  # same truncation convention as other notification bodies
    {'channelId': channel_id, 'messageId': message['id']},
)
```

`@everyone` fan-out loops over channel members the same way `notify_leaders_of_event_rsvp` loops over leaders (`src/notifications.py:67-91`) — one `add_in_app_notification` call per recipient, author excluded.

No click-through/navigation is added. Mention notifications land in the existing combined notification feed (`docs/superpowers/specs/2026-08-10-nav-notifications-design.md`) exactly like every other notification type today — no special-casing of `type: 'chat_mention'` in the feed UI beyond whatever generic title/message rendering it already does.

## Frontend (`static/js/dashboard-chat.js`, `templates/dashboard/chat.html`)

- Typing `@` in the compose box opens a dropdown filtered against the club's member list (already available to the dashboard for member-facing UI elsewhere; chat reuses it rather than fetching a new endpoint). Arrow keys/Enter/click select; selecting inserts `@Full Name ` (trailing space) at the cursor, verbatim, so it lines up with the server's exact-name match.
- The server echoes `mentions`/`mentionsEveryone` back on the created message (existing `POST` response) and on subsequent poll/history fetches (existing `GET .../messages`), since both are persisted fields.
- When rendering a message bubble, `dashboard-chat.js` wraps any substring of `body` matching a mentioned member's display name (or the literal `@everyone` when `mentionsEveryone`) in `<span class="mention">` for highlighting. This runs off the persisted fields, so highlighting is correct on reload/history, not just for freshly-sent messages.
- New i18n string for the `@everyone`-restricted case is not needed — non-leaders typing `@everyone` get no feedback, it's just text (consistent with "no error" from the backend).

## Error handling / edge cases

- No member names match anything in `body` → `mentions: []`, `mentionsEveryone: False`, no-op, no error, no behavior change from today.
- `@everyone` typed by a non-leader/mentor → literal text only, not mass-notified.
- Author mentions themselves → excluded from their own notification.
- A mentioned member is later removed from the club → historical `mentions` entries on old messages are left as-is (dangling email, never resolved to a live notification again); not cleaned up.

## Testing

Unit (`tests/test_chat*.py` or equivalent):
- Single mention resolves to the correct member email.
- Multiple distinct mentions in one message resolve to multiple emails.
- Two members sharing a display name both get notified.
- `@everyone` from a leader sets `mentionsEveryone = True` and notifies all other channel members.
- `@everyone` from a regular member does not set the flag and does not mass-notify.
- Self-mention is excluded from `mentions`.
- A name-shaped substring inside something like `jane@doe.com` does not falsely match (since matching requires the literal `@` + full display name, not just the name appearing anywhere).

Integration: `POST` a message containing a mention → assert an in-app notification row (`type: 'chat_mention'`) exists for the target member and not for the author.

No changes to existing chat tests should be needed beyond asserting the two new fields are present (and empty/false) on messages with no mentions.
