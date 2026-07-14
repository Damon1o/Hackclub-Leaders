# Chat Sprint 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add file uploads (Airtable attachments), server-side link previews, and client-side markdown rendering to club chat, gated behind `FEATURE_CHAT_*` env flags.

**Architecture:** Flask app with a storage abstraction (`SessionStorage` cookie backend / `AirtableStorage`). Chat routes live in `src/routes_chat.py` (registered via `register(app)`); the frontend is vanilla JS in `static/js/dashboard.js` polling every 30s. New server logic extends the existing message-post endpoint (no new endpoints); uploads go through Airtable's content-upload API onto the message's record; previews are fetched server-side with SSRF guards; markdown renders client-side escape-first.

**Tech Stack:** Python 3 / Flask, `requests` (already a dependency), stdlib `html.parser`/`ipaddress`/`socket`, vanilla JS, pytest.

**Spec:** `docs/superpowers/specs/2026-07-13-chat-sprint1-design.md`

## Global Constraints

- **Zero new dependencies** — Python stdlib + already-installed `requests`/Flask only; no new JS libraries, no build step.
- All chat endpoints stay under `/api/dashboard/chat/...`; do not add new endpoints.
- Upload cap **5 MB** (`5 * 1024 * 1024`); content-type allowlist exactly: `image/png`, `image/jpeg`, `image/gif`, `image/webp`, `application/pdf`, `text/plain`.
- Flags `FEATURE_CHAT_UPLOADS`, `FEATURE_CHAT_LINK_PREVIEWS`, `FEATURE_CHAT_MARKDOWN` default **on**; disabled by env value `false`/`0`/`off`/`no` (any case).
- Link preview fetch: 3s timeout, 500 KB read cap, max 3 redirects, http/https only, reject non-public IPs.
- Message bodies are stored as raw text (markdown source). Never store rendered HTML.
- All new tests go in `tests/test_chat.py` (no new test files). Tests that seed a club MUST run with `STORAGE_BACKEND=session` — the file's autouse `_session_backend` fixture already does this.
- Commit messages: conventional prefixes (`feat:`, `test:`), **no `Co-Authored-By` trailers** (CLAUDE.md rule).
- Run tests with: `python -m pytest tests/test_chat.py -v` (full suite: `python -m pytest`).

---

### Task 1: Feature flag helper

**Files:**
- Modify: `src/helpers.py` (add next to `MAX_MESSAGE_LEN`, around line 906)
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: nothing new. `os` is already imported at the top of `helpers.py`.
- Produces: `feature_enabled(name: str) -> bool` — Tasks 5, 6, 7 import this from `.helpers` / `src.helpers`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_chat.py`:

```python
# ── Feature flags ─────────────────────────────────────────────────────────────

def test_feature_flags_default_on(monkeypatch):
    from src.helpers import feature_enabled
    monkeypatch.delenv('FEATURE_CHAT_UPLOADS', raising=False)
    assert feature_enabled('FEATURE_CHAT_UPLOADS') is True


@pytest.mark.parametrize('value', ['false', 'FALSE', '0', 'off', 'no', ' False '])
def test_feature_flags_disabled_values(monkeypatch, value):
    from src.helpers import feature_enabled
    monkeypatch.setenv('FEATURE_CHAT_UPLOADS', value)
    assert feature_enabled('FEATURE_CHAT_UPLOADS') is False


def test_feature_flags_true_value(monkeypatch):
    from src.helpers import feature_enabled
    monkeypatch.setenv('FEATURE_CHAT_UPLOADS', 'true')
    assert feature_enabled('FEATURE_CHAT_UPLOADS') is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_chat.py -k feature_flags -v`
Expected: FAIL / ERROR with `ImportError: cannot import name 'feature_enabled'`

- [ ] **Step 3: Implement** — in `src/helpers.py`, directly below the `MAX_MESSAGE_LEN: Final[int] = 500` line:

```python
def feature_enabled(name: str) -> bool:
    """Env-driven feature flag: on unless the env var is set to false/0/off/no."""
    return os.environ.get(name, '').strip().lower() not in ('false', '0', 'off', 'no')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_chat.py -k feature_flags -v`
Expected: 8 PASS (1 + 6 parametrized + 1)

- [ ] **Step 5: Commit**

```bash
git add src/helpers.py tests/test_chat.py
git commit -m "feat: add env-driven FEATURE_CHAT_* flag helper"
```

---

### Task 2: Storage — Metadata JSON field, attachment loading, Airtable schema

**Files:**
- Modify: `src/storage.py` (`MESSAGE_FIELDS` ~line 102, new `JSON_KEYS` near `BOOL_KEYS` ~line 123, `load()` ~line 531-549, `_item_fields()` ~line 596-614)
- Modify: `scripts/setup_chat_tables.py` (Messages table fields ~line 34-43, `main()` loop ~line 66-91)
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: existing `AirtableStorage._list`, `_item_fields`, `load`.
- Produces: message state dicts round-trip an optional `linkPreview: dict` (stored as JSON text in the Airtable `Metadata` field) and expose `attachments: list[dict]` read-only from the Airtable `Attachments` field. The `Attachments` field is **never written** by `save()`/`_sync_children` — only by the content-upload API (Task 3) — because Airtable rewrites attachment URLs (they expire), so echoing stale URLs back would corrupt them.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_chat.py` (also add `import json` to the imports at the top of the file):

