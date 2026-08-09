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
