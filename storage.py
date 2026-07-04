"""Storage backends for the dashboard state.

The app talks to one of two backends, chosen by the STORAGE_BACKEND env var:

  session   (default) — state lives in the signed session cookie, exactly as
            before. Zero setup, single-player, ~2.8KB cap.
  airtable  — state lives in an Airtable base shared by the whole club.
            Requires AIRTABLE_TOKEN and AIRTABLE_BASE_ID.

Both backends expose the same three methods:

  resolve_club_key(viewer_email) -> str   which club this viewer belongs to
  load(club_key) -> dict | None           None means "no club yet, seed one"
  save(club_key, state)                   persist a full state dict

The Airtable schema this module expects (table names overridable via env):

  Clubs        Leader Email*, Club Name, Location, Website, Avatar, Join Code,
               Public Directory, Email Notifications, Dark Mode Default,
               Newsletter Subscribed
  Members      App Id*, Name, Email, Role, Status, Avatar, Club Email
  Events       App Id*, Title, Date, Time, Location, Type, RSVP, Attendees,
               Club Email
  Ships        App Id*, Title, Member, URL, Date, Club Email
  Newsletters  App Id*, Title, Excerpt, Body, Date, Read Time, Read, Club Email
  Orders       App Id*, Date, Status, Items, Club Email

(* = used as the lookup key; "Items" is JSON text. Checkbox fields: Public
Directory, Email Notifications, Dark Mode Default, Newsletter Subscribed,
RSVP, Read. Attendees is a number.)

Not stored in Airtable: shopItems (static catalog) and cart (transient,
kept in the session by app.py).
"""

import json
import os

import requests

AIRTABLE_API = 'https://api.airtable.com/v0'

# (state key, airtable field) pairs for each child table.
MEMBER_FIELDS = [('name', 'Name'), ('email', 'Email'), ('role', 'Role'),
                 ('status', 'Status'), ('avatar', 'Avatar')]
EVENT_FIELDS = [('title', 'Title'), ('date', 'Date'), ('time', 'Time'),
                ('location', 'Location'), ('type', 'Type'), ('rsvp', 'RSVP'),
                ('attendees', 'Attendees')]
SHIP_FIELDS = [('title', 'Title'), ('member', 'Member'), ('url', 'URL'),
               ('date', 'Date')]
NEWSLETTER_FIELDS = [('title', 'Title'), ('excerpt', 'Excerpt'),
                     ('body', 'Body'), ('date', 'Date'),
                     ('readTime', 'Read Time'), ('read', 'Read')]
ORDER_FIELDS = [('date', 'Date'), ('status', 'Status')]

SETTINGS_FIELDS = [('clubName', 'Club Name'), ('location', 'Location'),
                   ('website', 'Website'), ('avatar', 'Avatar'),
                   ('joinCode', 'Join Code'),
                   ('publicDirectory', 'Public Directory'),
                   ('emailNotifications', 'Email Notifications'),
                   ('darkModeDefault', 'Dark Mode Default'),
                   ('newsletterSubscribed', 'Newsletter Subscribed')]

BOOL_KEYS = {'rsvp', 'read', 'publicDirectory', 'emailNotifications',
             'darkModeDefault', 'newsletterSubscribed'}


class StorageError(Exception):
    """Raised when the configured backend cannot read or write state."""


class SessionStorage:
    """Today's behavior: the whole state rides in the session cookie."""

    def __init__(self, session):
        self._session = session

    def resolve_club_key(self, viewer_email):
        return (viewer_email or '').strip().lower()

    def load(self, club_key):
        return self._session.get('dashboard_state')

    def save(self, club_key, state):
        self._session['dashboard_state'] = state
        self._session.modified = True


