import json

import pytest

from src import helpers


@pytest.fixture
def shop_file(tmp_path, monkeypatch):
    """Point the shop writer at a throwaway catalog so tests never touch the
    real static/data/shop.json."""
    path = tmp_path / 'shop.json'
    path.write_text(
        json.dumps(
            [
                {
                    'name': 'Sticker Pack',
                    'cost': 'Free',
                    'hours': 'Free',
                    'image-src': '/static/images/shop/sticker-pack.png',
                    'filter': 'Swag',
                },
            ]
        ),
        encoding='utf-8',
    )
    monkeypatch.setattr(helpers, 'SHOP_JSON_PATH', str(path))
    return path


def _read(path):
    return json.loads(path.read_text(encoding='utf-8'))


# ── Shop writer (helpers) ────────────────────────────────────────────────────


def test_add_shop_item_appends_and_prices(shop_file):
    item = helpers.add_shop_item('Arduino Kit', '25', 'https://img/a.png', 'Hardware')
    raw = _read(shop_file)
    assert len(raw) == 2
    added = raw[-1]
    assert added['name'] == 'Arduino Kit'
    assert added['cost'] == '$25.00'
    assert added['hours'] == '$37.50'  # 1.5x the dollar cost
    assert added['filter'] == 'Hardware'
    assert item['id'] == 'arduino-kit'


def test_add_shop_item_defaults_tbd_and_swag(shop_file):
    item = helpers.add_shop_item('Mystery Box', '', '', 'Nonsense')
    assert item['cost'] == 'TBD'
    assert item['filter'] == 'Swag'  # unknown category falls back to Swag


def test_add_shop_item_rejects_blank_name(shop_file):
    with pytest.raises(ValueError):
        helpers.add_shop_item('   ', '5', '', 'Swag')


def test_add_shop_item_rejects_duplicate(shop_file):
    with pytest.raises(ValueError):
        helpers.add_shop_item('Sticker Pack', '5', '', 'Swag')


def test_remove_shop_item(shop_file):
    assert helpers.remove_shop_item('sticker-pack') is True
    assert _read(shop_file) == []
    assert helpers.remove_shop_item('sticker-pack') is False


# ── Admin API routes ─────────────────────────────────────────────────────────


def _seed(admin_client, requests=None):
    with admin_client.session_transaction() as sess:
        sess['csrf_token'] = 'tok'
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Admin Club', 'location': ''},
            'members': [],
            'itemRequests': requests if requests is not None else [],
        }


HEADERS = {'X-CSRF-Token': 'tok'}


def test_item_requests_requires_admin(auth_client):
    assert auth_client.get('/api/admin/item-requests').status_code == 403


def test_item_requests_lists_all(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed(
        admin_client,
        [
            {
                'id': 'r1',
                'name': 'Whiteboard',
                'note': 'big',
                'date': '2026-07-01',
                'status': 'Submitted',
            }
        ],
    )
    response = admin_client.get('/api/admin/item-requests')
    assert response.status_code == 200
    data = response.get_json()['itemRequests']
    assert data[0]['request']['name'] == 'Whiteboard'
    assert data[0]['clubName'] == 'Admin Club'


def test_approve_item_request_adds_to_shop(admin_client, monkeypatch, shop_file):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed(
        admin_client,
        [
            {
                'id': 'r1',
                'name': 'Whiteboard',
                'note': '',
                'date': '2026-07-01',
                'status': 'Submitted',
            }
        ],
    )
    response = admin_client.patch(
        '/api/admin/item-requests/admin@test.com/r1', json={'status': 'approved'}, headers=HEADERS
    )
    assert response.status_code == 200
    assert response.get_json()['request']['status'] == 'Approved'
    names = [entry['name'] for entry in _read(shop_file)]
    assert 'Whiteboard' in names


def test_reject_item_request_removes_it(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed(
        admin_client,
        [
            {
                'id': 'r1',
                'name': 'Whiteboard',
                'note': '',
                'date': '2026-07-01',
                'status': 'Submitted',
            }
        ],
    )
    response = admin_client.patch(
        '/api/admin/item-requests/admin@test.com/r1', json={'status': 'rejected'}, headers=HEADERS
    )
    assert response.status_code == 200
    with admin_client.session_transaction() as sess:
        assert sess['dashboard_state']['itemRequests'] == []


def test_add_shop_item_route(admin_client, monkeypatch, shop_file):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed(admin_client)
    response = admin_client.post(
        '/api/admin/shop-items',
        headers=HEADERS,
        json={'name': 'USB Drive', 'cost': '10', 'filter': 'Hardware', 'image': ''},
    )
    assert response.status_code == 200
    assert response.get_json()['shopItem']['cost'] == '$10.00'


def test_add_shop_item_route_rejects_bad_image(admin_client, monkeypatch, shop_file):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed(admin_client)
    response = admin_client.post(
        '/api/admin/shop-items',
        headers=HEADERS,
        json={'name': 'X', 'cost': '1', 'filter': 'Swag', 'image': 'javascript:alert(1)'},
    )
    assert response.status_code == 400


def test_delete_shop_item_route(admin_client, monkeypatch, shop_file):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed(admin_client)
    assert (
        admin_client.delete('/api/admin/shop-items/sticker-pack', headers=HEADERS).status_code
        == 200
    )
    assert (
        admin_client.delete('/api/admin/shop-items/sticker-pack', headers=HEADERS).status_code
        == 404
    )
