"""MongoDB storage backend for the dashboard state.

Selected with STORAGE_BACKEND=mongo. Requires MONGODB_URI (and optionally
MONGODB_DB, default "hackclub_leaders").

Unlike the Airtable backend, this one stores state keys verbatim — no field
name mapping — so a document is just the dashboard item plus the club it
belongs to:

    { _id: "<clubKey>|<appId>", clubKey: "leader@example.com", id: "mem-1",
      name: "Ada", email: "ada@example.com", ... }

The club row itself lives in `clubs` keyed by the leader email:

    { _id: "leader@example.com", clubKey: "...", clubName: "...", joinCode: ... }

Every query this module runs is backed by an index declared in INDEXES below;
ensure_indexes() creates them (idempotently) on first use and is also what
scripts/seed_mongo.py calls after importing from Airtable.
"""

import os
from typing import Any, Final, TypeAlias

from pymongo import ASCENDING, DESCENDING, MongoClient, ReplaceOne
from pymongo.errors import PyMongoError

from .storage import SHIPPED_STATUS, SUBMITTED_STATUS, StorageError

DEFAULT_DB_NAME: Final[str] = 'hackclub_leaders'

CLUBS_COLLECTION: Final[str] = 'clubs'
USERS_COLLECTION: Final[str] = 'users'

# State keys that live in their own collection, in the order load() assembles
# them. Mirrors AirtableStorage.CHILD_TABLES.
CHILD_COLLECTIONS: Final[list[str]] = [
    'members',
    'events',
    'newsletters',
    'orders',
    'itemRequests',
    'projects',
    'channels',
    'messages',
    'notifications',
    'ledger',
    'workshops',
]

# Every index the app's read paths rely on: {collection: [(keys, unique), ...]}.
# Each entry exists because some query below filters or sorts on exactly it.
# A third element, when present, is a dict of extra create_index kwargs
# (e.g. {'sparse': True} so pre-existing docs missing the field don't collide).
_IndexSpec: TypeAlias = tuple[list[tuple[str, int]], bool] | tuple[list[tuple[str, int]], bool, dict[str, bool]]
INDEXES: Final[dict[str, list[_IndexSpec]]] = {
    # find_club_by_join_code(); list_clubs() sorts by name.
    CLUBS_COLLECTION: [
        ([('joinCode', ASCENDING)], False),
        ([('clubName', ASCENDING)], False),
    ],
    # load()/load_lite() filter by clubKey; resolve_club_key() and
    # find_club_by_member_email() look a viewer up by email across all clubs.
    'members': [
        ([('clubKey', ASCENDING)], False),
        ([('email', ASCENDING)], False),
    ],
    # get_user_record()/save_user_record() look a user up by their own email —
    # _id IS the lowercased email, so no extra index is needed beyond the
    # default _id index Mongo always creates. No INDEXES entry for
    # USERS_COLLECTION on purpose.
    'events': [([('clubKey', ASCENDING), ('date', ASCENDING)], False)],
    'newsletters': [([('clubKey', ASCENDING), ('date', DESCENDING)], False)],
    'orders': [([('clubKey', ASCENDING), ('date', DESCENDING)], False)],
    # list_item_requests(): every club's requests, newest first.
    'itemRequests': [
        ([('clubKey', ASCENDING)], False),
        ([('date', DESCENDING)], False),
    ],
    # list_pending_projects() filters Status across all clubs and sorts by
    # date; list_clubs() counts ships per club by (clubKey, status).
    'projects': [
        ([('clubKey', ASCENDING), ('status', ASCENDING)], False),
        ([('status', ASCENDING), ('date', DESCENDING)], False),
        ([('isPublic', ASCENDING), ('status', ASCENDING), ('category', ASCENDING), ('date', DESCENDING)], False),
        # Sparse: projects created before Explore existed have no publicId;
        # a plain unique index would reject the second one as a duplicate null.
        ([('publicId', ASCENDING)], True, {'sparse': True}),
    ],
    'channels': [([('clubKey', ASCENDING)], False)],
    # The chat read path: one channel's thread in chronological order, which
    # is also what the `before` cursor pages backwards through.
    'messages': [
        ([('clubKey', ASCENDING), ('channelId', ASCENDING), ('createdAt', ASCENDING)], False),
        ([('clubKey', ASCENDING), ('createdAt', ASCENDING)], False),
        ([('clubKey', ASCENDING), ('parentId', ASCENDING), ('createdAt', ASCENDING)], False),
    ],
    # One read cursor per (channel, member) — upserted, never duplicated.
    'chatReads': [
        ([('clubKey', ASCENDING), ('channelId', ASCENDING), ('email', ASCENDING)], True),
    ],
    # The bell menu reads newest-first and counts unread.
    'notifications': [
        ([('clubKey', ASCENDING), ('createdAt', DESCENDING)], False),
        ([('clubKey', ASCENDING), ('read', ASCENDING)], False),
    ],
    'ledger': [
        ([('clubKey', ASCENDING), ('at', DESCENDING)], False),
    ],
    'workshops': [
        ([('clubKey', ASCENDING), ('createdAt', DESCENDING)], False),
    ],
}

