"""Chat (channels + messages) API coverage.

These exercise *successful* authenticated writes, so they also guard against
the whole write layer regressing (e.g. a missing save_dashboard_state import
would surface here as a 500 rather than slipping through the CSRF-only checks
in test_api.py).
"""

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
            'members': [{
                'id': 'm1', 'name': f'Test {role.title()}',
                'email': f'{role}@test.com',
                'role': 'Leader' if role == 'leader' else 'Member',
                'avatar': '', 'status': 'Active',
            }],
            'channels': channels or [],
            'messages': [],
            'settings': {'clubName': 'Test Club', 'joinCode': 'abc123'},
        }
    return client, {'X-CSRF-Token': CSRF}


_SEED_CHANNEL = {'id': 'chan-1', 'name': 'general', 'description': '',
                 'createdBy': 'x', 'lastMessageAt': ''}


def _make_channel(client, headers, name='general'):
    resp = client.post('/api/dashboard/chat/channels',
                       json={'name': name, 'description': 'desc'}, headers=headers)
    return resp


def test_leader_creates_channel(client):
    c, h = _seed(client, 'leader')
    resp = _make_channel(c, h, '#general')
    assert resp.status_code == 200
    channel = resp.get_json()['channel']
    assert channel['name'] == 'general'          # leading '#' stripped
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

    resp = c.post(f'/api/dashboard/chat/channels/{cid}/messages',
                  json={'body': 'Hello team!'}, headers=h)
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['message']['body'] == 'Hello team!'
    assert 'state' not in payload            # kept light for polling

    listing = c.get(f'/api/dashboard/chat/channels/{cid}/messages').get_json()
    assert any(m['body'] == 'Hello team!' for m in listing['messages'])
    assert listing['hasMore'] is False

    # channel.lastMessageAt is bumped on post
    channels = c.get('/api/dashboard/chat/channels').get_json()['channels']
    assert next(ch for ch in channels if ch['id'] == cid)['lastMessageAt']


def test_members_can_post(client):
    # a member owns their own (session) club here; seed a channel to post into
    c, h = _seed(client, 'member', channels=[dict(_SEED_CHANNEL)])
    resp = c.post('/api/dashboard/chat/channels/chan-1/messages',
                  json={'body': 'hi from member'}, headers=h)
    assert resp.status_code == 200


def test_empty_message_rejected(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    resp = c.post(f'/api/dashboard/chat/channels/{cid}/messages',
                  json={'body': '   '}, headers=h)
    assert resp.status_code == 400


def test_since_returns_only_newer(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    first = c.post(f'/api/dashboard/chat/channels/{cid}/messages',
                   json={'body': 'one'}, headers=h).get_json()['message']
    c.post(f'/api/dashboard/chat/channels/{cid}/messages',
           json={'body': 'two'}, headers=h)

    # query_string dict encodes the '+' in the ISO offset correctly
    resp = c.get(f'/api/dashboard/chat/channels/{cid}/messages',
                 query_string={'since': first['createdAt']})
    bodies = [m['body'] for m in resp.get_json()['messages']]
    assert bodies == ['two']


def test_messages_missing_channel_404(client):
    c, h = _seed(client, 'leader')
    resp = c.get('/api/dashboard/chat/channels/nope/messages')
    assert resp.status_code == 404


def test_delete_channel_cascades_messages(client):
    c, h = _seed(client, 'leader')
    cid = _make_channel(c, h).get_json()['channel']['id']
    c.post(f'/api/dashboard/chat/channels/{cid}/messages',
           json={'body': 'bye'}, headers=h)

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
