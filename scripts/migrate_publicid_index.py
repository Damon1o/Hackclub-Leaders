"""One-time local dev migration: drop the legacy non-sparse publicId index.

The earlier Explore WIP created a unique index named 'publicId_1' without
sparse=True. The new code creates 'publicId_1_sparse' instead, so this old
index is no longer declared anywhere and would keep rejecting saves of
projects that predate Explore. Index-only change; documents untouched.
"""

import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

uri = os.environ.get('MONGODB_URI', '')
db_name = os.environ.get('MONGODB_DB', 'hackclub_leaders')
if not uri:
    print('No MONGODB_URI in .env — nothing to do.')
    raise SystemExit(0)

client = MongoClient(uri, serverSelectionTimeoutMS=5000)
db = client[db_name]
names = {name: info for name, info in db['projects'].index_information().items()}

if 'publicId_1' in names and not names['publicId_1'].get('sparse'):
    db['projects'].drop_index('publicId_1')
    print('Dropped legacy non-sparse index publicId_1.')
else:
    print('No legacy index to drop.')

print('Remaining projects indexes:', sorted(db['projects'].index_information()))
