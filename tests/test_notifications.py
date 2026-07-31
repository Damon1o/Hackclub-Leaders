"""Notification centre API coverage.

The bell menu in dashboard_layout.html called these endpoints before they
existed, so every mark-as-read 404'd. These lock the contract down.
"""

import pytest

CSRF = 'test-csrf-token'


@pytest.fixture(autouse=True)
def _session_backend(monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')


def _seed(client, unread=2, read=1):
    items = [
        {
            'id': f'notif-u{i}',
            'type': 'event_rsvp',
            'title': f'Unread {i}',
            'message': 'Something happened.',
            'data': {},
            'read': False,
            'createdAt': f'2026-05-{i + 1:02d}T00:00:00+00:00',
        }
        for i in range(unread)
    ] + [
        {
            'id': f'notif-r{i}',
            'type': 'order_placed',
            'title': f'Read {i}',
            'message': 'Old news.',
            'data': {},
            'read': True,
            'createdAt': f'2026-04-{i + 1:02d}T00:00:00+00:00',
        }
        for i in range(read)
    ]
    with client.session_transaction() as sess:
        sess['user'] = {
            'id': 'u1',
            'name': 'Leader',
            'email': 'leader@test.com',
            'avatar': '',
            'provider': 'hackclub',
        }
        sess['csrf_token'] = CSRF
        sess['dashboard_state'] = {
            'members': [
                {
                    'id': 'm1',
                    'name': 'Leader',
                    'email': 'leader@test.com',
                    'role': 'Leader',
                    'status': 'Active',
                    'avatar': '',
                }
            ],
            'notifications': items,
            'settings': {'clubName': 'Test Club', 'joinCode': 'abc123'},
        }
    return client, {'X-CSRF-Token': CSRF}


def test_list_requires_login(client):
    assert client.get('/api/dashboard/notifications').status_code in (301, 302)


def test_list_returns_notifications_and_unread_count(client):
    c, _ = _seed(client, unread=2, read=1)
    body = c.get('/api/dashboard/notifications').get_json()
    assert body['total'] == 3
    assert body['unread'] == 2


def test_list_paginates(client):
    c, _ = _seed(client, unread=3, read=3)
    body = c.get('/api/dashboard/notifications?page=2&per_page=2').get_json()
    assert len(body['items']) == 2
    assert body['pages'] == 3


def test_mark_one_read(client):
    c, h = _seed(client, unread=2, read=0)
    response = c.patch('/api/dashboard/notifications/notif-u0', json={'read': True}, headers=h)
    assert response.status_code == 200
    body = response.get_json()
    assert body['notification']['read'] is True
    assert body['unread'] == 1


def test_mark_one_read_persists(client):
    c, h = _seed(client, unread=2, read=0)
    c.patch('/api/dashboard/notifications/notif-u0', json={'read': True}, headers=h)
    assert c.get('/api/dashboard/notifications').get_json()['unread'] == 1


def test_mark_unread_again(client):
    c, h = _seed(client, unread=0, read=2)
    body = c.patch(
        '/api/dashboard/notifications/notif-r0', json={'read': False}, headers=h
    ).get_json()
    assert body['notification']['read'] is False
    assert body['unread'] == 1


def test_mark_unknown_notification_is_404(client):
    c, h = _seed(client)
    assert c.patch('/api/dashboard/notifications/nope', json={'read': True}, headers=h).status_code == 404


def test_mark_requires_csrf(client):
    c, _ = _seed(client)
    assert c.patch('/api/dashboard/notifications/notif-u0', json={'read': True}).status_code == 403


def test_mark_all_read(client):
    c, h = _seed(client, unread=3, read=1)
    body = c.patch('/api/dashboard/notifications/mark-all-read', headers=h).get_json()
    assert body['updated'] == 3
    assert body['unread'] == 0
    assert c.get('/api/dashboard/notifications').get_json()['unread'] == 0


def test_mark_all_read_is_idempotent(client):
    c, h = _seed(client, unread=0, read=2)
    body = c.patch('/api/dashboard/notifications/mark-all-read', headers=h).get_json()
    assert body['updated'] == 0


def test_mark_all_read_route_is_not_swallowed_by_the_id_route(client):
    """The literal path must not be matched as a notification id."""
    c, h = _seed(client, unread=1, read=0)
    assert c.patch('/api/dashboard/notifications/mark-all-read', headers=h).status_code == 200


def test_mark_all_read_requires_csrf(client):
    c, _ = _seed(client)
    assert c.patch('/api/dashboard/notifications/mark-all-read').status_code == 403


def test_delete_notification(client):
    c, h = _seed(client, unread=2, read=0)
    assert c.delete('/api/dashboard/notifications/notif-u0', headers=h).status_code == 200
    body = c.get('/api/dashboard/notifications').get_json()
    assert body['total'] == 1
    assert body['unread'] == 1


def test_delete_unknown_notification_is_404(client):
    c, h = _seed(client)
    assert c.delete('/api/dashboard/notifications/nope', headers=h).status_code == 404


def test_default_state_has_a_notifications_list(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {'settings': {'clubName': 'C'}, 'members': []}
    assert auth_client.get('/api/dashboard/notifications').get_json()['total'] == 0
