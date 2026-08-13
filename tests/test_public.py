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


# ── Landing page overhaul ──────────────────────────────────────────────────


def test_index_has_no_fontawesome_cdn(client):
    response = client.get('/')
    assert b'font-awesome' not in response.data


def test_events_has_no_fontawesome_cdn(client):
    response = client.get('/events')
    assert b'font-awesome' not in response.data


def test_footer_attribution_is_not_hackclub_site(client):
    response = client.get('/')
    assert b'hackclub/site' not in response.data
    assert b'Commit 0defb6' not in response.data


def test_index_hero_offers_join_code_path(client):
    response = client.get('/')
    assert b'/dashboard/welcome' in response.data


def test_index_hero_has_dashboard_mockup_not_video_thumb(client):
    response = client.get('/')
    assert b'hero-mockup' in response.data
    assert b'img.youtube.com' not in response.data
    assert b'id="heroVideoPreview"' in response.data
    assert b'id="videoModal"' in response.data


def test_nav_primary_cta_targets_sign_in_when_signed_out(client):
    body = client.get('/').data.decode()
    start = body.index('apply-now-container')
    nav_cta = body[start:body.index('</section>', start)]
    assert '/sign-in' in nav_cta
    assert 'apply.hackclub.com' not in nav_cta


def test_index_has_feature_grid(client):
    body = client.get('/').data
    assert b'id="features"' in body
    assert body.count(b'<article class="feature-card') >= 5
    assert b'feature-pills' in body


def test_index_has_trust_chips(client):
    assert b'trust-chips' in client.get('/').data


def test_index_has_how_it_works_steps(client):
    body = client.get('/').data
    assert b'id="how-it-works"' in body
    assert body.count(b'<li class="step-card') >= 3


def test_index_has_leader_band(client):
    body = client.get('/').data
    assert b'id="leaders"' in body
    assert b'guide.leaders.hackclub.com' in body
    assert b'jams.hackclub.com' in body
    assert b'hackclub.com/slack' in body


def test_index_events_strip_is_dynamic(client):
    body = client.get('/').data
    assert b'events-data.js' in body
    assert b'id="happening-strip"' in body
    assert b'Ends 4 Jul' not in body


def test_events_page_uses_shared_events_data(client):
    assert b'events-data.js' in client.get('/events').data


def test_index_supporters_slimmed_to_trust_band(client):
    body = client.get('/').data
    assert b'Musk Foundation' not in body
    assert b'supporters-pills' not in body


def test_index_sections_use_squiggle_dividers(client):
    body = client.get('/').data
    assert body.count(b'class="squiggle') >= 5, 'expected squiggle dividers between landing sections'
    assert b'supporters-wave' not in body, 'old one-off smooth wave should be replaced by squiggle'


def test_events_data_matches_current_programs(client):
    body = client.get('/static/js/events-data.js').data.decode()
    for program in ('Outpost', 'Off-Track', 'OneKey', 'Calculate', 'Premiere',
                    'Breadboard', 'Doppel', 'Turf Wars', 'ThingOnDesk',
                    'Catgirl', 'Hackachu', 'Anvil', 'Keeb', 'Sunbeam'):
        assert program in body, f'{program} missing from events data'
    for expired in ('Fallout', 'Stasis'):
        assert expired not in body, f'{expired} is past its deadline'


# ── i18n coverage ──────────────────────────────────────────────────────────


def _i18n_translations():
    import pathlib
    import re
    src = pathlib.Path(__file__).parent.parent.joinpath(
        'static', 'js', 'i18n-data.js').read_text(encoding='utf-8')
    blocks = re.split(r'^ {8}(\w+): \{$', src, flags=re.M)
    return {
        lang: set(re.findall(r"^ {12}'([\w.]+)':", body, flags=re.M))
        for lang, body in zip(blocks[1::2], blocks[2::2], strict=False)
    }


