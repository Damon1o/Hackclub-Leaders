def test_state_endpoint_requires_login(client):
    response = client.get('/api/dashboard/state')
    assert response.status_code in (301, 302)


def test_state_endpoint_no_club_returns_403(auth_client):
    response = auth_client.get('/api/dashboard/state')
    assert response.status_code == 403


def test_csrf_required_for_mutations(auth_client):
    response = auth_client.post(
        '/api/dashboard/team', json={'name': 'Test', 'email': 'test@test.com', 'role': 'Member'}
    )
    assert response.status_code == 403
    data = response.get_json()
    assert 'error' in data


def test_api_endpoints_require_auth(client):
    api_paths = [
        ('GET', '/api/dashboard/state'),
        ('POST', '/api/dashboard/team'),
        ('POST', '/api/dashboard/events'),
        ('POST', '/api/dashboard/cart'),
        ('POST', '/api/dashboard/projects'),
        ('POST', '/api/dashboard/checkout'),
        ('POST', '/api/dashboard/item-requests'),
        ('POST', '/api/dashboard/newsletters'),
        ('PATCH', '/api/dashboard/settings'),
        ('PATCH', '/api/dashboard/profile'),
        ('PATCH', '/api/dashboard/team/test-id'),
        ('DELETE', '/api/dashboard/team/test-id'),
    ]
    for method, path in api_paths:
        response = client.open(path, method=method, follow_redirects=False)
        assert response.status_code in (301, 302), f'{method} {path} should require login'


def test_hackatime_endpoints_require_auth(client):
    response = client.get('/api/dashboard/hackatime')
    assert response.status_code in (301, 302)
    response = client.get('/api/dashboard/hackatime/projects')
    assert response.status_code in (301, 302)


def test_error_handlers(client):
    with client.application.app_context():
        from src.helpers import StateTooLarge

        with client.application.test_request_context('/api/test'):
            response = client.application.handle_user_exception(StateTooLarge())
            assert response[1] == 413


def test_json_payload_rejects_bad_image(client):
    response = client.post('/api/dashboard/projects/upload-image', data={'not_an_image': 'value'})
    assert response.status_code in (301, 302), (
        f'Expected redirect for unauthenticated upload, got {response.status_code}'
    )


def _save_settings(auth_client, monkeypatch, **overrides):
    # Use the cookie-backed store so the seeded club below is what the API sees.
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrf-token'
        # Seed a club so the membership gate lets settings mutations through.
        sess.setdefault(
            'dashboard_state',
            {
                'settings': {'clubName': 'Test Club', 'location': 'Testville'},
                'members': [],
            },
        )
    payload = {'clubName': 'Test Club', 'location': 'Testville'}
    payload.update(overrides)
    return auth_client.patch(
        '/api/dashboard/settings', json=payload, headers={'X-CSRF-Token': 'test-csrf-token'}
    )


def test_default_state_has_language(auth_client, monkeypatch):
    response = _save_settings(auth_client, monkeypatch)
    assert response.status_code == 200
    assert response.get_json()['state']['settings']['language'] == 'en'


def test_settings_persists_supported_language(auth_client, monkeypatch):
    response = _save_settings(auth_client, monkeypatch, language='ja')
    assert response.status_code == 200
    assert response.get_json()['state']['settings']['language'] == 'ja'


def test_settings_rejects_unsupported_language(auth_client, monkeypatch):
    response = _save_settings(auth_client, monkeypatch, language='klingon')
    assert response.status_code == 200
    # Unsupported codes fall back to English rather than being stored raw.
    assert response.get_json()['state']['settings']['language'] == 'en'
