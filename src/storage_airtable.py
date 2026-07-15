"""Airtable storage backend for Hack Club Leaders Portal."""

import base64
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Final
from urllib.parse import quote

import requests

from .storage_airtable_fields import (
    CHANNEL_FIELDS as CHANNEL_FIELDS,
)
from .storage_airtable_fields import (
    EVENT_FIELDS as EVENT_FIELDS,
)
from .storage_airtable_fields import (
    ITEM_REQUEST_FIELDS as ITEM_REQUEST_FIELDS,
)
from .storage_airtable_fields import (
    LEDGER_FIELDS as LEDGER_FIELDS,
)
from .storage_airtable_fields import (
    MEMBER_FIELDS as MEMBER_FIELDS,
)
from .storage_airtable_fields import (
    MESSAGE_FIELDS as MESSAGE_FIELDS,
)
from .storage_airtable_fields import (
    NEWSLETTER_FIELDS as NEWSLETTER_FIELDS,
)
from .storage_airtable_fields import (
    NOTIFICATION_FIELDS as NOTIFICATION_FIELDS,
)
from .storage_airtable_fields import (
    ORDER_FIELDS as ORDER_FIELDS,
)
from .storage_airtable_fields import (
    PROJECT_FIELDS as PROJECT_FIELDS,
)
from .storage_airtable_fields import (
    SETTINGS_FIELDS as SETTINGS_FIELDS,
)
from .storage_airtable_fields import (
    SETTINGS_INT_KEYS as SETTINGS_INT_KEYS,
)
from .storage_airtable_fields import (
    WORKSHOP_FIELDS as WORKSHOP_FIELDS,
)

AIRTABLE_API: Final[str] = 'https://api.airtable.com/v0'

SHIPPED_STATUS: Final[str] = 'Shipped'
SUBMITTED_STATUS: Final[str] = 'Submitted'


class StorageError(Exception):
    """Base exception for database failures."""
    pass