def test_i18n_all_languages_cover_public_page_keys(client):
    import re
    langs = _i18n_translations()
    assert len(langs) == 12, f'expected 12 languages, parsed {sorted(langs)}'

    html = (client.get('/').data + client.get('/events').data).decode()
    used = set(re.findall(r'data-i18n="([^"]+)"', html))
    for attrs in re.findall(r'data-i18n-attr="([^"]+)"', html):
        used |= {pair.split(':', 1)[1] for pair in attrs.split(';') if ':' in pair}

    undefined = used - langs['en']
    assert not undefined, f'keys used but not in English dict: {sorted(undefined)}'

    for lang, keys in sorted(langs.items()):
        missing = used - keys
        assert not missing, f'{lang} is missing {len(missing)} keys: {sorted(missing)}'


def test_dashboard_layout_has_coin_balance_chip(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Chip Club', 'coinBalance': 0, 'coinsSpent': 0},
            'members': [],
        }
    response = auth_client.get('/dashboard')
    assert response.status_code == 200
    assert b'id="coinBalanceAmount"' in response.data
    assert b'sidebar-profile-card' in response.data


def test_shop_page_has_cart_subtotal_shell(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Chip Club', 'coinBalance': 0, 'coinsSpent': 0},
            'members': [],
        }
    response = auth_client.get('/dashboard/shop')
    assert response.status_code == 200
    assert b'id="cartSubtotal"' in response.data


def test_dashboard_layout_has_workshops_nav_link(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {'settings': {'clubName': 'Nav Club'}, 'members': []}
    response = auth_client.get('/dashboard')
    assert response.status_code == 200
    assert b'/dashboard/workshops' in response.data
    assert b'id="homeWorkshopTotal"' in response.data


# ── StorageError resilience (no infinite self-redirect loop) ────────────────


def test_storage_error_on_index_degrades_instead_of_looping(auth_client, monkeypatch):
    from src.storage import AirtableStorage, StorageError

    def always_fail(*_args, **_kwargs):
        raise StorageError('simulated outage')

    monkeypatch.setattr(AirtableStorage, 'load', always_fail)
    monkeypatch.setattr(AirtableStorage, 'load_lite', always_fail)
    monkeypatch.setattr(AirtableStorage, 'resolve_club_key', always_fail)

    response = auth_client.get('/', follow_redirects=False)
    assert response.status_code == 200
    with auth_client.session_transaction() as sess:
        assert not sess.get('_flashes')


def test_storage_error_on_dashboard_redirects_once_not_forever(auth_client, monkeypatch):
    from src.storage import AirtableStorage, StorageError

    def always_fail(*_args, **_kwargs):
        raise StorageError('simulated outage')

    monkeypatch.setattr(AirtableStorage, 'load', always_fail)
    monkeypatch.setattr(AirtableStorage, 'load_lite', always_fail)
    monkeypatch.setattr(AirtableStorage, 'resolve_club_key', always_fail)

    first = auth_client.get('/dashboard', follow_redirects=False)
    assert first.status_code in (301, 302)

    second = auth_client.get(first.headers['Location'], follow_redirects=False)
    assert second.status_code == 200


def test_workshops_page_has_expected_shell(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Nav Club'},
            'members': [],
            'workshops': [],
        }
    response = auth_client.get('/dashboard/workshops')
    assert response.status_code == 200
    assert b'id="workshopGrid"' in response.data
    assert b'id="workshopProposeModal"' in response.data
    assert b'id="workshopDetailModal"' in response.data
    assert b'id="workshopScheduleModal"' in response.data


def test_dashboard_notifications_page_loads(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Nav Club'},
            'members': [],
        }
    response = auth_client.get('/dashboard/notifications')
    assert response.status_code == 200


def test_old_newsletters_path_redirects_to_notifications(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Nav Club'},
            'members': [],
        }
    response = auth_client.get('/dashboard/newsletters', follow_redirects=False)
    assert response.status_code == 301
    assert response.headers['Location'].endswith('/dashboard/notifications')
