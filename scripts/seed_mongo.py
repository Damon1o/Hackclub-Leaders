"""Copy every club out of Airtable and into MongoDB.

Run once when switching STORAGE_BACKEND from `airtable` to `mongo`:

    python scripts/seed_mongo.py            # dry run — reports what it would write
    python scripts/seed_mongo.py --apply    # actually write
    python scripts/seed_mongo.py --apply --drop   # wipe target collections first

Needs AIRTABLE_TOKEN, AIRTABLE_BASE_ID, and MONGODB_URI in the environment
(.env is loaded automatically). Re-running is safe: every document is upserted
by a deterministic _id, so a second run overwrites rather than duplicates.
"""

import argparse
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from src.storage import AirtableStorage, StorageError  # noqa: E402
from src.storage_mongo import (  # noqa: E402
    CHILD_COLLECTIONS,
    CLUBS_COLLECTION,
    MongoStorage,
    ensure_indexes,
)


def club_keys(airtable: AirtableStorage) -> list[str]:
    """Every club key in the base, taken from the Clubs table."""
    records = airtable._list_all(airtable.clubs_table, ['Leader Email'])
    keys = []
    for record in records:
        key = (record['fields'].get('Leader Email') or '').strip().lower()
        if key and key not in keys:
            keys.append(key)
    return keys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--apply', action='store_true', help='write to MongoDB (default is a dry run)'
    )
    parser.add_argument(
        '--drop',
        action='store_true',
        help='drop the target collections before seeding (implies --apply)',
    )
    args = parser.parse_args()
    apply_changes = args.apply or args.drop

    try:
        airtable = AirtableStorage()
    except StorageError as exc:
        print(f'Airtable source unavailable: {exc}')
        return 1
    try:
        mongo = MongoStorage()
    except StorageError as exc:
        print(f'MongoDB target unavailable: {exc}')
        return 1

    print(f'Source: Airtable base {airtable.base_id}')
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

    keys = club_keys(airtable)
    print(f'Found {len(keys)} club(s).\n')

    migrated = 0
    failures: list[tuple[str, str]] = []
    for key in keys:
        try:
            state = airtable.load(key)
        except StorageError as exc:
            failures.append((key, str(exc)))
            print(f'  {key}: READ FAILED — {exc}')
            continue
        if state is None:
            failures.append((key, 'club not found in Airtable'))
            print(f'  {key}: skipped (no club row)')
            continue

        counts = ', '.join(
            f'{name} {len(state.get(name) or [])}'
            for name in CHILD_COLLECTIONS
            if state.get(name)
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
    print(f'\n{verb} {migrated}/{len(keys)} club(s).')
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
