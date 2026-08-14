"""Club chat: channels + messages.

All members can read and post; only leaders/mentors manage channels. Channels
and messages ride the same dashboard state as everything else, so they persist
through whichever storage backend is configured (session cookie or Airtable).
"""

import ipaddress
import math
import re
import socket
import time
import urllib.parse
from datetime import datetime, timezone
from html.parser import HTMLParser

import flask
import requests
from flask import request, session

from .helpers import (
    MAX_MESSAGE_LEN,
    _club_key,
    _item_id,
    _storage,
    _viewer_email,
    channel_from_payload,
    clean_text,
    feature_enabled,
    find_by_id,
    get_dashboard_state,
    json_error,
    json_payload,
    login_required,
    require_dashboard_csrf,
    require_leader_api,
    save_dashboard_state,
    utc_iso,
    viewer_is_leader,
)
from .notifications import add_in_app_notification

# Cap for a no-cursor message fetch, so opening a long channel stays light.
MESSAGE_PAGE_SIZE = 50
# Ceiling on ?limit=, so a client can't ask for a whole channel in one go.
MAX_MESSAGE_PAGE_SIZE = 200

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
_rate_buckets: dict[str, list[float]] = {}


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


# ── Link previews ─────────────────────────────────────────────────────────────
# The server fetches user-posted URLs, so every request is SSRF-guarded:
# http/https only, public IPs only (re-checked per redirect hop), 3s timeout,
# 500KB read cap. Every failure path returns None — previews are best-effort.

_URL_RE = re.compile(r'https?://[^\s<>"\']+')
PREVIEW_TIMEOUT = 3
PREVIEW_MAX_BYTES = 500 * 1024
PREVIEW_MAX_REDIRECTS = 3


def first_url(text):
    match = _URL_RE.search(text or '')
    return match.group(0) if match else ''


def _host_is_public(hostname):
    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError:
        return False
    if not infos:
        return False
    return all(ipaddress.ip_address(info[4][0]).is_global for info in infos)


class _OgParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.og = {}
        self.title = ''
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == 'meta':
            attrs = dict(attrs)
            prop = (attrs.get('property') or attrs.get('name') or '').lower()
            if prop.startswith('og:') and attrs.get('content'):
                self.og.setdefault(prop[3:], attrs['content'])
        elif tag == 'title':
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == 'title':
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and len(self.title) < 300:
            self.title += data


def fetch_link_preview(url):
    original = url
    for _hop in range(PREVIEW_MAX_REDIRECTS + 1):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            return None
        if not _host_is_public(parsed.hostname):
            return None
        try:
            response = requests.get(
                url,
                timeout=PREVIEW_TIMEOUT,
                stream=True,
                allow_redirects=False,
                headers={'User-Agent': 'HackclubLeaders/1.0 (+link-preview)'},
            )
        except requests.RequestException:
            return None
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get('Location', '')
            if not location:
                return None
            url = urllib.parse.urljoin(url, location)
            continue
        if response.status_code != 200:
            return None
        if 'text/html' not in (response.headers.get('Content-Type') or ''):
            return None
        try:
            chunk = next(response.iter_content(PREVIEW_MAX_BYTES), b'') or b''
        except requests.RequestException:
            return None
        parser = _OgParser()
        try:
            parser.feed(chunk.decode(response.encoding or 'utf-8', 'replace'))
        except Exception:
            return None
        title = clean_text(parser.og.get('title') or parser.title.strip(), max_len=200)
        if not title:
            return None
        return {
            'url': original,
            'title': title,
            'description': clean_text(parser.og.get('description'), max_len=300),
            'image': clean_text(parser.og.get('image'), max_len=500),
        }
    return None



def _channels(state):
    return state.setdefault('channels', [])


def _messages(state):
    return state.setdefault('messages', [])


def _find_message(state, channel_id, message_id):
    message = find_by_id(_messages(state), message_id)
    if message and message.get('channelId') == channel_id:
        return message
    return None


def _page_limit(raw):
    """A sane page size from an untrusted ?limit= value."""
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        return MESSAGE_PAGE_SIZE
    return max(1, min(limit, MAX_MESSAGE_PAGE_SIZE))


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


_EVERYONE_RE = re.compile(r'(?<![\w@])@everyone(?![\w])')


