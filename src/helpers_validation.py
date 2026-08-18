"""Payload validation and construction helpers for Hack Club Leaders Portal."""

import math
import os
import re
from datetime import date
from typing import Any, Final

from flask import jsonify, request

DEFAULT_PAGE_SIZE: Final[int] = 25
MAX_PAGE_SIZE: Final[int] = 200
EVENT_REPEAT_OPTIONS: Final[set[str]] = {'', 'daily', 'weekly', 'biweekly', 'monthly', 'weekdays'}
ADMIN_REVIEW_STATUSES: Final[set[str]] = {'Shipped', 'Draft'}
DEFAULT_LANGUAGE: Final[str] = 'en'

# Chat auto-moderation: messages containing any of these words get flagged for
# admin review instead of being posted silently. Keep it small and obvious —
# the point is to surface the worst cases, not to replace human judgment.
AUTO_FLAG_WORDS: Final[tuple[str, ...]] = (
    'fuck',
    'shit',
    'bitch',
    'cunt',
    'nigger',
    'faggot',
    'retard',
    'free robux',
    'join my discord',
)

# Shared catalog path — helpers_shop resolves it through helpers at call time so
# tests can monkeypatch src.helpers.SHOP_JSON_PATH and reach the shop writer.
SHOP_JSON_PATH: Final[str] = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'static',
    'data',
    'shop.json',
)

def find_by_id(items: Any, item_id: str) -> Any:
    if not items or not isinstance(items, list):
        return None
    return next((item for item in items if isinstance(item, dict) and item.get('id') == item_id), None)


def clean_text(value: Any, fallback: str = '', max_len: int = 300) -> str:
    if value is None:
        return fallback
    return str(value).strip()[:max_len]


def auto_flag_reasons(body: str) -> str:
    """Return a comma-joined list of matched blocklist words, or '' if clean."""
    text = (body or '').lower()
    hits = [word for word in AUTO_FLAG_WORDS if re.search(rf'\b{re.escape(word)}\b', text)]
    return ', '.join(hits)


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {'1', 'true', 'yes', 'on'}


def _positive_int(raw: Any, default: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, min(value, maximum))


def paginate(
    items: list[Any],
    page: int | None = None,
    per_page: int | None = None,
) -> dict[str, Any]:
    args = request.args if request else {}
    per_page = per_page or _positive_int(args.get('per_page'), DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE)
    total = len(items)
    pages = max(1, math.ceil(total / per_page))
    page = page or _positive_int(args.get('page'), 1, pages)
    page = min(page, pages)
    start = (page - 1) * per_page
    return {
        'items': items[start : start + per_page],
        'page': page,
        'perPage': per_page,
        'total': total,
        'pages': pages,
        'hasMore': start + per_page < total,
    }


def json_payload() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def json_error(message: str, status: int = 400) -> tuple[Any, int]:
    return jsonify({'error': message}), status


def parse_repeat(value: Any, fallback: str = '') -> str:
    code = str(value or '').strip().lower()
    return code if code in EVENT_REPEAT_OPTIONS else fallback


def event_from_payload(
    payload: dict[str, Any], existing: dict[str, Any] | None = None
) -> tuple[dict[str, Any] | None, str | None]:
    existing = existing or {}
    title = clean_text(payload.get('title'), existing.get('title', ''))
    event_date = clean_text(payload.get('date'), existing.get('date', ''))
    event_time = clean_text(payload.get('time'), existing.get('time', ''))
    location = clean_text(payload.get('location'), existing.get('location', ''))
    event_type = clean_text(payload.get('type'), existing.get('type', 'Workshop'))
    repeat = parse_repeat(payload.get('repeat'), existing.get('repeat', ''))
    attendees = payload.get('attendees', existing.get('attendees', 0))

    if not title:
        return None, 'Event title is required.'
    try:
        date.fromisoformat(event_date)
    except ValueError:
        return None, 'Choose a valid event date.'
    if not event_time:
        return None, 'Event time is required.'
    if not location:
        return None, 'Event location is required.'
    try:
        attendees = max(0, int(attendees))
    except (TypeError, ValueError):
        attendees = existing.get('attendees', 0)

    return {
        'id': existing.get('id', ''),
        'title': title,
        'date': event_date,
        'time': event_time,
        'location': location,
        'type': event_type,
        'repeat': repeat,
        'rsvp': parse_bool(payload.get('rsvp', existing.get('rsvp', False))),
        'attendees': attendees,
    }, None


def workshop_from_payload(payload: dict[str, Any]) -> tuple[dict[str, str] | None, str | None]:
    title = clean_text(payload.get('title'), max_len=120)
    description = clean_text(payload.get('description'), max_len=2000)
    if not title:
        return None, 'Workshop title is required.'
    if not description:
        return None, 'Workshop description is required.'
    return {'title': title, 'description': description}, None


def channel_from_payload(
    payload: dict[str, Any], existing: dict[str, Any] | None = None
) -> tuple[dict[str, str] | None, str | None]:
    existing = existing or {}
    name = clean_text(payload.get('name'), existing.get('name', ''), max_len=60).lstrip('#').strip()
    description = clean_text(
        payload.get('description'), existing.get('description', ''), max_len=140
    )
    if not name:
        return None, 'Channel name is required.'
    return {'name': name, 'description': description}, None


def _persist_club(backend: Any, club_key: str, state: Any) -> None:
    from .storage import SessionStorage
    if isinstance(backend, SessionStorage):
        backend.save(club_key, state)
    else:
        persisted = {key: value for key, value in state.items() if key not in ('shopItems', 'cart')}
        backend.save(club_key, persisted)


def _load_admin_club(
    backend: Any, club_key: str
) -> tuple[Any | None, tuple[Any, int] | None]:
    state = backend.load(club_key)
    if state is None:
        return None, json_error('Club not found.', 404)
    return state, None


def _find_club_by_project(backend: Any, project_id: str) -> tuple[Any | None, str | None]:
    for club in backend.list_clubs():
        club_key = club.get('clubKey', '')
        state = backend.load(club_key)
        if state is None:
            continue
        if find_by_id(state.get('projects') or [], project_id):
            return state, club_key
    return None, None
