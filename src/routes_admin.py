from datetime import date, timedelta

import flask
from flask import current_app, flash, redirect, session, url_for

from .helpers import (
    ADMIN_REVIEW_STATUSES,
    COINS_PER_APPROVED_SHIP,
    _find_club_by_project,
    _load_admin_club,
    _persist_club,
    _positive_int,
    _storage,
    add_shop_item,
    admin_required,
    award_coins,
    ban_email,
    clean_text,
    find_by_id,
    json_error,
    json_payload,
    load_banned_emails,
    load_shop_items,
    log_action,
    paginate,
    parse_bool,
    remove_shop_item,
    require_admin_api,
    require_dashboard_csrf,
    unban_email,
    update_shop_item,
)
from .notifications import notify_owner_of_project_review


def _admin_email() -> str:
    return (session.get('user') or {}).get('email') or 'admin'


def register(app):
    # ── Admin pages ─────────────────────────────────────────────────────────

    @app.route('/dashboard/admin')
    @admin_required
    def dashboard_admin():
        """?page= and ?per_page= page the club list; ?projects_page= pages the
        review queue independently, so paging one doesn't reset the other."""
        backend = _storage()
        all_clubs = backend.list_clubs()
        # Headline metrics count every club, not just the page on screen.
        total_members = sum(club.get('memberCount') or 0 for club in all_clubs)
        clubs = paginate(all_clubs)
        projects = paginate(
            backend.list_pending_projects(),
            page=_positive_int(flask.request.args.get('projects_page'), 1, 10_000),
        )
        week_ago = (date.today() - timedelta(days=7)).isoformat()
        ships_this_week = 0
        for club in all_clubs:
            if not club.get('clubKey'):
                continue
            state = backend.load(club['clubKey'], sections=['projects'])
            if not state:
                continue
            for project in state.get('projects') or []:
                if project.get('status') == 'Shipped' and (project.get('date') or '') >= week_ago:
                    ships_this_week += 1
        open_reports = sum(
            1
            for entry in backend.list_reports()
            if (entry.get('report') or {}).get('status', 'Open') == 'Open'
        )
        return flask.render_template(
            'dashboard/admin.html',
            clubs=clubs['items'],
            clubs_page=clubs,
            pending_projects=projects['items'],
            pending_projects_page=projects,
            total_members=total_members,
            ships_this_week=ships_this_week,
            orders_count=len(backend.list_orders()),
            open_reports=open_reports,
            shop_items=load_shop_items(),
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
        if error or state is None:
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
        settings['website'] = website
        settings['avatar'] = avatar

        # Structured-address fields aren't in the admin form yet, so only
        # touch keys the payload actually sends — otherwise a plain
        # clubName/website/avatar save from admin_club.html would blank out
        # venue/address/bio the leader already entered via settings.
        text_fields = {
            'venue': 120,
            'addressLine1': 120,
            'addressLine2': 120,
            'city': 80,
            'state': 80,
            'zip': 20,
            'country': 80,
            'meetingDay': 20,
            'clubBio': 500,
        }
        for key, max_len in text_fields.items():
            if key in payload:
                settings[key] = clean_text(payload.get(key), max_len=max_len)

        if 'city' in payload or 'state' in payload:
            settings['location'] = ', '.join(
                filter(None, [settings.get('city', ''), settings.get('state', '')])
            )
        elif 'location' in payload:
            settings['location'] = clean_text(payload.get('location'))

        if 'publicDirectory' in payload:
            settings['publicDirectory'] = parse_bool(payload.get('publicDirectory'))
        log_action(state, _admin_email(), 'club_profile_updated')
        _persist_club(backend, club_key, state)
        return flask.jsonify({'club': state})

    @app.patch('/api/admin/clubs/<club_key>/coins')
    def api_admin_club_coins(club_key):
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        club_key = (club_key or '').strip().lower()
        backend = _storage()
        state, error = _load_admin_club(backend, club_key)
        if error or state is None:
            return error

        payload = json_payload()
        try:
            delta = int(payload.get('delta'))
        except (TypeError, ValueError):
            return json_error('Delta must be a whole number.')
        reason = clean_text(payload.get('reason'), max_len=200)
        if not reason:
            return json_error('A reason is required.')
        tx = award_coins(state, delta, 'admin_adjust', '', f'Admin: {reason}')
        log_action(state, _admin_email(), f'coins_adjusted: {delta}', reason)
        _persist_club(backend, club_key, state)
        return flask.jsonify({'transaction': tx, 'coinBalance': state.get('settings', {}).get('coinBalance', 0)})

    @app.patch('/api/admin/clubs/<club_key>/members/<member_id>')
    def api_admin_member_update(club_key, member_id):
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        club_key = (club_key or '').strip().lower()
        backend = _storage()
        state, error = _load_admin_club(backend, club_key)
        if error or state is None:
            return error

        member = find_by_id(state.get('members') or [], member_id)
        if not member:
            return json_error('Member not found.', 404)

        payload = json_payload()
        role = clean_text(payload.get('role'), member.get('role', 'Member')).title()
        if role not in {'Leader', 'Member', 'Mentor'}:
            return json_error('Choose Leader, Member, or Mentor.')

        leaders = [m for m in (state.get('members') or []) if m.get('role') == 'Leader']
        if member.get('role') == 'Leader' and role != 'Leader' and len(leaders) == 1:
            return json_error('A club needs at least one leader.')
        member['role'] = role
        if 'status' in payload:
            status = clean_text(payload.get('status'), member.get('status', 'Active')).title()
            if status not in {'Active', 'Invited'}:
                return json_error('Choose Active or Invited status.')
            member['status'] = status
        log_action(state, _admin_email(), f'member_role_set: {role}', member_id)
        _persist_club(backend, club_key, state)
        return flask.jsonify({'member': member})

    @app.delete('/api/admin/clubs/<club_key>/members/<member_id>')
    def api_admin_member_delete(club_key, member_id):
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        club_key = (club_key or '').strip().lower()
        backend = _storage()
        state, error = _load_admin_club(backend, club_key)
        if error or state is None:
            return error

        members = state.get('members') or []
        target = find_by_id(members, member_id)
        leaders = [m for m in members if m.get('role') == 'Leader']
        if target and target.get('role') == 'Leader' and len(leaders) == 1:
            return json_error('A club needs at least one leader.')
        remaining = [m for m in members if m.get('id') != member_id]
        if len(remaining) == len(members):
            return json_error('Member not found.', 404)
        state['members'] = remaining
        log_action(state, _admin_email(), 'member_removed', member_id)
        _persist_club(backend, club_key, state)
        return flask.jsonify({'removed': member_id})

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
        assert state is not None  # nosec B101

        project = find_by_id(state.get('projects') or [], project_id)
        if not project:
            return json_error('Project not found.', 404)

        payload = json_payload()
        status = clean_text(payload.get('status')).title()
        if status not in ADMIN_REVIEW_STATUSES:
            return json_error('Status must be Shipped or Draft.')

        old_status = project.get('status')
        project['status'] = status

        coins_awarded = 0
        if status != old_status:
            if status == 'Shipped':
                coins_awarded = COINS_PER_APPROVED_SHIP
                award_coins(
                    state,
                    coins_awarded,
                    'ship_approved',
                    project_id,
                    f'Approved: {project.get("name", "Untitled")}',
                )
            try:
                notify_owner_of_project_review(state, project, status == 'Shipped')
            except Exception as exc:
                current_app.logger.error(f'Failed to send project review notification: {exc}')

        log_action(state, _admin_email(), f'project_reviewed: {status}', project_id)
        _persist_club(backend, club_key, state)
        return flask.jsonify({'project': project, 'coinsAwarded': coins_awarded})

    # ── Item requests ─────────────────────────────────────────────────────────

    @app.get('/api/admin/item-requests')
    def api_admin_item_requests():
        """?page= / ?per_page= page the queue. `itemRequests` stays in the
        response under its original name so existing clients keep working."""
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        page = paginate(_storage().list_item_requests())
        return flask.jsonify({'itemRequests': page.pop('items'), **page})

    @app.patch('/api/admin/item-requests/<club_key>/<request_id>')
    def api_admin_item_request_review(club_key, request_id):
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        club_key = (club_key or '').strip().lower()
        backend = _storage()
        state, error = _load_admin_club(backend, club_key)
        if error or state is None:
            return error

        requests_list = state.get('itemRequests') or []
        item_request = find_by_id(requests_list, request_id)
        if not item_request:
            return json_error('Item request not found.', 404)

        decision = clean_text(json_payload().get('status')).lower()
        if decision == 'approved':
            item_request['status'] = 'Approved'
            # Auto-create a shop entry the admin can price/edit later. A
            # duplicate name just means it's already in the shop — approval
            # still stands, so swallow that.
            shop_item = None
            try:
                shop_item = add_shop_item(item_request.get('name'), 'TBD', '', 'Merch')
            except ValueError:
                pass
            log_action(state, _admin_email(), 'item_request_approved', request_id)
            _persist_club(backend, club_key, state)
            return flask.jsonify({'request': item_request, 'shopItem': shop_item})
        if decision == 'rejected':
            state['itemRequests'] = [r for r in requests_list if r.get('id') != request_id]
            log_action(state, _admin_email(), 'item_request_rejected', request_id)
            _persist_club(backend, club_key, state)
            return flask.jsonify({'request': {'id': request_id, 'status': 'Rejected'}})
        return json_error('Status must be approved or rejected.')

    # ── Chat moderation ───────────────────────────────────────────────────────

    @app.get('/api/admin/chat/messages')
    def api_admin_chat_messages():
        """?flagged=1 lists only auto-flagged messages; otherwise all recent
        ones. ?page= / ?per_page= page the result."""
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        flagged_only = parse_bool(flask.request.args.get('flagged', ''))
        page = paginate(_storage().list_messages(flagged_only=flagged_only))
        return flask.jsonify({'messages': page.pop('items'), **page})

    @app.delete('/api/admin/chat/messages/<club_key>/<message_id>')
    def api_admin_chat_message_delete(club_key, message_id):
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        club_key = (club_key or '').strip().lower()
        backend = _storage()
        state, error = _load_admin_club(backend, club_key)
        if error or state is None:
            return error

        message = find_by_id(state.get('messages') or [], message_id)
        if not message:
            return json_error('Message not found.', 404)
        message['deleted'] = True
        message['deletedByAdmin'] = True
        message['body'] = ''
        log_action(state, _admin_email(), 'chat_message_deleted', message_id)
        _persist_club(backend, club_key, state)
        return flask.jsonify({'message': message})

    @app.patch('/api/admin/chat/messages/<club_key>/<message_id>')
    def api_admin_chat_message_dismiss(club_key, message_id):
        """Clear the auto-flag on a message without deleting it."""
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        club_key = (club_key or '').strip().lower()
        backend = _storage()
        state, error = _load_admin_club(backend, club_key)
        if error or state is None:
            return error

        message = find_by_id(state.get('messages') or [], message_id)
        if not message:
            return json_error('Message not found.', 404)
        message.pop('autoFlagged', None)
        message.pop('flagReason', None)
        log_action(state, _admin_email(), 'chat_flag_dismissed', message_id)
        _persist_club(backend, club_key, state)
        return flask.jsonify({'message': message})

    # ── Banned emails ─────────────────────────────────────────────────────────

    @app.get('/api/admin/banned-emails')
    def api_admin_banned_emails():
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        return flask.jsonify({'bannedEmails': load_banned_emails()})

    @app.post('/api/admin/banned-emails')
    def api_admin_banned_email_add():
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        email = clean_text(json_payload().get('email'), max_len=120)
        try:
            added = ban_email(email)
        except ValueError as exc:
            return json_error(str(exc))
        return flask.jsonify({'banned': email, 'added': added})

    @app.delete('/api/admin/banned-emails/<path:email>')
    def api_admin_banned_email_remove(email):
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        if not unban_email(email):
            return json_error('That email is not banned.', 404)
        return flask.jsonify({'unbanned': (email or '').strip().lower()})

    # ── Reports ──────────────────────────────────────────────────────────────

    @app.get('/api/admin/reports')
    def api_admin_reports():
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        return flask.jsonify({'reports': _storage().list_reports()})

    @app.patch('/api/admin/reports/<club_key>/<report_id>')
    def api_admin_report_review(club_key, report_id):
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        club_key = (club_key or '').strip().lower()
        backend = _storage()
        state, error = _load_admin_club(backend, club_key)
        if error or state is None:
            return error

        report = find_by_id(state.get('reports') or [], report_id)
        if not report:
            return json_error('Report not found.', 404)

        status = clean_text(json_payload().get('status')).title()
        if status not in ('Open', 'Resolved', 'Dismissed'):
            return json_error('Status must be Open, Resolved, or Dismissed.')
        report['status'] = status
        log_action(state, _admin_email(), f'report_{status.lower()}', report_id)
        _persist_club(backend, club_key, state)
        return flask.jsonify({'report': report})

    # ── Orders ───────────────────────────────────────────────────────────────

    @app.get('/api/admin/orders')
    def api_admin_orders():
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        return flask.jsonify({'orders': _storage().list_orders()})

    @app.patch('/api/admin/orders/<club_key>/<order_id>')
    def api_admin_order_fulfill(club_key, order_id):
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        club_key = (club_key or '').strip().lower()
        backend = _storage()
        state, error = _load_admin_club(backend, club_key)
        if error or state is None:
            return error

        order = find_by_id(state.get('orders') or [], order_id)
        if not order:
            return json_error('Order not found.', 404)

        status = clean_text(json_payload().get('status')).title()
        if status not in ('Requested', 'Fulfilled', 'Shipped', 'Cancelled'):
            return json_error('Status must be Requested, Fulfilled, Shipped, or Cancelled.')
        order['status'] = status
        log_action(state, _admin_email(), f'order_{status.lower()}', order_id)
        _persist_club(backend, club_key, state)
        return flask.jsonify({'order': order})

    # ── Shop catalog ──────────────────────────────────────────────────────────
    @app.post('/api/admin/shop-items')
    def api_admin_shop_item_add():
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        payload = json_payload()
        name = clean_text(payload.get('name'), max_len=120)
        cost = clean_text(payload.get('cost'), max_len=20)
        item_filter = clean_text(payload.get('filter'), max_len=20)
        image = clean_text(payload.get('image'), max_len=500)
        if image and not image.startswith(('http://', 'https://', '/static/')):
            return json_error('Image URL must start with http://, https://, or /static/.')
        try:
            item = add_shop_item(name, cost, image, item_filter)
        except ValueError as exc:
            return json_error(str(exc))
        return flask.jsonify({'shopItem': item})

    @app.delete('/api/admin/shop-items/<slug>')
    def api_admin_shop_item_delete(slug):
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        if not remove_shop_item(slug):
            return json_error('Shop item not found.', 404)
        return flask.jsonify({'removed': (slug or '').strip()})

    @app.patch('/api/admin/shop-items/<slug>')
    def api_admin_shop_item_update(slug):
        admin_error = require_admin_api()
        if admin_error:
            return admin_error
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        payload = json_payload()
        name = clean_text(payload.get('name'), max_len=120)
        cost = clean_text(payload.get('cost'), max_len=20)
        item_filter = clean_text(payload.get('filter'), max_len=20)
        image = clean_text(payload.get('image'), max_len=500)
        if image and not image.startswith(('http://', 'https://', '/static/')):
            return json_error('Image URL must start with http://, https://, or /static/.')
        try:
            item = update_shop_item(slug, name, cost, image, item_filter)
        except ValueError as exc:
            return json_error(str(exc))
        if item is None:
            return json_error('Shop item not found.', 404)
        return flask.jsonify({'shopItem': item})