# Item keys that are stored as-is but must never leak Mongo's own bookkeeping.
_INTERNAL_KEYS: Final[set[str]] = {'_id', 'clubKey'}

_client: MongoClient[Any] | None = None


def _get_client(uri: str) -> MongoClient[Any]:
    """One pooled client per process — reconnecting per request would cost
    more than every query it serves."""
    global _client
    if _client is None:
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000, tz_aware=False)
    return _client


def reset_client() -> None:
    """Drop the cached client (tests, and after changing MONGODB_URI)."""
    global _client
    if _client is not None:
        _client.close()
    _client = None


def ensure_indexes(db: Any) -> None:
    """Create every index in INDEXES. Idempotent — Mongo no-ops on an index
    that already exists with the same spec."""
    for collection, specs in INDEXES.items():
        for spec in specs:
            keys, unique = spec[0], spec[1]
            options: dict[str, bool] = spec[2] if len(spec) > 2 else {}
            # Any spec that diverges from the default (unique/sparse/partial)
            # gets an explicit name: Mongo auto-names by key pattern alone,
            # so changing options on an existing index raises IndexKeySpecsConflict
            # (code 86) instead of recreating it.
            name = None
            if options:
                name = '_'.join(field for field, _d in keys) + '_' + '_'.join(options)
            kwargs: dict[str, Any] = {'unique': unique, 'background': True}
            if name:
                kwargs['name'] = name
            kwargs.update(options)
            db[collection].create_index(keys, **kwargs)