```python
# ── Storage round-trip for message extras ─────────────────────────────────────

def _airtable():
    from src.storage import AirtableStorage
    return AirtableStorage(token='test-token', base_id='test-base')


def test_item_fields_serializes_link_preview():
    from src.storage import MESSAGE_FIELDS
    s = _airtable()
    msg = {
        'id': 'msg-1', 'channelId': 'c1', 'authorEmail': 'a@x.com',
        'authorName': 'A', 'authorAvatar': '', 'body': 'hi', 'createdAt': 'now',
        'linkPreview': {'url': 'https://e.com', 'title': 'E'},
    }
    fields = s._item_fields('lead@x.com', msg, MESSAGE_FIELDS, serialize_items=False)
    assert json.loads(fields['Metadata']) == {'url': 'https://e.com', 'title': 'E'}
    assert 'Attachments' not in fields  # never synced back (URLs expire)


def test_item_fields_no_preview_writes_blank():
    from src.storage import MESSAGE_FIELDS
    s = _airtable()
    msg = {'id': 'msg-1', 'channelId': 'c1', 'authorEmail': 'a@x.com',
           'authorName': 'A', 'authorAvatar': '', 'body': 'hi', 'createdAt': 'now'}
    fields = s._item_fields('lead@x.com', msg, MESSAGE_FIELDS, serialize_items=False)
    assert fields['Metadata'] == ''


def test_load_parses_message_metadata_and_attachments(monkeypatch):
    s = _airtable()

    def fake_list(table, field, value):
        if table == s.clubs_table:
            return [{'id': 'rec0', 'fields': {'Leader Email': 'lead@x.com'}}]
        if table == s.tables['messages']:
            return [{'id': 'rec1', 'fields': {
                'App Id': 'msg-1', 'Channel Id': 'c1', 'Body': 'hi',
                'Metadata': '{"url": "https://e.com", "title": "E"}',
                'Attachments': [{'id': 'att1', 'url': 'https://cdn/x.png',
                                 'filename': 'x.png', 'type': 'image/png', 'size': 3}],
            }}]
        return []

    monkeypatch.setattr(s, '_list', fake_list)
    state = s.load('lead@x.com')
    msg = state['messages'][0]
    assert msg['linkPreview'] == {'url': 'https://e.com', 'title': 'E'}
    assert msg['attachments'] == [
        {'url': 'https://cdn/x.png', 'filename': 'x.png', 'type': 'image/png', 'size': 3}
    ]


def test_load_message_without_extras(monkeypatch):
    s = _airtable()

    def fake_list(table, field, value):
        if table == s.clubs_table:
            return [{'id': 'rec0', 'fields': {'Leader Email': 'lead@x.com'}}]
        if table == s.tables['messages']:
            return [{'id': 'rec1', 'fields': {'App Id': 'msg-1', 'Channel Id': 'c1', 'Body': 'hi'}}]
        return []

    monkeypatch.setattr(s, '_list', fake_list)
    msg = s.load('lead@x.com')['messages'][0]
    assert 'linkPreview' not in msg
    assert 'attachments' not in msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_chat.py -k "item_fields or load_parses or load_message" -v`
Expected: FAIL — `KeyError: 'Metadata'` / missing `linkPreview`/`attachments` assertions.

- [ ] **Step 3: Implement in `src/storage.py`**

3a. Append to `MESSAGE_FIELDS` (line ~102):

```python
MESSAGE_FIELDS: Final[list[tuple[str, str]]] = [
    ('channelId', 'Channel Id'),
    ('authorEmail', 'Author Email'),
    ('authorName', 'Author Name'),
    ('authorAvatar', 'Author Avatar'),
    ('body', 'Body'),
    ('createdAt', 'Created At'),
    ('linkPreview', 'Metadata'),
]
```

3b. Below the `BOOL_KEYS` block (line ~130), add:

```python
# State keys stored as JSON text in Airtable (no nested field types there).
JSON_KEYS: Final[set[str]] = {'linkPreview'}
```

3c. In `load()`, the per-field loop (currently lines ~535-542) becomes:

```python
                for item_key, field in field_pairs:
                    value = fields.get(field)
                    if item_key in BOOL_KEYS:
                        item[item_key] = bool(value)
                    elif item_key == 'attendees':
                        item[item_key] = int(value or 0)
                    elif item_key in JSON_KEYS:
                        if value:
                            try:
                                item[item_key] = json.loads(value)
                            except ValueError:
                                pass
                    else:
                        item[item_key] = value or ''
```

3d. Still in `load()`, after the existing `if state_key == 'orders':` block, add a messages branch at the same indentation:

```python
                if state_key == 'messages':
                    raw_attachments = fields.get('Attachments') or []
                    if raw_attachments:
                        item['attachments'] = [
                            {
                                'url': att.get('url', ''),
                                'filename': att.get('filename', ''),
                                'type': att.get('type', ''),
                                'size': att.get('size', 0),
                            }
                            for att in raw_attachments
                        ]
```

3e. In `_item_fields()` (line ~604-611), add the JSON branch:

```python
        for item_key, field in field_pairs:
            value = item.get(item_key)
            if item_key in BOOL_KEYS:
                fields[field] = bool(value)
            elif item_key == 'attendees':
                fields[field] = int(value or 0)
            elif item_key in JSON_KEYS:
                fields[field] = json.dumps(value) if value else ''
            else:
                fields[field] = value or ''
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_chat.py -k "item_fields or load_parses or load_message" -v`
Expected: 4 PASS

- [ ] **Step 5: Update the schema script** — in `scripts/setup_chat_tables.py`:

5a. Extend the `Messages` entry in `TABLES`:

```python
    'Messages': [
        ('App Id', 'singleLineText'),
        ('Channel Id', 'singleLineText'),
        ('Author Email', 'singleLineText'),
        ('Author Name', 'singleLineText'),
        ('Author Avatar', 'singleLineText'),
        ('Body', 'multilineText'),
        ('Created At', 'singleLineText'),
        ('Metadata', 'multilineText'),
        ('Attachments', 'multipleAttachments'),
        ('Club Email', 'singleLineText'),
    ],
```

5b. Replace the `existing = {...}` line and the `for name, fields in TABLES.items():` loop so existing tables gain missing fields instead of being skipped outright:

```python
    existing = {t['name']: t for t in resp.json().get('tables', [])}

    for name, fields in TABLES.items():
        table = existing.get(name)
        if table is not None:
            have = {f['name'] for f in table.get('fields', [])}
            missing = [(fn, ft) for fn, ft in fields if fn not in have]
            if not missing:
                print(f'= {name}: already exists, skipping')
                continue
            for field_name, field_type in missing:
                add = requests.post(
                    f'{META_API}/{base_id}/tables/{table["id"]}/fields',
                    headers=headers,
                    json={'name': field_name, 'type': field_type},
                    timeout=15,
                )
                if add.status_code >= 400:
                    sys.exit(f'x {name}.{field_name}: add failed ({add.status_code}): {add.text[:300]}')
                print(f'+ {name}: added field {field_name}')
            continue
        payload = {
            'name': name,
            'fields': [{'name': fname, 'type': ftype} for fname, ftype in fields],
        }
        # ... (rest of the create branch unchanged)
```

- [ ] **Step 6: Run the whole chat suite, then commit**

Run: `python -m pytest tests/test_chat.py -v`
Expected: all PASS

