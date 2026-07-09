def test_index(client):
    response = client.get('/')
    assert response.status_code == 200


def test_events_page(client):
    response = client.get('/events')
    assert response.status_code == 200


def test_sign_in_page(client):
    response = client.get('/sign-in')
    assert response.status_code == 200


def test_sign_in_redirects_if_logged_in(auth_client):
    response = auth_client.get('/sign-in', follow_redirects=False)
    assert response.status_code in (301, 302)


def test_sign_out_clears_session(auth_client):
    with auth_client.session_transaction() as sess:
        assert 'user' in sess
    response = auth_client.get('/sign-out', follow_redirects=False)
    assert response.status_code in (301, 302)
    with auth_client.session_transaction() as sess:
        assert 'user' not in sess


def test_join_code_page(client):
    response = client.get('/join/abc123')
    assert response.status_code == 200


def test_join_code_page_has_code(client):
    response = client.get('/join/TESTCODE')
    assert b'TESTCODE' in response.data


def test_dashboard_redirects_unauthenticated(client):
    response = client.get('/dashboard', follow_redirects=False)
    assert response.status_code in (301, 302)


def test_dashboard_redirects_to_welcome_when_no_club(auth_client):
    response = auth_client.get('/dashboard', follow_redirects=False)
    assert response.status_code in (301, 302)
    assert '/dashboard/welcome' in response.headers.get('Location', '')


def test_welcome_page_shows_for_user_without_club(auth_client):
    response = auth_client.get('/dashboard/welcome')
    assert response.status_code == 200


def test_dashboard_subpages_require_login(client):
    pages = [
        '/dashboard/team',
        '/dashboard/events',
        '/dashboard/ships',
        '/dashboard/projects',
        '/dashboard/levels',
        '/dashboard/tools',
        '/dashboard/shop',
        '/dashboard/newsletters',
        '/dashboard/map',
        '/dashboard/settings',
        '/dashboard/profile',
    ]
    for path in pages:
        response = client.get(path, follow_redirects=False)
        assert response.status_code in (301, 302), f'{path} should require login'


def test_dashboard_subpages_redirect_to_welcome_when_no_club(auth_client):
    pages = [
        '/dashboard/team',
        '/dashboard/events',
        '/dashboard/ships',
        '/dashboard/projects',
        '/dashboard/levels',
        '/dashboard/newsletters',
        '/dashboard/map',
        '/dashboard/tools',
        '/dashboard/shop',
        '/dashboard/settings',
        '/dashboard/profile',
    ]
    for path in pages:
        response = auth_client.get(path, follow_redirects=False)
        assert response.status_code in (301, 302), f'{path} should redirect to welcome'
        assert '/dashboard/welcome' in response.headers.get('Location', '')
