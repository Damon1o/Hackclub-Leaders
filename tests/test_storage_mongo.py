"""MongoStorage backend coverage, against an in-memory Mongo (mongomock).

These lock down the behaviours the rest of the app depends on: the same
interface as the Airtable backend, indexed lookups by member email and join
code, section-scoped loads, non-destructive partial saves, and message paging.
"""

import mongomock
import pytest

from src.storage import StorageError
from src.storage_mongo import CHILD_COLLECTIONS, INDEXES, MongoStorage, ensure_indexes


@pytest.fixture
def storage(monkeypatch):
    client = mongomock.MongoClient()
    monkeypatch.setattr('src.storage_mongo._get_client', lambda uri: client)
    monkeypatch.setenv('MONGODB_URI', 'mongodb://test/')
    monkeypatch.setenv('MONGODB_DB', 'test_leaders')
    return MongoStorage()


def _state(**overrides):
    state = {
        'settings': {'clubName': 'Test Club', 'joinCode': 'abc123'},
        'members': [
            {'id': 'm1', 'name': 'Leader', 'email': 'leader@test.com', 'role': 'Leader'},
            {'id': 'm2', 'name': 'Member', 'email': 'member@test.com', 'role': 'Member'},
        ],
        'events': [{'id': 'e1', 'title': 'Kickoff', 'date': '2026-01-01'}],
        'projects': [
            {'id': 'p1', 'name': 'Shipped thing', 'status': 'Shipped', 'date': '2026-02-01'},
            {'id': 'p2', 'name': 'Pending thing', 'status': 'Submitted', 'date': '2026-03-01'},
        ],
        'channels': [{'id': 'c1', 'name': 'general'}],
        'messages': [],
        'newsletters': [],
        'orders': [],
        'itemRequests': [{'id': 'r1', 'name': 'Stickers', 'date': '2026-04-01'}],
    }
    state.update(overrides)
    return state


def test_missing_uri_raises(monkeypatch):
    monkeypatch.delenv('MONGODB_URI', raising=False)
    with pytest.raises(StorageError):
        MongoStorage()


def test_save_then_load_round_trips(storage):
    storage.save('leader@test.com', _state())
    loaded = storage.load('leader@test.com')
    assert loaded['settings']['clubName'] == 'Test Club'
    assert [m['id'] for m in loaded['members']] == ['m1', 'm2']
    assert loaded['events'][0]['title'] == 'Kickoff'
    # Mongo bookkeeping must never leak into app state.
    assert '_id' not in loaded['members'][0]
    assert 'clubKey' not in loaded['members'][0]


def test_load_unknown_club_returns_none(storage):
    assert storage.load('nobody@test.com') is None


def test_indexes_cover_every_declared_collection(storage):
    ensure_indexes(storage.db)
    for collection, specs in INDEXES.items():
        existing = storage.db[collection].index_information()
        for keys, _unique in specs:
            wanted = [list(pair) for pair in keys]
            assert any(
                [list(k) for k in info['key']] == wanted for info in existing.values()
            ), f'{collection} missing index on {keys}'


def test_resolve_club_key_finds_member_club(storage):
    storage.save('leader@test.com', _state())
    assert storage.resolve_club_key('member@test.com') == 'leader@test.com'


def test_resolve_club_key_falls_back_to_own_email(storage):
    assert storage.resolve_club_key('Stranger@Test.com') == 'stranger@test.com'


def test_find_club_by_join_code(storage):
    storage.save('leader@test.com', _state())
    assert storage.find_club_by_join_code('abc123') == 'leader@test.com'
    assert storage.find_club_by_join_code('nope') is None


def test_list_clubs_counts_members_and_ships(storage):
    storage.save('leader@test.com', _state())
    clubs = storage.list_clubs()
    assert len(clubs) == 1
    assert clubs[0]['memberCount'] == 2
    assert clubs[0]['shipCount'] == 1
    assert clubs[0]['pendingShips'] == 1