```bash
git add src/storage.py scripts/setup_chat_tables.py tests/test_chat.py
git commit -m "feat: persist message link previews and load Airtable attachments"
```

---

### Task 3: `AirtableStorage.upload_attachment`

**Files:**
- Modify: `src/storage.py` (add `import base64` to imports; add `supports_uploads` to both storage classes; add method to `AirtableStorage` after `list_item_requests`, ~line 470)
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: `AirtableStorage._list(table, field, value)`, `self.token`, `self.base_id`, `self.tables['messages']`.
- Produces: `AirtableStorage.upload_attachment(message_id: str, filename: str, content: bytes, content_type: str) -> dict | None` returning `{'url', 'filename', 'type', 'size'}` on success, `None` on any failure (never raises). Class attributes `SessionStorage.supports_uploads = False`, `AirtableStorage.supports_uploads = True` — Task 6's route checks `getattr(backend, 'supports_uploads', False)`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_chat.py`:

```python
# ── Airtable attachment upload ────────────────────────────────────────────────

def test_upload_attachment_success(monkeypatch):
    s = _airtable()
    monkeypatch.setattr(
        s, '_list', lambda *a: [{'id': 'recABC', 'fields': {'App Id': 'msg-1'}}]
    )
    captured = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {'fields': {'Attachments': [
                {'id': 'att1', 'url': 'https://cdn/f.png',
                 'filename': 'f.png', 'type': 'image/png', 'size': 5}
            ]}}

    def fake_post(url, **kwargs):
        captured['url'] = url
        captured['json'] = kwargs.get('json')
        return FakeResponse()

    monkeypatch.setattr('src.storage.requests.post', fake_post)
    att = s.upload_attachment('msg-1', 'f.png', b'bytes', 'image/png')
    assert att == {'url': 'https://cdn/f.png', 'filename': 'f.png',
                   'type': 'image/png', 'size': 5}
    assert captured['url'] == (
        'https://content.airtable.com/v0/test-base/recABC/Attachments/uploadAttachment'
    )
    assert captured['json']['contentType'] == 'image/png'
    assert captured['json']['filename'] == 'f.png'


def test_upload_attachment_missing_record(monkeypatch):
    s = _airtable()
    monkeypatch.setattr(s, '_list', lambda *a: [])
    assert s.upload_attachment('nope', 'f.png', b'', 'image/png') is None


def test_upload_attachment_http_error(monkeypatch):
    s = _airtable()
    monkeypatch.setattr(
        s, '_list', lambda *a: [{'id': 'recABC', 'fields': {'App Id': 'msg-1'}}]
    )

    class FakeResponse:
        status_code = 422

        @staticmethod
        def json():
            return {}

    monkeypatch.setattr('src.storage.requests.post', lambda url, **k: FakeResponse())
    assert s.upload_attachment('msg-1', 'f.png', b'x', 'image/png') is None


def test_storage_upload_capability_flags():
    from src.storage import SessionStorage
    assert _airtable().supports_uploads is True
    assert SessionStorage({}).supports_uploads is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_chat.py -k upload_attachment -v`
Expected: FAIL with `AttributeError: 'AirtableStorage' object has no attribute 'upload_attachment'`

- [ ] **Step 3: Implement in `src/storage.py`**

3a. Add `import base64` as the first import (alphabetical, before `import json`).

3b. In `SessionStorage`, directly under the class docstring:

```python
    supports_uploads = False
```

3c. In `AirtableStorage`, directly under its docstring/class constants:

```python
    supports_uploads = True
```

3d. Add the method to `AirtableStorage` (place it after `list_item_requests`, before `load_lite`):

```python
    def upload_attachment(
        self, message_id: str, filename: str, content: bytes, content_type: str
    ) -> dict[str, Any] | None:
        """Attach `content` to a message row via Airtable's content-upload API.

        Returns {'url','filename','type','size'} or None on any failure — the
        caller posts the message regardless and reports the upload separately.
        """
        records = self._list(self.tables['messages'], 'App Id', message_id)
        if not records:
            return None
        record_id = records[0]['id']
        url = (
            f'https://content.airtable.com/v0/{self.base_id}/{record_id}'
            '/Attachments/uploadAttachment'
        )
        payload = {
            'contentType': content_type,
            'filename': filename,
            'file': base64.b64encode(content).decode('ascii'),
        }
        try:
            response = requests.post(
                url,
                headers={
                    'Authorization': f'Bearer {self.token}',
                    'Content-Type': 'application/json',
                },
                json=payload,
                timeout=30,
            )
        except requests.RequestException:
            return None
        if response.status_code >= 400:
            return None
        attachments = (response.json().get('fields') or {}).get('Attachments') or []
        if not attachments:
            return None
        uploaded = attachments[-1]
        return {
            'url': uploaded.get('url', ''),
            'filename': uploaded.get('filename', filename),
            'type': uploaded.get('type', content_type),
            'size': uploaded.get('size', len(content)),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_chat.py -k "upload_attachment or capability" -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/storage.py tests/test_chat.py
git commit -m "feat: add Airtable content-API attachment upload to storage"
```

---

### Task 4: Link preview fetcher with SSRF guards

**Files:**
- Modify: `src/routes_chat.py` (new module-level section after the imports/constants)
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: `clean_text` (already imported in `routes_chat.py`).
- Produces: `first_url(text: str) -> str` and `fetch_link_preview(url: str) -> dict | None` (returns `{'url','title','description','image'}` or `None`; never raises). Task 5 calls both. Module-level `requests` and `socket` are what tests monkeypatch (`src.routes_chat.requests`, `src.routes_chat.socket`).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_chat.py`:

```python
# ── Link preview fetcher ──────────────────────────────────────────────────────

from src import routes_chat


class _FakePreviewResponse:
    def __init__(self, status=200, headers=None, body=b'', encoding='utf-8'):
        self.status_code = status
        self.headers = headers if headers is not None else {
            'Content-Type': 'text/html; charset=utf-8'
        }
        self._body = body
        self.encoding = encoding

    def iter_content(self, size):
        yield self._body


_OG_HTML = (
    b'<html><head>'
    b'<meta property="og:title" content="Example Domain">'
    b'<meta property="og:description" content="A demo page">'
    b'<meta property="og:image" content="https://example.com/img.png">'
    b'<title>Fallback Title</title>'
    b'</head><body></body></html>'
)


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr(
        routes_chat.socket, 'getaddrinfo',
        lambda *a, **k: [(2, 1, 6, '', ('93.184.216.34', 0))],
    )


