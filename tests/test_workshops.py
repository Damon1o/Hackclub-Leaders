from src.helpers import workshop_from_payload


def test_workshop_from_payload_valid():
    data, error = workshop_from_payload(
        {'title': 'Intro to Git', 'description': 'Version control basics.'}
    )
    assert error is None
    assert data == {'title': 'Intro to Git', 'description': 'Version control basics.'}


def test_workshop_from_payload_missing_title():
    data, error = workshop_from_payload({'title': '', 'description': 'Version control basics.'})
    assert data is None
    assert error == 'Workshop title is required.'


def test_workshop_from_payload_missing_description():
    data, error = workshop_from_payload({'title': 'Intro to Git', 'description': ''})
    assert data is None
    assert error == 'Workshop description is required.'


def test_workshop_from_payload_strips_whitespace():
    data, error = workshop_from_payload({'title': '  Intro to Git  ', 'description': '  Basics.  '})
    assert error is None
    assert data['title'] == 'Intro to Git'
    assert data['description'] == 'Basics.'


def test_workshops_is_registered_everywhere():
    from src.helpers import STATE_SECTIONS
    from src.storage import AirtableStorage
    from src.storage_mongo import CHILD_COLLECTIONS, INDEXES

    assert 'workshops' in STATE_SECTIONS
    airtable_keys = {state_key for _s, _d, state_key, _f in AirtableStorage.CHILD_TABLES}
    assert 'workshops' in airtable_keys
    assert 'workshops' in CHILD_COLLECTIONS
    assert 'workshops' in INDEXES
    assert 'workshops' in AirtableStorage.OPTIONAL_CHILD_KEYS


def test_default_dashboard_state_seeds_empty_workshops(client):
    with client.session_transaction() as sess:
        sess['user'] = {'name': 'Test Leader', 'email': 'leader@test.com'}
    with client.application.test_request_context():
        from flask import session as flask_session

        flask_session['user'] = {'name': 'Test Leader', 'email': 'leader@test.com'}
        from src.helpers import default_dashboard_state

        state = default_dashboard_state()
        assert state['workshops'] == []


def test_dashboard_workshops_page_section_loads_workshops():
    from src.helpers import PAGE_SECTIONS

    assert PAGE_SECTIONS['dashboard_workshops'] == ('workshops',)
    assert 'workshops' in PAGE_SECTIONS['dashboard']


def _seed_workshop_club(client, monkeypatch, workshops=None, members=None):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    with client.session_transaction() as sess:
        sess['csrf_token'] = 'tok'
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Workshop Club'},
            'members': members if members is not None else [],
            'events': [],
            'workshops': workshops or [],
        }


HEADERS = {'X-CSRF-Token': 'tok'}


def test_propose_workshop_creates_proposed_entry(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client,
        monkeypatch,
        members=[
            {
                'id': 'm1',
                'name': 'Test Leader',
                'email': 'leader@test.com',
                'role': 'Member',
                'avatar': '',
                'status': 'Active',
            }
        ],
    )
    response = auth_client.post(
        '/api/dashboard/workshops',
        headers=HEADERS,
        json={'title': 'Intro to Git', 'description': 'Version control basics.'},
    )
    assert response.status_code == 200
    workshop = response.get_json()['workshop']
    assert workshop['title'] == 'Intro to Git'
    assert workshop['status'] == 'Proposed'
    assert workshop['proposerEmail'] == 'leader@test.com'
    assert workshop['applicants'] == []
    assert workshop['runnerEmail'] == ''
    assert workshop['eventId'] == ''
    assert workshop['id']
    assert workshop['createdAt']


def test_propose_workshop_requires_title(auth_client, monkeypatch):
    _seed_workshop_club(auth_client, monkeypatch)
    response = auth_client.post(
        '/api/dashboard/workshops',
        headers=HEADERS,
        json={'title': '', 'description': 'Version control basics.'},
    )
    assert response.status_code == 400


def _base_workshop(**overrides):
    workshop = {
        'id': 'w1',
        'title': 'Intro to Git',
        'description': 'Basics.',
        'status': 'Proposed',
        'proposerEmail': 'other@test.com',
        'proposerName': 'Other',
        'applicants': [],
        'runnerEmail': '',
        'runnerName': '',
        'eventId': '',
        'createdAt': '2026-08-09T00:00:00Z',
    }
    workshop.update(overrides)
    return workshop


def test_apply_to_workshop_adds_viewer_to_applicants(auth_client, monkeypatch):
    _seed_workshop_club(auth_client, monkeypatch, workshops=[_base_workshop()])
    response = auth_client.patch(
        '/api/dashboard/workshops/w1', headers=HEADERS, json={'applying': True}
    )
    assert response.status_code == 200
    assert 'leader@test.com' in response.get_json()['workshop']['applicants']


def test_withdraw_from_workshop_removes_viewer(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client, monkeypatch, workshops=[_base_workshop(applicants=['leader@test.com'])]
    )
    response = auth_client.patch(
        '/api/dashboard/workshops/w1', headers=HEADERS, json={'applying': False}
    )
    assert response.status_code == 200
    assert response.get_json()['workshop']['applicants'] == []


def test_apply_rejected_once_workshop_is_scheduled(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client,
        monkeypatch,
        workshops=[
            _base_workshop(
                status='Scheduled', runnerEmail='runner@test.com', runnerName='Runner', eventId='e1'
            )
        ],
    )
    response = auth_client.patch(
        '/api/dashboard/workshops/w1', headers=HEADERS, json={'applying': True}
    )
    assert response.status_code == 400


