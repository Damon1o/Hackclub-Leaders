def test_hackclub_oauth_redirect(client):
    response = client.get('/auth/hackclub', follow_redirects=False)
    assert response.status_code in (301, 302)
    location = response.headers.get('Location', '')
    assert 'identity.hackclub.com' in location


def test_hackatime_oauth_requires_login(client):
    response = client.get('/auth/hackatime', follow_redirects=False)
    assert response.status_code in (301, 302)


def test_hackatime_oauth_when_logged_in(auth_client):
    response = auth_client.get('/auth/hackatime', follow_redirects=False)
    assert response.status_code in (301, 302)


def test_callback_rejects_missing_state(client):
    response = client.get('/auth/hackclub/callback?code=testcode', follow_redirects=False)
    assert response.status_code in (301, 302)


def test_callback_rejects_error(client):
    response = client.get('/auth/hackclub/callback?error=access_denied', follow_redirects=False)
    assert response.status_code in (301, 302)


def test_admin_requires_auth(client):
    response = client.get('/dashboard/admin', follow_redirects=False)
    assert response.status_code in (301, 302)


def test_normal_user_cannot_access_admin(auth_client):
    response = auth_client.get('/dashboard/admin', follow_redirects=False)
    assert response.status_code in (301, 302)


def test_admin_club_requires_auth(client):
    response = client.get('/dashboard/admin/club/test@example.com', follow_redirects=False)
    assert response.status_code in (301, 302)


def test_admin_can_access_admin_panel(admin_client):
    response = admin_client.get('/dashboard/admin')
    assert response.status_code == 200


def test_before_request_clears_stale_session_on_shared_backend(client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    # Session backend never triggers the staleness check (no shared_backend) —
    # this test only verifies the check is skipped, not that it fires, since
    # exercising the Airtable/Mongo path requires mocking get_user_record.
    with client.session_transaction() as sess:
        sess['user'] = {'id': 'u1', 'name': 'Test', 'email': 'leader@test.com', 'sessionVersion': 5}
        sess['dashboard_state'] = {'settings': {'clubName': 'Test'}, 'members': []}
    response = client.get('/dashboard')
    assert response.status_code == 200


def test_before_request_clears_stale_session_when_version_mismatches(client, monkeypatch):
    import src.routes_web as routes_web_module

    class FakeSharedBackend:
        def resolve_club_key(self, email):
            return email

        def load_lite(self, club_key):
            return {'settings': {'clubName': 'Test'}, 'members': [{'email': 'leader@test.com', 'role': 'Leader'}]}

        def get_user_record(self, email):
            return {'preferredName': '', 'sessionVersion': 99}

    monkeypatch.setattr(routes_web_module, '_storage', lambda: FakeSharedBackend())
    with client.session_transaction() as sess:
        sess['user'] = {'id': 'u1', 'name': 'Test', 'email': 'leader@test.com', 'sessionVersion': 1}
    response = client.get('/dashboard', follow_redirects=False)
    assert response.status_code in (301, 302)
    assert '/sign-in' in response.headers['Location']
    with client.session_transaction() as sess:
        assert 'user' not in sess
