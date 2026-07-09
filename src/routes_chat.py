"""Club chat: channels + messages.

All members can read and post; only leaders/mentors manage channels. Channels
and messages ride the same dashboard state as everything else, so they persist
through whichever storage backend is configured (session cookie or Airtable).
"""

from datetime import datetime, timezone

import flask
from flask import request, session

from .helpers import (
    MAX_MESSAGE_LEN,
    _item_id,
    _viewer_email,
    channel_from_payload,
    clean_text,
    find_by_id,
    get_dashboard_state,
    json_error,
    json_payload,
    login_required,
    require_dashboard_csrf,
    require_leader_api,
    save_dashboard_state,
)

# Cap for a no-cursor message fetch, so opening a long channel stays light.
MESSAGE_PAGE_SIZE = 50


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _channels(state):
    return state.setdefault('channels', [])


def _messages(state):
    return state.setdefault('messages', [])


def register(app):
    # ── Channels ────────────────────────────────────────────────────────────

    @app.get('/api/dashboard/chat/channels')
    @login_required
    def api_chat_channels():
        state = get_dashboard_state()
        return flask.jsonify({'channels': _channels(state)})

    @app.post('/api/dashboard/chat/channels')
    @login_required
    def api_chat_channel_add():
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        fields, error = channel_from_payload(json_payload())
        if error:
            return json_error(error)

        state = get_dashboard_state()
        channel = {
            'id': _item_id('channel'),
            'createdBy': _viewer_email(),
            'lastMessageAt': '',
            **fields,
        }
        _channels(state).append(channel)
        save_dashboard_state(state)
        return flask.jsonify({'channel': channel, 'state': state})

    @app.patch('/api/dashboard/chat/channels/<channel_id>')
    @login_required
    def api_chat_channel_update(channel_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        state = get_dashboard_state()
        channel = find_by_id(_channels(state), channel_id)
        if not channel:
            return json_error('Channel not found.', 404)

        fields, error = channel_from_payload(json_payload(), channel)
        if error:
            return json_error(error)

        channel.update(fields)
        save_dashboard_state(state)
        return flask.jsonify({'channel': channel, 'state': state})

    @app.delete('/api/dashboard/chat/channels/<channel_id>')
    @login_required
    def api_chat_channel_delete(channel_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        state = get_dashboard_state()
        channels = _channels(state)
        original_count = len(channels)
        state['channels'] = [c for c in channels if c.get('id') != channel_id]
        if len(state['channels']) == original_count:
            return json_error('Channel not found.', 404)
        # Drop the channel's messages too, so they don't linger orphaned.
        state['messages'] = [m for m in _messages(state)
                             if m.get('channelId') != channel_id]
        save_dashboard_state(state)
        return flask.jsonify({'state': state})

    # ── Messages ────────────────────────────────────────────────────────────

    @app.get('/api/dashboard/chat/channels/<channel_id>/messages')
    @login_required
    def api_chat_messages(channel_id):
        state = get_dashboard_state()
        if not find_by_id(_channels(state), channel_id):
            return json_error('Channel not found.', 404)

        since = clean_text(request.args.get('since'), max_len=40)
        thread = [m for m in _messages(state)
                  if m.get('channelId') == channel_id]
        thread.sort(key=lambda m: m.get('createdAt') or '')
        if since:
            thread = [m for m in thread if (m.get('createdAt') or '') > since]
            return flask.jsonify({'messages': thread, 'hasMore': False})
        has_more = len(thread) > MESSAGE_PAGE_SIZE
        return flask.jsonify({'messages': thread[-MESSAGE_PAGE_SIZE:],
                              'hasMore': has_more})

    @app.post('/api/dashboard/chat/channels/<channel_id>/messages')
    @login_required
    def api_chat_message_add(channel_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        state = get_dashboard_state()
        channel = find_by_id(_channels(state), channel_id)
        if not channel:
            return json_error('Channel not found.', 404)

        body = clean_text(json_payload().get('body'), max_len=MAX_MESSAGE_LEN)
        if not body:
            return json_error('Type a message first.')

        user = session.get('user') or {}
        created_at = _now_iso()
        message = {
            'id': _item_id('msg'),
            'channelId': channel_id,
            'authorEmail': _viewer_email(),
            'authorName': user.get('name') or _viewer_email(),
            'authorAvatar': user.get('avatar') or '',
            'body': body,
            'createdAt': created_at,
        }
        _messages(state).append(message)
        channel['lastMessageAt'] = created_at
        save_dashboard_state(state)
        # Deliberately omit full state: the client polls messages separately,
        # and returning state here would trigger a heavy full-page re-render.
        return flask.jsonify({'message': message})