def test_first_url_extraction():
    assert routes_chat.first_url('see https://a.dev/x?y=1 now') == 'https://a.dev/x?y=1'
    assert routes_chat.first_url('no links here') == ''
    assert routes_chat.first_url('') == ''


def test_preview_happy_path(monkeypatch, public_dns):
    monkeypatch.setattr(
        routes_chat.requests, 'get', lambda *a, **k: _FakePreviewResponse(body=_OG_HTML)
    )
    preview = routes_chat.fetch_link_preview('https://example.com/page')
    assert preview == {
        'url': 'https://example.com/page',
        'title': 'Example Domain',
        'description': 'A demo page',
        'image': 'https://example.com/img.png',
    }


def test_preview_title_fallback(monkeypatch, public_dns):
    html = b'<html><head><title>Just A Title</title></head></html>'
    monkeypatch.setattr(
        routes_chat.requests, 'get', lambda *a, **k: _FakePreviewResponse(body=html)
    )
    preview = routes_chat.fetch_link_preview('https://example.com/')
    assert preview['title'] == 'Just A Title'


def test_preview_private_host_refused(monkeypatch):
    monkeypatch.setattr(
        routes_chat.socket, 'getaddrinfo',
        lambda *a, **k: [(2, 1, 6, '', ('10.0.0.5', 0))],
    )
    calls = []
    monkeypatch.setattr(routes_chat.requests, 'get', lambda *a, **k: calls.append(1))
    assert routes_chat.fetch_link_preview('https://internal.corp/') is None
    assert not calls  # never even connected


def test_preview_redirect_to_private_refused(monkeypatch):
    def fake_getaddrinfo(host, *a, **k):
        ip = '93.184.216.34' if host == 'example.com' else '127.0.0.1'
        return [(2, 1, 6, '', (ip, 0))]

    monkeypatch.setattr(routes_chat.socket, 'getaddrinfo', fake_getaddrinfo)
    calls = []

    def fake_get(url, **k):
        calls.append(url)
        return _FakePreviewResponse(status=302, headers={'Location': 'http://localhost/x'})

    monkeypatch.setattr(routes_chat.requests, 'get', fake_get)
    assert routes_chat.fetch_link_preview('https://example.com/') is None
    assert calls == ['https://example.com/']  # stopped before hitting localhost


def test_preview_timeout_returns_none(monkeypatch, public_dns):
    def boom(*a, **k):
        raise routes_chat.requests.Timeout('slow')

    monkeypatch.setattr(routes_chat.requests, 'get', boom)
    assert routes_chat.fetch_link_preview('https://example.com/') is None


def test_preview_non_html_skipped(monkeypatch, public_dns):
    resp = _FakePreviewResponse(headers={'Content-Type': 'application/pdf'}, body=b'%PDF')
    monkeypatch.setattr(routes_chat.requests, 'get', lambda *a, **k: resp)
    assert routes_chat.fetch_link_preview('https://example.com/doc.pdf') is None


def test_preview_bad_scheme_refused():
    assert routes_chat.fetch_link_preview('ftp://example.com/') is None
    assert routes_chat.fetch_link_preview('') is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_chat.py -k preview -v`
Expected: FAIL with `AttributeError: module 'src.routes_chat' has no attribute 'first_url'` (or `socket`)

- [ ] **Step 3: Implement** — in `src/routes_chat.py`, replace the import block and the `MESSAGE_PAGE_SIZE` section header area with (keep the existing `from .helpers import (...)` list intact, just extend it later in Task 5/6 as noted):

```python
import ipaddress
import re
import socket
import urllib.parse
from html.parser import HTMLParser

import flask
import requests
from flask import request, session
```

Then, below `MESSAGE_PAGE_SIZE = 50`, add:

```python
# ── Link previews ─────────────────────────────────────────────────────────────
# The server fetches user-posted URLs, so every request is SSRF-guarded:
# http/https only, public IPs only (re-checked per redirect hop), 3s timeout,
# 500KB read cap. Every failure path returns None — previews are best-effort.

_URL_RE = re.compile(r'https?://[^\s<>"\']+')
PREVIEW_TIMEOUT = 3
PREVIEW_MAX_BYTES = 500 * 1024
PREVIEW_MAX_REDIRECTS = 3


def first_url(text):
    match = _URL_RE.search(text or '')
    return match.group(0) if match else ''


def _host_is_public(hostname):
    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError:
        return False
    if not infos:
        return False
    return all(ipaddress.ip_address(info[4][0]).is_global for info in infos)


class _OgParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.og = {}
        self.title = ''
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == 'meta':
            attrs = dict(attrs)
            prop = (attrs.get('property') or attrs.get('name') or '').lower()
            if prop.startswith('og:') and attrs.get('content'):
                self.og.setdefault(prop[3:], attrs['content'])
        elif tag == 'title':
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == 'title':
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and len(self.title) < 300:
            self.title += data


def fetch_link_preview(url):
    original = url
    for _hop in range(PREVIEW_MAX_REDIRECTS + 1):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            return None
        if not _host_is_public(parsed.hostname):
            return None
        try:
            response = requests.get(
                url,
                timeout=PREVIEW_TIMEOUT,
                stream=True,
                allow_redirects=False,
                headers={'User-Agent': 'HackclubLeaders/1.0 (+link-preview)'},
            )
        except requests.RequestException:
            return None
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get('Location', '')
            if not location:
                return None
            url = urllib.parse.urljoin(url, location)
            continue
        if response.status_code != 200:
            return None
        if 'text/html' not in (response.headers.get('Content-Type') or ''):
            return None
        try:
            chunk = next(response.iter_content(PREVIEW_MAX_BYTES), b'') or b''
        except requests.RequestException:
            return None
        parser = _OgParser()
        try:
            parser.feed(chunk.decode(response.encoding or 'utf-8', 'replace'))
        except Exception:
            return None
        title = clean_text(parser.og.get('title') or parser.title.strip(), max_len=200)
        if not title:
            return None
        return {
            'url': original,
            'title': title,
            'description': clean_text(parser.og.get('description'), max_len=300),
            'image': clean_text(parser.og.get('image'), max_len=500),
        }
    return None
