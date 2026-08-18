"""Dashboard Explore: auth-gated routes, filters, pagination, publish gating."""

PUBLIC_PROJECTS = [
    {
        'publicId': 'showcase-web-1',
        'name': 'Club Site Builder',
        'description': 'Drag-and-drop site builder for club pages.',
        'thumbnail': 'https://cdn.example/site.png',
        'demoUrl': 'https://demo.example/site',
        'repoUrl': 'https://github.com/example/site',
        'ownerName': 'Ada',
        'clubName': 'Robot Club',
        'category': 'Web',
        'date': '2026-08-01',
        'clubKey': 'club-1',
    },
    {
        'publicId': 'showcase-game-1',
        'name': 'Pixel Racer',
        'description': 'A tiny 2D racer made in a weekend.',
        'thumbnail': '',
        'demoUrl': '',
        'repoUrl': 'https://github.com/example/racer',
        'ownerName': 'Bo',
        'clubName': 'Game Dev Club',
        'category': 'Game',
        'date': '2026-08-02',
        'clubKey': 'club-2',
    },
    {
        'publicId': 'showcase-hw-1',
        'name': 'Blinky Badge',
        'description': 'LED badge that blinks to music.',
        'thumbnail': 'https://cdn.example/badge.png',
        'demoUrl': 'https://demo.example/badge',
        'repoUrl': '',
        'ownerName': 'Cy',
        'clubName': 'Robot Club',
        'category': 'Hardware',
        'date': '2026-08-03',
        'clubKey': 'club-1',
    },
]


def _fake_shared_backend(monkeypatch, projects):
    import src.helpers as helpers_module

    class FakeBackend:
        def list_public_projects(self, club_key=''):
            return [
                project for project in projects
                if not club_key or project.get('clubKey') == club_key
            ]

        # The membership gate, staleness check, and dashboard context
        # processor hit these on /dashboard paths.
        def resolve_club_key(self, email):
            return 'club-1'

        def load_lite(self, club_key):
            return {'settings': {'clubName': 'Test Club'}, 'members': [
                {'id': 'm1', 'name': 'Test Leader', 'email': 'leader@test.com', 'role': 'Leader'},
            ]}

        def load(self, club_key, sections=None):
            return {
                'settings': {'clubName': 'Test Club', 'chatEnabledForMembers': True},
                'members': [
                    {'id': 'm1', 'name': 'Test Leader', 'email': 'leader@test.com', 'role': 'Leader'},
                ],
            }

        def get_user_record(self, email, *, strict=False):
            return {'sessionVersion': 0}

    monkeypatch.setattr(helpers_module, 'make_storage', lambda session: FakeBackend())


