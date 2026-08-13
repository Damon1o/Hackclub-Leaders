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
    payload = {'clubName': 'Test Club', 'venue': 'Test Venue', 'location': 'Testville'}
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


def _save_settings_v2(auth_client, monkeypatch, **overrides):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrf-token'
        sess.setdefault(
            'dashboard_state',
            {'settings': {'clubName': 'Test Club', 'location': 'Testville'}, 'members': []},
        )
    payload = {
        'clubName': 'Test Club',
        'venue': 'Lincoln High School',
        'website': '',
        'avatar': '',
        'meetingDay': 'Wednesday',
        'addressLine1': '100 Main St',
        'addressLine2': '',
        'city': 'Burlington',
        'state': 'VT',
        'zip': '05401',
        'country': 'US',
        'clubBio': 'We build cool stuff.',
    }
    payload.update(overrides)
    return auth_client.patch(
        '/api/dashboard/settings', json=payload, headers={'X-CSRF-Token': 'test-csrf-token'}
    )


def test_settings_saves_structured_address_fields(auth_client, monkeypatch):
    response = _save_settings_v2(auth_client, monkeypatch)
    assert response.status_code == 200
    settings = response.get_json()['state']['settings']
    assert settings['venue'] == 'Lincoln High School'
    assert settings['meetingDay'] == 'Wednesday'
    assert settings['addressLine1'] == '100 Main St'
    assert settings['city'] == 'Burlington'
    assert settings['state'] == 'VT'
    assert settings['zip'] == '05401'
    assert settings['country'] == 'US'
    assert settings['clubBio'] == 'We build cool stuff.'


def test_settings_derives_location_from_city_state(auth_client, monkeypatch):
    response = _save_settings_v2(auth_client, monkeypatch, city='Burlington', state='VT')
    assert response.status_code == 200
    assert response.get_json()['state']['settings']['location'] == 'Burlington, VT'


def test_settings_derives_location_with_only_city(auth_client, monkeypatch):
    response = _save_settings_v2(auth_client, monkeypatch, city='Burlington', state='')
    assert response.status_code == 200
    assert response.get_json()['state']['settings']['location'] == 'Burlington'


def test_settings_derives_empty_location_when_no_address(auth_client, monkeypatch):
    response = _save_settings_v2(auth_client, monkeypatch, city='', state='')
    assert response.status_code == 200
    assert response.get_json()['state']['settings']['location'] == ''


def test_settings_page_renders_all_section_anchors(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Test Club', 'venue': 'Test Venue'},
            'members': [{'id': 'm1', 'name': 'Test Leader', 'email': 'leader@test.com', 'role': 'Leader', 'avatar': '', 'status': 'Active'}],
        }
    response = auth_client.get('/dashboard/settings')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    for anchor_id in (
        'club-profile', 'members', 'your-account', 'appearance',
        'explore-privacy', 'notifications', 'danger-zone',
    ):
        assert f'id="{anchor_id}"' in body
        assert f'href="#{anchor_id}"' in body