class AirtableStorage:
    """State shared across the club via an Airtable base.

    Loads/saves are whole-club syncs; app.py caches per request in flask.g,
    so each HTTP request costs one load and mutations one extra save.
    """

    CHILD_TABLES = [
        # (env suffix, default table name, state key, field pairs)
        ('MEMBERS', 'Members', 'members', MEMBER_FIELDS),
        ('EVENTS', 'Events', 'events', EVENT_FIELDS),
        ('SHIPS', 'Ships', 'ships', SHIP_FIELDS),
        ('NEWSLETTERS', 'Newsletters', 'newsletters', NEWSLETTER_FIELDS),
        ('ORDERS', 'Orders', 'orders', ORDER_FIELDS),
    ]

    def __init__(self, token=None, base_id=None):
        self.token = token or os.environ.get('AIRTABLE_TOKEN', '')
        self.base_id = base_id or os.environ.get('AIRTABLE_BASE_ID', '')
        if not self.token or not self.base_id:
            raise StorageError(
                'Airtable backend selected but AIRTABLE_TOKEN or '
                'AIRTABLE_BASE_ID is missing.')
        self.clubs_table = os.environ.get('AIRTABLE_TABLE_CLUBS', 'Clubs')
        self.tables = {
            key: os.environ.get(f'AIRTABLE_TABLE_{suffix}', default)
            for suffix, default, key, _ in self.CHILD_TABLES
        }

    # ── HTTP plumbing ────────────────────────────────────────────────────────

    def _request(self, method, table, **kwargs):
        url = f'{AIRTABLE_API}/{self.base_id}/{requests.utils.quote(table)}'
        if 'record_path' in kwargs:
            url += '/' + kwargs.pop('record_path')
        headers = {'Authorization': f'Bearer {self.token}'}
        if method in ('post', 'patch'):
            headers['Content-Type'] = 'application/json'
        try:
            response = requests.request(method, url, headers=headers,
                                        timeout=15, **kwargs)
        except requests.RequestException as exc:
            raise StorageError(f'Could not reach Airtable: {exc}') from exc
        if response.status_code >= 400:
            detail = ''
            try:
                detail = response.json().get('error', {}).get('message', '')
            except (ValueError, AttributeError):
                pass
            raise StorageError(
                f'Airtable {method.upper()} {table} failed '
                f'({response.status_code}): {detail or response.text[:200]}')
        return response.json()

    def _escape_formula_value(self, value):
        return str(value).replace("\\", "\\\\").replace("'", "\\'")

    def _list(self, table, field, value):
        """All records in `table` where {field} = value, following pagination."""
        safe = self._escape_formula_value(value)
        params = {'filterByFormula': f"{{{field}}}='{safe}'", 'pageSize': 100}
        records = []
        while True:
            data = self._request('get', table, params=params)
            records.extend(data.get('records', []))
            offset = data.get('offset')
            if not offset:
                return records
            params['offset'] = offset

    def _batch(self, method, table, payloads):
        """Create/update/delete records in Airtable's 10-per-request batches."""
        for start in range(0, len(payloads), 10):
            chunk = payloads[start:start + 10]
            if method == 'delete':
                self._request('delete', table,
                              params=[('records[]', rid) for rid in chunk])
            else:
                self._request(method, table, json={'records': chunk})

    # ── Interface ────────────────────────────────────────────────────────────

    def resolve_club_key(self, viewer_email):
        """Members belong to the club whose roster lists their email;
        everyone else keys a club of their own."""
        email = (viewer_email or '').strip().lower()
        if not email:
            return email
        matches = self._list(self.tables['members'], 'Email', email)
        for record in matches:
            club_email = (record['fields'].get('Club Email') or '').strip().lower()
            if club_email:
                return club_email
        return email

    def load(self, club_key):
        club_records = self._list(self.clubs_table, 'Leader Email', club_key)
        if not club_records:
            return None
        club_fields = club_records[0]['fields']

        settings = {}
        for state_key, field in SETTINGS_FIELDS:
            value = club_fields.get(field)
            if state_key in BOOL_KEYS:
                settings[state_key] = bool(value)
            else:
                settings[state_key] = value or ''

        state = {'settings': settings}
        for _suffix, _default, state_key, field_pairs in self.CHILD_TABLES:
            items = []
            for record in self._list(self.tables[state_key], 'Club Email', club_key):
                fields = record['fields']
                item = {'id': fields.get('App Id') or record['id']}
                for item_key, field in field_pairs:
                    value = fields.get(field)
                    if item_key in BOOL_KEYS:
                        item[item_key] = bool(value)
                    elif item_key == 'attendees':
                        item[item_key] = int(value or 0)
                    else:
                        item[item_key] = value or ''
                if state_key == 'orders':
                    try:
                        item['items'] = json.loads(fields.get('Items') or '[]')
                    except ValueError:
                        item['items'] = []
                items.append(item)
            state[state_key] = items
        return state

    def save(self, club_key, state):
        self._save_club(club_key, state.get('settings') or {})
        for _suffix, _default, state_key, field_pairs in self.CHILD_TABLES:
            self._sync_children(self.tables[state_key], club_key,
                                state.get(state_key) or [], field_pairs,
                                serialize_items=(state_key == 'orders'))

    # ── Sync helpers ─────────────────────────────────────────────────────────

    def _save_club(self, club_key, settings):
        fields = {'Leader Email': club_key}
        for state_key, field in SETTINGS_FIELDS:
            value = settings.get(state_key)
            fields[field] = bool(value) if state_key in BOOL_KEYS else (value or '')
        existing = self._list(self.clubs_table, 'Leader Email', club_key)
        if existing:
            self._batch('patch', self.clubs_table,
                        [{'id': existing[0]['id'], 'fields': fields}])
        else:
            self._batch('post', self.clubs_table, [{'fields': fields}])

    def _item_fields(self, club_key, item, field_pairs, serialize_items):
        fields = {'App Id': item.get('id') or '', 'Club Email': club_key}
        for item_key, field in field_pairs:
            value = item.get(item_key)
            if item_key in BOOL_KEYS:
                fields[field] = bool(value)
            elif item_key == 'attendees':
                fields[field] = int(value or 0)
            else:
                fields[field] = value or ''
        if serialize_items:
            fields['Items'] = json.dumps(item.get('items') or [])
        return fields

    @staticmethod
    def _field_changed(old, new):
        # Airtable omits empty/false fields from responses, so a missing
        # value is equivalent to our '', 0, False, or [].
        if new in ('', 0, False, '[]', None):
            return old not in (None, '', 0, False, '[]')
        return old != new

    def _sync_children(self, table, club_key, items, field_pairs,
                       serialize_items=False):
        existing = {
            record['fields'].get('App Id'): record
            for record in self._list(table, 'Club Email', club_key)
        }
        creates, updates, keep = [], [], set()
        for item in items:
            app_id = item.get('id') or ''
            keep.add(app_id)
            fields = self._item_fields(club_key, item, field_pairs,
                                       serialize_items)
            record = existing.get(app_id)
            if record is None:
                creates.append({'fields': fields})
            elif any(self._field_changed(record['fields'].get(k), v)
                     for k, v in fields.items()):
                updates.append({'id': record['id'], 'fields': fields})
        deletes = [record['id'] for app_id, record in existing.items()
                   if app_id not in keep]
        if creates:
            self._batch('post', table, creates)
        if updates:
            self._batch('patch', table, updates)
        if deletes:
            self._batch('delete', table, deletes)


def make_storage(session):
    """Build the backend named by STORAGE_BACKEND (default: session)."""
    backend = os.environ.get('STORAGE_BACKEND', 'session').strip().lower()
    if backend == 'airtable':
        return AirtableStorage()
    return SessionStorage(session)
