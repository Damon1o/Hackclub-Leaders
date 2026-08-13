from datetime import date
from typing import cast

import flask
from flask import current_app, request, session

from .helpers import (
    STATE_SECTIONS,
    Event,
    ItemRequest,
    Member,
    Order,
    _item_id,
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
    notify_leaders_of_event_rsvp,
    send_event_rsvp_confirmation,
)
from .routes_api_projects import register_project_routes
from .routes_api_workshops import register_workshop_routes


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
        member: Member = {
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
        if error or event_data is None:
            return json_error(error or 'Invalid event.')

        state = get_dashboard_state()
        event = cast(Event, {'id': _item_id('event'), **event_data})
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
        if error or event_data is None:
            return json_error(error or 'Invalid event.')

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

    register_workshop_routes(app)


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
        cost = item['cost']
        if cost is None:
            return json_error("This item isn't priced yet.")

        try:
            quantity = max(1, int(payload.get('quantity', 1) or 1))
        except (TypeError, ValueError):
            return json_error('Cart quantity must be a number.')
        cart_item = find_by_id(state['cart'], item_id)
        if cart_item:
            cart_item['quantity'] += quantity
        else:
            state['cart'].append({'id': item_id, 'quantity': quantity, 'coinCost': cost})
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

        order: Order = {
            'id': _item_id('order'),
            'date': date.today().isoformat(),
            'status': 'Requested',
            'items': list(state['cart']),
        }
        state['orders'].insert(0, order)
        state['cart'] = []
        item_names = ', '.join(
            shop_item['name']
            if (shop_item := find_by_id(state['shopItems'], item['id']))
            else item['id']
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
        item_request = cast(
            ItemRequest,
            {
                'id': _item_id('itemreq'),
                'name': name,
                'note': note,
                'date': date.today().isoformat(),
                'status': 'Submitted',
            },
        )
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

    register_project_routes(app, MAX_IMAGE_BYTES)

