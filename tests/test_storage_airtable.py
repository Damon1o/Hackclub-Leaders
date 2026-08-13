"""AirtableStorage coverage for the cross-club Users table: get_user_record()
and save_user_record() only (the rest of AirtableStorage is exercised via the
app's integration tests, not unit-mocked here)."""

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
