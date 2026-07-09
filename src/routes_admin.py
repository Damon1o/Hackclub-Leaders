import flask
from flask import flash, redirect, url_for

from helpers import (
    ADMIN_REVIEW_STATUSES,
    _find_club_by_project,
    _load_admin_club,
    _persist_club,
    _storage,
    admin_required,
    clean_text,
    find_by_id,
    json_error,
    json_payload,
    parse_bool,
    require_admin_api,
    require_dashboard_csrf,
)


def register(app):
    # ── Admin pages ─────────────────────────────────────────────────────────

    @app.route('/dashboard/admin')
    @admin_required
    def dashboard_admin():
        backend = _storage()
        return flask.render_template(
            'dashboard/admin.html',
            clubs=backend.list_clubs(),
            pending_projects=backend.list_pending_projects(),
        )

    @app.route('/dashboard/admin/club/<club_key>')
    @admin_required
    def dashboard_admin_club(club_key):
        club_key = (club_key or '').strip().lower()
        state = _storage().load(club_key)
        if state is None:
            flash('That club no longer exists.', 'error')
            return redirect(url_for('dashboard_admin'))
        return flask.render_template(
            'dashboard/admin_club.html',
            club_key=club_key,
            club=state,
        )

    # ── Admin API ───────────────────────────────────────────────────────────

    @app.patch('/api/admin/clubs/<club_key>')
    def api_admin_club_update(club_key):
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        club_key = (club_key or '').strip().lower()
        backend = _storage()
        state, error = _load_admin_club(backend, club_key)
        if error:
            return error

        payload = json_payload()
        club_name = clean_text(payload.get('clubName'))
        website = clean_text(payload.get('website'))
        avatar = clean_text(payload.get('avatar'))
        if not club_name:
            return json_error('Club name is required.')
        if website and not website.startswith(('http://', 'https://')):
            return json_error('Club website must start with http:// or https://.')
        if avatar and not avatar.startswith(('http://', 'https://')):
            return json_error('Avatar URL must start with http:// or https://.')

        settings = state.setdefault('settings', {})
        settings['clubName'] = club_name
        settings['location'] = clean_text(payload.get('location'))
        settings['website'] = website
        settings['avatar'] = avatar
        if 'publicDirectory' in payload:
            settings['publicDirectory'] = parse_bool(payload.get('publicDirectory'))
        _persist_club(backend, club_key, state)
        return flask.jsonify({'club': state})

    @app.patch('/api/admin/projects/<club_key>/<project_id>')
    def api_admin_project_review(club_key, project_id):
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        club_key = (club_key or '').strip().lower()
        backend = _storage()
        state, error = _load_admin_club(backend, club_key)
        if error:
            state, club_key = _find_club_by_project(backend, project_id)
            if state is None:
                return error

        project = find_by_id(state.get('projects') or [], project_id)
        if not project:
            return json_error('Project not found.', 404)

        payload = json_payload()
        status = clean_text(payload.get('status')).title()
        if status not in ADMIN_REVIEW_STATUSES:
            return json_error('Status must be Shipped or Draft.')
        project['status'] = status
        _persist_club(backend, club_key, state)
        return flask.jsonify({'project': project})
