# Chat Sprint 1: Uploads, Link Previews, Markdown + Feature Flags

**Date:** 2026-07-13
**Source:** info.md corrections to the chat enhancement plan (corrected sprint order, item 9)
**Scope:** Sprint 1 only — file uploads, link previews, markdown rendering — plus the
`FEATURE_CHAT_*` flag scaffolding (item 14). Later sprints (reactions, moderation,
threads, SSE) each get their own spec.

## Context

The chat system (`src/routes_chat.py`, `templates/dashboard/chat.html`, chat section of
`static/js/dashboard.js`) already satisfies several info.md corrections: all endpoints
live under `/api/dashboard/chat/...` (item 5), messages carry stable
`id`/`channelId`/`authorEmail`/`body`/`createdAt` (item 7), and polling runs at 30s.
Messages persist via the dashboard-state abstraction: dedicated Airtable tables
(`Channels`, `Messages`) on the Airtable backend, session cookie otherwise.

Decisions made with Damon:

- Upload storage: **Airtable attachments** (info.md item 12, Phase 1; R2/S3 is a later phase).
- Link previews: **server-side OG fetch** with SSRF guards.
- Approach: **zero-dependency, minimal** — no new Python or JS libraries, no build step.

## 1. Feature flags

`feature_enabled(name)` in `src/helpers.py` reads the environment:

```
FEATURE_CHAT_UPLOADS=true
FEATURE_CHAT_LINK_PREVIEWS=true
FEATURE_CHAT_MARKDOWN=true
```

All default **on**; any casing of `false`/`0`/`off` disables. The chat page template
receives the flags in its render context so the UI hides disabled controls. The server
enforces flags independently of the client (a multipart post with uploads disabled is
rejected with 400).

## 2. Data model

Message dicts gain two optional keys:

```json
{
  "attachments": [{ "url": "…", "filename": "…", "type": "image/png", "size": 12345 }],
  "linkPreview": { "url": "…", "title": "…", "description": "…", "image": "…" }
}
```

Airtable `Messages` table gains:

- `Attachments` → native Airtable attachment field
- `Metadata` → long text holding the `linkPreview` JSON

`scripts/setup_chat_tables.py` and `MESSAGE_FIELDS` in `src/storage.py` are updated in
lockstep (field names/casing must match). Per info.md item 8, real fields are preferred
over JSON blobs; only the small flat `linkPreview` object is JSON because Airtable has
no nested type for it.

## 3. File uploads

No new endpoint. `POST /api/dashboard/chat/channels/<id>/messages` additionally accepts
`multipart/form-data` with `body` (optional if a file is present) and `file`.

Validation (before anything is saved):

- Flag `FEATURE_CHAT_UPLOADS` must be on.
- Max size 5 MB (Airtable content-upload API limit).
- Content-type allowlist: `image/png`, `image/jpeg`, `image/gif`, `image/webp`,
  `application/pdf`, `text/plain`.

Flow: save the message through the normal state path (this creates the Airtable row),
then call a new storage method:

```python
AirtableStorage.upload_attachment(club_key, message_id, filename, content, content_type)
  -> {url, filename, type, size} | None
```

which finds the record by `App Id` and POSTs the bytes (base64) to Airtable's
`uploadAttachment` content endpoint, then writes the returned URL back onto the message
in state. `SessionStorage.upload_attachment` returns `None`; the route turns that into a
400: "File uploads aren't available on this storage backend." (Session state lives in a
~4 KB cookie — it cannot hold files.)

Error handling: invalid file → 400 before the message posts. Airtable upload failure
after the message row exists → the message stays (without attachment) and the JSON
response includes `uploadError` so the client can toast it.

## 4. Link previews

On message post, when `FEATURE_CHAT_LINK_PREVIEWS` is on and the body contains an
`http(s)://` URL, the server fetches the **first** URL and stores
`message['linkPreview']`. Guards:

- Scheme must be http/https.
- Resolve the hostname first and reject private, loopback, and link-local addresses
  (`ipaddress` stdlib checks on every resolved address).
- 3-second timeout, read at most 500 KB.
- Redirects followed manually, max 3 hops, host re-validated on each hop.
- Parse `og:title`, `og:description`, `og:image` with a stdlib `html.parser` subclass;
  fall back to `<title>`. Values length-capped.

Any failure (timeout, non-HTML, blocked IP, parse error) is silent — the message posts
without a preview. Preview text is escaped at render time like all other message content.

## 5. Markdown rendering (client-side)

A small `renderChatMarkdown(body)` in `dashboard.js` (~40 lines), used in place of the
current `escapeHtml(message.body)` when the flag is on:

1. `escapeHtml()` the whole body first — sanitization by construction.
2. Inline regex passes on the escaped text: `` `code` `` → `<code>`, `**bold**` →
   `<strong>`, `*italic*` → `<em>`, `~~strike~~` → `<del>`, bare URLs →
   `<a target="_blank" rel="noopener noreferrer">`.

Inline-only (no headings/lists/blockquotes): messages are single-line, max 500 chars.
The raw markdown source is what gets stored, so Sprint 2 message-editing operates on
source text, never rendered HTML.

## 6. UI

- Composer: paperclip button (hidden when uploads are off) opening a file input;
  selected file shows as a removable chip next to the input.
- Messages: image attachments render as capped-size thumbnails linking to the full
  file; other types render as a filename chip. Link preview renders as a small card
  (title, description, optional image) under the message body.
- All dynamic values pass through `escapeHtml`. Preview images get `max-width`/
  `max-height` caps and `loading="lazy"`.
- ~6 new i18n keys (attach, remove file, upload errors, preview alt text) added to
  `i18n-data.js` following the existing key conventions.

## 7. Testing

Additions to `tests/test_chat.py`, forcing session storage mode where a club is seeded
(the `.env` forces the Airtable backend otherwise):

- Uploads flag off → multipart post rejected 400.
- Oversized / disallowed-type file → 400, no message created.
- Session backend + valid file → 400 "uploads aren't available", no partial state.
- Airtable upload path → exercised with a monkeypatched `upload_attachment`.
- Link preview fetcher unit tests with a mocked HTTP layer: happy path (og tags),
  `<title>` fallback, timeout → no preview, private-IP host → refused, redirect to
  private IP → refused.
- Markdown: server stores the raw body untouched (assert no HTML in stored state).
- Flags default on; `FEATURE_CHAT_MARKDOWN=false` reflected in template context.

## Out of scope (later sprints)

Reactions, editing/deletion, mentions (Sprint 2); moderation, slash commands,
permissions — with server-side validation per info.md item 6 (Sprint 3); threads,
polls, search (Sprint 4); SSE/WebSockets replacing polling before threads/reactions
land, virtual scrolling (Sprint 5); R2/S3 attachment storage (item 12 Phase 2).
