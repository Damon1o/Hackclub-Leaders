"""Club chat: channels + messages.

All members can read and post; only leaders/mentors manage channels. Channels
and messages ride the same dashboard state as everything else, so they persist
through whichever storage backend is configured (session cookie or Airtable).
"""

import math
import time
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
    viewer_is_leader,
)

# Cap for a no-cursor message fetch, so opening a long channel stays light.
MESSAGE_PAGE_SIZE = 50

# How long a message stays editable/deletable by its (non-leader) author.
EDIT_WINDOW_SECONDS = 5 * 60
DELETE_WINDOW_SECONDS = 24 * 60 * 60

# Per-user message rate limit: at most RATE_LIMIT_MAX posts per window.
RATE_LIMIT_MAX = 10
RATE_LIMIT_WINDOW_SECONDS = 10.0

# Reactions: how long an emoji may be and how many distinct emoji one message
# may carry, to keep the reaction bar bounded.
MAX_REACTION_LEN = 8
MAX_REACTION_EMOJI = 8

# How long a channel topic may be.
MAX_TOPIC_LEN = 120
# Sliding window of recent post timestamps, keyed by author email. This is a
# single-process app, so a module-level dict is enough; reset_rate_limits()
# makes it trivially clearable between tests.
_rate_buckets = {}


def reset_rate_limits():
    _rate_buckets.clear()


def _rate_limit_retry_after(email):
    """Record a post attempt; return retryAfter seconds if the user is over
    the limit, else None."""
    now = time.monotonic()
    recent = [t for t in _rate_buckets.get(email, [])
              if now - t < RATE_LIMIT_WINDOW_SECONDS]
    if len(recent) >= RATE_LIMIT_MAX:
        _rate_buckets[email] = recent
        return max(1, math.ceil(RATE_LIMIT_WINDOW_SECONDS - (now - recent[0])))
    recent.append(now)
    _rate_buckets[email] = recent
    return None


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _channels(state):
    return state.setdefault('channels', [])


def _messages(state):
    return state.setdefault('messages', [])


def _find_message(state, channel_id, message_id):
    message = find_by_id(_messages(state), message_id)
    if message and message.get('channelId') == channel_id:
        return message
    return None


def _within_window(created_at, seconds):
    """True if `created_at` (ISO) is no older than `seconds` ago. Unparseable
    or missing timestamps are treated as outside the window."""
    try:
        dt = datetime.fromisoformat(created_at)
    except (TypeError, ValueError):
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() <= seconds


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

        payload = json_payload()
        fields, error = channel_from_payload(payload, channel)
        if error:
            return json_error(error)

        channel.update(fields)
        # Topic is optional and edited independently: only touch it when the
        # payload carries the key, and an empty string clears it.
        if 'topic' in payload:
            channel['topic'] = clean_text(payload.get('topic'),
                                          max_len=MAX_TOPIC_LEN)
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

        retry_after = _rate_limit_retry_after(_viewer_email())
        if retry_after is not None:
            return flask.jsonify({
                'error': 'You are sending messages too quickly.',
                'retryAfter': retry_after,
            }), 429

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

    @app.delete('/api/dashboard/chat/channels/<channel_id>/messages')
    @login_required
    def api_chat_channel_clear(channel_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error
        role_error = require_leader_api()
        if role_error:
            return role_error

        state = get_dashboard_state()
        if not find_by_id(_channels(state), channel_id):
            return json_error('Channel not found.', 404)
        state['messages'] = [m for m in _messages(state)
                             if m.get('channelId') != channel_id]
        save_dashboard_state(state)
        return flask.jsonify({'cleared': True})

    @app.patch('/api/dashboard/chat/channels/<channel_id>/messages/<message_id>')
    @login_required
    def api_chat_message_update(channel_id, message_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        state = get_dashboard_state()
        if not find_by_id(_channels(state), channel_id):
            return json_error('Channel not found.', 404)
        message = _find_message(state, channel_id, message_id)
        if not message:
            return json_error('Message not found.', 404)

        if (message.get('authorEmail') or '').strip().lower() != _viewer_email():
            return json_error('You can only edit your own messages.', 403)
        if message.get('deleted'):
            return json_error('This message was deleted.', 409)
        # Leaders can edit their own messages at any time; everyone else only
        # within the edit window right after posting.
        if not viewer_is_leader() and not _within_window(
                message.get('createdAt'), EDIT_WINDOW_SECONDS):
            return json_error('The edit window for this message has closed.', 403)

        body = clean_text(json_payload().get('body'), max_len=MAX_MESSAGE_LEN)
        if not body:
            return json_error('Type a message first.')

        message['body'] = body
        message['editedAt'] = _now_iso()
        save_dashboard_state(state)
        return flask.jsonify({'message': message})

    @app.delete('/api/dashboard/chat/channels/<channel_id>/messages/<message_id>')
    @login_required
    def api_chat_message_delete(channel_id, message_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        state = get_dashboard_state()
        if not find_by_id(_channels(state), channel_id):
            return json_error('Channel not found.', 404)
        message = _find_message(state, channel_id, message_id)
        if not message:
            return json_error('Message not found.', 404)

        # Leaders can remove any message; authors can remove their own within
        # the delete window.
        is_author = ((message.get('authorEmail') or '').strip().lower()
                     == _viewer_email())
        if not viewer_is_leader() and not (
                is_author and _within_window(message.get('createdAt'),
                                             DELETE_WINDOW_SECONDS)):
            return json_error('You can only delete your own recent messages.', 403)

        # Soft delete: keep the record so threads stay ordered, but drop the
        # body and flag it so the client can render a placeholder.
        message['deleted'] = True
        message['body'] = ''
        save_dashboard_state(state)
        return flask.jsonify({'message': message})

    # ── Reactions ─────────────────────────────────────────────────────────────

    @app.post('/api/dashboard/chat/channels/<channel_id>/messages/'
              '<message_id>/reactions')
    @login_required
    def api_chat_message_react(channel_id, message_id):
        csrf_error = require_dashboard_csrf()
        if csrf_error:
            return csrf_error

        state = get_dashboard_state()
        if not find_by_id(_channels(state), channel_id):
            return json_error('Channel not found.', 404)
        message = _find_message(state, channel_id, message_id)
        if not message:
            return json_error('Message not found.', 404)
        if message.get('deleted'):
            return json_error('This message was deleted.', 409)

        raw = json_payload().get('emoji')
        emoji = raw.strip() if isinstance(raw, str) else ''
        if not emoji or len(emoji) > MAX_REACTION_LEN:
            return json_error('Pick a single emoji to react with.')

        viewer = _viewer_email()
        reactions = message.setdefault('reactions', {})
        authors = reactions.get(emoji, [])
        if viewer in authors:
            # Toggle off: drop the viewer, and drop the emoji key if it empties.
            authors = [a for a in authors if a != viewer]
            if authors:
                reactions[emoji] = authors
            else:
                reactions.pop(emoji, None)
        else:
            if emoji not in reactions and len(reactions) >= MAX_REACTION_EMOJI:
                return json_error(
                    'This message already has the maximum number of reactions.')
            reactions[emoji] = authors + [viewer]

        # Keep the message tidy: no empty reactions map lingering on it.
        if not reactions:
            message.pop('reactions', None)
        save_dashboard_state(state)
        return flask.jsonify({'message': message})
