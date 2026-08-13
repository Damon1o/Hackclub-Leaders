"""Project and image upload API routes for Hack Club Leaders Portal."""

import os
from datetime import date
from typing import cast

import flask
from flask import current_app, request, session

from .helpers import (
    Project,
    _item_id,
    _join_missing,
    _owned_project_or_error,
    _slugify,
    _sniff_image,
    _upload_to_blob,
    _viewer_email,
    clean_text,
    get_dashboard_state,
    json_error,
    json_payload,
    login_required,
    require_dashboard_csrf,
    save_dashboard_state,
)
from .notifications import notify_admins_of_project_submission
from .storage import StorageError


def register_project_routes(app: flask.Flask, max_image_bytes: int) -> None:

    def _handle_image_upload(folder: str, default_stem: str) -> flask.Response | tuple[flask.Response, int]:
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        file = request.files.get('image')
        if file is None or not file.filename:
            return json_error('Choose an image to upload.')
        data = file.read(max_image_bytes + 1)
        if not data:
            return json_error('That image is empty.')
        if len(data) > max_image_bytes:
            return json_error('Image must be 4 MB or smaller.')

        content_type, ext = _sniff_image(data)
        if not content_type:
            return json_error('Only PNG, JPEG, WebP, or GIF images are allowed.')

        stem = _slugify(os.path.splitext(file.filename)[0]) or default_stem
        try:
            url = _upload_to_blob(f'{folder}/{stem}.{ext}', data, content_type)
        except StorageError as exc:
            return json_error(str(exc), 502)
        if not url:
            return json_error('Upload succeeded but no URL was returned.', 502)
        return flask.jsonify({'url': url})

    @app.post('/api/dashboard/projects/upload-image')
    @login_required
    def api_project_upload_image() -> flask.Response | tuple[flask.Response, int]:
        return _handle_image_upload('projects', 'image')

    @app.post('/api/dashboard/upload-image')
    @login_required
    def api_upload_avatar() -> flask.Response | tuple[flask.Response, int]:
        return _handle_image_upload('avatars', 'avatar')

    @app.post('/api/dashboard/projects')
    @login_required
    def api_project_add() -> flask.Response | tuple[flask.Response, int]:
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        payload = json_payload()
        name = clean_text(payload.get('name'), max_len=120)
        description = clean_text(payload.get('description'), max_len=500)
        url = clean_text(payload.get('url'))
        repo_url = clean_text(payload.get('repoUrl'))
        demo_url = clean_text(payload.get('demoUrl'))
        thumbnail = clean_text(payload.get('thumbnail'))
        hackatime_project = clean_text(payload.get('hackatimeProject'), max_len=120)
        if not name:
            return json_error('Project name is required.')
        if url and not url.startswith(('http://', 'https://')):
            return json_error('Project URL must start with http:// or https://.')
        if repo_url and not repo_url.startswith(('http://', 'https://')):
            return json_error('Repository URL must start with http:// or https://.')
        if demo_url and not demo_url.startswith(('http://', 'https://')):
            return json_error('Demo URL must start with http:// or https://.')
        if thumbnail and not thumbnail.startswith(('http://', 'https://')):
            return json_error('Thumbnail URL must start with http:// or https://.')

        if demo_url:
            url = demo_url

        user = session.get('user') or {}
        state = get_dashboard_state()
        project = cast(
            Project,
            {
                'id': _item_id('project'),
                'name': name,
                'description': description,
                'url': url,
                'repoUrl': repo_url,
                'demoUrl': demo_url,
                'thumbnail': thumbnail,
                'hackatimeProject': hackatime_project,
                'status': 'Draft',
                'ownerEmail': _viewer_email(),
                'ownerName': user.get('name') or _viewer_email(),
                'date': date.today().isoformat(),
            },
        )
        state.setdefault('projects', []).insert(0, project)
        save_dashboard_state(state)
        return flask.jsonify({'project': project, 'state': state})

    @app.patch('/api/dashboard/projects/<project_id>')
    @login_required
    def api_project_update(project_id: str) -> flask.Response | tuple[flask.Response, int]:
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        state = get_dashboard_state()
        project, error = _owned_project_or_error(state, project_id)
        if error or project is None:
            return error or json_error('Project not found.', 404)

        payload = json_payload()
        if 'name' in payload:
            name = clean_text(payload.get('name'), project.get('name', ''), max_len=120)
            if not name:
                return json_error('Project name is required.')
            project['name'] = name
        if 'description' in payload:
            project['description'] = clean_text(
                payload.get('description'), project.get('description', ''), max_len=500
            )
        if 'url' in payload:
            url = clean_text(payload.get('url'), project.get('url', ''))
            if url and not url.startswith(('http://', 'https://')):
                return json_error('Project URL must start with http:// or https://.')
            project['url'] = url
        if 'repoUrl' in payload:
            repo_url = clean_text(payload.get('repoUrl'), project.get('repoUrl', ''))
            if repo_url and not repo_url.startswith(('http://', 'https://')):
                return json_error('Repository URL must start with http:// or https://.')
            project['repoUrl'] = repo_url
        if 'demoUrl' in payload:
            demo_url = clean_text(payload.get('demoUrl'), project.get('demoUrl', ''))
            if demo_url and not demo_url.startswith(('http://', 'https://')):
                return json_error('Demo URL must start with http:// or https://.')
            project['demoUrl'] = demo_url
            if demo_url:
                project['url'] = demo_url
        if 'thumbnail' in payload:
            thumbnail = clean_text(payload.get('thumbnail'), project.get('thumbnail', ''))
            if thumbnail and not thumbnail.startswith(('http://', 'https://')):
                return json_error('Thumbnail URL must start with http:// or https://.')
            project['thumbnail'] = thumbnail
        if 'hackatimeProject' in payload:
            project['hackatimeProject'] = clean_text(
                payload.get('hackatimeProject'), project.get('hackatimeProject', ''), max_len=120
            )
        if 'status' in payload:
            status = clean_text(payload.get('status'), project.get('status', 'Draft')).title()
            if status not in {'Draft', 'Submitted'}:
                return json_error('Status must be Draft or Submitted.')
            was_draft = project.get('status') == 'Draft'
            if status == 'Submitted':
                missing: list[str] = []
                if not (project.get('repoUrl') or '').strip():
                    missing.append('a repository URL')
                if not (project.get('demoUrl') or '').strip():
                    missing.append('a demo URL')
                if not (project.get('hackatimeProject') or '').strip():
                    missing.append('a Hackatime project')
                if missing:
                    return json_error('Add ' + _join_missing(missing) + ' before submitting.', 400)
            project['status'] = status

            if status == 'Submitted' and was_draft:
                try:
                    notify_admins_of_project_submission(project)
                except Exception as e:
                    current_app.logger.error(f'Failed to send project submission notification: {e}')

        save_dashboard_state(state)
        return flask.jsonify({'project': project, 'state': state})

    @app.delete('/api/dashboard/projects/<project_id>')
    @login_required
    def api_project_delete(project_id: str) -> flask.Response | tuple[flask.Response, int]:
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        state = get_dashboard_state()
        _project, error = _owned_project_or_error(state, project_id)
        if error:
            return error
        state['projects'] = [p for p in state.get('projects') or [] if p.get('id') != project_id]
        save_dashboard_state(state)
        return flask.jsonify({'state': state})