def test_list_pending_projects_only_returns_submitted(storage):
    storage.save('leader@test.com', _state())
    pending = storage.list_pending_projects()
    assert [item['project']['id'] for item in pending] == ['p2']
    assert pending[0]['clubName'] == 'Test Club'


def test_list_item_requests_carries_club_name(storage):
    storage.save('leader@test.com', _state())
    requests = storage.list_item_requests()
    assert len(requests) == 1
    assert requests[0]['request']['name'] == 'Stickers'
    assert requests[0]['clubName'] == 'Test Club'


def test_load_lite_returns_only_settings_and_members(storage):
    storage.save('leader@test.com', _state())
    lite = storage.load_lite('leader@test.com')
    assert lite['_lite'] is True
    assert set(lite) == {'settings', 'members', '_lite'}


def test_load_sections_fetches_only_what_was_asked_for(storage):
    storage.save('leader@test.com', _state())
    partial = storage.load('leader@test.com', sections=['events'])
    assert set(partial) == {'settings', 'events'}
    assert partial['events'][0]['id'] == 'e1'


def test_load_ignores_unknown_section_names(storage):
    storage.save('leader@test.com', _state())
    partial = storage.load('leader@test.com', sections=['events', 'not-a-section'])
    assert set(partial) == {'settings', 'events'}


def test_partial_save_leaves_absent_sections_alone(storage):
    storage.save('leader@test.com', _state())
    # A page that only loaded events saves only events back.
    storage.save('leader@test.com', {'settings': {'clubName': 'Test Club'}, 'events': []})
    reloaded = storage.load('leader@test.com')
    assert reloaded['events'] == []
    assert len(reloaded['members']) == 2
    assert len(reloaded['projects']) == 2


def test_save_deletes_items_dropped_from_a_loaded_section(storage):
    storage.save('leader@test.com', _state())
    state = storage.load('leader@test.com')
    state['members'] = [state['members'][0]]
    storage.save('leader@test.com', state)
    assert [m['id'] for m in storage.load('leader@test.com')['members']] == ['m1']


def test_clubs_are_isolated_from_each_other(storage):
    storage.save('a@test.com', _state())
    storage.save('b@test.com', _state(members=[{'id': 'm9', 'email': 'solo@test.com'}]))
    assert len(storage.load('a@test.com')['members']) == 2
    assert len(storage.load('b@test.com')['members']) == 1
    for collection in CHILD_COLLECTIONS:
        for doc in storage.db[collection].find({}):
            assert doc['clubKey'] in ('a@test.com', 'b@test.com')


def test_get_user_record_defaults_when_missing(storage):
    record = storage.get_user_record('nobody@example.com')
    assert record == {'preferredName': '', 'sessionVersion': 0}


def test_save_and_get_user_record_round_trips(storage):
    storage.save_user_record('leader@example.com', {'preferredName': 'Ada', 'sessionVersion': 1})
    record = storage.get_user_record('leader@example.com')
    assert record == {'preferredName': 'Ada', 'sessionVersion': 1}


def test_save_user_record_merges_partial_update(storage):
    storage.save_user_record('leader@example.com', {'preferredName': 'Ada'})
    storage.save_user_record('leader@example.com', {'sessionVersion': 2})
    record = storage.get_user_record('leader@example.com')
    assert record == {'preferredName': 'Ada', 'sessionVersion': 2}


def test_get_user_record_lowercases_email(storage):
    storage.save_user_record('Leader@Example.com', {'preferredName': 'Ada'})
    record = storage.get_user_record('leader@example.com')
    assert record['preferredName'] == 'Ada'


def _messages(count):
    return [
        {
            'id': f'msg-{i}',
            'channelId': 'c1',
            'authorEmail': 'leader@test.com',
            'body': f'message {i}',
            'createdAt': f'2026-01-01T00:{i:02d}:00+00:00',
        }
        for i in range(count)
    ]


