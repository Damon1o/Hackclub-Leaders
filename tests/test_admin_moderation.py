"""Admin moderation + fulfillment endpoints added with the admin-page update."""

import pytest

from src import helpers


@pytest.fixture
def ban_file(tmp_path, monkeypatch):
    """Point the ban writer at a throwaway file so tests never touch the real
    banned_emails.json."""
    path = tmp_path / 'banned_emails.json'
    monkeypatch.setattr(helpers, 'BANS_JSON_PATH', str(path))
    return path


def _seed_state(admin_client, **extra):
    with admin_client.session_transaction() as sess:
        sess['csrf_token'] = 'tok'
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Mod Club', 'coinBalance': 10, 'coinsSpent': 0},
            'members': [
                {'id': 'm1', 'name': 'Al', 'email': 'al@test.com', 'role': 'Leader', 'status': 'Active'},
                {'id': 'm2', 'name': 'Bo', 'email': 'bo@test.com', 'role': 'Member', 'status': 'Active'},
            ],
            'orders': [
                {
                    'id': 'o1',
                    'date': '2026-08-10',
                    'status': 'Requested',
                    'items': [{'id': 's1', 'name': 'Sticker Pack', 'quantity': 2}],
                }
            ],
            'reports': [
                {
                    'id': 'rp1',
                    'channelId': 'ch1',
                    'messageId': 'msg1',
                    'reason': 'spam',
                    'reporterEmail': 'bo@test.com',
                    'reporterName': 'Bo',
                    'createdAt': '2026-08-17T00:00:00Z',
                    'status': 'Open',
                }
            ],
            'messages': [
                {
                    'id': 'msg1',
                    'channelId': 'ch1',
                    'body': 'hello',
                    'authorEmail': 'bo@test.com',
                    'authorName': 'Bo',
                    'createdAt': '2026-08-17T00:00:00Z',
                }
            ],
            'ledger': [
                {'id': 'c0', 'delta': 10, 'kind': 'starter_grant', 'ref': '', 'note': '', 'at': '2026-08-01T00:00:00Z'},
            ],
            'auditLog': [],
            **extra,
        }


HEADERS = {'X-CSRF-Token': 'tok'}


# ── Shop item update ─────────────────────────────────────────────────────────


def test_update_shop_item_route(admin_client, monkeypatch, shop_file):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(admin_client)
    response = admin_client.patch(
        '/api/admin/shop-items/sticker-pack',
        headers=HEADERS,
        json={'name': 'Sticker Pack', 'cost': '15', 'filter': 'Swag', 'image': ''},
    )
    assert response.status_code == 200
    assert response.get_json()['shopItem']['cost'] == 15


def test_update_shop_item_route_404_unknown(admin_client, monkeypatch, shop_file):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(admin_client)
    response = admin_client.patch(
        '/api/admin/shop-items/nope',
        headers=HEADERS,
        json={'name': 'Nope', 'cost': '1', 'filter': 'Swag', 'image': ''},
    )
    assert response.status_code == 404


# ── Orders ───────────────────────────────────────────────────────────────────


def test_orders_requires_admin(auth_client):
    assert auth_client.get('/api/admin/orders').status_code == 403


