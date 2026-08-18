"""Storage backends for the dashboard state.

The app talks to one of three backends, chosen by the STORAGE_BACKEND env var:

  session   (default) — state lives in the signed session cookie, exactly as
            before. Zero setup, single-player, ~2.8KB cap.
  airtable  — state lives in an Airtable base shared by the whole club.
            Requires AIRTABLE_TOKEN and AIRTABLE_BASE_ID.
  mongo     — state lives in MongoDB (src/storage_mongo.py). Requires
            MONGODB_URI. Import existing Airtable data with
            `python scripts/seed_mongo.py`.

Both backends expose the same three methods:

  resolve_club_key(viewer_email) -> str   which club this viewer belongs to
  load(club_key) -> dict | None           None means "no club yet, seed one"
  save(club_key, state)                   persist a full state dict
"""

import os
from typing import Any, Final, cast

# Re-export AirtableStorage from storage_airtable
from .storage_airtable import (
    CHANNEL_FIELDS as CHANNEL_FIELDS,
)
from .storage_airtable import (
    EVENT_FIELDS as EVENT_FIELDS,
)
from .storage_airtable import (
    ITEM_REQUEST_FIELDS as ITEM_REQUEST_FIELDS,
)
from .storage_airtable import (
    LEDGER_FIELDS as LEDGER_FIELDS,
)
from .storage_airtable import (
    MEMBER_FIELDS as MEMBER_FIELDS,
)
from .storage_airtable import (
    MESSAGE_FIELDS as MESSAGE_FIELDS,
)
from .storage_airtable import (
    NEWSLETTER_FIELDS as NEWSLETTER_FIELDS,
)
from .storage_airtable import (
    NOTIFICATION_FIELDS as NOTIFICATION_FIELDS,
)
from .storage_airtable import (
    ORDER_FIELDS as ORDER_FIELDS,
)
from .storage_airtable import (
    PROJECT_FIELDS as PROJECT_FIELDS,
)
from .storage_airtable import (
    SETTINGS_FIELDS as SETTINGS_FIELDS,
)
from .storage_airtable import (
    SETTINGS_INT_KEYS as SETTINGS_INT_KEYS,
)
from .storage_airtable import (
    WORKSHOP_FIELDS as WORKSHOP_FIELDS,
)
from .storage_airtable import (
    AirtableStorage as AirtableStorage,
)
from .storage_airtable import (
    StorageError as StorageError,
)

SHIPPED_STATUS: Final[str] = 'Shipped'
SUBMITTED_STATUS: Final[str] = 'Submitted'


class SessionStorage:
    """Today's behavior: the whole state rides in the session cookie."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def resolve_club_key(self, viewer_email: str) -> str:
        return (viewer_email or '').strip().lower()

    def load(self, club_key: str, sections: list[str] | None = None) -> dict[str, Any] | None:
        return cast(dict[str, Any] | None, self._session.get('dashboard_state'))

    def load_lite(self, club_key: str) -> dict[str, Any] | None:
        return cast(dict[str, Any] | None, self._session.get('dashboard_state'))

    def save(self, club_key: str, state: dict[str, Any]) -> None:
        self._session['dashboard_state'] = state
        self._session.modified = True

    def find_club_by_join_code(self, code: str) -> str | None:
        return None

    def find_club_by_member_email(self, email: str) -> str | None:
        return None

    def list_clubs(self) -> list[dict[str, Any]]:
        state = self._session.get('dashboard_state')
        if not state:
            return []
        settings = state.get('settings') or {}
        projects = state.get('projects') or []
        return [
            {
                'clubKey': self.resolve_club_key(
                    (self._session.get('user') or {}).get('email') or ''
                ),
                'clubName': settings.get('clubName') or 'Club',
                'location': settings.get('location') or '',
                'memberCount': len(state.get('members') or []),
                'shipCount': sum(1 for p in projects if p.get('status') == SHIPPED_STATUS),
                'pendingShips': sum(1 for p in projects if p.get('status') == SUBMITTED_STATUS),
            }
        ]

    def list_pending_projects(self) -> list[dict[str, Any]]:
        clubs = self.list_clubs()
        club_key = clubs[0]['clubKey'] if clubs else ''
        club_name = clubs[0]['clubName'] if clubs else ''
        state = self._session.get('dashboard_state') or {}
        return [
            {'clubKey': club_key, 'clubName': club_name, 'project': project}
            for project in state.get('projects') or []
            if project.get('status') == SUBMITTED_STATUS
        ]

    def list_item_requests(self) -> list[dict[str, Any]]:
        clubs = self.list_clubs()
        club_key = clubs[0]['clubKey'] if clubs else ''
        club_name = clubs[0]['clubName'] if clubs else ''
        state = self._session.get('dashboard_state') or {}
        return [
            {'clubKey': club_key, 'clubName': club_name, 'request': request}
            for request in state.get('itemRequests') or []
        ]

    def list_orders(self) -> list[dict[str, Any]]:
        clubs = self.list_clubs()
        club_key = clubs[0]['clubKey'] if clubs else ''
        club_name = clubs[0]['clubName'] if clubs else ''
        state = self._session.get('dashboard_state') or {}
        return [
            {'clubKey': club_key, 'clubName': club_name, 'order': order}
            for order in state.get('orders') or []
        ]

    def list_messages(
        self, limit: int = 200, flagged_only: bool = False
    ) -> list[dict[str, Any]]:
        clubs = self.list_clubs()
        club_key = clubs[0]['clubKey'] if clubs else ''
        club_name = clubs[0]['clubName'] if clubs else ''
        state = self._session.get('dashboard_state') or {}
        messages = state.get('messages') or []
        if flagged_only:
            messages = [m for m in messages if m.get('autoFlagged')]
        return [
            {'clubKey': club_key, 'clubName': club_name, 'message': message}
            for message in messages[-limit:]
        ]

    def list_reports(self) -> list[dict[str, Any]]:
        clubs = self.list_clubs()
        club_key = clubs[0]['clubKey'] if clubs else ''
        club_name = clubs[0]['clubName'] if clubs else ''
        state = self._session.get('dashboard_state') or {}
        return [
            {'clubKey': club_key, 'clubName': club_name, 'report': report}
            for report in (state.get('reports') or [])
        ]


def make_storage(session: dict[str, Any]) -> Any:
    """Build the backend named by STORAGE_BACKEND (default: session)."""
    if (session.get('user') or {}).get('provider') == 'playtest':
        return SessionStorage(session)
    backend = os.environ.get('STORAGE_BACKEND', 'session').strip().lower()
    if backend == 'airtable':
        return AirtableStorage()
    if backend in ('mongo', 'mongodb'):
        from .storage_mongo import MongoStorage

        return MongoStorage()
    return SessionStorage(session)
