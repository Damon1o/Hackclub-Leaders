from datetime import date

import flask
import requests
from flask import request, session

from .helpers import (
    _item_id,
    _storage,
    clean_text,
    find_by_id,
    get_dashboard_state,
    json_error,
    json_payload,
    login_required,
    parse_bool,
    parse_language,
    require_dashboard_csrf,
    require_leader_api,
    save_dashboard_state,
    unique_join_code,
)
from .storage import SessionStorage


def register(app, HACKATIME_CLIENT_ID):
    # ── Newsletters ───────────────────────────────────────────────────────

    @app.post('/api/dashboard/newsletters')
    @login_required
    def api_newsletters_add():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        payload = json_payload()
        title = clean_text(payload.get('title'))
        excerpt = clean_text(payload.get('excerpt'))
        body = clean_text(payload.get('body'), max_len=1000)
        read_time = clean_text(payload.get('readTime'), '2 min read', max_len=20)

        if not title:
            return json_error('Dispatch title is required.')
        if not excerpt:
            return json_error('Dispatch excerpt is required.')
        if not body:
            return json_error('Dispatch body is required.')

        state = get_dashboard_state()
        newsletter = {
            'id': _item_id('dispatch'),
            'title': title,
            'excerpt': excerpt,
            'body': body,
            'date': date.today().isoformat(),
            'readTime': read_time,
            'read': False,
        }
        state['newsletters'].insert(0, newsletter)
        save_dashboard_state(state)
        return flask.jsonify({'newsletter': newsletter, 'state': state})

    @app.patch('/api/dashboard/newsletters/<newsletter_id>')
    @login_required
    def api_newsletters_update(newsletter_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        state = get_dashboard_state()
        newsletter = find_by_id(state['newsletters'], newsletter_id)
        if not newsletter:
            return json_error('Dispatch not found.', 404)

        payload = json_payload()
        if 'read' in payload:
            newsletter['read'] = parse_bool(payload.get('read'))
        save_dashboard_state(state)
        return flask.jsonify({'newsletter': newsletter, 'state': state})

    @app.patch('/api/dashboard/newsletter-subscription')
    @login_required
    def api_newsletter_subscription_update():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        state = get_dashboard_state()
        state['settings']['newsletterSubscribed'] = parse_bool(json_payload().get('subscribed'))
        save_dashboard_state(state)
        return flask.jsonify({'state': state})

    # ── Settings ──────────────────────────────────────────────────────────

    @app.patch('/api/dashboard/settings')
    @login_required
    def api_settings_update():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        payload = json_payload()
        club_name = clean_text(payload.get('clubName'))
        venue = clean_text(payload.get('venue'), max_len=120)
        website = clean_text(payload.get('website'))
        avatar = clean_text(payload.get('avatar'))
        meeting_day = clean_text(payload.get('meetingDay'), max_len=20)
        address_line1 = clean_text(payload.get('addressLine1'), max_len=120)
        address_line2 = clean_text(payload.get('addressLine2'), max_len=120)
        city = clean_text(payload.get('city'), max_len=80)
        state_field = clean_text(payload.get('state'), max_len=80)
        zip_code = clean_text(payload.get('zip'), max_len=20)
        country = clean_text(payload.get('country'), max_len=80)
        club_bio = clean_text(payload.get('clubBio'), max_len=500)

        if not club_name:
            return json_error('Club name is required.')
        if not venue:
            return json_error('School or venue is required.')
        if website and not website.startswith(('http://', 'https://')):
            return json_error('Club website must start with http:// or https://.')
        if avatar and not avatar.startswith(('http://', 'https://')):
            return json_error('Avatar URL must start with http:// or https://.')

        location = ', '.join(filter(None, [city, state_field]))

        state = get_dashboard_state()
        state['settings'].update(
            {
                'clubName': club_name,
                'venue': venue,
                'location': location,
                'addressLine1': address_line1,
                'addressLine2': address_line2,
                'city': city,
                'state': state_field,
                'zip': zip_code,
                'country': country,
                'meetingDay': meeting_day,
                'clubBio': club_bio,
                'website': website,
                'avatar': avatar,
                'publicDirectory': parse_bool(payload.get('publicDirectory')),
                'emailNotifications': parse_bool(payload.get('emailNotifications')),
                'darkModeDefault': parse_bool(payload.get('darkModeDefault')),
                'newsletterSubscribed': parse_bool(payload.get('newsletterSubscribed')),
                'language': parse_language(payload.get('language')),
            }
        )
        save_dashboard_state(state)
        return flask.jsonify({'state': state})

    @app.post('/api/dashboard/settings/join-code/refresh')
    @login_required
    def api_join_code_refresh():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        state = get_dashboard_state()
        new_code = unique_join_code(_storage())
        state['settings']['joinCode'] = new_code
        save_dashboard_state(state)
        return flask.jsonify({'joinCode': new_code, 'state': state})

    # ── Profile ───────────────────────────────────────────────────────────

    @app.patch('/api/dashboard/profile')
    @login_required
    def api_profile_update():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        payload = json_payload()
        name = clean_text(payload.get('name'), max_len=80)
        email = clean_text(payload.get('email'), max_len=120)
        avatar = clean_text(payload.get('avatar'), max_len=300)
        bio = clean_text(payload.get('bio'), max_len=500)
        hackatime_id = clean_text(payload.get('hackatimeId'), max_len=40)

        if not name:
            return json_error('Name is required.')
        if not email or '@' not in email:
            return json_error('A valid email is required.')
        if avatar and not avatar.startswith(('http://', 'https://')):
            return json_error('Avatar URL must start with http:// or https://.')
        if hackatime_id and not hackatime_id.isdigit():
            return json_error('Hackatime user ID should be just the number from your profile URL.')

        old_email = ((session.get('user') or {}).get('email') or '').strip().lower()
        user = dict(session.get('user') or {})
        user.update(
            {
                'name': name,
                'email': email,
                'avatar': avatar,
                'bio': bio,
                'hackatimeId': hackatime_id,
            }
        )
        session['user'] = user

        state = get_dashboard_state()
        for member in state.get('members', []):
            if (member.get('email') or '').strip().lower() == old_email:
                member.update({'name': name, 'email': email.lower(), 'avatar': avatar})
                save_dashboard_state(state)
                return flask.jsonify({'user': user, 'state': state})

        return flask.jsonify({'user': user})

    @app.patch('/api/dashboard/account/preferred-name')
    @login_required
    def api_account_preferred_name_update():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        preferred_name = clean_text(json_payload().get('preferredName'), max_len=80)
        if not preferred_name:
            return json_error('Preferred name is required.')

        backend = _storage()
        if isinstance(backend, SessionStorage):
            user = dict(session.get('user') or {})
            user['preferredName'] = preferred_name
            session['user'] = user
        else:
            email = (session.get('user') or {}).get('email') or ''
            backend.save_user_record(email, {'preferredName': preferred_name})

        return flask.jsonify({'preferredName': preferred_name})

    # ── Hackatime API ─────────────────────────────────────────────────────

    HACKATIME_API = 'https://hackatime.hackclub.com/api/v1'  # noqa: N806

    def _fetch_hackatime_data():
        user_id = (
            request.args.get('userId') or (session.get('user') or {}).get('hackatimeId') or ''
        ).strip()
        if not user_id:
            return json_error('Add your Hackatime user ID on your profile first.', 400)
        if not user_id.isdigit():
            return json_error('That Hackatime user ID is not valid.', 400)

        try:
            response = requests.get(
                f'{HACKATIME_API}/users/{user_id}/stats',
                params={'features': 'projects,languages'},
                headers={'Accept': 'application/json'},
                timeout=8,
            )
        except requests.RequestException:
            return json_error('Could not reach Hackatime right now.', 502)

        if response.status_code == 404:
            return json_error('No public Hackatime profile for that ID.', 404)
        if response.status_code >= 400:
            return json_error('Hackatime returned an error.', 502)

        data = (response.json() or {}).get('data') or {}
        if not data.get('is_coding_activity_visible', True):
            return json_error('That Hackatime profile is private.', 403)
        return data

    @app.get('/api/dashboard/hackatime')
    @login_required
    def api_hackatime_stats():
        data = _fetch_hackatime_data()
        if not isinstance(data, dict):
            return data

        languages = [
            {
                'name': lang.get('name'),
                'text': lang.get('text'),
                'totalSeconds': lang.get('total_seconds'),
            }
            for lang in (data.get('languages') or [])[:5]
        ]
        return flask.jsonify(
            {
                'username': data.get('username'),
                'totalSeconds': data.get('total_seconds'),
                'humanReadableTotal': data.get('human_readable_total'),
                'humanReadableDailyAverage': data.get('human_readable_daily_average'),
                'languages': languages,
            }
        )

    @app.get('/api/dashboard/hackatime/projects')
    @login_required
    def api_hackatime_projects():
        data = _fetch_hackatime_data()
        if not isinstance(data, dict):
            return data

        projects = [
            {
                'name': p['name'],
                'hours': round((p.get('total_seconds') or 0) / 3600, 1),
                'text': p.get('text') or '',
            }
            for p in (data.get('projects') or [])
            if p.get('name')
        ]
        projects.sort(key=lambda p: p['hours'], reverse=True)
        return flask.jsonify({'projects': projects[:30]})
