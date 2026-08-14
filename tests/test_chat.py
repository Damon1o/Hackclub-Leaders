"""Chat (channels + messages) API coverage.

These exercise *successful* authenticated writes, so they also guard against
the whole write layer regressing (e.g. a missing save_dashboard_state import
would surface here as a 500 rather than slipping through the CSRF-only checks
in test_api.py).
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

CSRF = 'test-csrf-token'


@pytest.fixture(autouse=True)
def _session_backend(monkeypatch):
    # The app's .env may select the Airtable backend; these tests need the
    # in-cookie session backend so a seeded club is actually visible.
    monkeypatch.setenv('STORAGE_BACKEND', 'session')


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    # The message POST limiter keeps a process-global bucket per user; clear it
    # between tests so counts from one test don't spill into the next.
    try:
        from src.routes_chat import reset_rate_limits
        reset_rate_limits()
    except ImportError:
        pass
    yield


def _seed(client, role, channels=None):
    with client.session_transaction() as sess:
        sess['user'] = {
            'id': 'u-' + role,
            'name': f'Test {role.title()}',
            'email': f'{role}@test.com',
            'avatar': '',
            'provider': 'hackclub',
        }
        sess['csrf_token'] = CSRF
        sess['dashboard_state'] = {
            'members': [
                {
                    'id': 'm1',
                    'name': f'Test {role.title()}',
                    'email': f'{role}@test.com',
                    'role': 'Leader' if role == 'leader' else 'Member',
                    'avatar': '',
                    'status': 'Active',
                }
            ],
            'channels': channels or [],
            'messages': [],
            'settings': {'clubName': 'Test Club', 'joinCode': 'abc123'},
        }
    return client, {'X-CSRF-Token': CSRF}


_SEED_CHANNEL = {
    'id': 'chan-1',
    'name': 'general',
    'description': '',
    'createdBy': 'x',
    'lastMessageAt': '',
}


def _make_channel(client, headers, name='general'):
    resp = client.post(
        '/api/dashboard/chat/channels', json={'name': name, 'description': 'desc'}, headers=headers
    )
    return resp


def test_leader_creates_channel(client):
    c, h = _seed(client, 'leader')
    resp = _make_channel(c, h, '#general')
    assert resp.status_code == 200
    channel = resp.get_json()['channel']
    assert channel['name'] == 'general'  # leading '#' stripped
    assert channel['createdBy'] == 'leader@test.com'
    assert channel['id']


def test_member_cannot_create_channel(client):
    c, h = _seed(client, 'member')
    resp = _make_channel(c, h)
    assert resp.status_code == 403


def test_channel_requires_csrf(client):
    c, _ = _seed(client, 'leader')
    resp = c.post('/api/dashboard/chat/channels', json={'name': 'x'})
    assert resp.status_code == 403


def test_blank_channel_name_rejected(client):
    c, h = _seed(client, 'leader')
    resp = c.post('/api/dashboard/chat/channels', json={'name': '  '}, headers=h)
    assert resp.status_code == 400


def test_post_and_list_messages(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']

    resp = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages', json={'body': 'Hello team!'}, headers=h
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['message']['body'] == 'Hello team!'
    assert 'state' not in payload  # kept light for polling

    listing = c.get(f'/api/dashboard/chat/channels/{cid}/messages').get_json()
    assert any(m['body'] == 'Hello team!' for m in listing['messages'])
    assert listing['hasMore'] is False

    # channel.lastMessageAt is bumped on post
    channels = c.get('/api/dashboard/chat/channels').get_json()['channels']
    assert next(ch for ch in channels if ch['id'] == cid)['lastMessageAt']


def test_members_can_post(client):
    # a member owns their own (session) club here; seed a channel to post into
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    resp = c.post(
        '/api/dashboard/chat/channels/chan-1/messages', json={'body': 'hi from member'}, headers=h
    )
    assert resp.status_code == 200


def test_empty_message_rejected(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = c.post(f'/api/dashboard/chat/channels/{cid}/messages', json={'body': '   '}, headers=h)
    assert resp.status_code == 400


def test_since_returns_only_newer(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    first = c.post(
        f'/api/dashboard/chat/channels/{cid}/messages', json={'body': 'one'}, headers=h
    ).get_json()['message']
    c.post(f'/api/dashboard/chat/channels/{cid}/messages', json={'body': 'two'}, headers=h)

    # query_string dict encodes the '+' in the ISO offset correctly
    resp = c.get(
        f'/api/dashboard/chat/channels/{cid}/messages', query_string={'since': first['createdAt']}
    )
    bodies = [m['body'] for m in resp.get_json()['messages']]
    assert bodies == ['two']


def test_messages_missing_channel_404(client):
    c, h = _seed(client, 'leader')
    resp = c.get('/api/dashboard/chat/channels/nope/messages')
    assert resp.status_code == 404


def test_delete_channel_cascades_messages(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    c.post(f'/api/dashboard/chat/channels/{cid}/messages', json={'body': 'bye'}, headers=h)

    resp = c.delete(f'/api/dashboard/chat/channels/{cid}', headers=h)
    assert resp.status_code == 200
    state = resp.get_json()['state']
    assert not any(ch['id'] == cid for ch in state.get('channels', []))
    assert not any(m.get('channelId') == cid for m in state.get('messages', []))


def test_member_cannot_delete_channel(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    resp = c.delete('/api/dashboard/chat/channels/chan-1', headers=h)
    assert resp.status_code == 403


# ── Message deletion / editing helpers ──────────────────────────────────────

def _iso(delta=None):
    now = datetime.now(timezone.utc)
    return (now + delta if delta else now).isoformat()


def _seed_message(client, message):
    """Append a pre-built message onto the seeded dashboard state."""
    with client.session_transaction() as sess:
        state = sess['dashboard_state']
        state['messages'].append(message)
        # Reassign the top-level key: mutating the nested list alone doesn't
        # mark the session dirty, so it wouldn't persist.
        sess['dashboard_state'] = state


def _msg(mid, author, body='hello', created=None, **extra):
    return {
        'id': mid, 'channelId': 'chan-1', 'authorEmail': author,
        'authorName': author, 'authorAvatar': '',
        'body': body, 'createdAt': created or _iso(), **extra,
    }


# ── Message deletion ────────────────────────────────────────────────────────

def test_leader_deletes_any_message(client):
    c, h = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'someone@test.com'))
    resp = c.delete('/api/dashboard/chat/channels/chan-1/messages/m-1', headers=h)
    assert resp.status_code == 200
    msg = resp.get_json()['message']
    assert msg['deleted'] is True
    assert msg['body'] == ''


def test_author_deletes_own_recent_message(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'member@test.com'))
    resp = c.delete('/api/dashboard/chat/channels/chan-1/messages/m-1', headers=h)
    assert resp.status_code == 200
    assert resp.get_json()['message']['deleted'] is True


def test_member_cannot_delete_others_message(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'someone@test.com'))
    resp = c.delete('/api/dashboard/chat/channels/chan-1/messages/m-1', headers=h)
    assert resp.status_code == 403


def test_member_cannot_delete_own_stale_message(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'member@test.com',
                          created=_iso(timedelta(hours=-25))))
    resp = c.delete('/api/dashboard/chat/channels/chan-1/messages/m-1', headers=h)
    assert resp.status_code == 403


def test_delete_missing_message_404(client):
    c, h = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    resp = c.delete('/api/dashboard/chat/channels/chan-1/messages/nope', headers=h)
    assert resp.status_code == 404


def test_delete_message_requires_csrf(client):
    c, _ = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'leader@test.com'))
    resp = c.delete('/api/dashboard/chat/channels/chan-1/messages/m-1')
    assert resp.status_code == 403


# ── Message editing ─────────────────────────────────────────────────────────

def test_author_edits_own_recent_message(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'member@test.com', body='typo'))
    resp = c.patch('/api/dashboard/chat/channels/chan-1/messages/m-1',
                   json={'body': 'fixed'}, headers=h)
    assert resp.status_code == 200
    msg = resp.get_json()['message']
    assert msg['body'] == 'fixed'
    assert msg['editedAt']


def test_member_cannot_edit_after_5_minutes(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'member@test.com',
                          created=_iso(timedelta(minutes=-6))))
    resp = c.patch('/api/dashboard/chat/channels/chan-1/messages/m-1',
                   json={'body': 'late edit'}, headers=h)
    assert resp.status_code == 403


def test_leader_edits_own_message_anytime(client):
    c, h = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'leader@test.com',
                          created=_iso(timedelta(days=-3))))
    resp = c.patch('/api/dashboard/chat/channels/chan-1/messages/m-1',
                   json={'body': 'still editable'}, headers=h)
    assert resp.status_code == 200
    assert resp.get_json()['message']['body'] == 'still editable'


def test_member_cannot_edit_others_message(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'someone@test.com'))
    resp = c.patch('/api/dashboard/chat/channels/chan-1/messages/m-1',
                   json={'body': 'hijack'}, headers=h)
    assert resp.status_code == 403


def test_cannot_edit_deleted_message(client):
    c, h = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'leader@test.com', body='', deleted=True))
    resp = c.patch('/api/dashboard/chat/channels/chan-1/messages/m-1',
                   json={'body': 'undelete'}, headers=h)
    assert resp.status_code == 409


def test_edit_empty_body_rejected(client):
    c, h = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'leader@test.com'))
    resp = c.patch('/api/dashboard/chat/channels/chan-1/messages/m-1',
                   json={'body': '   '}, headers=h)
    assert resp.status_code == 400


def test_edit_enforces_length_limit(client):
    c, h = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'leader@test.com'))
    resp = c.patch('/api/dashboard/chat/channels/chan-1/messages/m-1',
                   json={'body': 'x' * 600}, headers=h)
    assert resp.status_code == 200
    assert len(resp.get_json()['message']['body']) == 500


def test_edit_missing_message_404(client):
    c, h = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    resp = c.patch('/api/dashboard/chat/channels/chan-1/messages/nope',
                   json={'body': 'x'}, headers=h)
    assert resp.status_code == 404


# ── Rate limiting ───────────────────────────────────────────────────────────

def test_message_post_rate_limited(client):
    c, h = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    for _ in range(10):
        ok = c.post('/api/dashboard/chat/channels/chan-1/messages',
                    json={'body': 'spam'}, headers=h)
        assert ok.status_code == 200
    blocked = c.post('/api/dashboard/chat/channels/chan-1/messages',
                     json={'body': 'one too many'}, headers=h)
    assert blocked.status_code == 429
    assert blocked.get_json()['retryAfter'] >= 1


# ── Emoji reactions ─────────────────────────────────────────────────────────

_REACT_URL = '/api/dashboard/chat/channels/chan-1/messages/m-1/reactions'


def test_add_reaction(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'someone@test.com'))
    resp = c.post(_REACT_URL, json={'emoji': '👍'}, headers=h)
    assert resp.status_code == 200
    assert resp.get_json()['message']['reactions'] == {
        '👍': ['member@test.com']}


def test_toggle_reaction_off_drops_empty_key(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'someone@test.com',
                          reactions={'👍': ['member@test.com']}))
    resp = c.post(_REACT_URL, json={'emoji': '👍'}, headers=h)
    assert resp.status_code == 200
    # viewer's reaction removed and the now-empty emoji key dropped entirely
    assert resp.get_json()['message'].get('reactions', {}) == {}


def test_reaction_appends_to_other_authors(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'someone@test.com',
                          reactions={'👍': ['other@test.com']}))
    resp = c.post(_REACT_URL, json={'emoji': '👍'}, headers=h)
    assert resp.status_code == 200
    assert resp.get_json()['message']['reactions']['👍'] == [
        'other@test.com', 'member@test.com']


def test_reaction_requires_csrf(client):
    c, _ = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'someone@test.com'))
    resp = c.post(_REACT_URL, json={'emoji': '👍'})
    assert resp.status_code == 403


def test_reaction_empty_emoji_rejected(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'someone@test.com'))
    resp = c.post(_REACT_URL, json={'emoji': '   '}, headers=h)
    assert resp.status_code == 400


def test_reaction_overlong_emoji_rejected(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'someone@test.com'))
    resp = c.post(_REACT_URL, json={'emoji': 'x' * 9}, headers=h)
    assert resp.status_code == 400


def test_reaction_missing_channel_404(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    resp = c.post('/api/dashboard/chat/channels/nope/messages/m-1/reactions',
                  json={'emoji': '👍'}, headers=h)
    assert resp.status_code == 404


def test_reaction_missing_message_404(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    resp = c.post('/api/dashboard/chat/channels/chan-1/messages/nope/reactions',
                  json={'emoji': '👍'}, headers=h)
    assert resp.status_code == 404


def test_cannot_react_to_deleted_message(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('m-1', 'someone@test.com', body='', deleted=True))
    resp = c.post(_REACT_URL, json={'emoji': '👍'}, headers=h)
    assert resp.status_code == 409


def test_reaction_distinct_emoji_capped_at_8(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    full = {e: ['someone@test.com'] for e in '😀😁😂🤣😃😄😅😆'}  # 8 distinct
    _seed_message(c, _msg('m-1', 'someone@test.com', reactions=full))
    # a 9th distinct emoji is refused
    resp = c.post(_REACT_URL, json={'emoji': '🎉'}, headers=h)
    assert resp.status_code == 400
    # but joining an emoji already present on the message still works
    ok = c.post(_REACT_URL, json={'emoji': '😀'}, headers=h)
    assert ok.status_code == 200
    assert 'member@test.com' in ok.get_json()['message']['reactions']['😀']


# ── Channel topic ───────────────────────────────────────────────────────────

def test_channel_patch_sets_topic(client):
    c, h = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    resp = c.patch('/api/dashboard/chat/channels/chan-1',
                   json={'topic': 'Weekly standup'}, headers=h)
    assert resp.status_code == 200
    assert resp.get_json()['channel']['topic'] == 'Weekly standup'


def test_channel_topic_cleared_by_empty_string(client):
    c, h = _seed(client, 'leader',
                 channels=[dict(_SEED_CHANNEL, topic='old topic')])
    resp = c.patch('/api/dashboard/chat/channels/chan-1',
                   json={'topic': ''}, headers=h)
    assert resp.status_code == 200
    assert resp.get_json()['channel']['topic'] == ''


def test_channel_topic_length_capped(client):
    c, h = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    resp = c.patch('/api/dashboard/chat/channels/chan-1',
                   json={'topic': 'x' * 200}, headers=h)
    assert resp.status_code == 200
    assert len(resp.get_json()['channel']['topic']) == 120


def test_member_cannot_set_topic(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    resp = c.patch('/api/dashboard/chat/channels/chan-1',
                   json={'topic': 'nope'}, headers=h)
    assert resp.status_code == 403


def test_topic_included_in_channel_listing(client):
    c, h = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    c.patch('/api/dashboard/chat/channels/chan-1',
            json={'topic': 'Reading group'}, headers=h)
    channels = c.get('/api/dashboard/chat/channels').get_json()['channels']
    got = next(ch for ch in channels if ch['id'] == 'chan-1')
    assert got['topic'] == 'Reading group'


def test_leader_clears_channel_messages(client):
    c, h = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('msg-1', 'someone@test.com'))
    _seed_message(c, _msg('msg-2', 'else@test.com'))
    resp = c.delete('/api/dashboard/chat/channels/chan-1/messages', headers=h)
    assert resp.status_code == 200
    resp = c.get('/api/dashboard/chat/channels/chan-1/messages')
    assert resp.get_json()['messages'] == []


def test_member_cannot_clear_channel_messages(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    _seed_message(c, _msg('msg-1', 'member@test.com'))
    resp = c.delete('/api/dashboard/chat/channels/chan-1/messages', headers=h)
    assert resp.status_code == 403


def test_clear_missing_channel_404s(client):
    c, h = _seed(client, 'leader')
    resp = c.delete('/api/dashboard/chat/channels/nope/messages', headers=h)
    assert resp.status_code == 404


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


# ── Storage round-trip for message extras ─────────────────────────────────────

def _airtable():
    from src.storage import AirtableStorage
    return AirtableStorage(token='test-token', base_id='test-base')


def _save_messages_and_capture(monkeypatch, s, messages):
    captured = {}
    monkeypatch.setattr(s, '_list', lambda table, field, value: [])
    monkeypatch.setattr(
        s, '_request',
        lambda method, table, **kw: {'records': [{'id': 'clubrec'}]},
    )
    monkeypatch.setattr(
        s, '_batch',
        lambda method, table, records: captured.setdefault(table, records),
    )
    s.save('lead@x.com', {'settings': {}, 'messages': messages})
    return captured[s.tables['messages']][0]['fields']


def test_item_fields_serializes_link_preview(monkeypatch):
    s = _airtable()
    msg = {
        'id': 'msg-1', 'channelId': 'c1', 'authorEmail': 'a@x.com',
        'authorName': 'A', 'authorAvatar': '', 'body': 'hi', 'createdAt': 'now',
        'linkPreview': {'url': 'https://e.com', 'title': 'E'},
    }
    fields = _save_messages_and_capture(monkeypatch, s, [msg])
    assert json.loads(fields['Metadata']) == {'url': 'https://e.com', 'title': 'E'}
    assert 'Attachments' not in fields  # never synced back (URLs expire)


def test_item_fields_no_preview_writes_blank(monkeypatch):
    s = _airtable()
    msg = {'id': 'msg-1', 'channelId': 'c1', 'authorEmail': 'a@x.com',
           'authorName': 'A', 'authorAvatar': '', 'body': 'hi', 'createdAt': 'now'}
    fields = _save_messages_and_capture(monkeypatch, s, [msg])
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


# ── Mention resolution ────────────────────────────────────────────────────────

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


# ── Mentions on message post ──────────────────────────────────────────────────

def _add_member(client, name, email):
    with client.session_transaction() as sess:
        state = sess['dashboard_state']
        state['members'].append({
            'id': 'm-' + email, 'name': name, 'email': email,
            'role': 'Member', 'avatar': '', 'status': 'Active',
        })
        sess['dashboard_state'] = state


def _notifications(client):
    with client.session_transaction() as sess:
        return sess['dashboard_state'].get('notifications', [])


def test_message_with_mention_notifies_recipient(client):
    c, h = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    _add_member(c, 'Bob Lee', 'bob@test.com')

    resp = c.post(
        '/api/dashboard/chat/channels/chan-1/messages',
        json={'body': 'hey @Bob Lee check this'}, headers=h,
    )
    assert resp.status_code == 200
    message = resp.get_json()['message']
    assert message['mentions'] == ['bob@test.com']
    assert message['mentionsEveryone'] is False

    assert any(
        n['type'] == 'chat_mention' and n['data'].get('messageId') == message['id']
        for n in _notifications(c)
    )


def test_message_without_mentions_has_empty_fields(client):
    c, h = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    resp = c.post('/api/dashboard/chat/channels/chan-1/messages',
                  json={'body': 'nothing to see'}, headers=h)
    message = resp.get_json()['message']
    assert message['mentions'] == []
    assert message['mentionsEveryone'] is False
    assert _notifications(c) == []


def test_message_self_mention_not_notified(client):
    c, h = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    resp = c.post(
        '/api/dashboard/chat/channels/chan-1/messages',
        json={'body': 'note to self @Test Leader'}, headers=h,
    )
    assert resp.get_json()['message']['mentions'] == []
    assert not any(n['type'] == 'chat_mention' for n in _notifications(c))


def test_everyone_mention_by_leader_notifies_all_other_members(client):
    c, h = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    _add_member(c, 'Bob Lee', 'bob@test.com')
    resp = c.post(
        '/api/dashboard/chat/channels/chan-1/messages',
        json={'body': '@everyone standup now'}, headers=h,
    )
    assert resp.get_json()['message']['mentionsEveryone'] is True
    # bob notified, the leader who sent it excluded
    mention_notifs = [n for n in _notifications(c) if n['type'] == 'chat_mention']
    assert len(mention_notifs) == 1


def test_everyone_mention_by_member_not_honored(client):
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    _add_member(c, 'Bob Lee', 'bob@test.com')
    resp = c.post(
        '/api/dashboard/chat/channels/chan-1/messages',
        json={'body': '@everyone anyone around?'}, headers=h,
    )
    assert resp.get_json()['message']['mentionsEveryone'] is False
    assert not any(n['type'] == 'chat_mention' for n in _notifications(c))


def test_mentions_persist_on_message_listing(client):
    c, h = _seed(client, 'leader', channels=[dict(_SEED_CHANNEL)])
    _add_member(c, 'Bob Lee', 'bob@test.com')
    c.post('/api/dashboard/chat/channels/chan-1/messages',
           json={'body': 'ping @Bob Lee'}, headers=h)
    listing = c.get('/api/dashboard/chat/channels/chan-1/messages').get_json()
    assert listing['messages'][-1]['mentions'] == ['bob@test.com']


# ── Read receipts ─────────────────────────────────────────────────────────────


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
    assert len(rows) == 1


def test_mark_channel_read_never_rewinds(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']

    c.post(f'/api/dashboard/chat/channels/{cid}/read',
           json={'readAt': '2026-08-13T12:00:00Z'}, headers=h)
    resp = c.post(f'/api/dashboard/chat/channels/{cid}/read',
                  json={'readAt': '2026-08-13T10:00:00Z'}, headers=h)
    assert resp.get_json()['read']['lastReadAt'] == '2026-08-13T12:00:00Z'


def test_mark_channel_read_requires_csrf(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = c.post(f'/api/dashboard/chat/channels/{cid}/read', json={})
    assert resp.status_code == 403


def test_mark_channel_read_missing_channel(client):
    c, h = _seed(client, 'leader')
    resp = c.post('/api/dashboard/chat/channels/nope/read', json={}, headers=h)
    assert resp.status_code == 404


def test_channel_list_unread_flag(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']

    channels = c.get('/api/dashboard/chat/channels').get_json()['channels']
    assert channels[0]['unread'] is False

    c.post(f'/api/dashboard/chat/channels/{cid}/messages',
           json={'body': 'hi'}, headers=h)
    channels = c.get('/api/dashboard/chat/channels').get_json()['channels']
    assert channels[0]['unread'] is True

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
    assert resp.get_json()['reads'] == {'leader@test.com': '2026-08-13T10:00:00Z'}


def test_get_reads_scoped_to_channel(client):
    c, h = _seed(client, 'leader')
    cid1 = _make_channel(c, h, 'general').get_json()['channel']['id']
    cid2 = _make_channel(c, h, 'random').get_json()['channel']['id']
    c.post(f'/api/dashboard/chat/channels/{cid1}/read', json={}, headers=h)

    reads2 = c.get(f'/api/dashboard/chat/channels/{cid2}/reads').get_json()['reads']
    assert reads2 == {}


def test_delete_channel_drops_chat_reads(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    c.post(f'/api/dashboard/chat/channels/{cid}/read', json={}, headers=h)

    resp = c.delete(f'/api/dashboard/chat/channels/{cid}', headers=h)
    assert resp.status_code == 200
    with c.session_transaction() as sess:
        rows = sess['dashboard_state'].get('chatReads', [])
    assert rows == []


def _switch_user(client, name, email):
    with client.session_transaction() as sess:
        sess['user'] = {'id': 'u-' + email, 'name': name, 'email': email,
                        'avatar': '', 'provider': 'hackclub'}


def test_second_member_unread_clears_after_read(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    c.post(f'/api/dashboard/chat/channels/{cid}/messages',
           json={'body': 'hi'}, headers=h)

    _add_member(c, 'Bob Lee', 'bob@test.com')
    _switch_user(c, 'Bob Lee', 'bob@test.com')
    channels = c.get('/api/dashboard/chat/channels').get_json()['channels']
    assert channels[0]['unread'] is True

    c.post(f'/api/dashboard/chat/channels/{cid}/read', json={}, headers=h)
    channels = c.get('/api/dashboard/chat/channels').get_json()['channels']
    assert channels[0]['unread'] is False

    reads = c.get(f'/api/dashboard/chat/channels/{cid}/reads').get_json()['reads']
    assert set(reads) == {'bob@test.com'}   # the leader never marked it read