def test_club_profile_section_renders_new_fields(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {
            'settings': {
                'clubName': 'Test Club', 'venue': 'Test High', 'meetingDay': 'Wednesday',
                'addressLine1': '1 Main St', 'addressLine2': '', 'city': 'Burlington',
                'state': 'VT', 'zip': '05401', 'country': 'US', 'clubBio': 'We build stuff.',
                'website': '', 'avatar': '',
            },
            'members': [{'id': 'm1', 'name': 'Test Leader', 'email': 'leader@test.com', 'role': 'Leader', 'avatar': '', 'status': 'Active'}],
        }
    response = auth_client.get('/dashboard/settings')
    body = response.get_data(as_text=True)
    for field_name in ('venue', 'meetingDay', 'addressLine1', 'addressLine2', 'city', 'state', 'zip', 'country', 'clubBio'):
        assert f'name="{field_name}"' in body
    assert 'value="Test High"' in body
    assert 'We build stuff.' in body


def test_members_section_renders_join_link_card_and_stub(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Test Club', 'venue': 'Test High'},
            'members': [{'id': 'm1', 'name': 'Test Leader', 'email': 'leader@test.com', 'role': 'Leader', 'avatar': '', 'status': 'Active'}],
        }
    response = auth_client.get('/dashboard/settings')
    body = response.get_data(as_text=True)
    assert 'id="joinLinkCode"' in body
    assert 'id="copyJoinLink"' in body
    assert 'id="refreshJoinLink"' in body
    assert 'Not available yet' in body


def test_appearance_privacy_notifications_sections_render_toggles(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {
            'settings': {
                'clubName': 'Test Club', 'venue': 'Test High',
                'darkModeDefault': True, 'publicDirectory': False,
                'emailNotifications': True, 'newsletterSubscribed': False,
            },
            'members': [{'id': 'm1', 'name': 'Test Leader', 'email': 'leader@test.com', 'role': 'Leader', 'avatar': '', 'status': 'Active'}],
        }
    response = auth_client.get('/dashboard/settings')
    body = response.get_data(as_text=True)
    assert 'name="darkModeDefault"' in body and 'form="settingsForm"' in body
    assert 'name="publicDirectory"' in body
    assert 'name="emailNotifications"' in body
    assert 'name="newsletterSubscribed"' in body


def test_preferred_name_round_trips_on_session_backend(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrf-token'
        sess['dashboard_state'] = {'settings': {'clubName': 'Test Club'}, 'members': []}
    response = auth_client.patch(
        '/api/dashboard/account/preferred-name',
        json={'preferredName': 'Ada'},
        headers={'X-CSRF-Token': 'test-csrf-token'},
    )
    assert response.status_code == 200
    assert response.get_json()['preferredName'] == 'Ada'
    with auth_client.session_transaction() as sess:
        assert sess['user']['preferredName'] == 'Ada'


def test_preferred_name_rejects_blank(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrf-token'
        sess['dashboard_state'] = {'settings': {'clubName': 'Test Club'}, 'members': []}
    response = auth_client.patch(
        '/api/dashboard/account/preferred-name',
        json={'preferredName': '  '},
        headers={'X-CSRF-Token': 'test-csrf-token'},
    )
    assert response.status_code == 400


def test_your_account_section_renders_stub_rows(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Test Club', 'venue': 'Test High'},
            'members': [{'id': 'm1', 'name': 'Test Leader', 'email': 'leader@test.com', 'role': 'Leader', 'avatar': '', 'status': 'Active'}],
        }
    response = auth_client.get('/dashboard/settings')
    body = response.get_data(as_text=True)
    assert 'name="preferredName"' in body
    for label in ('Full name', 'Slack', 'Verification', 'Phone', 'Birthday', 'Mailing address'):
        assert label in body
    assert 'Not available yet' in body


def test_sign_out_everywhere_requires_shared_backend(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrf-token'
        sess['dashboard_state'] = {'settings': {'clubName': 'Test Club'}, 'members': []}
    response = auth_client.post(
        '/api/dashboard/account/sign-out-everywhere',
        headers={'X-CSRF-Token': 'test-csrf-token'},
    )
    assert response.status_code == 400
    assert 'demo mode' in response.get_json()['error'].lower()


def test_sign_out_everywhere_bumps_session_version_and_clears_session(auth_client, monkeypatch):
    import src.helpers as helpers_module

    class FakeSharedBackend:
        def __init__(self):
            self.saved = None

        def get_user_record(self, email, *, strict=False):
            return {'preferredName': '', 'sessionVersion': 3}

        def save_user_record(self, email, fields):
            self.saved = (email, fields)

        def resolve_club_key(self, email):
            return 'club-1'

        def load_lite(self, club_key):
            return {'settings': {'clubName': 'Test Club'}, 'members': [
                {'id': 'm1', 'name': 'Test Leader', 'email': 'leader@test.com', 'role': 'Leader'},
            ]}

    fake_backend = FakeSharedBackend()
    # helpers._storage() always resolves the backend via helpers.make_storage
    # (cached per-request on flask.g), and every module — routes_club's
    # endpoint under test, plus routes_web's before_request club-membership/
    # staleness gate from Task 8, plus viewer_club_lite/_club_key — calls the
    # *same* underlying _storage function object, which closes over helpers'
    # own module-global `make_storage`. Patching make_storage here (rather
    # than each module's separately-imported `_storage` name) is what makes
    # every one of those call sites see the same fake backend within the
    # request, instead of the real Airtable backend .env configures.
    monkeypatch.setattr(helpers_module, 'make_storage', lambda session: fake_backend)
    with auth_client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrf-token'
        sess['user']['sessionVersion'] = 3

    response = auth_client.post(
        '/api/dashboard/account/sign-out-everywhere',
        headers={'X-CSRF-Token': 'test-csrf-token'},
    )
    assert response.status_code == 200
    assert response.get_json()['signedOut'] is True
    assert fake_backend.saved == ('leader@test.com', {'sessionVersion': 4})
    with auth_client.session_transaction() as sess:
        assert 'user' not in sess


def test_preferred_name_update_surfaces_storage_error(auth_client, monkeypatch):
    import src.helpers as helpers_module
    from src.storage import StorageError

    class BrokenSharedBackend:
        def resolve_club_key(self, email):
            return email

        def load_lite(self, club_key):
            return {'settings': {'clubName': 'Test'}, 'members': [
                {'id': 'm1', 'email': 'leader@test.com', 'role': 'Leader'},
            ]}

        def get_user_record(self, email, *, strict=False):
            return {'preferredName': '', 'sessionVersion': 0}

        def save_user_record(self, email, fields):
            raise StorageError(
                'This club uses Airtable but has no Users table yet. '
                'Ask your Airtable base owner to add a Users table first.'
            )

    # Same rationale as the sign-out-everywhere test above: patch
    # make_storage so every _storage() call site (this route plus the
    # before_request membership/staleness gate) shares the fake backend.
    monkeypatch.setattr(helpers_module, 'make_storage', lambda session: BrokenSharedBackend())
    with auth_client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrf-token'
        sess['user']['sessionVersion'] = 0

    response = auth_client.patch(
        '/api/dashboard/account/preferred-name',
        json={'preferredName': 'Ada'},
        headers={'X-CSRF-Token': 'test-csrf-token'},
    )
    assert response.status_code == 400
    assert 'Users table' in response.get_json()['error']


def test_sign_out_everywhere_surfaces_storage_error(auth_client, monkeypatch):
    import src.helpers as helpers_module
    from src.storage import StorageError

    class BrokenSharedBackend:
        def resolve_club_key(self, email):
            return email

        def load_lite(self, club_key):
            return {'settings': {'clubName': 'Test'}, 'members': [
                {'id': 'm1', 'email': 'leader@test.com', 'role': 'Leader'},
            ]}

        def get_user_record(self, email, *, strict=False):
            return {'preferredName': '', 'sessionVersion': 0}

        def save_user_record(self, email, fields):
            raise StorageError('This club uses Airtable but has no Users table yet.')

    monkeypatch.setattr(helpers_module, 'make_storage', lambda session: BrokenSharedBackend())
    with auth_client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrf-token'
        sess['user']['sessionVersion'] = 0

    response = auth_client.post(
        '/api/dashboard/account/sign-out-everywhere',
        headers={'X-CSRF-Token': 'test-csrf-token'},
    )
    assert response.status_code == 400
    assert 'error' in response.get_json()
    # The session must survive an availability failure — clearing it on a
    # storage error would sign the user out without ever bumping the
    # version, which is not what "sign out everywhere" failing should do.
    with auth_client.session_transaction() as sess:
        assert 'user' in sess


def test_admin_club_update_partial_payload_preserves_address_fields(admin_client, monkeypatch):
    # The admin form (admin_club.html) only submits clubName/website/avatar —
    # it has no address/venue/bio inputs. A partial payload like that must
    # not blank out the structured address fields a leader already saved
    # via the settings page (Critical finding #1).
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with admin_client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrf-token'
        sess['dashboard_state'] = {
            'settings': {
                'clubName': 'Test Club',
                'website': 'https://old.example.com',
                'avatar': '',
                'venue': 'Lincoln High School',
                'meetingDay': 'Wednesday',
                'addressLine1': '100 Main St',
                'addressLine2': '',
                'city': 'Burlington',
                'state': 'VT',
                'zip': '05401',
                'country': 'US',
                'clubBio': 'We build cool stuff.',
                'location': 'Burlington, VT',
            },
            'members': [],
        }
    response = admin_client.patch(
        '/api/admin/clubs/test-club',
        json={'clubName': 'Renamed Club', 'website': 'https://new.example.com', 'avatar': ''},
        headers={'X-CSRF-Token': 'test-csrf-token'},
    )
    assert response.status_code == 200
    settings = response.get_json()['club']['settings']
    assert settings['clubName'] == 'Renamed Club'
    assert settings['website'] == 'https://new.example.com'
    # None of the address/venue/bio fields were in the payload, so they
    # must survive untouched rather than being blanked.
    assert settings['venue'] == 'Lincoln High School'
    assert settings['meetingDay'] == 'Wednesday'
    assert settings['addressLine1'] == '100 Main St'
    assert settings['city'] == 'Burlington'
    assert settings['state'] == 'VT'
    assert settings['zip'] == '05401'
    assert settings['country'] == 'US'
    assert settings['clubBio'] == 'We build cool stuff.'
    assert settings['location'] == 'Burlington, VT'
