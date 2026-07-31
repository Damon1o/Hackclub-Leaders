"""Pagination and section-scoped loading across the API.

These run on the session (cookie) backend so a seeded club is visible without
touching Airtable or Mongo.
"""

import pytest

CSRF = 'test-csrf-token'


@pytest.fixture(autouse=True)
def _session_backend(monkeypatch):
    # The app's .env may select a shared backend; these need the cookie one.
    monkeypatch.setenv('STORAGE_BACKEND', 'session')


def _seed(client, members=1, events=0, projects=0, messages=0):
    with client.session_transaction() as sess:
        sess['user'] = {
            'id': 'u-leader',
            'name': 'Test Leader',
            'email': 'leader@test.com',
            'avatar': '',
            'provider': 'hackclub',
        }
        sess['csrf_token'] = CSRF
        sess['dashboard_state'] = {
            'members': [
                {
                    'id': f'm{i}',
                    'name': f'Member {i}',
                    'email': f'm{i}@test.com',
                    'role': 'Leader' if i == 0 else 'Member',
                    'avatar': '',
                    'status': 'Active',
                }
                for i in range(members)
            ],
            'events': [
                {'id': f'e{i}', 'title': f'Event {i}', 'date': f'2026-01-{i + 1:02d}', 'time': ''}
                for i in range(events)
            ],
            'projects': [
                {
                    'id': f'p{i}',
                    'name': f'Project {i}',
                    'status': 'Shipped' if i % 2 else 'Draft',
                    'date': f'2026-02-{i + 1:02d}',
                }
                for i in range(projects)
            ],
            'channels': [{'id': 'c1', 'name': 'general', 'lastMessageAt': ''}],
            'messages': [
                {
                    'id': f'msg-{i}',
                    'channelId': 'c1',
                    'authorEmail': 'leader@test.com',
                    'authorName': 'Test Leader',
                    'body': f'message {i}',
                    'createdAt': f'2026-01-01T00:{i:02d}:00+00:00',
                }
                for i in range(messages)
            ],
            'settings': {'clubName': 'Test Club', 'joinCode': 'abc123'},
        }
    return client, {'X-CSRF-Token': CSRF}


# ── Paginated list endpoints ──────────────────────────────────────────────────


def test_team_list_paginates(client):
    c, _ = _seed(client, members=30)
    body = c.get('/api/dashboard/team?page=1&per_page=10').get_json()
    assert len(body['items']) == 10
    assert body['total'] == 30
    assert body['pages'] == 3
    assert body['hasMore'] is True


def test_team_list_second_page_continues(client):
    c, _ = _seed(client, members=30)
    first = c.get('/api/dashboard/team?page=1&per_page=10').get_json()['items']
    second = c.get('/api/dashboard/team?page=2&per_page=10').get_json()['items']
    assert [m['id'] for m in first] != [m['id'] for m in second]
    assert len(first) == len(second) == 10


def test_last_page_reports_no_more(client):
    c, _ = _seed(client, members=25)
    body = c.get('/api/dashboard/team?page=3&per_page=10').get_json()
    assert len(body['items']) == 5
    assert body['hasMore'] is False


def test_page_beyond_the_end_clamps_to_last_page(client):
    c, _ = _seed(client, members=5)
    body = c.get('/api/dashboard/team?page=99&per_page=2').get_json()
    assert body['page'] == 3
    assert body['items']


def test_garbage_paging_values_fall_back_to_defaults(client):
    c, _ = _seed(client, members=5)
    body = c.get('/api/dashboard/team?page=-4&per_page=abc').get_json()
    assert body['page'] == 1
    assert body['perPage'] == 25


def test_per_page_is_capped(client):
    c, _ = _seed(client, members=5)
    assert c.get('/api/dashboard/team?per_page=99999').get_json()['perPage'] == 200


def test_events_list_is_sorted_soonest_first(client):
    c, _ = _seed(client, events=5)
    items = c.get('/api/dashboard/events?per_page=5').get_json()['items']
    assert [e['id'] for e in items] == ['e0', 'e1', 'e2', 'e3', 'e4']


