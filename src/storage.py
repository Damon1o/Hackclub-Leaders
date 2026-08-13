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

The Airtable schema this module expects (table names overridable via env):

  Clubs        Leader Email*, Club Name, Location, Website, Avatar, Join Code,
               Public Directory, Email Notifications, Dark Mode Default,
               Newsletter Subscribed, Coin Balance, Coins Spent
  Members      App Id*, Name, Email, Role, Status, Avatar, Club Email
  Events       App Id*, Title, Date, Time, Location, Type, RSVP, Attendees,
               Club Email
  Newsletters  App Id*, Title, Excerpt, Body, Date, Read Time, Read, Club Email
  Orders       App Id*, Date, Status, Items, Club Email
  Projects     App Id*, Name, Description, URL, Repo URL, Demo URL, Thumbnail,
               Hackatime Project, Status, Owner Email, Owner Name, Date,
               Club Email
  Notifications App Id*, Type, Title, Message, Data, Read, Created At, Club Email
  Ledger       App Id*, Delta, Kind, Ref, Note, At, Club Email
  Workshops    App Id*, Title, Description, Status, Proposer Email, Proposer Name,
               Applicants, Runner Email, Runner Name, Event Id, Created At, Club Email
  Users        Email*, Preferred Name, Session Version — cross-club, one row per
               person regardless of which club(s) they belong to; missing table
               or row both degrade to defaults rather than erroring.

A "ship" is just a Project with Status = "Shipped" (set when an admin approves a
Submitted project) — there is no separate Ships table.

(* = used as the lookup key; "Items", "Data", and "Applicants" are JSON text. Checkbox fields:
Public Directory, Email Notifications, Dark Mode Default, Newsletter
Subscribed, RSVP, Read. Attendees, Coin Balance, and Coins Spent are numbers.)

Not stored in Airtable: shopItems (static catalog) and cart (transient,
kept in the session by app.py).
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Final

import requests

AIRTABLE_API: Final[str] = 'https://api.airtable.com/v0'

# (state key, airtable field) pairs for each child table.
MEMBER_FIELDS: Final[list[tuple[str, str]]] = [
    ('name', 'Name'),
    ('email', 'Email'),
    ('role', 'Role'),
    ('status', 'Status'),
    ('avatar', 'Avatar'),
]
EVENT_FIELDS: Final[list[tuple[str, str]]] = [
    ('title', 'Title'),
    ('date', 'Date'),
    ('time', 'Time'),
    ('location', 'Location'),
    ('type', 'Type'),
    ('repeat', 'Repeat'),
    ('rsvp', 'RSVP'),
    ('attendees', 'Attendees'),
]
NEWSLETTER_FIELDS: Final[list[tuple[str, str]]] = [
    ('title', 'Title'),
    ('excerpt', 'Excerpt'),
    ('body', 'Body'),
    ('date', 'Date'),
    ('readTime', 'Read Time'),
    ('read', 'Read'),
]
ORDER_FIELDS: Final[list[tuple[str, str]]] = [('date', 'Date'), ('status', 'Status')]
ITEM_REQUEST_FIELDS: Final[list[tuple[str, str]]] = [
    ('name', 'Name'),
    ('note', 'Note'),
    ('date', 'Date'),
    ('status', 'Status'),
]
PROJECT_FIELDS: Final[list[tuple[str, str]]] = [
    ('name', 'Name'),
    ('description', 'Description'),
    ('url', 'URL'),
    ('repoUrl', 'Repo URL'),
    ('demoUrl', 'Demo URL'),
    ('thumbnail', 'Thumbnail'),
    ('hackatimeProject', 'Hackatime Project'),
    ('status', 'Status'),
    ('ownerEmail', 'Owner Email'),
    ('ownerName', 'Owner Name'),
    ('date', 'Date'),
]
LEDGER_FIELDS: Final[list[tuple[str, str]]] = [
    ('delta', 'Delta'),
    ('kind', 'Kind'),
    ('ref', 'Ref'),
    ('note', 'Note'),
    ('at', 'At'),
]
WORKSHOP_FIELDS: Final[list[tuple[str, str]]] = [
    ('title', 'Title'),
    ('description', 'Description'),
    ('status', 'Status'),
    ('proposerEmail', 'Proposer Email'),
    ('proposerName', 'Proposer Name'),
    ('runnerEmail', 'Runner Email'),
    ('runnerName', 'Runner Name'),
    ('eventId', 'Event Id'),
    ('createdAt', 'Created At'),
]
CHANNEL_FIELDS: Final[list[tuple[str, str]]] = [
    ('name', 'Name'),
    ('description', 'Description'),
    ('topic', 'Topic'),
    ('createdBy', 'Created By'),
    ('lastMessageAt', 'Last Message At'),
]
MESSAGE_FIELDS: Final[list[tuple[str, str]]] = [
    ('channelId', 'Channel Id'),
    ('authorEmail', 'Author Email'),
    ('authorName', 'Author Name'),
    ('authorAvatar', 'Author Avatar'),
    ('body', 'Body'),
    ('createdAt', 'Created At'),
]
NOTIFICATION_FIELDS: Final[list[tuple[str, str]]] = [
    ('type', 'Type'),
    ('title', 'Title'),
    ('message', 'Message'),
    ('read', 'Read'),
    ('createdAt', 'Created At'),
]