def resolve_mentions(body, members, author_email, author_is_leader):
    """Resolve @-mentions in `body` against the club's member list.

    Returns (sorted emails to notify, excluding the author; whether
    @everyone was honored). A name only matches when preceded by a literal
    '@' with no other word character immediately before it, so
    "jane@test.com" does not match a member named "Jane".
    """
    author_email = (author_email or '').strip().lower()
    text = body or ''
    matched_emails = set()

    # Longest name first, blanking each match out of the text as it is
    # consumed, so "@Jane Doe" resolves to Jane Doe and never also to a
    # separate member literally named "Jane".
    emails_by_name: dict[str, list[str]] = {}
    for member in members:
        name, email = member.get('name'), member.get('email')
        if name and email:
            emails_by_name.setdefault(name, []).append(email.strip().lower())

    for name in sorted(emails_by_name, key=len, reverse=True):
        pattern = re.compile(r'(?<![\w@])@' + re.escape(name) + r'(?![\w])')
        text, hits = pattern.subn('\x00', text)
        if hits:
            matched_emails.update(emails_by_name[name])

    matched_emails.discard(author_email)

    mentions_everyone = bool(author_is_leader and _EVERYONE_RE.search(text))
    return sorted(matched_emails), mentions_everyone


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
        channel: dict[str, str] = {
            'id': _item_id('channel'),
            'createdBy': _viewer_email(),
            'lastMessageAt': '',
            'name': (fields or {}).get('name', ''),
            'description': (fields or {}).get('description', ''),
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
        state['messages'] = [m for m in _messages(state) if m.get('channelId') != channel_id]
        save_dashboard_state(state)
        return flask.jsonify({'state': state})

    # ── Messages ────────────────────────────────────────────────────────────

    @app.get('/api/dashboard/chat/channels/<channel_id>/messages')
    @login_required
    def api_chat_messages(channel_id):
        """One page of a channel's thread, oldest message first.

        ?since=<iso>   everything newer than this timestamp (the poll path)
        ?before=<iso>  the page immediately older than this timestamp
        ?limit=<n>     page size, capped at MAX_MESSAGE_PAGE_SIZE

        `hasMore` reports whether older messages exist before the page
        returned, which is what the client's scroll-up loader keys off.
        """
        since = clean_text(request.args.get('since'), max_len=40)
        before = clean_text(request.args.get('before'), max_len=40)
        limit = _page_limit(request.args.get('limit'))

        backend = _storage()
        pager = getattr(backend, 'page_messages', None)
        if pager is not None:
            # Backend can page in the database — don't load the channel's
            # history into the process just to slice the tail off it.
            state = get_dashboard_state(['members', 'channels'])
            if not find_by_id(_channels(state), channel_id):
                return json_error('Channel not found.', 404)
            messages, has_more = pager(_club_key(), channel_id, limit, before, since)
            return flask.jsonify({'messages': messages, 'hasMore': has_more})

        state = get_dashboard_state()
        if not find_by_id(_channels(state), channel_id):
            return json_error('Channel not found.', 404)

        thread = [m for m in _messages(state) if m.get('channelId') == channel_id]
        thread.sort(key=lambda m: m.get('createdAt') or '')
        if since:
            thread = [m for m in thread if (m.get('createdAt') or '') > since]
            return flask.jsonify({'messages': thread, 'hasMore': False})
        if before:
            thread = [m for m in thread if (m.get('createdAt') or '') < before]
        has_more = len(thread) > limit
        return flask.jsonify({'messages': thread[-limit:], 'hasMore': has_more})

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
        created_at = utc_iso()
        message = {
            'id': _item_id('msg'),
            'channelId': channel_id,
            'authorEmail': _viewer_email(),
            'authorName': user.get('name') or _viewer_email(),
            'authorAvatar': user.get('avatar') or '',
            'body': body,
            'createdAt': created_at,
        }
        mention_emails, mentions_everyone = resolve_mentions(
            body, state.get('members', []), _viewer_email(), viewer_is_leader()
        )
        message['mentions'] = mention_emails
        message['mentionsEveryone'] = mentions_everyone
        if body and feature_enabled('FEATURE_CHAT_LINK_PREVIEWS'):
            url = first_url(body)
            if url:
                preview = fetch_link_preview(url)
                if preview:
                    message['linkPreview'] = preview
        _messages(state).append(message)
        channel['lastMessageAt'] = created_at

        recipients = set(mention_emails)
        if mentions_everyone:
            recipients.update((m.get('email') or '').strip().lower()
                              for m in state.get('members', []))
        recipients.discard(_viewer_email())
        channel_name = channel.get('name') or 'the channel'
        for recipient in sorted(filter(None, recipients)):
            add_in_app_notification(
                recipient,
                'chat_mention',
                f"{message['authorName']} mentioned you in #{channel_name}",
                body[:200],
                {'channelId': channel_id, 'messageId': message['id']},
                state=state,
            )
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
        message['editedAt'] = utc_iso()
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
