"""Create the chat tables (Channels, Messages) in the configured Airtable base.

Idempotent: skips any table that already exists. Requires AIRTABLE_TOKEN with
the `schema.bases:write` scope and AIRTABLE_BASE_ID (read from .env).

    python scripts/setup_chat_tables.py

Field names/casing here MUST match src/storage.py (CHANNEL_FIELDS,
MESSAGE_FIELDS) plus the auto columns 'App Id' (primary key) and 'Club Email'.
Timestamps are singleLineText on purpose — the app stores and compares raw ISO
strings, so an Airtable date type would reformat them and break ?since polling.
"""

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

META_API = 'https://api.airtable.com/v0/meta/bases'

# (table name, [(field name, airtable field type), ...]); first field is primary.
TABLES = {
    'Channels': [
        ('App Id', 'singleLineText'),
        ('Name', 'singleLineText'),
        ('Description', 'singleLineText'),
        ('Created By', 'singleLineText'),
        ('Last Message At', 'singleLineText'),
        ('Club Email', 'singleLineText'),
    ],
    'Messages': [
        ('App Id', 'singleLineText'),
        ('Channel Id', 'singleLineText'),
        ('Author Email', 'singleLineText'),
        ('Author Name', 'singleLineText'),
        ('Author Avatar', 'singleLineText'),
        ('Body', 'multilineText'),
        ('Created At', 'singleLineText'),
        ('Club Email', 'singleLineText'),
    ],
}


def main():
    token = os.environ.get('AIRTABLE_TOKEN', '').strip()
    base_id = os.environ.get('AIRTABLE_BASE_ID', '').strip()
    if not token or not base_id:
        sys.exit('AIRTABLE_TOKEN and AIRTABLE_BASE_ID must be set (check your .env).')

    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    # Which tables already exist?
    resp = requests.get(f'{META_API}/{base_id}/tables', headers=headers, timeout=15)
    if resp.status_code == 403:
        sys.exit(
            '403 from Airtable: your token lacks the "schema.bases:write" (and '
            '"schema.bases:read") scope. Add it at airtable.com/create/tokens, '
            'or create the tables manually.'
        )
    resp.raise_for_status()
    existing = {t['name'] for t in resp.json().get('tables', [])}

    for name, fields in TABLES.items():
        if name in existing:
            print(f'= {name}: already exists, skipping')
            continue
        payload = {
            'name': name,
            'fields': [{'name': fname, 'type': ftype} for fname, ftype in fields],
        }
        create = requests.post(
            f'{META_API}/{base_id}/tables', headers=headers, json=payload, timeout=15
        )
        if create.status_code == 403:
            sys.exit(
                f'x {name}: 403 on create. Your token can read the schema but '
                'not write it — add the "schema.bases:write" scope to your token '
                'at airtable.com/create/tokens (and give it access to this base), '
                'then re-run. Or create the tables manually.'
            )
        if create.status_code >= 400:
            detail = ''
            try:
                detail = create.json().get('error', {})
            except ValueError:
                detail = create.text[:300]
            sys.exit(f'x {name}: create failed ({create.status_code}): {detail}')
        print(f'+ {name}: created with {len(fields)} fields')

    print('\nDone. Restart the app — chat will now save and be visible to members.')


if __name__ == '__main__':
    main()