SETTINGS_FIELDS: Final[list[tuple[str, str]]] = [
    ('clubName', 'Club Name'),
    ('venue', 'Venue'),
    ('location', 'Location'),
    ('addressLine1', 'Address Line 1'),
    ('addressLine2', 'Address Line 2'),
    ('city', 'City'),
    ('state', 'State'),
    ('zip', 'Zip'),
    ('country', 'Country'),
    ('meetingDay', 'Meeting Day'),
    ('clubBio', 'Club Bio'),
    ('website', 'Website'),
    ('avatar', 'Avatar'),
    ('joinCode', 'Join Code'),
    ('publicDirectory', 'Public Directory'),
    ('emailNotifications', 'Email Notifications'),
    ('darkModeDefault', 'Dark Mode Default'),
    ('newsletterSubscribed', 'Newsletter Subscribed'),
    ('coinBalance', 'Coin Balance'),
    ('coinsSpent', 'Coins Spent'),
]

# Settings keys that hold numbers rather than strings/booleans — mirrors the
# attendees/delta int-coercion on child-table records below. Without this,
# the generic `value or ''` branch would turn a real 0 balance into '' on
# both load and save.
SETTINGS_INT_KEYS: Final[set[str]] = {'coinBalance', 'coinsSpent'}

BOOL_KEYS: Final[set[str]] = {
    'rsvp',
    'read',
    'publicDirectory',
    'emailNotifications',
    'darkModeDefault',
    'newsletterSubscribed',
}

# A project counts as a "ship" (toward club levels) once an admin approves it.
SHIPPED_STATUS: Final[str] = 'Shipped'
SUBMITTED_STATUS: Final[str] = 'Submitted'


class StorageError(Exception):
    """Raised when the configured backend cannot read or write state."""