class MongoStorage:
    """State shared across the club via MongoDB.

    Same interface as AirtableStorage, but each read is an indexed query
    instead of a filtered full-table scan, and load() can fetch a subset of
    sections so a page only pays for what it renders.
    """

    def __init__(self, uri: str | None = None, db_name: str | None = None) -> None:
        uri = uri or os.environ.get('MONGODB_URI', '')
        if not uri:
            raise StorageError('Mongo backend selected but MONGODB_URI is missing.')
        self.db_name = db_name or os.environ.get('MONGODB_DB', DEFAULT_DB_NAME)
        self.db = _get_client(uri)[self.db_name]
        self._indexed = False

    # ── Plumbing ─────────────────────────────────────────────────────────────

    def _ensure_indexes_once(self) -> None:
        if self._indexed:
            return
        try:
            ensure_indexes(self.db)
        except PyMongoError as exc:
            raise StorageError(f'Could not create MongoDB indexes: {exc}') from exc
        self._indexed = True

    @staticmethod
    def _doc_id(club_key: str, app_id: str) -> str:
        return f'{club_key}|{app_id}'

    @staticmethod
    def _to_item(doc: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in doc.items() if k not in _INTERNAL_KEYS}

    def _find(self, collection: str, query: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
        try:
            return list(self.db[collection].find(query, **kwargs))
        except PyMongoError as exc:
            raise StorageError(f'MongoDB read on {collection} failed: {exc}') from exc

    # ── Interface ────────────────────────────────────────────────────────────

    def resolve_club_key(self, viewer_email: str) -> str:
        """Members belong to the club whose roster lists their email;
        everyone else keys a club of their own."""
        email = (viewer_email or '').strip().lower()
        if not email:
            return email
        self._ensure_indexes_once()
        return self.find_club_by_member_email(email) or email

    def find_club_by_join_code(self, code: str) -> str | None:
        code = (code or '').strip()
        if not code:
            return None
        self._ensure_indexes_once()
        docs = self._find(CLUBS_COLLECTION, {'joinCode': code}, projection={'clubKey': 1}, limit=1)
        for doc in docs:
            key = (doc.get('clubKey') or '').strip().lower()
            if key:
                return key
        return None

    def find_club_by_member_email(self, email: str) -> str | None:
        email = (email or '').strip().lower()
        if not email:
            return None
        try:
            docs = self._find('members', {'email': email}, projection={'clubKey': 1}, limit=1)
        except StorageError:
            return None
        for doc in docs:
            key = (doc.get('clubKey') or '').strip().lower()
            if key:
                return key
        return None

    def list_clubs(self) -> list[dict[str, Any]]:
        """Summary of every club, for the admin overview. Member and project
        counts come from indexed aggregations, so no document bodies cross the
        wire just to be counted."""
        self._ensure_indexes_once()
        club_docs = self._find(
            CLUBS_COLLECTION,
            {},
            projection={'clubKey': 1, 'clubName': 1, 'location': 1},
        )
        member_counts = self._count_by_club('members', {})
        ship_counts = self._count_by_club('projects', {'status': SHIPPED_STATUS})
        pending_counts = self._count_by_club('projects', {'status': SUBMITTED_STATUS})

        clubs: list[dict[str, Any]] = []
        for doc in club_docs:
            key = (doc.get('clubKey') or '').strip().lower()
            if not key:
                continue
            clubs.append(
                {
                    'clubKey': key,
                    'clubName': doc.get('clubName') or 'Club',
                    'location': doc.get('location') or '',
                    'memberCount': member_counts.get(key, 0),
                    'shipCount': ship_counts.get(key, 0),
                    'pendingShips': pending_counts.get(key, 0),
                }
            )
        clubs.sort(key=lambda c: c['clubName'].lower())
        return clubs

    def _count_by_club(self, collection: str, match: dict[str, Any]) -> dict[str, int]:
        pipeline: list[dict[str, Any]] = []
        if match:
            pipeline.append({'$match': match})
        pipeline.append({'$group': {'_id': '$clubKey', 'n': {'$sum': 1}}})
        try:
            rows = list(self.db[collection].aggregate(pipeline))
        except PyMongoError as exc:
            raise StorageError(f'MongoDB count on {collection} failed: {exc}') from exc
        return {(row['_id'] or '').strip().lower(): row['n'] for row in rows if row.get('_id')}

    def _club_names(self) -> dict[str, str]:
        docs = self._find(CLUBS_COLLECTION, {}, projection={'clubKey': 1, 'clubName': 1})
        return {
            (doc.get('clubKey') or '').strip().lower(): doc.get('clubName') or 'Club'
            for doc in docs
        }

    def list_pending_projects(self) -> list[dict[str, Any]]:
        """Every Submitted project across all clubs, newest first. The status
        filter and the sort are both served by the (status, date) index."""
        self._ensure_indexes_once()
        club_names = self._club_names()
        docs = self._find(
            'projects',
            {'status': SUBMITTED_STATUS},
            sort=[('date', DESCENDING)],
        )
        return [
            {
                'clubKey': (doc.get('clubKey') or '').strip().lower(),
                'clubName': club_names.get(
                    (doc.get('clubKey') or '').strip().lower(),
                    (doc.get('clubKey') or '').strip().lower() or 'Unknown club',
                ),
                'project': self._to_item(doc),
            }
            for doc in docs
        ]

    def list_public_projects(self, club_key: str = '') -> list[dict[str, Any]]:
        """Return only fields that are safe to render on the private Explore pages.

        `club_key` set scopes the list to one club (the "Your club" filter);
        the key itself is never included in the projection.
        """
        self._ensure_indexes_once()
        clubs = self._find(
            CLUBS_COLLECTION,
            {'publicDirectory': True},
            projection={'clubKey': 1, 'clubName': 1},
        )
        public_clubs = {
            (club.get('clubKey') or '').strip().lower(): club.get('clubName') or 'Hack Club'
            for club in clubs
            if (club.get('clubKey') or '').strip()
        }
        if not public_clubs:
            return []
        club_filter = (club_key or '').strip().lower()
        query: dict[str, Any] = {
            'clubKey': {'$in': list(public_clubs)},
            'status': SHIPPED_STATUS,
            'isPublic': True,
        }
        if club_filter:
            query['clubKey'] = club_filter
        docs = self._find(
            'projects',
            query,
            sort=[('date', DESCENDING)],
        )
        return [
            {
                'publicId': doc.get('publicId') or '',
                'name': doc.get('name') or 'Untitled project',
                'description': doc.get('description') or '',
                'thumbnail': doc.get('thumbnail') or '',
                'demoUrl': doc.get('demoUrl') or doc.get('url') or '',
                'repoUrl': doc.get('repoUrl') or '',
                'ownerName': doc.get('ownerName') or 'Hack Clubber',
                'clubName': public_clubs.get((doc.get('clubKey') or '').strip().lower(), 'Hack Club'),
                'category': doc.get('category') or 'Other',
                'date': doc.get('date') or '',
            }
            for doc in docs
            if doc.get('publicId')
        ]

    def list_item_requests(self) -> list[dict[str, Any]]:
        """Every item request across all clubs, newest first."""
        self._ensure_indexes_once()
        club_names = self._club_names()
        docs = self._find('itemRequests', {}, sort=[('date', DESCENDING)])
        return [
            {
                'clubKey': (doc.get('clubKey') or '').strip().lower(),
                'clubName': club_names.get(
                    (doc.get('clubKey') or '').strip().lower(),
                    (doc.get('clubKey') or '').strip().lower() or 'Unknown club',
                ),
                'request': self._to_item(doc),
            }
            for doc in docs
        ]

    def _settings(self, club_key: str) -> dict[str, Any] | None:
        docs = self._find(CLUBS_COLLECTION, {'_id': club_key}, limit=1)
        if not docs:
            return None
        return self._to_item(docs[0])

    def load_lite(self, club_key: str) -> dict[str, Any] | None:
        """Just settings + members — enough for the membership gate and role
        check, so the page shell doesn't wait on chat history."""
        return self.load(club_key, sections=['members'], lite=True)

    def load(
        self,
        club_key: str,
        sections: list[str] | None = None,
        lite: bool = False,
    ) -> dict[str, Any] | None:
        """Full club state, or just the named sections.

        `sections` is a list of state keys from CHILD_COLLECTIONS; None means
        all of them. Unknown names are ignored rather than erroring, so a
        stale client can't 500 the endpoint.
        """
        self._ensure_indexes_once()
        settings = self._settings(club_key)
        if settings is None:
            return None

        wanted = (
            CHILD_COLLECTIONS
            if sections is None
            else [key for key in CHILD_COLLECTIONS if key in set(sections)]
        )
        state: dict[str, Any] = {'settings': settings}
        for key in wanted:
            sort = None
            if key == 'events':
                sort = [('date', ASCENDING)]
            elif key == 'messages':
                sort = [('createdAt', ASCENDING)]
            elif key == 'notifications':
                # The bell renders newest first.
                sort = [('createdAt', DESCENDING)]
            elif key == 'ledger':
                # Newest first: the bell menu's counterpart for coin history.
                sort = [('at', DESCENDING)]
            elif key == 'workshops':
                # Newest-proposed-first, matching the catalog page's default order.
                sort = [('createdAt', DESCENDING)]
            docs = self._find(key, {'clubKey': club_key}, sort=sort)
            state[key] = [self._to_item(doc) for doc in docs]
        if lite:
            state['_lite'] = True
        return state

    def save(self, club_key: str, state: dict[str, Any]) -> None:
        """Persist a full state dict. Sections absent from `state` are left
        untouched, so saving a lazily-loaded partial state can't wipe the
        sections that page never fetched."""
        self._ensure_indexes_once()
        settings = dict(state.get('settings') or {})
        doc = {**settings, '_id': club_key, 'clubKey': club_key}
        try:
            self.db[CLUBS_COLLECTION].replace_one({'_id': club_key}, doc, upsert=True)
        except PyMongoError as exc:
            raise StorageError(f'MongoDB write on clubs failed: {exc}') from exc

        for key in CHILD_COLLECTIONS:
            if key not in state:
                continue
            self._sync_children(key, club_key, state.get(key) or [])

    def _sync_children(self, collection: str, club_key: str, items: list[dict[str, Any]]) -> None:
        keep: set[str] = set()
        operations: list[ReplaceOne[Any]] = []
        for item in items:
            app_id = str(item.get('id') or '')
            doc_id = self._doc_id(club_key, app_id)
            keep.add(doc_id)
            doc = {
                **{k: v for k, v in item.items() if k not in _INTERNAL_KEYS},
                '_id': doc_id,
                'clubKey': club_key,
            }
            operations.append(ReplaceOne({'_id': doc_id}, doc, upsert=True))
        try:
            if operations:
                self.db[collection].bulk_write(operations, ordered=False)
            self.db[collection].delete_many({'clubKey': club_key, '_id': {'$nin': list(keep)}})
        except PyMongoError as exc:
            raise StorageError(f'MongoDB write on {collection} failed: {exc}') from exc

    # ── Chat paging ──────────────────────────────────────────────────────────

    def page_messages(
        self,
        club_key: str,
        channel_id: str,
        limit: int,
        before: str = '',
        since: str = '',
        parent_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        """One page of messages, oldest-first, plus whether older messages
        remain. `parent_id` set scopes to that thread's replies (matched by
        `parentId` alone — a reply's own `channelId` already equals its
        parent's); unset returns the channel's top-level view, excluding
        replies. Served entirely by one of two (clubKey, ..., createdAt)
        indexes — the app never loads a whole channel or thread to slice the
        tail off it.
        """
        self._ensure_indexes_once()
        if parent_id:
            query: dict[str, Any] = {'clubKey': club_key, 'parentId': parent_id}
        else:
            query = {
                'clubKey': club_key,
                'channelId': channel_id,
                'parentId': {'$exists': False},
            }
        if since:
            query['createdAt'] = {'$gt': since}
            docs = self._find('messages', query, sort=[('createdAt', ASCENDING)])
            return [self._to_item(doc) for doc in docs], False

        if before:
            query['createdAt'] = {'$lt': before}
        # Walk backwards from the newest, take one extra to detect "has more",
        # then flip to chronological for the client.
        docs = self._find(
            'messages', query, sort=[('createdAt', DESCENDING)], limit=limit + 1
        )
        has_more = len(docs) > limit
        page = list(reversed(docs[:limit]))
        return [self._to_item(doc) for doc in page], has_more

    # ── Cross-club user records ─────────────────────────────────────────────

    def get_user_record(self, email: str, *, strict: bool = False) -> dict[str, Any]:
        """Cross-club record for `email` — the session-invalidation counter.
        Defaults if no row exists yet.

        `strict=True` re-raises StorageError instead of degrading to
        defaults — for callers (the session-staleness gate) that need to
        tell "the version really is 0" apart from "couldn't check"."""
        email = (email or '').strip().lower()
        defaults = {'sessionVersion': 0}
        if not email:
            return defaults
        try:
            docs = self._find(USERS_COLLECTION, {'_id': email}, limit=1)
        except StorageError:
            if strict:
                raise
            return defaults
        if not docs:
            return defaults
        doc = docs[0]
        return {
            'sessionVersion': int(doc.get('sessionVersion') or 0),
        }

    def save_user_record(self, email: str, fields: dict[str, Any]) -> None:
        """Upsert `fields` (sessionVersion) onto the user's cross-club
        record, merging onto whatever's already there."""
        email = (email or '').strip().lower()
        if not email:
            raise StorageError('Cannot save a user record without an email.')
        update: dict[str, Any] = {}
        if 'sessionVersion' in fields:
            update['sessionVersion'] = int(fields['sessionVersion'] or 0)
        try:
            self.db[USERS_COLLECTION].update_one(
                {'_id': email}, {'$set': update}, upsert=True
            )
        except PyMongoError as exc:
            raise StorageError(f'MongoDB write on {USERS_COLLECTION} failed: {exc}') from exc