def test_orders_list(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(admin_client)
    response = admin_client.get('/api/admin/orders')
    assert response.status_code == 200
    orders = response.get_json()['orders']
    assert orders[0]['order']['id'] == 'o1'
    assert orders[0]['clubName'] == 'Mod Club'


def test_fulfill_order(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(admin_client)
    response = admin_client.patch(
        '/api/admin/orders/admin@test.com/o1', json={'status': 'Fulfilled'}, headers=HEADERS
    )
    assert response.status_code == 200
    assert response.get_json()['order']['status'] == 'Fulfilled'
    with admin_client.session_transaction() as sess:
        assert sess['dashboard_state']['orders'][0]['status'] == 'Fulfilled'
        assert any(
            e['action'] == 'order_fulfilled' for e in sess['dashboard_state']['auditLog']
        )


# ── Coin adjust ──────────────────────────────────────────────────────────────


def test_coin_adjust(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(admin_client)
    response = admin_client.patch(
        '/api/admin/clubs/admin@test.com/coins',
        json={'delta': 40, 'reason': 'prize correction'},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.get_json()['coinBalance'] == 50
    with admin_client.session_transaction() as sess:
        state = sess['dashboard_state']
        assert any(t['kind'] == 'admin_adjust' for t in state['ledger'])
        assert any(e['action'].startswith('coins_adjusted') for e in state['auditLog'])


def test_coin_adjust_requires_reason(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(admin_client)
    response = admin_client.patch(
        '/api/admin/clubs/admin@test.com/coins', json={'delta': 5}, headers=HEADERS
    )
    assert response.status_code == 400


# ── Members ──────────────────────────────────────────────────────────────────


def test_member_delete(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(admin_client)
    response = admin_client.delete(
        '/api/admin/clubs/admin@test.com/members/m2', headers=HEADERS
    )
    assert response.status_code == 200
    with admin_client.session_transaction() as sess:
        assert [m['id'] for m in sess['dashboard_state']['members']] == ['m1']


def test_member_delete_blocks_last_leader(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(admin_client, members=[
        {'id': 'm1', 'name': 'Al', 'email': 'al@test.com', 'role': 'Leader', 'status': 'Active'},
    ])
    response = admin_client.delete(
        '/api/admin/clubs/admin@test.com/members/m1', headers=HEADERS
    )
    assert response.status_code == 400


def test_member_role_update(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(admin_client)
    response = admin_client.patch(
        '/api/admin/clubs/admin@test.com/members/m2',
        json={'role': 'Mentor'},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.get_json()['member']['role'] == 'Mentor'


# ── Chat moderation ──────────────────────────────────────────────────────────


def test_chat_messages_list(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(admin_client)
    response = admin_client.get('/api/admin/chat/messages')
    assert response.status_code == 200
    messages = response.get_json()['messages']
    assert messages[0]['message']['id'] == 'msg1'


def test_chat_messages_flagged_filter(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(
        admin_client,
        messages=[
            {
                'id': 'msg1',
                'channelId': 'ch1',
                'body': 'clean',
                'authorEmail': 'bo@test.com',
                'authorName': 'Bo',
                'createdAt': '2026-08-17T00:00:00Z',
            },
            {
                'id': 'msg2',
                'channelId': 'ch1',
                'body': 'this is shit',
                'authorEmail': 'bo@test.com',
                'authorName': 'Bo',
                'createdAt': '2026-08-17T00:01:00Z',
                'autoFlagged': True,
                'flagReason': 'shit',
            },
        ],
    )
    response = admin_client.get('/api/admin/chat/messages?flagged=1')
    assert response.status_code == 200
    messages = response.get_json()['messages']
    assert [m['message']['id'] for m in messages] == ['msg2']


def test_chat_message_admin_delete(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(admin_client)
    response = admin_client.delete(
        '/api/admin/chat/messages/admin@test.com/msg1', headers=HEADERS
    )
    assert response.status_code == 200
    with admin_client.session_transaction() as sess:
        message = sess['dashboard_state']['messages'][0]
        assert message['deleted'] is True
        assert message['deletedByAdmin'] is True
        assert message['body'] == ''


def test_chat_message_dismiss_flag(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(
        admin_client,
        messages=[
            {
                'id': 'msg1',
                'channelId': 'ch1',
                'body': 'harsh words',
                'authorEmail': 'bo@test.com',
                'authorName': 'Bo',
                'createdAt': '2026-08-17T00:00:00Z',
                'autoFlagged': True,
                'flagReason': 'shit',
            }
        ],
    )
    response = admin_client.patch(
        '/api/admin/chat/messages/admin@test.com/msg1', headers=HEADERS
    )
    assert response.status_code == 200
    with admin_client.session_transaction() as sess:
        message = sess['dashboard_state']['messages'][0]
        assert 'autoFlagged' not in message
        assert 'flagReason' not in message


def test_auto_flag_reasons():
    assert helpers.auto_flag_reasons('this is fine') == ''
    assert helpers.auto_flag_reasons('this is SHIT') == 'shit'
    assert helpers.auto_flag_reasons('get free robux now') == 'free robux'
    # Word boundary: 'shirts' must not match 'shit'.
    assert helpers.auto_flag_reasons('nice shirts') == ''


# ── Reports ──────────────────────────────────────────────────────────────────


def test_reports_list(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(admin_client)
    response = admin_client.get('/api/admin/reports')
    assert response.status_code == 200
    reports = response.get_json()['reports']
    assert reports[0]['report']['id'] == 'rp1'


def test_report_resolve(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(admin_client)
    response = admin_client.patch(
        '/api/admin/reports/admin@test.com/rp1', json={'status': 'Resolved'}, headers=HEADERS
    )
    assert response.status_code == 200
    assert response.get_json()['report']['status'] == 'Resolved'


# ── Banned emails ────────────────────────────────────────────────────────────


def test_ban_and_unban(admin_client, monkeypatch, ban_file):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(admin_client)
    response = admin_client.post(
        '/api/admin/banned-emails', json={'email': 'spammer@test.com'}, headers=HEADERS
    )
    assert response.status_code == 200
    assert response.get_json()['added'] is True
    assert helpers.is_banned_email('spammer@test.com')
    # Re-ban is a no-op.
    response = admin_client.post(
        '/api/admin/banned-emails', json={'email': 'spammer@test.com'}, headers=HEADERS
    )
    assert response.get_json()['added'] is False
    # Unban removes it.
    response = admin_client.delete(
        '/api/admin/banned-emails/spammer@test.com', headers=HEADERS
    )
    assert response.status_code == 200
    assert not helpers.is_banned_email('spammer@test.com')


def test_ban_list_requires_admin(auth_client):
    assert auth_client.get('/api/admin/banned-emails').status_code == 403


def test_banned_user_cannot_join(admin_client, monkeypatch, ban_file):
    """A banned email is rejected by the join-code route."""
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(admin_client)
    helpers.ban_email('banned@test.com')
    with admin_client.session_transaction() as sess:
        sess['csrf_token'] = 'tok'
        sess['user'] = {'name': 'Banned', 'email': 'banned@test.com', 'provider': 'hackclub'}
    response = admin_client.post(
        '/dashboard/welcome/join',
        data={'joinCode': 'whatever', 'csrf_token': 'tok'},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b'not allowed to join' in response.data


def test_banned_user_cannot_post_chat(admin_client, monkeypatch, ban_file):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    state = {
        'settings': {'clubName': 'Mod Club', 'chatEnabledForMembers': True},
        'members': [
            {'id': 'm9', 'name': 'Banned', 'email': 'banned@test.com', 'role': 'Member', 'status': 'Active'},
        ],
        'channels': [{'id': 'ch1', 'name': 'general'}],
        'messages': [],
    }
    helpers.ban_email('banned@test.com')
    with admin_client.session_transaction() as sess:
        sess['csrf_token'] = 'tok'
        sess['user'] = {'name': 'Banned', 'email': 'banned@test.com', 'provider': 'hackclub'}
        sess['dashboard_state'] = state
    response = admin_client.post(
        '/api/dashboard/chat/channels/ch1/messages',
        json={'body': 'hi'},
        headers=HEADERS,
    )
    assert response.status_code == 403


# ── Audit log helper ─────────────────────────────────────────────────────────


def test_log_action_prepends(admin_client):
    state = {'auditLog': []}
    helpers.log_action(state, 'admin@test.com', 'thing_done', 't1')
    assert state['auditLog'][0]['action'] == 'thing_done'
    assert state['auditLog'][0]['target'] == 't1'
    assert state['auditLog'][0]['actor'] == 'admin@test.com'


def test_admin_page_renders_new_panels(admin_client, monkeypatch, shop_file):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_state(admin_client)
    response = admin_client.get('/dashboard/admin')
    assert response.status_code == 200
    text = response.data.decode()
    for marker in ('adminShopCatalogTable', 'adminOrderList', 'adminChatList',
                   'adminReportList', 'adminBanList', 'Ships this week', 'Open reports'):
        assert marker in text