def test_apply_does_not_require_leader_role(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client,
        monkeypatch,
        members=[
            {
                'id': 'm1',
                'name': 'Test Leader',
                'email': 'leader@test.com',
                'role': 'Member',
                'avatar': '',
                'status': 'Active',
            }
        ],
        workshops=[_base_workshop()],
    )
    response = auth_client.patch(
        '/api/dashboard/workshops/w1', headers=HEADERS, json={'applying': True}
    )
    assert response.status_code == 200


def test_apply_to_missing_workshop_404s(auth_client, monkeypatch):
    _seed_workshop_club(auth_client, monkeypatch)
    response = auth_client.patch(
        '/api/dashboard/workshops/nope', headers=HEADERS, json={'applying': True}
    )
    assert response.status_code == 404


def test_schedule_workshop_creates_linked_event(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client,
        monkeypatch,
        members=[
            {
                'id': 'm1',
                'name': 'Runner',
                'email': 'runner@test.com',
                'role': 'Member',
                'avatar': '',
                'status': 'Active',
            }
        ],
        workshops=[_base_workshop(applicants=['runner@test.com'])],
    )
    response = auth_client.patch(
        '/api/dashboard/workshops/w1',
        headers=HEADERS,
        json={
            'status': 'Scheduled',
            'runnerEmail': 'runner@test.com',
            'date': '2026-09-01',
            'time': '15:00',
            'location': 'Room 204',
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    workshop = body['workshop']
    assert workshop['status'] == 'Scheduled'
    assert workshop['runnerEmail'] == 'runner@test.com'
    assert workshop['runnerName'] == 'Runner'
    assert workshop['eventId']
    events = body['state']['events']
    assert any(
        e['id'] == workshop['eventId']
        and e['title'] == 'Intro to Git'
        and e['type'] == 'Workshop'
        and e['location'] == 'Room 204'
        for e in events
    )


def test_schedule_workshop_rejects_non_applicant(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client, monkeypatch, workshops=[_base_workshop(applicants=['runner@test.com'])]
    )
    response = auth_client.patch(
        '/api/dashboard/workshops/w1',
        headers=HEADERS,
        json={
            'status': 'Scheduled',
            'runnerEmail': 'nobody@test.com',
            'date': '2026-09-01',
            'time': '15:00',
            'location': 'Room 204',
        },
    )
    assert response.status_code == 400


def test_schedule_workshop_rejects_invalid_date(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client, monkeypatch, workshops=[_base_workshop(applicants=['runner@test.com'])]
    )
    response = auth_client.patch(
        '/api/dashboard/workshops/w1',
        headers=HEADERS,
        json={
            'status': 'Scheduled',
            'runnerEmail': 'runner@test.com',
            'date': 'not-a-date',
            'time': '15:00',
            'location': 'Room 204',
        },
    )
    assert response.status_code == 400


def test_schedule_workshop_requires_leader(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client,
        monkeypatch,
        members=[
            {
                'id': 'm1',
                'name': 'Test Leader',
                'email': 'leader@test.com',
                'role': 'Member',
                'avatar': '',
                'status': 'Active',
            }
        ],
        workshops=[_base_workshop(applicants=['runner@test.com'])],
    )
    response = auth_client.patch(
        '/api/dashboard/workshops/w1',
        headers=HEADERS,
        json={
            'status': 'Scheduled',
            'runnerEmail': 'runner@test.com',
            'date': '2026-09-01',
            'time': '15:00',
            'location': 'Room 204',
        },
    )
    assert response.status_code == 403


def test_mark_workshop_run_requires_scheduled_status(auth_client, monkeypatch):
    _seed_workshop_club(auth_client, monkeypatch, workshops=[_base_workshop(status='Proposed')])
    response = auth_client.patch(
        '/api/dashboard/workshops/w1', headers=HEADERS, json={'status': 'Run'}
    )
    assert response.status_code == 400


def test_mark_workshop_run_succeeds_when_scheduled(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client,
        monkeypatch,
        workshops=[
            _base_workshop(
                status='Scheduled', runnerEmail='runner@test.com', runnerName='Runner', eventId='e1'
            )
        ],
    )
    response = auth_client.patch(
        '/api/dashboard/workshops/w1', headers=HEADERS, json={'status': 'Run'}
    )
    assert response.status_code == 200
    assert response.get_json()['workshop']['status'] == 'Run'


def test_delete_workshop_requires_leader(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client,
        monkeypatch,
        members=[
            {
                'id': 'm1',
                'name': 'Test Leader',
                'email': 'leader@test.com',
                'role': 'Member',
                'avatar': '',
                'status': 'Active',
            }
        ],
        workshops=[_base_workshop()],
    )
    response = auth_client.delete('/api/dashboard/workshops/w1', headers=HEADERS)
    assert response.status_code == 403


def test_delete_workshop_removes_it(auth_client, monkeypatch):
    _seed_workshop_club(auth_client, monkeypatch, workshops=[_base_workshop()])
    response = auth_client.delete('/api/dashboard/workshops/w1', headers=HEADERS)
    assert response.status_code == 200
    with auth_client.session_transaction() as sess:
        assert sess['dashboard_state']['workshops'] == []


def test_delete_workshop_rejects_once_scheduled(auth_client, monkeypatch):
    _seed_workshop_club(
        auth_client,
        monkeypatch,
        workshops=[
            _base_workshop(
                status='Scheduled', runnerEmail='runner@test.com', runnerName='Runner', eventId='e1'
            )
        ],
    )
    response = auth_client.delete('/api/dashboard/workshops/w1', headers=HEADERS)
    assert response.status_code == 400