class SessionStorage:
    """Today's behavior: the whole state rides in the session cookie."""

    def __init__(self, session: dict[str, Any]) -> None:
        self._session = session

    def resolve_club_key(self, viewer_email: str) -> str:
        return (viewer_email or '').strip().lower()

    def load(self, club_key: str, sections: list[str] | None = None) -> dict[str, Any] | None:
        # Cookie state is one blob, so there is nothing to load lazily —
        # `sections` is accepted only to match the other backends.
        return self._session.get('dashboard_state')

    def load_lite(self, club_key: str) -> dict[str, Any] | None:
        # Everything is already in memory, so lite == full here.
        return self._session.get('dashboard_state')

    def save(self, club_key: str, state: dict[str, Any]) -> None:
        self._session['dashboard_state'] = state
        self._session.modified = True

    def find_club_by_join_code(self, code: str) -> str | None:
        # Cookie state is per-browser, so there is no other club to find.
        return None

    def find_club_by_member_email(self, email: str) -> str | None:
        return None

    def list_clubs(self) -> list[dict[str, Any]]:
        # Only this browser's own club exists in session mode.
        state = self._session.get('dashboard_state')
        if not state:
            return []
        settings = state.get('settings') or {}
        projects = state.get('projects') or []
        return [
            {
                'clubKey': self.resolve_club_key((self._session.get('user') or {}).get('email')),
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


class AirtableStorage:
    """State shared across the club via an Airtable base.

    Loads/saves are whole-club syncs; app.py caches per request in flask.g,
    so each HTTP request costs one load and mutations one extra save.
    """

    CHILD_TABLES: Final[list[tuple[str, str, str, list[tuple[str, str]]]]] = [
        # (env suffix, default table name, state key, field pairs)
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

    # Tables that degrade gracefully if the base doesn't have them yet (that
    # section is empty / not persisted instead of erroring). Projects is NOT
    # here — it is the single source of truth for projects and ships, so the
    # base must have a Projects table. Chat tables are optional so existing
    # bases keep working until the club adds the Channels/Messages tables.
    OPTIONAL_CHILD_KEYS: Final[set[str]] = {
        'itemRequests',
        'channels',
        'messages',
        'notifications',
        'ledger',
        'workshops',
    }

    def __init__(self, token: str | None = None, base_id: str | None = None) -> None:
        self.token = token or os.environ.get('AIRTABLE_TOKEN', '')
        self.base_id = base_id or os.environ.get('AIRTABLE_BASE_ID', '')
        if not self.token or not self.base_id:
            raise StorageError(
                'Airtable backend selected but AIRTABLE_TOKEN or AIRTABLE_BASE_ID is missing.'
            )
        self.clubs_table = os.environ.get('AIRTABLE_TABLE_CLUBS', 'Clubs')
        self.users_table = os.environ.get('AIRTABLE_TABLE_USERS', 'Users')
        self.tables: dict[str, str] = {
            key: os.environ.get(f'AIRTABLE_TABLE_{suffix}', default)
            for suffix, default, key, _ in self.CHILD_TABLES
        }
        # A request typically asks "which club is this viewer in?" more than
        # once (membership gate, role check, club key). The answer can't
        # change mid-request, so look it up once. The instance is per-request
        # (built into flask.g), so this never goes stale across requests.
        self._member_club_cache: dict[str, str | None] = {}

    # ── HTTP plumbing ─────────────────────────────────────────────────────────

    def _request(self, method: str, table: str, **kwargs: Any) -> dict[str, Any]:
        url = f'{AIRTABLE_API}/{self.base_id}/{requests.utils.quote(table)}'
        if 'record_path' in kwargs:
            url += '/' + kwargs.pop('record_path')
        headers = {'Authorization': f'Bearer {self.token}'}
        if method in ('post', 'patch'):
            headers['Content-Type'] = 'application/json'
        try:
            response = requests.request(method, url, headers=headers, timeout=15, **kwargs)
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
                f'({response.status_code}): {detail or response.text[:200]}'
            )
        return response.json()

    def _escape_formula_value(self, value: Any) -> str:
        return str(value).replace('\\', '\\\\').replace("'", "\\'")

    def _list(
        self,
        table: str,
        field: str,
        value: Any,
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """All records in `table` where {field} = value, following pagination.

        `fields` narrows the columns Airtable sends back — a lookup that only
        needs one column shouldn't drag every other column over the wire.
        """
        safe = self._escape_formula_value(value)
        params: dict[str, Any] = {'filterByFormula': f"{{{field}}}='{safe}'", 'pageSize': 100}
        if fields:
            params['fields[]'] = fields
        return self._paged(table, params)

    def _list_all(
        self,
        table: str,
        fields: list[str] | None = None,
        formula: str = '',
    ) -> list[dict[str, Any]]:
        """Every record in `table`, optionally narrowed by a filter formula
        and a column projection. Pushing the filter to Airtable beats pulling
        the whole table down and dropping most of it in Python.
        """
        params: dict[str, Any] = {'pageSize': 100}
        if fields:
            params['fields[]'] = fields
        if formula:
            params['filterByFormula'] = formula
        return self._paged(table, params)

    def _paged(self, table: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        params = dict(params)
        records: list[dict[str, Any]] = []
        while True:
            data = self._request('get', table, params=params)
            records.extend(data.get('records', []))
            offset = data.get('offset')
            if not offset:
                return records
            params['offset'] = offset

    def _batch(self, method: str, table: str, payloads: list[dict[str, Any]]) -> None:
        """Create/update/delete records in Airtable's 10-per-request batches."""
        for start in range(0, len(payloads), 10):
            chunk = payloads[start : start + 10]
            if method == 'delete':
                self._request('delete', table, params=[('records[]', rid) for rid in chunk])
            else:
                self._request(method, table, json={'records': chunk})

    # ── Interface ─────────────────────────────────────────────────────────────

    def _lookup_member_club(self, email: str) -> str | None:
        """The club whose roster lists `email`, or None. Only the Club Email
        column is fetched, and the answer is memoized per instance."""
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

    def resolve_club_key(self, viewer_email: str) -> str:
        """Members belong to the club whose roster lists their email;
        everyone else keys a club of their own."""
        email = (viewer_email or '').strip().lower()
        if not email:
            return email
        return self._lookup_member_club(email) or email

    def find_club_by_join_code(self, code: str) -> str | None:
        """The club key owning this join code, or None."""
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
        """Check whether any club roster includes this email. Returns the
        first matching club key or None."""
        email = (email or '').strip().lower()
        if not email:
            return None
        try:
            return self._lookup_member_club(email)
        except StorageError:
            return None

    def list_clubs(self) -> list[dict[str, Any]]:
        """Summary of every club, for the admin overview. Three full-table
        scans (clubs, members, projects), run concurrently and each narrowed
        to the handful of columns the summary actually reads. "Ships" =
        projects with Status "Shipped"; "pending" = projects awaiting review."""
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
        clubs.sort(key=lambda c: c['clubName'].lower())
        return clubs

    def list_pending_projects(self) -> list[dict[str, Any]]:
        """Every Submitted project across all clubs, newest first, for the
        admin review queue. The Status filter runs in Airtable rather than in
        Python, so only the review queue itself crosses the wire."""
        formula = f"{{Status}}='{self._escape_formula_value(SUBMITTED_STATUS)}'"
        with ThreadPoolExecutor(max_workers=2) as pool:
            clubs_future = pool.submit(
                self._list_all, self.clubs_table, ['Leader Email', 'Club Name']
            )
            projects_future = pool.submit(self._list_all, self.tables['projects'], None, formula)
            club_rows = clubs_future.result()
            try:
                project_rows = projects_future.result()
            except StorageError:
                project_rows = []

        club_names: dict[str, str] = {
            (r['fields'].get('Leader Email') or '').strip().lower(): r['fields'].get('Club Name')
            or 'Club'
            for r in club_rows
        }
        pending: list[dict[str, Any]] = []
        for record in project_rows:
            fields = record['fields']
            key = (fields.get('Club Email') or '').strip().lower()
            project: dict[str, Any] = {'id': fields.get('App Id') or record['id']}
            for item_key, field in PROJECT_FIELDS:
                value = fields.get(field)
                project[item_key] = bool(value) if item_key in BOOL_KEYS else (value or '')
            pending.append(
                {
                    'clubKey': key,
                    'clubName': club_names.get(key, key or 'Unknown club'),
                    'project': project,
                }
            )
        pending.sort(key=lambda p: p['project'].get('date') or '', reverse=True)
        return pending

    def list_item_requests(self) -> list[dict[str, Any]]:
        """Every item request across all clubs, newest first, for the admin
        panel. Degrades to an empty list if the (optional) ItemRequests table
        isn't in the base yet."""
        with ThreadPoolExecutor(max_workers=2) as pool:
            clubs_future = pool.submit(
                self._list_all, self.clubs_table, ['Leader Email', 'Club Name']
            )
            requests_future = pool.submit(self._list_all, self.tables['itemRequests'])
            club_rows = clubs_future.result()
            try:
                request_rows = requests_future.result()
            except StorageError:
                request_rows = []

        club_names: dict[str, str] = {
            (r['fields'].get('Leader Email') or '').strip().lower(): r['fields'].get('Club Name')
            or 'Club'
            for r in club_rows
        }
        result: list[dict[str, Any]] = []
        for record in request_rows:
            fields = record['fields']
            key = (fields.get('Club Email') or '').strip().lower()
            request: dict[str, Any] = {'id': fields.get('App Id') or record['id']}
            for item_key, field in ITEM_REQUEST_FIELDS:
                request[item_key] = fields.get(field) or ''
            result.append(
                {
                    'clubKey': key,
                    'clubName': club_names.get(key, key or 'Unknown club'),
                    'request': request,
                }
            )
        result.sort(key=lambda r: r['request'].get('date') or '', reverse=True)
        return result

    def load_lite(self, club_key: str) -> dict[str, Any] | None:
        """Just the club settings + members — enough for the membership gate
        and role check. Two parallel queries instead of the full eight, so the
        page shell returns fast; the rest is fetched client-side."""
        with ThreadPoolExecutor(max_workers=2) as pool:
            club_future = pool.submit(self._list, self.clubs_table, 'Leader Email', club_key)
            members_future = pool.submit(self._list, self.tables['members'], 'Club Email', club_key)
            club_records = club_future.result()
            member_records = members_future.result()

        if not club_records:
            return None
        club_fields = club_records[0]['fields']
        settings: dict[str, Any] = {}
        for state_key, field in SETTINGS_FIELDS:
            value = club_fields.get(field)
            if state_key in BOOL_KEYS:
                settings[state_key] = bool(value)
            elif state_key in SETTINGS_INT_KEYS:
                settings[state_key] = int(value or 0)
            else:
                settings[state_key] = value or ''

        members: list[dict[str, Any]] = []
        for record in member_records:
            fields = record['fields']
            item: dict[str, Any] = {'id': fields.get('App Id') or record['id']}
            for item_key, field in MEMBER_FIELDS:
                value = fields.get(field)
                item[item_key] = bool(value) if item_key in BOOL_KEYS else (value or '')
            members.append(item)
        return {'settings': settings, 'members': members, '_lite': True}

    def load(self, club_key: str, sections: list[str] | None = None) -> dict[str, Any] | None:
        """Full club state, or just the named sections.

        `sections` is a list of state keys; None means all of them. Skipping a
        section skips its Airtable round-trip entirely, so a page that only
        renders events doesn't pay for the club's whole chat history.
        """
        wanted = {state_key for _s, _d, state_key, _f in self.CHILD_TABLES}
        if sections is not None:
            wanted &= set(sections)
        # Fire the club lookup and every child-table query at once — they are
        # independent GETs, so this turns ~8 sequential round-trips into one.
        with ThreadPoolExecutor(max_workers=len(self.CHILD_TABLES) + 1) as pool:
            club_future = pool.submit(self._list, self.clubs_table, 'Leader Email', club_key)
            child_futures: dict[str, Any] = {
                state_key: pool.submit(self._list, self.tables[state_key], 'Club Email', club_key)
                for _s, _d, state_key, _f in self.CHILD_TABLES
                if state_key in wanted
            }
            club_records = club_future.result()

        if not club_records:
            return None
        club_fields = club_records[0]['fields']

        settings: dict[str, Any] = {}
        for state_key, field in SETTINGS_FIELDS:
            value = club_fields.get(field)
            if state_key in BOOL_KEYS:
                settings[state_key] = bool(value)
            elif state_key in SETTINGS_INT_KEYS:
                settings[state_key] = int(value or 0)
            else:
                settings[state_key] = value or ''

        state: dict[str, Any] = {'settings': settings}
        for _suffix, _default, state_key, field_pairs in self.CHILD_TABLES:
            if state_key not in wanted:
                continue
            try:
                records = child_futures[state_key].result()
            except StorageError:
                if state_key in self.OPTIONAL_CHILD_KEYS:
                    state[state_key] = []
                    continue
                raise
            items: list[dict[str, Any]] = []
            for record in records:
                fields = record['fields']
                item: dict[str, Any] = {'id': fields.get('App Id') or record['id']}
                for item_key, field in field_pairs:
                    value = fields.get(field)
                    if item_key in BOOL_KEYS:
                        item[item_key] = bool(value)
                    elif item_key in ('attendees', 'delta'):
                        item[item_key] = int(value or 0)
                    else:
                        item[item_key] = value or ''
                if state_key == 'orders':
                    try:
                        item['items'] = json.loads(fields.get('Items') or '[]')
                    except ValueError:
                        item['items'] = []
                if state_key == 'messages':
                    try:
                        reactions = json.loads(fields.get('Reactions') or '{}')
                    except ValueError:
                        reactions = {}
                    if reactions:
                        item['reactions'] = reactions
                if state_key == 'notifications':
                    try:
                        item['data'] = json.loads(fields.get('Data') or '{}')
                    except ValueError:
                        item['data'] = {}
                if state_key == 'workshops':
                    try:
                        item['applicants'] = json.loads(fields.get('Applicants') or '[]')
                    except ValueError:
                        item['applicants'] = []
                items.append(item)
            state[state_key] = items
        return state

    def save(self, club_key: str, state: dict[str, Any]) -> None:
        """Persist a state dict. Sections absent from `state` are left alone,
        so saving a lazily-loaded partial state can't delete the sections that
        request never fetched."""

        # The club row and each child table are independent; sync them all
        # concurrently instead of one blocking round-trip after another.
        def sync(state_key: str, field_pairs: list[tuple[str, str]]) -> None:
            self._sync_children(
                self.tables[state_key],
                club_key,
                state.get(state_key) or [],
                field_pairs,
                state_key=state_key,
            )

        with ThreadPoolExecutor(max_workers=len(self.CHILD_TABLES) + 1) as pool:
            futures: list[Any] = [
                pool.submit(self._save_club, club_key, state.get('settings') or {})
            ]
            future_keys: dict[Any, str] = {}
            for _s, _d, state_key, field_pairs in self.CHILD_TABLES:
                if state_key not in state:
                    continue
                future = pool.submit(sync, state_key, field_pairs)
                future_keys[future] = state_key
                futures.append(future)

            for future in futures:
                state_key = future_keys.get(future)
                try:
                    future.result()
                except StorageError:
                    if state_key in self.OPTIONAL_CHILD_KEYS:
                        continue  # table not created yet — skip persisting it
                    raise

    # ── Sync helpers ─────────────────────────────────────────────────────────

    def _save_club(self, club_key: str, settings: dict[str, Any]) -> None:
        fields: dict[str, Any] = {'Leader Email': club_key}
        for state_key, field in SETTINGS_FIELDS:
            value = settings.get(state_key)
            if state_key in BOOL_KEYS:
                fields[field] = bool(value)
            elif state_key in SETTINGS_INT_KEYS:
                fields[field] = int(value or 0)
            else:
                fields[field] = value or ''
        existing = self._list(self.clubs_table, 'Leader Email', club_key)
        if existing:
            self._batch('patch', self.clubs_table, [{'id': existing[0]['id'], 'fields': fields}])
        else:
            self._batch('post', self.clubs_table, [{'fields': fields}])

    def _item_fields(
        self,
        club_key: str,
        item: dict[str, Any],
        field_pairs: list[tuple[str, str]],
        state_key: str,
    ) -> dict[str, Any]:
        fields: dict[str, Any] = {'App Id': item.get('id') or '', 'Club Email': club_key}
        for item_key, field in field_pairs:
            value = item.get(item_key)
            if item_key in BOOL_KEYS:
                fields[field] = bool(value)
            elif item_key in ('attendees', 'delta'):
                fields[field] = int(value or 0)
            else:
                fields[field] = value or ''
        if state_key == 'orders':
            fields['Items'] = json.dumps(item.get('items') or [])
        if state_key == 'messages':
            fields['Reactions'] = json.dumps(item.get('reactions') or {})
        if state_key == 'notifications':
            fields['Data'] = json.dumps(item.get('data') or {})
        if state_key == 'workshops':
            fields['Applicants'] = json.dumps(item.get('applicants') or [])
        return fields

    @staticmethod
    def _field_changed(old: Any, new: Any) -> bool:
        # Airtable omits empty/false fields from responses, so a missing
        # value is equivalent to our '', 0, False, or [].
        if new in ('', 0, False, '[]', '{}', None):
            return old not in (None, '', 0, False, '[]', '{}')
        return old != new

    def _sync_children(
        self,
        table: str,
        club_key: str,
        items: list[dict[str, Any]],
        field_pairs: list[tuple[str, str]],
        state_key: str | None = None,
    ) -> None:
        existing: dict[str, dict[str, Any]] = {
            record['fields'].get('App Id'): record
            for record in self._list(table, 'Club Email', club_key)
        }
        creates: list[dict[str, Any]] = []
        updates: list[dict[str, Any]] = []
        keep: set[str] = set()
        for item in items:
            app_id = item.get('id') or ''
            keep.add(app_id)
            fields = self._item_fields(club_key, item, field_pairs, state_key)
            record = existing.get(app_id)
            if record is None:
                creates.append({'fields': fields})
            elif any(self._field_changed(record['fields'].get(k), v) for k, v in fields.items()):
                updates.append({'id': record['id'], 'fields': fields})
        deletes = [record['id'] for app_id, record in existing.items() if app_id not in keep]
        if creates:
            self._batch('post', table, creates)
        if updates:
            self._batch('patch', table, updates)
        if deletes:
            self._batch('delete', table, deletes)

    # ── Cross-club user records ─────────────────────────────────────────────

    def get_user_record(self, email: str, *, strict: bool = False) -> dict[str, Any]:
        """Cross-club record for `email` — preferred display name and the
        session-invalidation counter. Defaults if the Users table is missing
        from this base, or the user has no row in it yet.

        `strict=True` re-raises StorageError instead of degrading to
        defaults — for callers (the session-staleness gate) that need to
        tell "the version really is 0" apart from "couldn't check"."""
        email = (email or '').strip().lower()
        defaults = {'preferredName': '', 'sessionVersion': 0}
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
            'preferredName': fields.get('Preferred Name') or '',
            'sessionVersion': int(fields.get('Session Version') or 0),
        }

    def save_user_record(self, email: str, fields: dict[str, Any]) -> None:
        """Upsert `fields` (preferredName and/or sessionVersion) onto the
        user's Users-table row. Raises StorageError (surfaced by the route as
        a setup instruction) if this base has no Users table yet."""
        email = (email or '').strip().lower()
        if not email:
            raise StorageError('Cannot save a user record without an email.')
        airtable_fields: dict[str, Any] = {}
        if 'preferredName' in fields:
            airtable_fields['Preferred Name'] = str(fields['preferredName'] or '')
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


def make_storage(session: dict[str, Any]) -> Any:
    """Build the backend named by STORAGE_BACKEND (default: session)."""
    if (session.get('user') or {}).get('provider') == 'playtest':
        return SessionStorage(session)
    backend = os.environ.get('STORAGE_BACKEND', 'session').strip().lower()
    if backend == 'airtable':
        return AirtableStorage()
    if backend in ('mongo', 'mongodb'):
        # Imported lazily so the pymongo dependency is only needed by
        # deployments that actually select this backend.
        from .storage_mongo import MongoStorage

        return MongoStorage()
    return SessionStorage(session)
