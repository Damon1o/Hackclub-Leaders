"""Workshop API routes for Hack Club Leaders Portal."""

from datetime import date

import flask
from flask import current_app, session

from .helpers import (
    Event,
    Workshop,
    _item_id,
    _viewer_email,
    clean_text,
    find_by_id,
    get_dashboard_state,
    json_error,
    json_payload,
    login_required,
    parse_bool,
    require_dashboard_csrf,
    require_leader_api,
    save_dashboard_state,
    utc_iso,
    workshop_from_payload,
)
from .notifications import (
    notify_leaders_of_workshop_application,
    notify_runner_of_workshop_selection,
)


def register_workshop_routes(app: flask.Flask) -> None:

    @app.post('/api/dashboard/workshops')
    @login_required
    def api_workshops_add() -> flask.Response | tuple[flask.Response, int]:
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        workshop_data, error = workshop_from_payload(json_payload())
        if workshop_data is None:
            return json_error(error or 'Invalid workshop.')

        user = session.get('user') or {}
        state = get_dashboard_state()
        workshop: Workshop = {
            'id': _item_id('workshop'),
            'title': workshop_data['title'],
            'description': workshop_data['description'],
            'status': 'Proposed',
            'proposerEmail': _viewer_email(),
            'proposerName': user.get('name', 'A member'),
            'applicants': [],
            'runnerEmail': '',
            'runnerName': '',
            'eventId': '',
            'createdAt': utc_iso(),
        }
        state.setdefault('workshops', []).insert(0, workshop)
        save_dashboard_state(state)
        return flask.jsonify({'workshop': workshop, 'state': state})

    @app.patch('/api/dashboard/workshops/<workshop_id>')
    @login_required
    def api_workshops_update(workshop_id: str) -> flask.Response | tuple[flask.Response, int]:
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        payload = json_payload()
        is_apply_only = set(payload.keys()) <= {'applying'}
        if not is_apply_only:
            role_error = require_leader_api()
            if role_error:
                return role_error

        state = get_dashboard_state()
        workshops = state.get('workshops') or []
        workshop = find_by_id(workshops, workshop_id)
        if not workshop:
            return json_error('Workshop not found.', 404)

        if is_apply_only:
            if workshop['status'] != 'Proposed':
                return json_error('This workshop is no longer open to applicants.')
            applying = parse_bool(payload.get('applying'))
            viewer_email = _viewer_email()
            already_applied = viewer_email in workshop['applicants']
            if applying == already_applied:
                return flask.jsonify({'workshop': workshop, 'state': state})
            if applying:
                workshop['applicants'].append(viewer_email)
            else:
                workshop['applicants'].remove(viewer_email)
            save_dashboard_state(state)

            user = session.get('user') or {}
            try:
                notify_leaders_of_workshop_application(
                    workshop, viewer_email, user.get('name', 'A member'), applying
                )
            except Exception as e:
                current_app.logger.warning(f'Failed to send workshop application notification: {e}')
            return flask.jsonify({'workshop': workshop, 'state': state})

        new_status = payload.get('status')
        if new_status == 'Scheduled':
            if workshop['status'] != 'Proposed':
                return json_error('This workshop has already been scheduled.')
            runner_email = clean_text(payload.get('runnerEmail')).lower()
            if runner_email not in workshop['applicants']:
                return json_error('Pick an applicant who actually applied to run this.')
            event_date = clean_text(payload.get('date'))
            event_time = clean_text(payload.get('time'))
            location = clean_text(payload.get('location'))
            try:
                date.fromisoformat(event_date)
            except ValueError:
                return json_error('Choose a valid date.')
            if not event_time:
                return json_error('Event time is required.')
            if not location:
                return json_error('Event location is required.')

            runner = next(
                (m for m in (state.get('members') or []) if (m.get('email') or '').lower() == runner_email),
                None,
            )
            runner_name = runner.get('name', 'A member') if runner else 'A member'

            new_event: Event = {
                'id': _item_id('event'),
                'title': workshop['title'],
                'date': event_date,
                'time': event_time,
                'location': location,
                'type': 'Workshop',
                'repeat': '',
                'rsvp': False,
                'attendees': 0,
            }
            state.setdefault('events', []).append(new_event)
            state['events'].sort(key=lambda item: (item.get('date', ''), item.get('time', '')))

            workshop['status'] = 'Scheduled'
            workshop['runnerEmail'] = runner_email
            workshop['runnerName'] = runner_name
            workshop['eventId'] = new_event['id']
            save_dashboard_state(state)

            try:
                notify_runner_of_workshop_selection(workshop, runner_email, runner_name)
            except Exception as e:
                current_app.logger.warning(f'Failed to send workshop selection notification: {e}')

            return flask.jsonify({'workshop': workshop, 'state': state})

        if new_status == 'Run':
            if workshop['status'] != 'Scheduled':
                return json_error('Only a scheduled workshop can be marked as run.')
            workshop['status'] = 'Run'
            save_dashboard_state(state)
            return flask.jsonify({'workshop': workshop, 'state': state})

        return json_error('Unsupported update.')

    @app.delete('/api/dashboard/workshops/<workshop_id>')
    @login_required
    def api_workshops_delete(workshop_id: str) -> flask.Response | tuple[flask.Response, int]:
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        state = get_dashboard_state()
        workshops = state.get('workshops') or []
        workshop = find_by_id(workshops, workshop_id)
        if not workshop:
            return json_error('Workshop not found.', 404)
        if workshop['status'] != 'Proposed':
            return json_error('Only a proposed (not yet scheduled) workshop can be deleted.')
        state['workshops'] = [w for w in workshops if w.get('id') != workshop_id]
        save_dashboard_state(state)
        return flask.jsonify({'state': state})