def _seed_session_club(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess.setdefault(
            'dashboard_state',
            {
                'settings': {'clubName': 'Test Club'},
                'members': [
                    {'id': 'm1', 'name': 'Test Leader', 'email': 'leader@test.com', 'role': 'Leader'},
                ],
            },
        )


def test_explore_requires_login(client):
    assert client.get('/dashboard/explore', follow_redirects=False).status_code in (301, 302)
    assert client.get('/dashboard/explore/projects/showcase-web-1', follow_redirects=False).status_code in (301, 302)


def test_explore_redirects_to_welcome_without_club(auth_client):
    response = auth_client.get('/dashboard/explore', follow_redirects=False)
    assert response.status_code in (301, 302)
    assert '/dashboard/welcome' in response.headers.get('Location', '')


def test_explore_unavailable_in_session_mode(auth_client, monkeypatch):
    _seed_session_club(auth_client, monkeypatch)
    response = auth_client.get('/dashboard/explore')
    assert response.status_code == 503
    assert b'explore-unavailable' in response.data
    assert b'Explore is offline' in response.data


def test_explore_project_unavailable_in_session_mode(auth_client, monkeypatch):
    _seed_session_club(auth_client, monkeypatch)
    response = auth_client.get('/dashboard/explore/projects/showcase-web-1')
    assert response.status_code == 503


def test_explore_renders_public_projects(auth_client, monkeypatch):
    _fake_shared_backend(monkeypatch, PUBLIC_PROJECTS)
    response = auth_client.get('/dashboard/explore')
    assert response.status_code == 200
    body = response.data.decode()
    assert 'Club Site Builder' in body
    assert 'Pixel Racer' in body
    assert body.count('class="explore-card"') == 3


def test_explore_search_filters(auth_client, monkeypatch):
    _fake_shared_backend(monkeypatch, PUBLIC_PROJECTS)
    response = auth_client.get('/dashboard/explore?q=robot')
    body = response.data.decode()
    assert 'Club Site Builder' in body
    assert 'Blinky Badge' in body
    assert 'Pixel Racer' not in body


def test_explore_category_filter(auth_client, monkeypatch):
    _fake_shared_backend(monkeypatch, PUBLIC_PROJECTS)
    response = auth_client.get('/dashboard/explore?category=Game')
    body = response.data.decode()
    assert 'Pixel Racer' in body
    assert 'Club Site Builder' not in body


def test_explore_invalid_category_is_ignored(auth_client, monkeypatch):
    _fake_shared_backend(monkeypatch, PUBLIC_PROJECTS)
    response = auth_client.get('/dashboard/explore?category=NotAThing')
    body = response.data.decode()
    assert 'Club Site Builder' in body
    assert 'Pixel Racer' in body


def test_explore_your_club_filter(auth_client, monkeypatch):
    _fake_shared_backend(monkeypatch, PUBLIC_PROJECTS)
    response = auth_client.get('/dashboard/explore?club=1')
    assert response.status_code == 200
    body = response.data.decode()
    # The viewer resolves to club-1, so only its two projects appear.
    assert 'Club Site Builder' in body
    assert 'Blinky Badge' in body
    assert 'Pixel Racer' not in body


def test_explore_your_club_filter_combines_with_category(auth_client, monkeypatch):
    _fake_shared_backend(monkeypatch, PUBLIC_PROJECTS)
    response = auth_client.get('/dashboard/explore?club=1&category=Web')
    body = response.data.decode()
    assert 'Club Site Builder' in body
    assert 'Blinky Badge' not in body
    assert 'Pixel Racer' not in body
    # The active filter set must be preserved in the category chip links.
    assert 'club=1' in body


def test_explore_pagination(auth_client, monkeypatch):
    projects = [
        {**PUBLIC_PROJECTS[0], 'publicId': f'showcase-{i}', 'name': f'Project {i}', 'date': f'2026-07-{i + 1:02d}'}
        for i in range(25)
    ]
    _fake_shared_backend(monkeypatch, projects)
    response = auth_client.get('/dashboard/explore')
    assert response.status_code == 200
    assert response.data.count(b'class="explore-card"') == 12
    assert b'1 / 3' in response.data

    last_page = auth_client.get('/dashboard/explore?page=3')
    assert last_page.status_code == 200
    assert last_page.data.count(b'class="explore-card"') == 1
    assert b'3 / 3' in last_page.data

    clamped = auth_client.get('/dashboard/explore?page=999')
    assert clamped.status_code == 200
    assert b'3 / 3' in clamped.data


def test_explore_empty_state(auth_client, monkeypatch):
    _fake_shared_backend(monkeypatch, PUBLIC_PROJECTS)
    response = auth_client.get('/dashboard/explore?q=zzzzz')
    assert response.status_code == 200
    assert b'explore-empty' in response.data


def test_explore_project_detail(auth_client, monkeypatch):
    _fake_shared_backend(monkeypatch, PUBLIC_PROJECTS)
    response = auth_client.get('/dashboard/explore/projects/showcase-web-1')
    assert response.status_code == 200
    body = response.data.decode()
    assert 'Club Site Builder' in body
    assert 'https://demo.example/site' in body
    assert 'https://github.com/example/site' in body


def test_explore_project_missing_is_404(auth_client, monkeypatch):
    _fake_shared_backend(monkeypatch, PUBLIC_PROJECTS)
    response = auth_client.get('/dashboard/explore/projects/does-not-exist')
    assert response.status_code == 404


def test_sitemap_excludes_private_explore(client):
    response = client.get('/sitemap.xml')
    assert response.status_code == 200
    assert b'/explore' not in response.data


# ── Publish gating ──────────────────────────────────────────────────────────


def _seed_project(auth_client, monkeypatch, **overrides):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    project = {
        'id': 'proj-1',
        'name': 'My Ship',
        'description': '',
        'repoUrl': 'https://github.com/x/y',
        'demoUrl': 'https://demo.x.y',
        'thumbnail': '',
        'hackatimeProject': 'x',
        'status': 'Shipped',
        'ownerEmail': 'leader@test.com',
        'ownerName': 'Test Leader',
        'date': '2026-08-01',
        'publicId': 'showcase-seed-1',
        'isPublic': False,
        'category': '',
    }
    project.update(overrides)
    with auth_client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrf-token'
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Test Club'},
            'members': [
                {'id': 'm1', 'name': 'Test Leader', 'email': 'leader@test.com', 'role': 'Leader'},
            ],
            'projects': [project],
        }


def _patch_project(auth_client, payload):
    return auth_client.patch(
        '/api/dashboard/projects/proj-1',
        json=payload,
        headers={'X-CSRF-Token': 'test-csrf-token'},
    )


def test_publish_requires_shipped(auth_client, monkeypatch):
    _seed_project(auth_client, monkeypatch, status='Draft')
    response = _patch_project(auth_client, {'isPublic': True})
    assert response.status_code == 400
    assert 'shipped' in response.get_json()['error'].lower()


def test_publish_requires_category(auth_client, monkeypatch):
    _seed_project(auth_client, monkeypatch)
    response = _patch_project(auth_client, {'isPublic': True})
    assert response.status_code == 400
    assert 'category' in response.get_json()['error'].lower()


def test_publish_succeeds_for_shipped_with_category(auth_client, monkeypatch):
    _seed_project(auth_client, monkeypatch)
    response = _patch_project(auth_client, {'isPublic': True, 'category': 'Web'})
    assert response.status_code == 200
    assert response.get_json()['project']['isPublic'] is True
    assert response.get_json()['project']['category'] == 'Web'


def test_unpublish_always_allowed(auth_client, monkeypatch):
    _seed_project(auth_client, monkeypatch, isPublic=True, category='Web')
    response = _patch_project(auth_client, {'isPublic': False})
    assert response.status_code == 200
    assert response.get_json()['project']['isPublic'] is False


def test_invalid_category_rejected(auth_client, monkeypatch):
    _seed_project(auth_client, monkeypatch)
    response = _patch_project(auth_client, {'category': 'Bogus'})
    assert response.status_code == 400


def test_new_project_gets_public_id_and_defaults(auth_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with auth_client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrf-token'
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Test Club'},
            'members': [
                {'id': 'm1', 'name': 'Test Leader', 'email': 'leader@test.com', 'role': 'Leader'},
            ],
        }
    response = auth_client.post(
        '/api/dashboard/projects',
        json={'name': 'Fresh project', 'description': ''},
        headers={'X-CSRF-Token': 'test-csrf-token'},
    )
    assert response.status_code == 200
    project = response.get_json()['project']
    assert project['publicId'].startswith('showcase-')
    assert project['isPublic'] is False
    assert project['category'] == ''
