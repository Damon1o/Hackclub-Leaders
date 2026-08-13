"""Import club data from Airtable CSV exports into MongoDB.

Fallback for scripts/seed_mongo.py when Airtable's REST API is unusable (e.g.
a billing-limit lockout) but the base itself is still reachable through the
Airtable UI. Export each table as CSV (grid view "..." menu -> Download CSV)
into one directory, keeping the table's default name as the filename:

    Clubs.csv, Members.csv, Events.csv, Newsletters.csv, Orders.csv,
    ItemRequests.csv, Projects.csv, Channels.csv, Messages.csv,
    Notifications.csv, Ledger.csv, Workshops.csv

Then:

    python scripts/import_mongo_from_csv.py <dir>              # dry run
    python scripts/import_mongo_from_csv.py <dir> --apply       # write
    python scripts/import_mongo_from_csv.py <dir> --apply --drop

Missing CSVs degrade the same way AirtableStorage.load() does: optional
tables (everything except Clubs and Projects) are treated as empty. Needs
MONGODB_URI in the environment (.env is loaded automatically). Re-running is
safe: MongoStorage.save() upserts by a deterministic _id.
"""

import argparse
import csv
import json
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from src.storage import (  # noqa: E402
    BOOL_KEYS,
    SETTINGS_FIELDS,
    SETTINGS_INT_KEYS,
    AirtableStorage,
    StorageError,
)
from src.storage_mongo import (  # noqa: E402
    CHILD_COLLECTIONS,
    CLUBS_COLLECTION,
    MongoStorage,
    ensure_indexes,
)

REQUIRED_TABLES = {'Clubs', 'Projects'}
_TRUTHY = {'checked', 'true', '1', 'yes', 'x'}


def _read_csv(path: str) -> list[dict[str, str]]:
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def _as_bool(value: str | None) -> bool:
    return (value or '').strip().lower() in _TRUTHY


def _as_int(value: str | None) -> int:
    try:
        return int(float(value)) if value not in (None, '') else 0
    except ValueError:
        return 0


def _settings_from_row(row: dict[str, str]) -> dict[str, object]:
    settings: dict[str, object] = {}
    for state_key, field in SETTINGS_FIELDS:
        value = row.get(field)
        if state_key in BOOL_KEYS:
            settings[state_key] = _as_bool(value)
        elif state_key in SETTINGS_INT_KEYS:
            settings[state_key] = _as_int(value)
        else:
            settings[state_key] = value or ''
    return settings


def _item_from_row(row: dict[str, str], state_key: str, field_pairs: list[tuple[str, str]]) -> dict[str, object]:
    item: dict[str, object] = {'id': (row.get('App Id') or '').strip()}
    for item_key, field in field_pairs:
        value = row.get(field)
        if item_key in BOOL_KEYS:
            item[item_key] = _as_bool(value)
        elif item_key in ('attendees', 'delta'):
            item[item_key] = _as_int(value)
        else:
            item[item_key] = value or ''
    if state_key == 'orders':
        try:
            item['items'] = json.loads(row.get('Items') or '[]')
        except ValueError:
            item['items'] = []
    if state_key == 'messages':
        try:
            reactions = json.loads(row.get('Reactions') or '{}')
        except ValueError:
            reactions = {}
        if reactions:
            item['reactions'] = reactions
    if state_key == 'notifications':
        try:
            item['data'] = json.loads(row.get('Data') or '{}')
        except ValueError:
            item['data'] = {}
    if state_key == 'workshops':
        try:
            item['applicants'] = json.loads(row.get('Applicants') or '[]')
        except ValueError:
            item['applicants'] = []
    return item


def load_states(directory: str) -> tuple[list[str], dict[str, dict[str, object]], dict[str, int]]:
    """Mirror AirtableStorage.load() output for every club, built from CSVs."""
    clubs_rows = _read_csv(os.path.join(directory, 'Clubs.csv'))
    if not clubs_rows:
        raise StorageError(f'No Clubs.csv found (or empty) in {directory}')

    club_keys: list[str] = []
    states: dict[str, dict[str, object]] = {}
    for row in clubs_rows:
        key = (row.get('Leader Email') or '').strip().lower()
        if not key:
            continue
        club_keys.append(key)
        states[key] = {'settings': _settings_from_row(row)}

    skipped: dict[str, int] = {}
    for _suffix, default_name, state_key, field_pairs in AirtableStorage.CHILD_TABLES:
        rows = _read_csv(os.path.join(directory, f'{default_name}.csv'))
        if not rows and default_name in REQUIRED_TABLES:
            raise StorageError(f'{default_name}.csv missing or empty in {directory}')
        buckets: dict[str, list[dict[str, object]]] = {key: [] for key in club_keys}
        missing = 0
        for row in rows:
            club_email = (row.get('Club Email') or '').strip().lower()
            app_id = (row.get('App Id') or '').strip()
            if club_email not in buckets or not app_id:
                missing += 1
                continue
            buckets[club_email].append(_item_from_row(row, state_key, field_pairs))
        if missing:
            skipped[default_name] = missing
        for key, items in buckets.items():
            states[key][state_key] = items

    return club_keys, states, skipped


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('directory', help='folder containing the exported CSVs')
    parser.add_argument(
        '--apply', action='store_true', help='write to MongoDB (default is a dry run)'
    )
    parser.add_argument(
        '--drop',
        action='store_true',
        help='drop the target collections before importing (implies --apply)',
    )
    args = parser.parse_args()
    apply_changes = args.apply or args.drop

    try:
        club_keys, states, skipped = load_states(args.directory)
    except StorageError as exc:
        print(f'CSV source unavailable: {exc}')
        return 1

    try:
        mongo = MongoStorage()
    except StorageError as exc:
        print(f'MongoDB target unavailable: {exc}')
        return 1

    print(f'Source: CSV export at {args.directory}')
    print(f'Target: MongoDB database {mongo.db_name}')
    if not apply_changes:
        print('DRY RUN — nothing will be written. Re-run with --apply to commit.\n')

    if args.drop:
        for name in [CLUBS_COLLECTION, *CHILD_COLLECTIONS]:
            mongo.db[name].drop()
        print(f'Dropped {len(CHILD_COLLECTIONS) + 1} collections.')

    if apply_changes:
        ensure_indexes(mongo.db)
        print('Indexes ensured.')

    print(f'Found {len(club_keys)} club(s).\n')

    migrated = 0
    failures: list[tuple[str, str]] = []
    for key in club_keys:
        state = states[key]
        counts = ', '.join(
            f'{name} {len(state.get(name) or [])}' for name in CHILD_COLLECTIONS if state.get(name)
        )
        print(f'  {key}: {counts or "no child records"}')
        if apply_changes:
            try:
                mongo.save(key, state)
            except StorageError as exc:
                failures.append((key, str(exc)))
                print(f'  {key}: WRITE FAILED — {exc}')
                continue
        migrated += 1

    verb = 'Migrated' if apply_changes else 'Would migrate'
    print(f'\n{verb} {migrated}/{len(club_keys)} club(s).')
    if skipped:
        print('\nRows skipped (no matching club or missing App Id):')
        for table, count in skipped.items():
            print(f'  {table}.csv: {count} row(s) skipped')
    if failures:
        print(f'{len(failures)} failure(s):')
        for key, reason in failures:
            print(f'  {key}: {reason}')
        return 1
    if apply_changes:
        print('Done. Set STORAGE_BACKEND=mongo to start serving from MongoDB.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
