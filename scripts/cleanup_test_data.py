"""Delete test records from the live Airtable base.

During development, sign-in tests created a throwaway club keyed to
dev@example.com. This removes that club's row and every child record
(members, events, ships, newsletters, orders) tied to it.

    python scripts/cleanup_test_data.py            # dry run, lists matches
    python scripts/cleanup_test_data.py --delete   # actually delete

Only touches records whose Club Email / Leader Email equals the target,
so your real clubs are never affected. Change TARGET_EMAILS if you seeded
other test accounts.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from storage import AirtableStorage, StorageError  # noqa: E402

TARGET_EMAILS = ['dev@example.com', 'mia@example.com', 'perf@example.com',
                 'lead@example.com']


def main():
    do_delete = '--delete' in sys.argv
    try:
        store = AirtableStorage()
    except StorageError as exc:
        print(f'FAIL  {exc}')
        sys.exit(1)

    total = 0
    for email in TARGET_EMAILS:
        email = email.strip().lower()
        print(f'\nClub: {email}')

        # Child tables keyed by Club Email.
        for _suffix, _default, state_key, _fields in store.CHILD_TABLES:
            table = store.tables[state_key]
            records = store._list(table, 'Club Email', email)
            total += len(records)
            print(f'  {table}: {len(records)} record(s)')
            if do_delete and records:
                store._batch('delete', table, [r['id'] for r in records])

        # The club row itself, keyed by Leader Email.
        clubs = store._list(store.clubs_table, 'Leader Email', email)
        total += len(clubs)
        print(f'  {store.clubs_table}: {len(clubs)} record(s)')
        if do_delete and clubs:
            store._batch('delete', store.clubs_table, [r['id'] for r in clubs])

    if do_delete:
        print(f'\nDeleted {total} record(s).')
    else:
        print(f'\n{total} record(s) match. Re-run with --delete to remove them.')


if __name__ == '__main__':
    main()