```

Note: `_host_is_public` uses `ip.is_global`, which is False for private, loopback, link-local, reserved, and unspecified addresses. Known accepted limitation (documented in the spec): DNS could re-resolve differently between our check and the actual request (TOCTOU) — acceptable risk for this app; do not build IP pinning.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_chat.py -k "preview or first_url" -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add src/routes_chat.py tests/test_chat.py
git commit -m "feat: add SSRF-guarded link preview fetcher for chat"
```

---

### Task 5: Wire link previews into message posting

**Files:**
- Modify: `src/routes_chat.py` (`api_chat_message_add`, ~line 137-169; extend the `.helpers` import list)
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: `feature_enabled` (Task 1), `first_url`/`fetch_link_preview` (Task 4).
- Produces: posted messages optionally carry `linkPreview` in both the POST response and subsequent GET listings.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_chat.py`:

```python
# ── Link previews on message post ─────────────────────────────────────────────

def test_message_gets_link_preview(client, monkeypatch):
    monkeypatch.setattr(
        'src.routes_chat.fetch_link_preview',
        lambda url: {'url': url, 'title': 'Example', 'description': '', 'image': ''},
    )
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'look at https://example.com'}, headers=h,
    )
    assert resp.status_code == 200
    assert resp.get_json()['message']['linkPreview']['title'] == 'Example'
    listing = c.get(f'/api/dashboard/chat/channels/{cid}/messages').get_json()
    assert listing['messages'][-1]['linkPreview']['title'] == 'Example'


def test_no_url_no_preview_fetch(client, monkeypatch):
    monkeypatch.setattr(
        'src.routes_chat.fetch_link_preview',
        lambda url: pytest.fail('must not fetch when body has no URL'),
    )
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'plain text'}, headers=h,
    )
    assert 'linkPreview' not in resp.get_json()['message']


def test_link_preview_flag_off(client, monkeypatch):
    monkeypatch.setenv('FEATURE_CHAT_LINK_PREVIEWS', 'false')
    monkeypatch.setattr(
        'src.routes_chat.fetch_link_preview',
        lambda url: pytest.fail('must not fetch when flag is off'),
    )
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'https://example.com'}, headers=h,
    )
    assert 'linkPreview' not in resp.get_json()['message']


def test_failed_preview_message_still_posts(client, monkeypatch):
    monkeypatch.setattr('src.routes_chat.fetch_link_preview', lambda url: None)
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        json={'body': 'https://example.com'}, headers=h,
    )
    assert resp.status_code == 200
    assert 'linkPreview' not in resp.get_json()['message']
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_chat.py -k "link_preview or no_url or failed_preview" -v`
Expected: `test_message_gets_link_preview` FAILS (`KeyError: 'linkPreview'`); the guard tests may already pass — that's fine.

- [ ] **Step 3: Implement** — add `feature_enabled` to the `from .helpers import (...)` list in `routes_chat.py`. In `api_chat_message_add`, insert between building `message = {...}` and `_messages(state).append(message)`:

```python
        if body and feature_enabled('FEATURE_CHAT_LINK_PREVIEWS'):
            url = first_url(body)
            if url:
                preview = fetch_link_preview(url)
                if preview:
                    message['linkPreview'] = preview
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_chat.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/routes_chat.py tests/test_chat.py
git commit -m "feat: attach server-fetched link previews to chat messages"
```

---

### Task 6: Multipart file uploads on the message endpoint

**Files:**
- Modify: `src/routes_chat.py` (rewrite `api_chat_message_add`; add constants; extend `.helpers` import with `_storage`)
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: `_storage()` from helpers (returns the active backend), `backend.supports_uploads` and `backend.upload_attachment(message_id, filename, content, content_type)` (Task 3), `feature_enabled` (Task 1).
- Produces: `POST /api/dashboard/chat/channels/<id>/messages` accepts multipart (`body` optional when `file` present). Success responses: `{'message': {...}}`, plus `'uploadError': <str>` when the message posted but the upload failed. JSON posts behave exactly as before.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_chat.py` (add `import io` to the top-of-file imports):

```python
# ── File uploads ──────────────────────────────────────────────────────────────

def _upload_file(name='pic.png', mimetype='image/png', size=10):
    return (io.BytesIO(b'x' * size), name, mimetype)


def _post_multipart(c, h, cid, data):
    return c.post(
        f'/api/dashboard/chat/channels/{cid}/messages',
        data=data, headers=h, content_type='multipart/form-data',
    )


def _enable_session_uploads(monkeypatch, result):
    from src.storage import SessionStorage
    monkeypatch.setattr(SessionStorage, 'supports_uploads', True, raising=False)
    monkeypatch.setattr(
        SessionStorage, 'upload_attachment', lambda self, *a: result, raising=False
    )


def test_upload_flag_off_rejected(client, monkeypatch):
    monkeypatch.setenv('FEATURE_CHAT_UPLOADS', 'false')
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = _post_multipart(c, h, cid, {'body': 'hi', 'file': _upload_file()})
    assert resp.status_code == 400
    assert 'disabled' in resp.get_json()['error']


def test_upload_session_backend_unavailable(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = _post_multipart(c, h, cid, {'body': '', 'file': _upload_file()})
    assert resp.status_code == 400
    assert 'storage backend' in resp.get_json()['error']


def test_upload_too_large_rejected(client, monkeypatch):
    _enable_session_uploads(monkeypatch, result=None)
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = _post_multipart(
        c, h, cid, {'body': '', 'file': _upload_file(size=5 * 1024 * 1024 + 1)}
    )
    assert resp.status_code == 400
    assert 'too large' in resp.get_json()['error']
    # nothing was saved
    listing = c.get(f'/api/dashboard/chat/channels/{cid}/messages').get_json()
    assert listing['messages'] == []


def test_upload_bad_type_rejected(client, monkeypatch):
    _enable_session_uploads(monkeypatch, result=None)
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = _post_multipart(
        c, h, cid,
        {'body': '', 'file': _upload_file('run.exe', 'application/x-msdownload')},
    )
    assert resp.status_code == 400


def test_upload_success_attaches_file(client, monkeypatch):
    att = {'url': 'https://cdn/pic.png', 'filename': 'pic.png',
           'type': 'image/png', 'size': 10}
    _enable_session_uploads(monkeypatch, result=att)
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = _post_multipart(c, h, cid, {'body': 'look', 'file': _upload_file()})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['message']['attachments'] == [att]
    assert 'uploadError' not in payload
    listing = c.get(f'/api/dashboard/chat/channels/{cid}/messages').get_json()
    assert listing['messages'][-1]['attachments'] == [att]


def test_upload_file_only_message_allowed(client, monkeypatch):
    att = {'url': 'https://cdn/pic.png', 'filename': 'pic.png',
           'type': 'image/png', 'size': 10}
    _enable_session_uploads(monkeypatch, result=att)
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = _post_multipart(c, h, cid, {'body': '', 'file': _upload_file()})
    assert resp.status_code == 200
    assert resp.get_json()['message']['body'] == ''


def test_upload_failure_keeps_message(client, monkeypatch):
    _enable_session_uploads(monkeypatch, result=None)  # upload itself fails
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = _post_multipart(c, h, cid, {'body': 'hello', 'file': _upload_file()})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['uploadError']
    assert 'attachments' not in payload['message']
    listing = c.get(f'/api/dashboard/chat/channels/{cid}/messages').get_json()
    assert listing['messages'][-1]['body'] == 'hello'


def test_markdown_stored_raw(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    body = '**bold** and `code` and https://x.dev'
    resp = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages', json={'body': body}, headers=h
    )
    assert resp.get_json()['message']['body'] == body  # raw source, no HTML
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_chat.py -k upload -v`
Expected: the new route tests FAIL (multipart posts currently 400 "Type a message first." with no upload handling; success/unavailable assertions fail).

