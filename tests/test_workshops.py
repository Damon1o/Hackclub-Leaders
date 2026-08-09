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