def test_projects_list_filters_by_status(client):
    c, _ = _seed(client, projects=6)
    body = c.get('/api/dashboard/projects?status=Shipped&per_page=50').get_json()
    assert body['total'] == 3
    assert all(p['status'] == 'Shipped' for p in body['items'])


def test_projects_list_is_newest_first(client):
    c, _ = _seed(client, projects=4)
    items = c.get('/api/dashboard/projects?per_page=10').get_json()['items']
    assert [p['id'] for p in items] == ['p3', 'p2', 'p1', 'p0']


def test_list_endpoints_require_login(client):
    for path in ('/api/dashboard/team', '/api/dashboard/events', '/api/dashboard/projects'):
        assert client.get(path).status_code in (301, 302)


# ── Section-scoped state ──────────────────────────────────────────────────────


def test_state_endpoint_returns_everything_by_default(client):
    c, _ = _seed(client, members=2, events=2, projects=2)
    state = c.get('/api/dashboard/state').get_json()['state']
    assert {'members', 'events', 'projects'} <= set(state)


def test_state_endpoint_accepts_sections(client):
    c, _ = _seed(client, members=2, events=2)
    state = c.get('/api/dashboard/state?sections=members,events').get_json()['state']
    # Session mode always has the whole blob in the cookie, so the response
    # is a superset — what matters is that the request is accepted and the
    # requested sections are present.
    assert state['members'] and state['events']


def test_state_endpoint_ignores_unknown_sections(client):
    c, _ = _seed(client, members=2)
    response = c.get('/api/dashboard/state?sections=members,haxx,%20')
    assert response.status_code == 200
    assert response.get_json()['state']['members']


# ── Chat message paging ───────────────────────────────────────────────────────


def _messages(client, query=''):
    return client.get(f'/api/dashboard/chat/channels/c1/messages{query}').get_json()


def test_chat_returns_newest_page_by_default(client):
    c, _ = _seed(client, messages=60)
    body = _messages(c)
    assert len(body['messages']) == 50
    assert body['messages'][-1]['id'] == 'msg-59'
    assert body['hasMore'] is True


def test_chat_limit_is_honoured(client):
    c, _ = _seed(client, messages=20)
    body = _messages(c, '?limit=5')
    assert [m['id'] for m in body['messages']] == [
        'msg-15',
        'msg-16',
        'msg-17',
        'msg-18',
        'msg-19',
    ]
    assert body['hasMore'] is True


def test_chat_before_cursor_walks_backwards(client):
    c, _ = _seed(client, messages=20)
    body = _messages(c, '?limit=5&before=2026-01-01T00:10:00%2B00:00')
    assert [m['id'] for m in body['messages']] == ['msg-5', 'msg-6', 'msg-7', 'msg-8', 'msg-9']
    assert body['hasMore'] is True


def test_chat_before_cursor_reports_start_of_history(client):
    c, _ = _seed(client, messages=20)
    body = _messages(c, '?limit=10&before=2026-01-01T00:05:00%2B00:00')
    assert [m['id'] for m in body['messages']] == [f'msg-{i}' for i in range(5)]
    assert body['hasMore'] is False


def test_chat_since_still_returns_only_newer_messages(client):
    c, _ = _seed(client, messages=10)
    body = _messages(c, '?since=2026-01-01T00:07:00%2B00:00')
    assert [m['id'] for m in body['messages']] == ['msg-8', 'msg-9']
    assert body['hasMore'] is False


def test_chat_limit_is_capped(client):
    c, _ = _seed(client, messages=300)
    body = _messages(c, '?limit=99999')
    assert len(body['messages']) == 200


def test_chat_bad_limit_falls_back_to_default(client):
    c, _ = _seed(client, messages=60)
    assert len(_messages(c, '?limit=nope')['messages']) == 50


def test_chat_unknown_channel_is_404(client):
    c, _ = _seed(client, messages=3)
    assert client.get('/api/dashboard/chat/channels/nope/messages').status_code == 404
