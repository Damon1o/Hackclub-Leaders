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
    response = client.get('/auth/hackclub/callback?error=access_denied',
                          follow_redirects=False)
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
