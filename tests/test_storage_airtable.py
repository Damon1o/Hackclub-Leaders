"""AirtableStorage coverage for the cross-club Users table (get_user_record()
and save_user_record()) and the Explore read path (list_public_projects)."""

import pytest

from src.storage import AirtableStorage, StorageError


@pytest.fixture
def storage(monkeypatch):
    monkeypatch.setenv('AIRTABLE_TOKEN', 'test-token')
    monkeypatch.setenv('AIRTABLE_BASE_ID', 'test-base')
    return AirtableStorage()


def test_get_user_record_defaults_when_table_missing(storage, monkeypatch):
    def fake_list(table, field, value, fields=None):
        raise StorageError('Airtable GET Users failed (404): Table not found')

    monkeypatch.setattr(storage, '_list', fake_list)
    record = storage.get_user_record('nobody@example.com')
    assert record == {'sessionVersion': 0}


def test_get_user_record_defaults_when_no_row(storage, monkeypatch):
    monkeypatch.setattr(storage, '_list', lambda table, field, value, fields=None: [])
    record = storage.get_user_record('nobody@example.com')
    assert record == {'sessionVersion': 0}


def test_get_user_record_reads_existing_row(storage, monkeypatch):
    def fake_list(table, field, value, fields=None):
        assert table == storage.users_table
        assert field == 'Email'
        assert value == 'leader@example.com'
        return [
            {
                'id': 'rec1',
                'fields': {'Email': 'leader@example.com', 'Session Version': 3},
            }
        ]

    monkeypatch.setattr(storage, '_list', fake_list)
    record = storage.get_user_record('leader@example.com')
    assert record == {'sessionVersion': 3}


def test_get_user_record_lowercases_email(storage, monkeypatch):
    seen = {}

    def fake_list(table, field, value, fields=None):
        seen['value'] = value
        return []

    monkeypatch.setattr(storage, '_list', fake_list)
    storage.get_user_record('Leader@Example.com')
    assert seen['value'] == 'leader@example.com'


def test_save_user_record_raises_when_table_missing(storage, monkeypatch):
    def fake_list(table, field, value, fields=None):
        raise StorageError('Airtable GET Users failed (404): Table not found')

    monkeypatch.setattr(storage, '_list', fake_list)
    with pytest.raises(StorageError, match='Users table'):
        storage.save_user_record('leader@example.com', {'sessionVersion': 1})


def test_save_user_record_creates_new_row(storage, monkeypatch):
    monkeypatch.setattr(storage, '_list', lambda table, field, value, fields=None: [])
    calls = []
    monkeypatch.setattr(
        storage, '_request', lambda method, table, **kwargs: calls.append((method, table, kwargs)) or {}
    )
    storage.save_user_record('leader@example.com', {'sessionVersion': 2})
    assert len(calls) == 1
    method, table, kwargs = calls[0]
    assert method == 'post'
    assert table == storage.users_table
    assert kwargs['json']['fields'] == {
        'Session Version': 2,
        'Email': 'leader@example.com',
    }


def test_save_user_record_updates_existing_row(storage, monkeypatch):
    monkeypatch.setattr(
        storage,
        '_list',
        lambda table, field, value, fields=None: [
            {'id': 'rec1', 'fields': {'Email': 'leader@example.com', 'Session Version': 1}}
        ],
    )
    calls = []
    monkeypatch.setattr(
        storage, '_request', lambda method, table, **kwargs: calls.append((method, table, kwargs)) or {}
    )
    storage.save_user_record('leader@example.com', {'sessionVersion': 2})
    assert len(calls) == 1
    method, table, kwargs = calls[0]
    assert method == 'patch'
    assert table == storage.users_table
    assert kwargs['record_path'] == 'rec1'
    assert kwargs['json']['fields'] == {'Session Version': 2}


def _club_row(leader_email, club_name, public=True):
    return {'id': f'rec-{leader_email}', 'fields': {
        'Leader Email': leader_email, 'Club Name': club_name, 'Public Directory': public,
    }}


def _project_row(public_id, club_email, name='Ship', category='Web'):
    return {'id': f'rec-{public_id}', 'fields': {
        'Club Email': club_email, 'Status': 'Shipped', 'Public': True,
        'Public ID': public_id, 'Name': name, 'Description': 'desc',
        'Thumbnail': '', 'Demo URL': '', 'URL': '', 'Repo URL': '',
        'Owner Name': 'Ada', 'Category': category, 'Date': '2026-08-01',
    }}


def _fake_list_all_for(rows):
    def fake_list_all(table, fields=None):
        return list(rows.get(table, []))

    return fake_list_all


def test_list_public_projects_returns_narrow_projection(storage, monkeypatch):
    rows = {
        storage.clubs_table: [
            _club_row('a@club.com', 'Club A'),
            _club_row('b@club.com', 'Club B'),
        ],
        storage.tables['projects']: [
            _project_row('showcase-a', 'a@club.com', 'Alpha'),
            _project_row('showcase-b', 'b@club.com', 'Beta'),
        ],
    }
    monkeypatch.setattr(storage, '_list_all', _fake_list_all_for(rows))
    projects = storage.list_public_projects()
    assert [p['publicId'] for p in projects] == ['showcase-a', 'showcase-b']
    assert projects[0]['clubName'] == 'Club A'
    assert 'ownerEmail' not in projects[0]
    assert 'id' not in projects[0]


def test_list_public_projects_filters_to_one_club(storage, monkeypatch):
    rows = {
        storage.clubs_table: [
            _club_row('a@club.com', 'Club A'),
            _club_row('b@club.com', 'Club B'),
        ],
        storage.tables['projects']: [
            _project_row('showcase-a', 'a@club.com', 'Alpha'),
            _project_row('showcase-b', 'b@club.com', 'Beta'),
        ],
    }
    monkeypatch.setattr(storage, '_list_all', _fake_list_all_for(rows))
    projects = storage.list_public_projects('b@club.com')
    assert [p['publicId'] for p in projects] == ['showcase-b']


def test_list_public_projects_excludes_unpublished_rows(storage, monkeypatch):
    hidden = _project_row('showcase-h', 'a@club.com', 'Hidden')
    hidden['fields']['Public'] = False
    rows = {
        storage.clubs_table: [_club_row('a@club.com', 'Club A')],
        storage.tables['projects']: [_project_row('showcase-a', 'a@club.com'), hidden],
    }
    monkeypatch.setattr(storage, '_list_all', _fake_list_all_for(rows))
    assert [p['publicId'] for p in storage.list_public_projects()] == ['showcase-a']
