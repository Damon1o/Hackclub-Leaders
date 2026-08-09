import os
from datetime import date

import flask
from flask import current_app, request, session

from .helpers import (
    STATE_SECTIONS,
    _item_id,
    _join_missing,
    _owned_project_or_error,
    _slugify,
    _sniff_image,
    _upload_to_blob,
    _viewer_email,
    award_coins,
    clean_text,
    coin_balance,
    event_from_payload,
    find_by_id,
    get_dashboard_state,
    json_error,
    json_payload,
    login_required,
    paginate,
    parse_bool,
    require_dashboard_csrf,
    require_leader_api,
    save_dashboard_state,
    viewer_is_leader,
)
from .notifications import (
    notify_admins_of_project_submission,
    notify_leaders_of_event_rsvp,
    send_event_rsvp_confirmation,
)
from .storage import StorageError


def register(app, MAX_IMAGE_BYTES):
    # ── State ───────────────────────────────────────────────────────────────

    @app.get('/api/dashboard/state')
    @login_required
    def api_dashboard_state():
        """The club state, or just the sections named in ?sections=a,b,c.

        The client asks for what the page it is rendering needs; unknown names
        are ignored so an older client can't 500 this. No `sections` at all
        keeps the original behaviour and returns everything.
        """
        raw = clean_text(request.args.get('sections'), max_len=200)
        sections = None
        if raw:
            asked = {part.strip() for part in raw.split(',') if part.strip()}
            sections = [key for key in STATE_SECTIONS if key in asked]
        return flask.jsonify({'state': get_dashboard_state(sections)})

    # ── Paginated list reads ────────────────────────────────────────────────
    #
    # The dashboard used to render these from the whole state blob. Each has
    # its own endpoint now so a club with hundreds of members, events, or
    # projects sends one page at a time: ?page= (1-based) and ?per_page=.

    @app.get('/api/dashboard/team')
    @login_required
    def api_team_list():
        members = get_dashboard_state(['members']).get('members') or []
        return flask.jsonify(paginate(members))

    @app.get('/api/dashboard/events')
    @login_required
    def api_events_list():
        events = get_dashboard_state(['events']).get('events') or []
        # Soonest first — the list is a schedule, not an archive.
        events = sorted(events, key=lambda e: (e.get('date') or '', e.get('time') or ''))
        return flask.jsonify(paginate(events))

    @app.get('/api/dashboard/projects')
    @login_required
    def api_projects_list():
        """?status= narrows to one review state (e.g. Shipped)."""
        projects = get_dashboard_state(['projects']).get('projects') or []
        status = clean_text(request.args.get('status'), max_len=20)
        if status:
            projects = [p for p in projects if (p.get('status') or '') == status]
        projects = sorted(projects, key=lambda p: p.get('date') or '', reverse=True)
        return flask.jsonify(paginate(projects))

    # ── Notifications ───────────────────────────────────────────────────────
    #
    # The notification centre in dashboard_layout.html calls these. They were
    # missing entirely, so every mark-as-read from the bell menu 404'd.

    @app.get('/api/dashboard/notifications')
    @login_required
    def api_notifications_list():
        """Newest first, paginated with ?page= / ?per_page=."""
        notifications = get_dashboard_state(['notifications']).get('notifications') or []
        page = paginate(notifications)
        page['unread'] = sum(1 for n in notifications if not n.get('read'))
        return flask.jsonify(page)

    # Registered before the <notification_id> rule so the literal path can
    # never be swallowed as an id.
    @app.patch('/api/dashboard/notifications/mark-all-read')
    @login_required
    def api_notifications_mark_all_read():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        state = get_dashboard_state(['notifications'])
        notifications = state.get('notifications') or []
        updated = [n for n in notifications if not n.get('read')]
        for notification in updated:
            notification['read'] = True
        if updated:
            save_dashboard_state(state)
        return flask.jsonify({'updated': len(updated), 'unread': 0})

    @app.patch('/api/dashboard/notifications/<notification_id>')
    @login_required
    def api_notification_update(notification_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        state = get_dashboard_state(['notifications'])
        notifications = state.get('notifications') or []
        notification = find_by_id(notifications, notification_id)
        if not notification:
            return json_error('Notification not found.', 404)

        read = parse_bool(json_payload().get('read', True))
        if notification.get('read') != read:
            notification['read'] = read
            save_dashboard_state(state)
        unread = sum(1 for n in notifications if not n.get('read'))
        return flask.jsonify({'notification': notification, 'unread': unread})

    @app.delete('/api/dashboard/notifications/<notification_id>')
    @login_required
    def api_notification_delete(notification_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        state = get_dashboard_state(['notifications'])
        notifications = state.get('notifications') or []
        remaining = [n for n in notifications if n.get('id') != notification_id]
        if len(remaining) == len(notifications):
            return json_error('Notification not found.', 404)
        state['notifications'] = remaining
        save_dashboard_state(state)
        return flask.jsonify({'unread': sum(1 for n in remaining if not n.get('read'))})

    # ── Team ────────────────────────────────────────────────────────────────

    @app.post('/api/dashboard/team')
    @login_required
    def api_team_add():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        payload = json_payload()
        name = clean_text(payload.get('name'))
        email = clean_text(payload.get('email')).lower()
        role = clean_text(payload.get('role'), 'Member').title()
        avatar = clean_text(payload.get('avatar'))

        if not name:
            return json_error('Member name is required.')
        if '@' not in email:
            return json_error('Enter a valid member email.')
        if role not in {'Leader', 'Member', 'Mentor'}:
            return json_error('Choose Leader, Member, or Mentor.')

        state = get_dashboard_state()
        member = {
            'id': _item_id('member'),
            'name': name,
            'email': email,
            'role': role,
            'avatar': avatar,
            'status': 'Invited',
        }
        state['members'].append(member)
        save_dashboard_state(state)
        return flask.jsonify({'member': member, 'state': state})

    @app.patch('/api/dashboard/team/<member_id>')
    @login_required
    def api_team_update(member_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        state = get_dashboard_state()
        member = find_by_id(state['members'], member_id)
        if not member:
            return json_error('Member not found.', 404)

        payload = json_payload()
        name = clean_text(payload.get('name'), member['name'])
        email = clean_text(payload.get('email'), member['email']).lower()
        role = clean_text(payload.get('role'), member['role']).title()
        avatar = clean_text(payload.get('avatar'), member.get('avatar', ''))
        status = clean_text(payload.get('status'), member.get('status', 'Active')).title()

        if not name:
            return json_error('Member name is required.')
        if '@' not in email:
            return json_error('Enter a valid member email.')
        if role not in {'Leader', 'Member', 'Mentor'}:
            return json_error('Choose Leader, Member, or Mentor.')
        if status not in {'Active', 'Invited'}:
            return json_error('Choose Active or Invited status.')

        leaders = [m for m in state['members'] if m.get('role') == 'Leader']
        if member.get('role') == 'Leader' and role != 'Leader' and len(leaders) == 1:
            return json_error('A club needs at least one leader.')

        member.update(
            {
                'name': name,
                'email': email,
                'role': role,
                'avatar': avatar,
                'status': status,
            }
        )
        save_dashboard_state(state)
        return flask.jsonify({'member': member, 'state': state})

    @app.delete('/api/dashboard/team/<member_id>')
    @login_required
    def api_team_delete(member_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        state = get_dashboard_state()
        target = find_by_id(state['members'], member_id)
        leaders = [m for m in state['members'] if m.get('role') == 'Leader']
        if target and target.get('role') == 'Leader' and len(leaders) == 1:
            return json_error('A club needs at least one leader.')
        original_count = len(state['members'])
        state['members'] = [member for member in state['members'] if member.get('id') != member_id]
        if len(state['members']) == original_count:
            return json_error('Member not found.', 404)
        save_dashboard_state(state)
        return flask.jsonify({'state': state})

    # ── Events ──────────────────────────────────────────────────────────────

    @app.post('/api/dashboard/events')
    @login_required
    def api_events_add():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        event_data, error = event_from_payload(json_payload())
        if error:
            return json_error(error)

        state = get_dashboard_state()
        event = {'id': _item_id('event'), **event_data}
        state['events'].append(event)
        state['events'].sort(key=lambda item: (item.get('date', ''), item.get('time', '')))
        save_dashboard_state(state)
        return flask.jsonify({'event': event, 'state': state})

    @app.patch('/api/dashboard/events/<event_id>')
    @login_required
    def api_events_update(event_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        payload = json_payload()
        is_rsvp_only = set(payload.keys()) <= {'rsvp'}
        if not viewer_is_leader() and not is_rsvp_only:
            return flask.jsonify({'error': 'Only leaders and mentors can edit events.'}), 403

        state = get_dashboard_state()
        event = find_by_id(state['events'], event_id)
        if not event:
            return json_error('Event not found.', 404)

        old_rsvp = event.get('rsvp', False)
        event_data, error = event_from_payload(payload, event)
        if error:
            return json_error(error)

        new_rsvp = event_data.get('rsvp', old_rsvp)
        rsvp_changed = old_rsvp != new_rsvp

        event.update(event_data)
        state['events'].sort(key=lambda item: (item.get('date', ''), item.get('time', '')))
        save_dashboard_state(state)

        # Send RSVP notifications
        if rsvp_changed:
            user = session.get('user') or {}
            user_email = user.get('email', '').lower()
            user_name = user.get('name', 'A member')
            try:
                send_event_rsvp_confirmation(event, user_email, user_name, new_rsvp)
                notify_leaders_of_event_rsvp(event, user_email, user_name, new_rsvp)
            except Exception as e:
                current_app.logger.warning(f'Failed to send RSVP notification: {e}')

        return flask.jsonify({'event': event, 'state': state})

    @app.delete('/api/dashboard/events/<event_id>')
    @login_required
    def api_events_delete(event_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        state = get_dashboard_state()
        original_count = len(state['events'])
        state['events'] = [event for event in state['events'] if event.get('id') != event_id]
        if len(state['events']) == original_count:
            return json_error('Event not found.', 404)
        save_dashboard_state(state)
        return flask.jsonify({'state': state})

    # ── Cart ────────────────────────────────────────────────────────────────

    @app.post('/api/dashboard/cart')
    @login_required
    def api_cart_add():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        payload = json_payload()
        item_id = clean_text(payload.get('itemId'))
        state = get_dashboard_state()
        item = find_by_id(state['shopItems'], item_id)
        if not item:
            return json_error('Shop item not found.', 404)
        if item.get('cost') is None:
            return json_error("This item isn't priced yet.")

        try:
            quantity = max(1, int(payload.get('quantity', 1) or 1))
        except (TypeError, ValueError):
            return json_error('Cart quantity must be a number.')
        cart_item = find_by_id(state['cart'], item_id)
        if cart_item:
            cart_item['quantity'] += quantity
        else:
            state['cart'].append({'id': item_id, 'quantity': quantity, 'coinCost': item['cost']})
        save_dashboard_state(state)
        return flask.jsonify({'state': state})

    @app.patch('/api/dashboard/cart/<item_id>')
    @login_required
    def api_cart_update(item_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        payload = json_payload()
        try:
            quantity = max(0, int(payload.get('quantity', 1)))
        except (TypeError, ValueError):
            return json_error('Cart quantity must be a number.')

        state = get_dashboard_state()
        cart_item = find_by_id(state['cart'], item_id)
        if not cart_item:
            return json_error('Cart item not found.', 404)

        if quantity == 0:
            state['cart'] = [item for item in state['cart'] if item.get('id') != item_id]
        else:
            cart_item['quantity'] = quantity
        save_dashboard_state(state)
        return flask.jsonify({'state': state})

    @app.delete('/api/dashboard/cart/<item_id>')
    @login_required
    def api_cart_delete(item_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        state = get_dashboard_state()
        state['cart'] = [item for item in state['cart'] if item.get('id') != item_id]
        save_dashboard_state(state)
        return flask.jsonify({'state': state})

    # ── Checkout ────────────────────────────────────────────────────────────

    @app.post('/api/dashboard/checkout')
    @login_required
    def api_cart_checkout():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        state = get_dashboard_state()
        if not state['cart']:
            return json_error('Add at least one item before submitting a request.')

        total = sum(item['coinCost'] * item['quantity'] for item in state['cart'])
        if total > coin_balance(state.get('ledger') or []):
            return json_error("You don't have enough coins for this order.")

        order = {
            'id': _item_id('order'),
            'date': date.today().isoformat(),
            'status': 'Requested',
            'items': [dict(item) for item in state['cart']],
        }
        state['orders'].insert(0, order)
        state['cart'] = []
        item_names = ', '.join(
            (find_by_id(state['shopItems'], item.get('id', '')) or {}).get('name')
            or item.get('id', '')
            for item in order['items']
        )
        award_coins(state, -total, 'shop_order', order['id'], f'Order: {item_names}')
        save_dashboard_state(state)
        return flask.jsonify({'order': order, 'state': state})

    # ── Item requests ───────────────────────────────────────────────────────

    @app.post('/api/dashboard/item-requests')
    @login_required
    def api_item_request_add():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        payload = json_payload()
        name = clean_text(payload.get('name'), max_len=120)
        note = clean_text(payload.get('note'), max_len=300)
        if not name:
            return json_error('What item would you like added?')

        state = get_dashboard_state()
        item_request = {
            'id': _item_id('itemreq'),
            'name': name,
            'note': note,
            'date': date.today().isoformat(),
            'status': 'Submitted',
        }
        state.setdefault('itemRequests', []).insert(0, item_request)
        save_dashboard_state(state)
        return flask.jsonify({'itemRequest': item_request, 'state': state})

    @app.delete('/api/dashboard/item-requests/<request_id>')
    @login_required
    def api_item_request_delete(request_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        state = get_dashboard_state()
        requests_list = state.get('itemRequests') or []
        remaining = [r for r in requests_list if r.get('id') != request_id]
        if len(remaining) == len(requests_list):
            return json_error('Request not found.', 404)
        state['itemRequests'] = remaining
        save_dashboard_state(state)
        return flask.jsonify({'state': state})

    # ── Projects ────────────────────────────────────────────────────────────

    def _handle_image_upload(folder, default_stem):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        file = request.files.get('image')
        if file is None or not file.filename:
            return json_error('Choose an image to upload.')
        data = file.read(MAX_IMAGE_BYTES + 1)
        if not data:
            return json_error('That image is empty.')
        if len(data) > MAX_IMAGE_BYTES:
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
    def api_project_upload_image():
        return _handle_image_upload('projects', 'image')

    @app.post('/api/dashboard/upload-image')
    @login_required
    def api_upload_avatar():
        return _handle_image_upload('avatars', 'avatar')

    @app.post('/api/dashboard/projects')
    @login_required
    def api_project_add():
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
        project = {
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
        }
        state.setdefault('projects', []).insert(0, project)
        save_dashboard_state(state)
        return flask.jsonify({'project': project, 'state': state})

    @app.patch('/api/dashboard/projects/<project_id>')
    @login_required
    def api_project_update(project_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        state = get_dashboard_state()
        project, error = _owned_project_or_error(state, project_id)
        if error:
            return error

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
                missing = []
                if not (project.get('repoUrl') or '').strip():
                    missing.append('a repository URL')
                if not (project.get('demoUrl') or '').strip():
                    missing.append('a demo URL')
                if not (project.get('hackatimeProject') or '').strip():
                    missing.append('a Hackatime project')
                if missing:
                    return json_error('Add ' + _join_missing(missing) + ' before submitting.', 400)
            project['status'] = status

            # Notify admins when project is submitted
            if status == 'Submitted' and was_draft:
                try:
                    notify_admins_of_project_submission(project)
                except Exception as e:
                    current_app.logger.error(f'Failed to send project submission notification: {e}')

        save_dashboard_state(state)
        return flask.jsonify({'project': project, 'state': state})

    @app.delete('/api/dashboard/projects/<project_id>')
    @login_required
    def api_project_delete(project_id):
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
