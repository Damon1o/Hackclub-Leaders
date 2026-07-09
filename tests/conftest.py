import pytest

from app import app


@pytest.fixture(autouse=True)
def _test_config():
    app.config['TESTING'] = True
    app.config['SERVER_NAME'] = 'localhost'
    app.config['SESSION_COOKIE_SECURE'] = False
    app.config['PREFERRED_URL_SCHEME'] = 'http'


@pytest.fixture
def client():
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_client(client):
    with client.session_transaction() as sess:
        sess['user'] = {
            'id': 'test-user-1',
            'name': 'Test Leader',
            'email': 'leader@test.com',
            'avatar': '',
            'provider': 'hackclub',
        }
    return client


@pytest.fixture
def admin_client(client, monkeypatch):
    monkeypatch.setenv('ADMIN_EMAILS', 'admin@test.com')
    from src.helpers import ADMIN_EMAILS
    ADMIN_EMAILS.clear()
    ADMIN_EMAILS.add('admin@test.com')
    with client.session_transaction() as sess:
        sess['user'] = {
            'id': 'admin-user',
            'name': 'Admin',
            'email': 'admin@test.com',
            'provider': 'hackclub',
        }
    return client