- [ ] **Step 3: Implement** — in `src/routes_chat.py`:

3a. Add `_storage` to the `from .helpers import (...)` list.

3b. Below the link-preview constants, add:

```python
# ── Uploads ───────────────────────────────────────────────────────────────────

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # Airtable's content-upload API cap
ALLOWED_UPLOAD_TYPES = {
    'image/png', 'image/jpeg', 'image/gif', 'image/webp',
    'application/pdf', 'text/plain',
}
```

3c. Replace the whole `api_chat_message_add` view body with:

```python
    @app.post('/api/dashboard/chat/channels/<channel_id>/messages')
    @login_required
    def api_chat_message_add(channel_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        state = get_dashboard_state()
        channel = find_by_id(_channels(state), channel_id)
        if not channel:
            return json_error('Channel not found.', 404)

        multipart = (request.content_type or '').startswith('multipart/form-data')
        raw_body = request.form.get('body') if multipart else json_payload().get('body')
        body = clean_text(raw_body, max_len=MAX_MESSAGE_LEN)
        upload = request.files.get('file') if multipart else None

        if not body and not upload:
            return json_error('Type a message first.')

        backend = None
        content = b''
        if upload:
            if not feature_enabled('FEATURE_CHAT_UPLOADS'):
                return json_error('File uploads are disabled.')
            backend = _storage()
            if not getattr(backend, 'supports_uploads', False):
                return json_error("File uploads aren't available on this storage backend.")
            content = upload.read()
            if len(content) > MAX_UPLOAD_BYTES:
                return json_error('File is too large (max 5 MB).')
            if upload.mimetype not in ALLOWED_UPLOAD_TYPES:
                return json_error("That file type isn't allowed.")

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
        if body and feature_enabled('FEATURE_CHAT_LINK_PREVIEWS'):
            url = first_url(body)
            if url:
                preview = fetch_link_preview(url)
                if preview:
                    message['linkPreview'] = preview
        _messages(state).append(message)
        channel['lastMessageAt'] = created_at
        # Save first: on the Airtable backend the message row must exist before
        # the content API can attach a file to it.
        save_dashboard_state(state)

        upload_error = ''
        if upload:
            filename = clean_text(upload.filename, fallback='upload', max_len=120) or 'upload'
            attachment = backend.upload_attachment(
                message['id'], filename, content, upload.mimetype
            )
            if attachment:
                message['attachments'] = [attachment]
                save_dashboard_state(state)
            else:
                upload_error = 'The file could not be uploaded; the message was posted without it.'

        # Deliberately omit full state: the client polls messages separately,
        # and returning state here would trigger a heavy full-page re-render.
        payload = {'message': message}
        if upload_error:
            payload['uploadError'] = upload_error
        return flask.jsonify(payload)
```

- [ ] **Step 4: Run the full chat suite**

Run: `python -m pytest tests/test_chat.py -v`
Expected: all PASS (including all pre-existing tests — JSON posting must be unchanged)

- [ ] **Step 5: Commit**

```bash
git add src/routes_chat.py tests/test_chat.py
git commit -m "feat: accept multipart file uploads on chat message endpoint"
```

---

### Task 7: Flags to the chat page + composer upload UI markup

**Files:**
- Modify: `src/routes_web.py` (`dashboard_chat`, lines 252-255; add `feature_enabled` to the `.helpers` import list at the top)
- Modify: `templates/dashboard/chat.html` (root div line 7; composer form lines 62-66)
- Test: `tests/test_chat.py`

**Interfaces:**
- Consumes: `feature_enabled` (Task 1).
- Produces: template context `chat_flags = {'uploads': bool, 'previews': bool, 'markdown': bool}`; DOM contract for Task 8 — `data-chat-flags` JSON attribute on `[data-dashboard-page="chat"]`, and elements `#chatAttachButton`, `#chatFileInput`, `#chatFileChip`, `#chatFileName`, `#chatFileRemove`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_chat.py`:

```python
# ── Chat page flags & upload UI ───────────────────────────────────────────────

def test_chat_page_exposes_flags(client):
    c, _ = _seed(client, 'leader')
    html = c.get('/dashboard/chat').get_data(as_text=True)
    assert 'data-chat-flags' in html
    assert 'chatAttachButton' in html  # uploads default on


def test_chat_page_hides_upload_ui_when_disabled(client, monkeypatch):
    monkeypatch.setenv('FEATURE_CHAT_UPLOADS', 'false')
    c, _ = _seed(client, 'leader')
    html = c.get('/dashboard/chat').get_data(as_text=True)
    assert 'chatAttachButton' not in html
    assert '"uploads": false' in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_chat.py -k chat_page -v`
Expected: FAIL — `data-chat-flags` not in the rendered page.

- [ ] **Step 3: Implement the route** — add `feature_enabled` to the `from .helpers import (...)` list in `src/routes_web.py`, then:

```python
    @app.route('/dashboard/chat')
    @login_required
    def dashboard_chat():
        return flask.render_template(
            'dashboard/chat.html',
            chat_flags={
                'uploads': feature_enabled('FEATURE_CHAT_UPLOADS'),
                'previews': feature_enabled('FEATURE_CHAT_LINK_PREVIEWS'),
                'markdown': feature_enabled('FEATURE_CHAT_MARKDOWN'),
            },
        )