class AirtableStorage:
    supports_uploads = True

    CHILD_TABLES: Final[list[tuple[str, str, str, list[tuple[str, str]]]]] = [
        ('MEMBERS', 'Members', 'members', MEMBER_FIELDS),
        ('EVENTS', 'Events', 'events', EVENT_FIELDS),
        ('NEWSLETTERS', 'Newsletters', 'newsletters', NEWSLETTER_FIELDS),
        ('ORDERS', 'Orders', 'orders', ORDER_FIELDS),
        ('ITEM_REQUESTS', 'ItemRequests', 'itemRequests', ITEM_REQUEST_FIELDS),
        ('PROJECTS', 'Projects', 'projects', PROJECT_FIELDS),
        ('CHANNELS', 'Channels', 'channels', CHANNEL_FIELDS),
        ('MESSAGES', 'Messages', 'messages', MESSAGE_FIELDS),
        ('NOTIFICATIONS', 'Notifications', 'notifications', NOTIFICATION_FIELDS),
        ('LEDGER', 'Ledger', 'ledger', LEDGER_FIELDS),
        ('WORKSHOPS', 'Workshops', 'workshops', WORKSHOP_FIELDS),
    ]

    OPTIONAL_CHILD_KEYS: Final[set[str]] = {
        'newsletters',
        'orders',
        'itemRequests',
        'channels',
        'messages',
        'notifications',
        'ledger',
        'workshops',
    }

    def __init__(self, token: str | None = None, base_id: str | None = None) -> None:
        self.token = (token or os.environ.get('AIRTABLE_TOKEN', '')).strip()
        self.base_id = (base_id or os.environ.get('AIRTABLE_BASE_ID', '')).strip()
        if not self.token or not self.base_id:
            raise StorageError(
                'Airtable backend selected but AIRTABLE_TOKEN or AIRTABLE_BASE_ID is missing.'
            )
        self.clubs_table = os.environ.get('AIRTABLE_TABLE_CLUBS', 'Clubs').strip()
        self.users_table = os.environ.get('AIRTABLE_TABLE_USERS', 'Users').strip()
        self.tables = {
            state_key: os.environ.get(f'AIRTABLE_TABLE_{env_suffix}', default_name).strip()
            for env_suffix, default_name, state_key, _fields in self.CHILD_TABLES
        }
        self._member_club_cache: dict[str, str | None] = {}

    def _headers(self) -> dict[str, str]:
        return {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
        }

    def _request(
        self,
        method: str,
        table: str,
        params: dict[str, Any] | None = None,
        json: Any = None,
        record_path: str | None = None,
    ) -> dict[str, Any]:
        url = f'{AIRTABLE_API}/{self.base_id}/{quote(table)}'
        if record_path:
            url += f'/{record_path}'
        for attempt in range(4):
            try:
                res = requests.request(
                    method, url, headers=self._headers(), params=params, json=json, timeout=10
                )
            except requests.RequestException as exc:
                if attempt == 3:
                    raise StorageError(f'Airtable unreachable: {exc}') from exc
                time.sleep(0.3 * (2**attempt))
                continue
            if res.status_code == 429:
                time.sleep(0.5 * (2**attempt))
                continue
            if res.status_code == 404:
                return {'records': [], 'not_found': True}
            if res.status_code >= 400:
                detail = ''
                try:
                    detail = (res.json() or {}).get('error', {}).get('message', '')
                except (ValueError, AttributeError):
                    detail = res.text[:200]
                raise StorageError(
                    f'Airtable {table} error ({res.status_code}){": " + detail if detail else ""}'
                )
            return res.json() or {}
        raise StorageError(f'Airtable rate limit exceeded on {table}')

    def _paged(self, table: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        offset: str | None = None
        while True:
            p = dict(params)
            if offset:
                p['offset'] = offset
            res = self._request('GET', table, params=p)
            records.extend(res.get('records') or [])
            offset = res.get('offset')
            if not offset:
                break
        return records

    def _list_all(self, table: str, fields: list[str] | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if fields:
            params['fields[]'] = fields
        return self._paged(table, params)

    def _list(
        self, table: str, field: str, value: str, fields: list[str] | None = None
    ) -> list[dict[str, Any]]:
        escaped = value.replace("'", "\\'")
        params: dict[str, Any] = {'filterByFormula': f"{{{field}}} = '{escaped}'"}
        if fields:
            params['fields[]'] = fields
        return self._paged(table, params)

    def _batch(self, method: str, table: str, records: list[dict[str, Any]]) -> None:
        for i in range(0, len(records), 10):
            chunk = records[i : i + 10]
            if method == 'DELETE':
                params = [('records[]', r['id']) for r in chunk]
                self._request('DELETE', table, params=dict(params))
            else:
                self._request(method, table, json={'records': chunk})

    def _lookup_member_club(self, email: str) -> str | None:
        if email in self._member_club_cache:
            return self._member_club_cache[email]
        records = self._list(self.tables['members'], 'Email', email, fields=['Club Email'])
        found: str | None = None
        for record in records:
            club_email = (record['fields'].get('Club Email') or '').strip().lower()
            if club_email:
                found = club_email
                break
        self._member_club_cache[email] = found
        return found

    def upload_attachment(
        self, message_id: str, filename: str, content: bytes, content_type: str
    ) -> dict[str, Any] | None:
        """Attach `content` to a message row via Airtable's content-upload API.

        Returns {'url','filename','type','size'} or None on any failure — the
        caller posts the message regardless and reports the upload separately.
        """
        records = self._list(self.tables['messages'], 'App Id', message_id)
        if not records:
            return None
        record_id = records[0]['id']
        url = (
            f'https://content.airtable.com/v0/{self.base_id}/{record_id}'
            '/Attachments/uploadAttachment'
        )
        payload = {
            'contentType': content_type,
            'filename': filename,
            'file': base64.b64encode(content).decode('ascii'),
        }
        try:
            response = requests.post(url, headers=self._headers(), json=payload, timeout=30)
        except requests.RequestException:
            return None
        if response.status_code >= 400:
            return None
        attachments = (response.json().get('fields') or {}).get('Attachments') or []
        if not attachments:
            return None
        uploaded = attachments[-1]
        return {
            'url': uploaded.get('url', ''),
            'filename': uploaded.get('filename', filename),
            'type': uploaded.get('type', content_type),
            'size': uploaded.get('size', len(content)),
        }

    def resolve_club_key(self, viewer_email: str) -> str:
        email = (viewer_email or '').strip().lower()
        if not email:
            return email
        return self._lookup_member_club(email) or email

    def find_club_by_join_code(self, code: str) -> str | None:
        code = (code or '').strip()
        if not code:
            return None
        records = self._list(self.clubs_table, 'Join Code', code, fields=['Leader Email'])
        for record in records:
            leader = (record['fields'].get('Leader Email') or '').strip().lower()
            if leader:
                return leader
        return None

    def find_club_by_member_email(self, email: str) -> str | None:
        email = (email or '').strip().lower()
        if not email:
            return None
        try:
            return self._lookup_member_club(email)
        except StorageError:
            return None

    def list_clubs(self) -> list[dict[str, Any]]:
        with ThreadPoolExecutor(max_workers=3) as pool:
            clubs_future = pool.submit(
                self._list_all, self.clubs_table, ['Leader Email', 'Club Name', 'Location']
            )
            members_future = pool.submit(self._list_all, self.tables['members'], ['Club Email'])
            projects_future = pool.submit(
                self._list_all, self.tables['projects'], ['Club Email', 'Status']
            )
            club_rows = clubs_future.result()
            member_rows = members_future.result()
            try:
                project_rows = projects_future.result()
            except StorageError:
                project_rows = []

        member_counts: dict[str, int] = {}
        ship_counts: dict[str, int] = {}
        pending_counts: dict[str, int] = {}
        for record in member_rows:
            key = (record['fields'].get('Club Email') or '').strip().lower()
            if key:
                member_counts[key] = member_counts.get(key, 0) + 1
        for record in project_rows:
            key = (record['fields'].get('Club Email') or '').strip().lower()
            if not key:
                continue
            status = record['fields'].get('Status')
            if status == SHIPPED_STATUS:
                ship_counts[key] = ship_counts.get(key, 0) + 1
            elif status == SUBMITTED_STATUS:
                pending_counts[key] = pending_counts.get(key, 0) + 1

        clubs: list[dict[str, Any]] = []
        for record in club_rows:
            fields = record['fields']
            key = (fields.get('Leader Email') or '').strip().lower()
            if not key:
                continue
            clubs.append(
                {
                    'clubKey': key,
                    'clubName': fields.get('Club Name') or 'Club',
                    'location': fields.get('Location') or '',
                    'memberCount': member_counts.get(key, 0),
                    'shipCount': ship_counts.get(key, 0),
                    'pendingShips': pending_counts.get(key, 0),
                }
            )
        return clubs

    def list_pending_projects(self) -> list[dict[str, Any]]:
        clubs = {c['clubKey']: c['clubName'] for c in self.list_clubs()}
        records = self._list(self.tables['projects'], 'Status', SUBMITTED_STATUS)
        pending: list[dict[str, Any]] = []
        for record in records:
            fields = record['fields']
            club_email = (fields.get('Club Email') or '').strip().lower()
            pending.append(
                {
                    'clubKey': club_email,
                    'clubName': clubs.get(club_email, club_email),
                    'project': {
                        'id': fields.get('App Id', record['id']),
                        'name': fields.get('Name', ''),
                        'description': fields.get('Description', ''),
                        'url': fields.get('URL', ''),
                        'repoUrl': fields.get('Repo URL', ''),
                        'demoUrl': fields.get('Demo URL', ''),
                        'thumbnail': fields.get('Thumbnail', ''),
                        'hackatimeProject': fields.get('Hackatime Project', ''),
                        'status': fields.get('Status', SUBMITTED_STATUS),
                        'ownerEmail': fields.get('Owner Email', ''),
                        'ownerName': fields.get('Owner Name', ''),
                        'date': fields.get('Date', ''),
                    },
                }
            )
        return pending

    def list_item_requests(self) -> list[dict[str, Any]]:
        clubs = {c['clubKey']: c['clubName'] for c in self.list_clubs()}
        records = self._list_all(self.tables['itemRequests'])
        return [
            {
                'clubKey': (r['fields'].get('Club Email') or '').strip().lower(),
                'clubName': clubs.get((r['fields'].get('Club Email') or '').strip().lower(), ''),
                'request': {
                    'id': r['fields'].get('App Id', r['id']),
                    'name': r['fields'].get('Name', ''),
                    'note': r['fields'].get('Note', ''),
                    'date': r['fields'].get('Date', ''),
                    'status': r['fields'].get('Status', 'Pending'),
                },
            }
            for r in records
            if r['fields'].get('Club Email')
        ]

    def load_lite(self, club_key: str) -> dict[str, Any] | None:
        return self.load(club_key, sections=['members'])

    def load(self, club_key: str, sections: list[str] | None = None) -> dict[str, Any] | None:
        key = (club_key or '').strip().lower()
        if not key:
            return None
        club_records = self._list(self.clubs_table, 'Leader Email', key)
        if not club_records:
            return None
        fields = club_records[0]['fields']
        settings = {
            'joinCode': fields.get('Join Code') or '',
            'clubName': fields.get('Club Name') or f"{key}'s Hack Club",
            'venue': fields.get('Venue') or '',
            'location': fields.get('Location') or '',
            'addressLine1': fields.get('Address Line 1') or '',
            'addressLine2': fields.get('Address Line 2') or '',
            'city': fields.get('City') or '',
            'state': fields.get('State') or '',
            'zip': fields.get('Zip') or '',
            'country': fields.get('Country') or '',
            'meetingDay': fields.get('Meeting Day') or '',
            'clubBio': fields.get('Club Bio') or '',
            'website': fields.get('Website') or '',
            'avatar': fields.get('Avatar') or '',
            'publicDirectory': bool(fields.get('Public Directory', True)),
            'emailNotifications': bool(fields.get('Email Notifications', True)),
            'darkModeDefault': bool(fields.get('Dark Mode Default', False)),
            'newsletterSubscribed': bool(fields.get('Newsletter Subscribed', True)),
            'language': fields.get('Language') or 'en',
            'coinBalance': int(fields.get('Coin Balance') or 0),
            'coinsSpent': int(fields.get('Coins Spent') or 0),
        }
        state: dict[str, Any] = {'settings': settings}
        active_tables = [
            (env_suffix, table_default, state_key, field_pairs)
            for env_suffix, table_default, state_key, field_pairs in self.CHILD_TABLES
            if sections is None or state_key in sections
        ]

        def _load_child(item: tuple[str, str, str, list[tuple[str, str]]]) -> tuple[str, list[dict[str, Any]]]:
            _env, default_name, state_key, field_pairs = item
            table_name = self.tables[state_key]
            records = self._list(table_name, 'Club Email', key)
            out: list[dict[str, Any]] = []
            for r in records:
                f = r['fields']
                row: dict[str, Any] = {'id': f.get('App Id', r['id'])}
                for key_name, airtable_name in field_pairs:
                    val = f.get(airtable_name)
                    if key_name in ('rsvp', 'read'):
                        row[key_name] = bool(val)
                    elif key_name in ('attendees', 'delta'):
                        row[key_name] = int(val or 0)
                    elif key_name in ('items', 'data', 'applicants'):
                        try:
                            row[key_name] = json.loads(val or ('[]' if key_name != 'data' else '{}'))
                        except (ValueError, TypeError):
                            row[key_name] = [] if key_name != 'data' else {}
                    elif key_name == 'linkPreview':
                        if val:
                            try:
                                row[key_name] = json.loads(val)
                            except ValueError:
                                pass
                    else:
                        row[key_name] = val or ''
                if state_key == 'messages':
                    raw_attachments = f.get('Attachments') or []
                    if raw_attachments:
                        row['attachments'] = [
                            {
                                'url': att.get('url', ''),
                                'filename': att.get('filename', ''),
                                'type': att.get('type', ''),
                                'size': att.get('size', 0),
                            }
                            for att in raw_attachments
                        ]
                out.append(row)
            return state_key, out

        with ThreadPoolExecutor(max_workers=min(10, len(active_tables) or 1)) as pool:
            for state_key, rows in pool.map(_load_child, active_tables):
                state[state_key] = rows
        return state

    def save(self, club_key: str, state: dict[str, Any]) -> None:
        key = (club_key or '').strip().lower()
        if not key:
            return
        settings = state.get('settings') or {}
        fields: dict[str, Any] = {'Leader Email': key}
        for key_name, airtable_name in SETTINGS_FIELDS:
            if key_name in settings:
                fields[airtable_name] = settings[key_name]
        existing_clubs = self._list(self.clubs_table, 'Leader Email', key)
        if existing_clubs:
            self._request('PATCH', self.clubs_table, json={'records': [{'id': existing_clubs[0]['id'], 'fields': fields}]})
        else:
            self._request('POST', self.clubs_table, json={'records': [{'fields': fields}]})

        def _save_child(item: tuple[str, str, str, list[tuple[str, str]]]) -> None:
            _env, default_name, state_key, field_pairs = item
            if state_key not in state:
                return
            table_name = self.tables[state_key]
            desired = state.get(state_key) or []
            existing_records = self._list(table_name, 'Club Email', key)
            existing_by_app_id = {r['fields'].get('App Id'): r for r in existing_records if r['fields'].get('App Id')}

            to_create: list[dict[str, Any]] = []
            to_update: list[dict[str, Any]] = []
            desired_app_ids = set()

            for item_dict in desired:
                app_id = item_dict.get('id')
                if not app_id:
                    continue
                desired_app_ids.add(app_id)
                row_fields: dict[str, Any] = {'Club Email': key, 'App Id': app_id}
                for key_name, airtable_name in field_pairs:
                    val = item_dict.get(key_name)
                    if key_name in ('items', 'data', 'applicants'):
                        row_fields[airtable_name] = json.dumps(val or ([] if key_name != 'data' else {}))
                    elif key_name == 'linkPreview':
                        row_fields[airtable_name] = json.dumps(val) if val else ''
                    else:
                        row_fields[airtable_name] = val
                if app_id in existing_by_app_id:
                    to_update.append({'id': existing_by_app_id[app_id]['id'], 'fields': row_fields})
                else:
                    to_create.append({'fields': row_fields})

            to_delete = [r for r in existing_records if r['fields'].get('App Id') not in desired_app_ids]
            if to_delete:
                self._batch('DELETE', table_name, to_delete)
            if to_create:
                self._batch('POST', table_name, to_create)
            if to_update:
                self._batch('PATCH', table_name, to_update)

        with ThreadPoolExecutor(max_workers=len(self.CHILD_TABLES)) as pool:
            list(pool.map(_save_child, self.CHILD_TABLES))

    # ── Cross-club user records ─────────────────────────────────────────────

    def get_user_record(self, email: str, *, strict: bool = False) -> dict[str, Any]:
        """Cross-club session-invalidation counter for `email`.

        Degrades to `{'sessionVersion': 0}` when the Users table is missing
        or has no row; `strict=True` re-raises StorageError instead."""
        email = (email or '').strip().lower()
        defaults = {'sessionVersion': 0}
        if not email:
            return defaults
        try:
            rows = self._list(self.users_table, 'Email', email)
        except StorageError:
            if strict:
                raise
            return defaults
        if not rows:
            return defaults
        fields = rows[0].get('fields', {})
        return {
            'sessionVersion': int(fields.get('Session Version') or 0),
        }

    def save_user_record(self, email: str, fields: dict[str, Any]) -> None:
        """Upsert `fields` (sessionVersion) onto the user's Users-table row."""
        email = (email or '').strip().lower()
        if not email:
            raise StorageError('Cannot save a user record without an email.')
        airtable_fields: dict[str, Any] = {}
        if 'sessionVersion' in fields:
            airtable_fields['Session Version'] = int(fields['sessionVersion'] or 0)
        try:
            existing = self._list(self.users_table, 'Email', email)
        except StorageError as exc:
            raise StorageError(
                'This club uses Airtable but has no Users table yet. '
                'Ask your Airtable base owner to add a Users table first.'
            ) from exc
        if existing:
            record_id = existing[0]['id']
            self._request(
                'patch',
                self.users_table,
                record_path=record_id,
                json={'fields': airtable_fields},
            )
        else:
            airtable_fields.setdefault('Email', email)
            self._request('post', self.users_table, json={'fields': airtable_fields})
