"""Airtable readiness check.

Run this after creating your base and setting AIRTABLE_TOKEN /
AIRTABLE_BASE_ID, and before flipping STORAGE_BACKEND=airtable:

    python scripts/check_airtable.py

It verifies the token works, every table exists, and each table has the
fields storage.py reads and writes. Exits non-zero if anything is missing.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

import requests  # noqa: E402  (after load_dotenv on purpose)

REQUIRED_FIELDS = {
    'Clubs': [
        'Leader Email',
        'Club Name',
        'Location',
        'Website',
        'Avatar',
        'Join Code',
        'Public Directory',
        'Email Notifications',
        'Dark Mode Default',
        'Newsletter Subscribed',
    ],
    'Members': ['App Id', 'Name', 'Email', 'Role', 'Status', 'Avatar', 'Club Email'],
    'Events': [
        'App Id',
        'Title',
        'Date',
        'Time',
        'Location',
        'Type',
        'Repeat',
        'RSVP',
        'Attendees',
        'Club Email',
    ],
    'Projects': [
        'App Id',
        'Name',
        'Description',
        'URL',
        'Repo URL',
        'Demo URL',
        'Thumbnail',
        'Hackatime Project',
        'Status',
        'Owner Email',
        'Owner Name',
        'Date',
        'Club Email',
    ],
    'Newsletters': [
        'App Id',
        'Title',
        'Excerpt',
        'Body',
        'Date',
        'Read Time',
        'Read',
        'Club Email',
    ],
    'Orders': ['App Id', 'Date', 'Status', 'Items', 'Club Email'],
}

OPTIONAL_FIELDS = {
    'ItemRequests': ['App Id', 'Name', 'Note', 'Date', 'Status', 'Club Email'],
}

ENV_TABLE_OVERRIDES = {
    'Clubs': 'AIRTABLE_TABLE_CLUBS',
    'Members': 'AIRTABLE_TABLE_MEMBERS',
    'Events': 'AIRTABLE_TABLE_EVENTS',
    'Projects': 'AIRTABLE_TABLE_PROJECTS',
    'Newsletters': 'AIRTABLE_TABLE_NEWSLETTERS',
    'Orders': 'AIRTABLE_TABLE_ORDERS',
    'ItemRequests': 'AIRTABLE_TABLE_ITEM_REQUESTS',
}


def fail(message):
    print(f'  FAIL  {message}')
    sys.exit(1)


def main():
    token = os.environ.get('AIRTABLE_TOKEN', '')
    base_id = os.environ.get('AIRTABLE_BASE_ID', '')
    if not token:
        fail('AIRTABLE_TOKEN is not set (add it to your .env).')
    if not base_id:
        fail('AIRTABLE_BASE_ID is not set (add it to your .env).')

    print(f'Base: {base_id}')
    response = requests.get(
        f'https://api.airtable.com/v0/meta/bases/{base_id}/tables',
        headers={'Authorization': f'Bearer {token}'},
        timeout=15,
    )
    if response.status_code == 401:
        fail(
            'Token rejected (401). Check AIRTABLE_TOKEN and its scopes — '
            'it needs data.records:read, data.records:write, and '
            'schema.bases:read for this base.'
        )
    if response.status_code == 404:
        fail(
            'Base not found (404). Check AIRTABLE_BASE_ID (starts with '
            '"app") and that the token has access to this base.'
        )
    if response.status_code >= 400:
        fail(f'Airtable metadata API returned {response.status_code}: {response.text[:200]}')

    tables = {table['name']: table for table in response.json()['tables']}
    problems = 0

    for default_name, required in REQUIRED_FIELDS.items():
        name = os.environ.get(ENV_TABLE_OVERRIDES[default_name], default_name)
        table = tables.get(name)
        if table is None:
            print(f'  MISSING TABLE  {name}')
            problems += 1
            continue
        have = {field['name'] for field in table['fields']}
        missing = [field for field in required if field not in have]
        if missing:
            print(f'  {name}: missing fields -> {", ".join(missing)}')
            problems += 1
        else:
            print(f'  OK    {name}')

    # Optional tables: warn but don't fail — the app degrades gracefully.
    for default_name, required in OPTIONAL_FIELDS.items():
        name = os.environ.get(ENV_TABLE_OVERRIDES[default_name], default_name)
        table = tables.get(name)
        if table is None:
            print(
                f"  OPTIONAL (absent)  {name} — that feature won't persist "
                'until you add this table.'
            )
            continue
        have = {field['name'] for field in table['fields']}
        missing = [field for field in required if field not in have]
        if missing:
            print(f'  OPTIONAL {name}: missing fields -> {", ".join(missing)}')
        else:
            print(f'  OK    {name}')

    if problems:
        print(
            f'\n{problems} required table(s) need attention. Fix them in '
            'Airtable and run this again.'
        )
        sys.exit(1)

    print('\nRequired tables ready. Set STORAGE_BACKEND=airtable and restart the app.')


if __name__ == '__main__':
    main()