```

- [ ] **Step 4: Implement the template** — in `templates/dashboard/chat.html`:

4a. Line 7 root div (single-quoted attribute — Flask's `tojson` escapes `'` but not `"`):

```html
<div class="dashboard-page" data-dashboard-page="chat" data-chat-flags='{{ chat_flags | tojson }}'>
```

4b. Replace the composer form (lines 62-66) with:

```html
            <form class="chat-composer" id="chatComposer" hidden autocomplete="off">
                {% if chat_flags.uploads %}
                <input type="file" id="chatFileInput" hidden
                    accept="image/png,image/jpeg,image/gif,image/webp,application/pdf,text/plain">
                <button class="icon-button" type="button" id="chatAttachButton"
                    title="Attach a file" aria-label="Attach a file"
                    data-i18n-attr="title:chat.attach;aria-label:chat.attach">
                    <span aria-hidden="true">&#128206;</span>
                </button>
                {% endif %}
                <span class="chat-file-chip" id="chatFileChip" hidden>
                    <span id="chatFileName"></span>
                    <button type="button" id="chatFileRemove" aria-label="Remove file"
                        data-i18n-attr="aria-label:chat.removeFile">&times;</button>
                </span>
                <input class="chat-composer-input" type="text" name="body" maxlength="500"
                    data-i18n-attr="placeholder:chat.messagePlaceholder" placeholder="Type a message…" aria-label="Message">
                <button class="btn-primary" type="submit" data-i18n="chat.send">Send</button>
            </form>
```

(New strings use `data-i18n`/`data-i18n-attr` with English defaults in markup, matching how every existing `chat.*` key works — the dashboard chat keys are not in `i18n-data.js`; the visible text is the fallback.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_chat.py -k chat_page -v`
Expected: 2 PASS

- [ ] **Step 6: Commit**

```bash
git add src/routes_web.py templates/dashboard/chat.html tests/test_chat.py
git commit -m "feat: expose chat feature flags to the chat page and add upload UI"
```

---

### Task 8: Frontend — markdown renderer, attachments, previews, file sending

**Files:**
- Modify: `static/js/dashboard.js` (`apiRequest` ~line 208; chat section ~line 1369+; `appendMessage` ~line 1486; composer submit handler ~line 1945)
- Modify: `static/css/dashboard.css` (append new rules at the end)
- Test: full pytest suite (server contract) + manual browser check; there is no JS test framework in this project — do not add one.

**Interfaces:**
- Consumes: DOM ids from Task 7; `message.attachments` / `message.linkPreview` / `uploadError` from Task 6; existing `escapeHtml`, `showToast`, `$`, `avatarMarkup`, `chatTime`.
- Produces: `renderChatMarkdown(body)`, `attachmentMarkup(att)`, `linkPreviewMarkup(preview)`, `clearChatFile()`, module-scoped `chatFlags` and `chatFile`.

- [ ] **Step 1: Teach `apiRequest` about FormData** — replace the body of `apiRequest` (line ~208):

```js
    async function apiRequest(path, options = {}) {
        const method = options.method || 'GET';
        const isForm = options.body instanceof FormData;
        const headers = { Accept: 'application/json' };
        if (method !== 'GET') {
            if (!isForm) headers['Content-Type'] = 'application/json';
            headers['X-CSRF-Token'] = csrfToken;
        }

        const response = await fetch(path, {
            method,
            headers,
            credentials: 'same-origin',
            body: isForm ? options.body : (options.body ? JSON.stringify(options.body) : undefined),
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload.error || 'Request failed.');
        }
        if (payload.state) {
            setState(payload.state);
        }
        return payload;
    }
```

(Never set Content-Type for FormData — the browser must add the multipart boundary itself.)

- [ ] **Step 2: Add chat flags + markdown/attachment renderers** — in the chat section, below the `let chatVisibilityBound = false;` line (~1378), add:

```js
    const chatFlagsEl = document.querySelector('[data-dashboard-page="chat"]');
    let chatFlags = { uploads: true, previews: true, markdown: true };
    try {
        chatFlags = { ...chatFlags, ...JSON.parse(chatFlagsEl?.dataset.chatFlags || '{}') };
    } catch (error) { /* malformed attribute — keep defaults */ }
    let chatFile = null;

    // Escape-first inline markdown: the whole body is HTML-escaped before any
    // tags are introduced, so user input can never inject markup.
    function renderChatMarkdown(body) {
        let html = escapeHtml(body);
        if (!chatFlags.markdown) return html;
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
        html = html.replace(/~~([^~]+)~~/g, '<del>$1</del>');
        html = html.replace(/(^|\s)(https?:\/\/[^\s<]+)/g,
            (m, pre, url) => `${pre}<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`);
        return html;
    }

    function attachmentMarkup(att) {
        const url = escapeHtml(att.url || '');
        const name = escapeHtml(att.filename || 'file');
        if ((att.type || '').startsWith('image/')) {
            return `<a class="chat-attachment" href="${url}" target="_blank" rel="noopener noreferrer">
                <img class="chat-attachment-image" src="${url}" alt="${name}" loading="lazy"></a>`;
        }
        return `<a class="chat-attachment chat-attachment-file" href="${url}" target="_blank" rel="noopener noreferrer">&#128206; ${name}</a>`;
    }

    function linkPreviewMarkup(preview) {
        if (!preview || !preview.title) return '';
        const image = preview.image
            ? `<img class="chat-preview-image" src="${escapeHtml(preview.image)}" alt="" loading="lazy">` : '';
        const desc = preview.description
            ? `<p class="chat-preview-desc">${escapeHtml(preview.description)}</p>` : '';
        return `<a class="chat-link-preview" href="${escapeHtml(preview.url)}" target="_blank" rel="noopener noreferrer">
            ${image}<span class="chat-preview-text"><span class="chat-preview-title">${escapeHtml(preview.title)}</span>${desc}</span></a>`;
    }

    function clearChatFile() {
        chatFile = null;
        const chip = document.getElementById('chatFileChip');
        const fileInput = document.getElementById('chatFileInput');
        if (chip) chip.hidden = true;
        if (fileInput) fileInput.value = '';
    }
```

- [ ] **Step 3: Render extras in `appendMessage`** — replace the `row.innerHTML` template (line ~1493-1501) with:

```js
        const attachments = (message.attachments || []).map(attachmentMarkup).join('');
        row.innerHTML = `
            ${avatarMarkup(person, 'avatar-sm')}
            <div class="chat-message-body">
                <div class="chat-message-meta">
                    <span class="chat-message-author">${escapeHtml(message.authorName || message.authorEmail || 'Member')}</span>
                    <span class="chat-message-time">${escapeHtml(chatTime(message.createdAt))}</span>
                </div>
                ${message.body ? `<p class="chat-message-text">${renderChatMarkdown(message.body)}</p>` : ''}
                ${attachments}
                ${linkPreviewMarkup(message.linkPreview)}
            </div>`;
```

- [ ] **Step 4: Rework the composer submit + file picker handlers** — replace the `$('#chatComposer')?.addEventListener('submit', ...)` block (line ~1945-1962) with:

```js
        $('#chatComposer')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const input = event.currentTarget.elements.body;
            const body = (input.value || '').trim();
            if ((!body && !chatFile) || !chatActiveId) return;
            input.value = '';
            let payload;
            if (chatFile) {
                payload = new FormData();
                payload.append('body', body);
                payload.append('file', chatFile);
            } else {
                payload = { body };
            }
            try {
                const result = await apiRequest(
                    `/api/dashboard/chat/channels/${encodeURIComponent(chatActiveId)}/messages`, {
                        method: 'POST',
                        body: payload,
                    });
                if (result.uploadError) showToast(result.uploadError, 'error');
                clearChatFile();
                await fetchMessages(chatActiveId);
                scrollChatToBottom();
            } catch (error) {
                input.value = body;   // restore so the user doesn't lose their text
                showToast(error.message, 'error');
            }
        });

        $('#chatAttachButton')?.addEventListener('click', () => $('#chatFileInput')?.click());
        $('#chatFileInput')?.addEventListener('change', (event) => {
            const file = event.currentTarget.files[0];
            if (!file) return;
            if (file.size > 5 * 1024 * 1024) {
                showToast('File is too large (max 5 MB).', 'error');
                event.currentTarget.value = '';
                return;
            }
            chatFile = file;
            $('#chatFileName').textContent = file.name;
            $('#chatFileChip').hidden = false;
        });
        $('#chatFileRemove')?.addEventListener('click', clearChatFile);