def test_page_messages_returns_newest_page_oldest_first(storage):
    storage.save('leader@test.com', _state(messages=_messages(10)))
    page, has_more = storage.page_messages('leader@test.com', 'c1', limit=4)
    assert [m['id'] for m in page] == ['msg-6', 'msg-7', 'msg-8', 'msg-9']
    assert has_more is True


def test_page_messages_before_cursor_walks_backwards(storage):
    storage.save('leader@test.com', _state(messages=_messages(10)))
    page, has_more = storage.page_messages(
        'leader@test.com', 'c1', limit=4, before='2026-01-01T00:06:00+00:00'
    )
    assert [m['id'] for m in page] == ['msg-2', 'msg-3', 'msg-4', 'msg-5']
    assert has_more is True


def test_page_messages_reports_no_more_at_the_start(storage):
    storage.save('leader@test.com', _state(messages=_messages(3)))
    page, has_more = storage.page_messages('leader@test.com', 'c1', limit=10)
    assert len(page) == 3
    assert has_more is False


def test_page_messages_since_returns_everything_newer(storage):
    storage.save('leader@test.com', _state(messages=_messages(6)))
    page, has_more = storage.page_messages(
        'leader@test.com', 'c1', limit=2, since='2026-01-01T00:03:00+00:00'
    )
    assert [m['id'] for m in page] == ['msg-4', 'msg-5']
    assert has_more is False


def test_page_messages_scoped_to_one_channel(storage):
    other = dict(_messages(2)[0], id='other-1', channelId='c2')
    storage.save('leader@test.com', _state(messages=_messages(3) + [other]))
    page, _ = storage.page_messages('leader@test.com', 'c1', limit=10)
    assert all(m['channelId'] == 'c1' for m in page)
    assert len(page) == 3


# ── Section-scoped loading through the app ────────────────────────────────────


@pytest.fixture
def mongo_client(monkeypatch, storage):
    """A signed-in test client served by the Mongo backend."""
    from app import app

    monkeypatch.setenv('STORAGE_BACKEND', 'mongo')
    storage.save('leader@test.com', _state(messages=_messages(5)))
    app.config['TESTING'] = True
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user'] = {
            'id': 'u1',
            'name': 'Leader',
            'email': 'leader@test.com',
            'avatar': '',
            'provider': 'hackclub',
            'sessionVersion': 0,
        }
        sess['csrf_token'] = 'test-csrf-token'
    return client


def _embedded_state(response):
    import json
    import re

    html = response.get_data(as_text=True)
    raw = re.search(
        r'<script id="dashboard-state" type="application/json">(.*?)</script>', html, re.S
    )
    return json.loads(raw.group(1))


def test_team_page_embeds_only_members(mongo_client):
    state = _embedded_state(mongo_client.get('/dashboard/team'))
    assert state['members']
    # The roster page renders no chat, so none of it is shipped to the browser.
    assert 'messages' not in state
    assert 'channels' not in state


def test_chat_page_embeds_chat_sections(mongo_client):
    state = _embedded_state(mongo_client.get('/dashboard/chat'))
    assert 'channels' in state
    assert 'messages' in state
    assert 'orders' not in state


def test_state_endpoint_honours_sections_on_mongo(mongo_client):
    state = mongo_client.get('/api/dashboard/state?sections=events').get_json()['state']
    assert 'events' in state
    assert 'messages' not in state


def test_saving_from_a_partial_page_keeps_other_sections(mongo_client, storage):
    response = mongo_client.post(
        '/api/dashboard/team',
        json={'name': 'New Person', 'email': 'new@test.com', 'role': 'Member'},
        headers={'X-CSRF-Token': 'test-csrf-token'},
    )
    assert response.status_code == 200
    stored = storage.load('leader@test.com')
    assert len(stored['members']) == 3
    # The write went through a members-only page; chat history must survive it.
    assert len(stored['messages']) == 5
    assert len(stored['projects']) == 2
