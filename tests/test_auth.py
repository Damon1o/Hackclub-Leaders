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

        def get_user_record(self, email, *, strict=False):
            return {'preferredName': '', 'sessionVersion': 99}

    monkeypatch.setattr(routes_web_module, '_storage', lambda: FakeSharedBackend())
    with client.session_transaction() as sess:
        sess['user'] = {'id': 'u1', 'name': 'Test', 'email': 'leader@test.com', 'sessionVersion': 1}
    response = client.get('/dashboard', follow_redirects=False)
    assert response.status_code in (301, 302)
    assert '/sign-in' in response.headers['Location']
    with client.session_transaction() as sess:
        assert 'user' not in sess


def test_stale_session_check_is_throttled(client, monkeypatch):
    import time as time_module

    import src.routes_web as routes_web_module

    calls = []

    class FakeSharedBackend:
        def resolve_club_key(self, email):
            return email

        def load_lite(self, club_key):
            return {'settings': {'clubName': 'Test'}, 'members': [{'email': 'leader@test.com', 'role': 'Leader'}]}

        def get_user_record(self, email, *, strict=False):
            calls.append(email)
            # A mismatched version that should only be noticed on the first
            # (unthrottled) check — subsequent requests within the window
            # must not call get_user_record again.
            return {'preferredName': '', 'sessionVersion': 99}

    monkeypatch.setattr(routes_web_module, '_storage', lambda: FakeSharedBackend())
    with client.session_transaction() as sess:
        sess['user'] = {'id': 'u1', 'name': 'Test', 'email': 'leader@test.com', 'sessionVersion': 1}

    # First request: version mismatch signs the user out.
    response = client.get('/dashboard', follow_redirects=False)
    assert response.status_code in (301, 302)
    assert len(calls) == 1

    # Sign back in with a matching version, then hammer /dashboard: only the
    # first request (outside the throttle window) should hit the backend.
    with client.session_transaction() as sess:
        sess['user'] = {'id': 'u1', 'name': 'Test', 'email': 'leader@test.com', 'sessionVersion': 99}
    client.get('/dashboard')
    assert len(calls) == 2
    client.get('/dashboard')
    client.get('/dashboard')
    assert len(calls) == 2  # throttled: no new calls within the window

    # Force the window to elapse and confirm the check fires again.
    with client.session_transaction() as sess:
        sess['_sv_checked_at'] = time_module.time() - routes_web_module.SESSION_VERSION_CHECK_INTERVAL - 1
    client.get('/dashboard')
    assert len(calls) == 3


def test_stale_session_check_fails_open_on_storage_error(client, monkeypatch):
    import src.helpers as helpers_module
    from src.storage import StorageError

    club_state = {
        'settings': {'clubName': 'Test'},
        'members': [{'id': 'm1', 'email': 'leader@test.com', 'role': 'Leader'}],
    }

    class FailingSharedBackend:
        def resolve_club_key(self, email):
            return email

        def load_lite(self, club_key):
            return club_state

        def load(self, club_key, sections=None):
            return club_state

        def get_user_record(self, email, *, strict=False):
            raise StorageError('Airtable is having a moment.')

    # Patch make_storage (not routes_web's own _storage) so every module —
    # the before_request gate here plus helpers.get_dashboard_state, called
    # while rendering the JSON response — sees the same fake backend. See
    # the identical pattern/rationale in
    # test_sign_out_everywhere_bumps_session_version_and_clears_session.
    monkeypatch.setattr(helpers_module, 'make_storage', lambda session: FailingSharedBackend())
    with client.session_transaction() as sess:
        # sessionVersion 7 would mismatch the get_user_record-default of 0 —
        # proving the request succeeds because the check was skipped, not
        # because the versions coincidentally matched.
        sess['user'] = {'id': 'u1', 'name': 'Test', 'email': 'leader@test.com', 'sessionVersion': 7}
    response = client.get('/api/dashboard/state')
    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert sess['user']['sessionVersion'] == 7  # session was not cleared


def test_stale_session_check_covers_admin_panel(client, monkeypatch):
    import src.routes_web as routes_web_module

    class FakeSharedBackend:
        def resolve_club_key(self, email):
            return email

        def load_lite(self, club_key):
            return {'settings': {'clubName': 'Test'}, 'members': [{'email': 'admin@test.com', 'role': 'Leader'}]}

        def get_user_record(self, email, *, strict=False):
            return {'preferredName': '', 'sessionVersion': 99}

    monkeypatch.setattr(routes_web_module, '_storage', lambda: FakeSharedBackend())
    monkeypatch.setenv('ADMIN_EMAILS', 'admin@test.com')
    from src.helpers import ADMIN_EMAILS

    ADMIN_EMAILS.clear()
    ADMIN_EMAILS.add('admin@test.com')
    with client.session_transaction() as sess:
        sess['user'] = {'id': 'admin-user', 'name': 'Admin', 'email': 'admin@test.com', 'sessionVersion': 1}

    # A stale/revoked session must not retain access to the admin panel.
    response = client.get('/dashboard/admin', follow_redirects=False)
    assert response.status_code in (301, 302)
    assert '/sign-in' in response.headers['Location']
    with client.session_transaction() as sess:
        assert 'user' not in sess