```

- [ ] **Step 5: Append chat CSS** — at the end of `static/css/dashboard.css` (before adding, check the top of the file for this project's CSS custom-property names and swap the `var(...)` names below to the real ones; the fallbacks make the rules work either way):

```css
/* ── Chat attachments & link previews ─────────────────────────────────────── */
.chat-attachment { display: block; margin-top: 6px; max-width: 320px; }
.chat-attachment-image { max-width: 100%; max-height: 240px; border-radius: 8px; display: block; }
.chat-attachment-file {
    display: inline-block; padding: 6px 10px; font-size: 0.85rem;
    border: 1px solid var(--border, #e0e6ed); border-radius: 8px; text-decoration: none;
}
.chat-file-chip {
    display: inline-flex; align-items: center; gap: 6px; font-size: 0.8rem;
    padding: 2px 8px; border-radius: 999px; background: var(--surface-2, #f1f5f9);
    white-space: nowrap;
}
.chat-file-chip button { border: 0; background: none; cursor: pointer; font-size: 0.9rem; }
.chat-link-preview {
    display: flex; gap: 10px; margin-top: 6px; padding: 8px 10px; max-width: 420px;
    border-left: 3px solid var(--red, #ec3750); border-radius: 6px;
    background: var(--surface-2, #f8fafc); text-decoration: none;
}
.chat-preview-image { width: 56px; height: 56px; object-fit: cover; border-radius: 6px; flex: none; }
.chat-preview-title { font-weight: 600; display: block; }
.chat-preview-desc { font-size: 0.8rem; margin: 2px 0 0; }
.chat-message-text code {
    background: var(--surface-2, #f1f5f9); padding: 1px 5px;
    border-radius: 4px; font-size: 0.85em;
}
```

Also check `static/css/dark-mode.css` for how other dashboard surfaces override colors; if it overrides hardcoded fallbacks elsewhere, add matching dark-mode rules for `.chat-link-preview`, `.chat-file-chip`, and `.chat-message-text code` there.

- [ ] **Step 6: Verify**

Run: `python -m pytest`
Expected: full suite PASS.

Manual check (the JS has no automated tests): start the app (`python app.py`), sign in via the playtest provider if enabled, open `/dashboard/chat`, and confirm: markdown renders (`**bold**`, backtick code), a URL in a message becomes a link, the paperclip button opens a picker and shows the chip, and removing the chip clears it. On the session backend a file send should toast "File uploads aren't available on this storage backend." — that's correct behavior, not a bug.

- [ ] **Step 7: Commit**

```bash
git add static/js/dashboard.js static/css/dashboard.css
git commit -m "feat: render chat markdown, attachments, and link previews in the client"
```

---

### Task 9: Full verification + Airtable schema rollout

**Files:**
- No code changes expected; fixes only if verification finds regressions.

- [ ] **Step 1: Run the entire test suite**

Run: `python -m pytest`
Expected: all tests pass (70+ pre-existing plus ~35 new).

- [ ] **Step 2: Apply the Airtable schema** (uses `.env` credentials; idempotent):

Run: `python scripts/setup_chat_tables.py`
Expected output includes `+ Messages: added field Metadata` and `+ Messages: added field Attachments` (or `= Messages: already exists, skipping` on re-runs).

- [ ] **Step 3: End-to-end check on the Airtable backend** — with the real `.env` (STORAGE_BACKEND=airtable), start the app, post a chat message containing a public URL and a small PNG, and confirm: the message appears with a preview card, the image renders, and the Airtable Messages table shows the row with `Metadata` JSON and an `Attachments` file.

- [ ] **Step 4: Commit anything outstanding and report**

```bash
git status   # should be clean of sprint-1 files
```

Report results honestly: list any step that failed or was skipped.
