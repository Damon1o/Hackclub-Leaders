from src.helpers import (
    CoinTransaction,
    Settings,
    award_coins,
    coin_balance,
    coins_spent,
    reconcile_coins,
)
from src.storage import SETTINGS_FIELDS, AirtableStorage
from src.storage_mongo import CHILD_COLLECTIONS, INDEXES


def _tx(delta: int, kind: str = 'ship_approved') -> CoinTransaction:
    return {
        'id': 'coin-x',
        'delta': delta,
        'kind': kind,
        'ref': '',
        'note': '',
        'at': '2026-08-07T00:00:00Z',
    }


def test_coin_balance_sums_all_deltas():
    ledger = [_tx(25), _tx(-10), _tx(50)]
    assert coin_balance(ledger) == 65


def test_coin_balance_empty_ledger_is_zero():
    assert coin_balance([]) == 0


def test_coins_spent_only_counts_negative_deltas():
    ledger = [_tx(25), _tx(-10), _tx(-5)]
    assert coins_spent(ledger) == 15


def test_coins_spent_ignores_earn_entries():
    ledger = [_tx(25), _tx(50)]
    assert coins_spent(ledger) == 0


def test_reconcile_coins_writes_cache_into_settings():
    state = {'ledger': [_tx(25), _tx(-10)], 'settings': {}}
    reconcile_coins(state)
    assert state['settings']['coinBalance'] == 15
    assert state['settings']['coinsSpent'] == 10


def test_reconcile_coins_handles_missing_ledger_key():
    state = {'settings': {}}
    reconcile_coins(state)
    assert state['settings']['coinBalance'] == 0
    assert state['settings']['coinsSpent'] == 0


def test_award_coins_appends_transaction_and_reconciles():
    state = {'ledger': [], 'settings': {}}
    tx = award_coins(state, 25, 'ship_approved', 'proj-1', 'Approved: Tide Tracker')
    assert len(state['ledger']) == 1
    assert state['ledger'][0] is tx
    assert tx['delta'] == 25
    assert tx['kind'] == 'ship_approved'
    assert tx['ref'] == 'proj-1'
    assert tx['id']
    assert tx['at']
    assert state['settings']['coinBalance'] == 25


def test_award_coins_creates_ledger_key_if_absent():
    state = {'settings': {}}
    award_coins(state, -10, 'shop_order', 'order-1', 'Order: Stickers')
    assert state['ledger'][0]['delta'] == -10
    assert state['settings']['coinBalance'] == -10


def test_award_coins_negative_delta_updates_spent_cache():
    state = {'ledger': [], 'settings': {}}
    award_coins(state, 50, 'starter_grant', '', 'Welcome grant')
    award_coins(state, -30, 'shop_order', 'order-1', 'Order: Pin')
    assert state['settings']['coinBalance'] == 20
    assert state['settings']['coinsSpent'] == 30


def test_every_state_section_has_an_airtable_table():
    from src.helpers import STATE_SECTIONS

    airtable_keys = {state_key for _s, _d, state_key, _f in AirtableStorage.CHILD_TABLES}
    missing = set(STATE_SECTIONS) - airtable_keys
    assert not missing, f'STATE_SECTIONS keys with no AirtableStorage.CHILD_TABLES entry: {missing}'


def test_every_state_section_has_a_mongo_collection():
    from src.helpers import STATE_SECTIONS

    missing = set(STATE_SECTIONS) - set(CHILD_COLLECTIONS)
    assert not missing, f'STATE_SECTIONS keys with no Mongo CHILD_COLLECTIONS entry: {missing}'


def test_every_mongo_collection_has_an_index():
    missing = set(CHILD_COLLECTIONS) - set(INDEXES)
    assert not missing, f'CHILD_COLLECTIONS with no INDEXES entry: {missing}'


def test_every_settings_key_has_an_airtable_field():
    # `language` is a session-local preference that predates this backfill
    # and is not yet synced to Airtable at all (pre-existing gap, out of
    # this fix's scope) — tracked here explicitly so no *other* Settings key
    # can silently join it without this test catching it.
    known_gaps = {'language'}
    airtable_keys = {state_key for state_key, _field in SETTINGS_FIELDS}
    missing = set(Settings.__annotations__) - airtable_keys - known_gaps
    assert not missing, f'Settings keys with no AirtableStorage.SETTINGS_FIELDS entry: {missing}'


def test_default_dashboard_state_seeds_a_starter_grant(client):
    with client.session_transaction() as sess:
        sess['user'] = {'name': 'Test Leader', 'email': 'leader@test.com'}
    with client.application.test_request_context():
        from flask import session as flask_session

        flask_session['user'] = {'name': 'Test Leader', 'email': 'leader@test.com'}
        from src.helpers import STARTER_GRANT_COINS, default_dashboard_state

        state = default_dashboard_state()
        assert len(state['ledger']) == 1
        assert state['ledger'][0]['kind'] == 'starter_grant'
        assert state['ledger'][0]['delta'] == STARTER_GRANT_COINS
        assert state['settings']['coinBalance'] == STARTER_GRANT_COINS
        assert state['settings']['coinsSpent'] == 0


def test_get_dashboard_state_reconciles_stale_mongo_settings_cache(client, monkeypatch):
    """Regression for a pre-existing MongoDB-backed club whose stored
    `settings` document predates the coin fields: schemaless Mongo never
    defaulted `coinBalance`/`coinsSpent` onto that document, so they're
    genuinely absent, while the `ledger` collection query correctly returns
    a real, present, empty list (no transactions exist yet).

    Without the fix, get_dashboard_state()'s settings-backfill loop fills
    the missing settings keys from a throwaway default_dashboard_state()
    call, which side-effects its own STARTER_GRANT_COINS award — handing
    this real, empty-ledger club a phantom 50-coin balance with zero
    backing transactions. The cache must instead be recomputed from the
    ledger this club actually has.

    Storage is mocked directly (not forced into session mode) so the two
    independent backfill loops — top-level state keys vs. settings
    sub-keys — actually diverge the way they do against a schemaless
    backend: `ledger` present and empty, `settings` missing the coin keys.
    """
    with client.session_transaction() as sess:
        sess['user'] = {'name': 'Test Leader', 'email': 'leader@test.com'}

    with client.application.test_request_context():
        from flask import session as flask_session

        flask_session['user'] = {'name': 'Test Leader', 'email': 'leader@test.com'}

        stale_state = {
            'members': [],
            'ledger': [],  # real, present, empty — as Mongo's own query returns
            'settings': {
                'joinCode': 'abc123xyz',
                'clubName': "Test Leader's Hack Club",
                # coinBalance/coinsSpent intentionally absent: pre-migration doc
            },
        }

        class FakeMongoLikeStorage:
            def load(self, club_key: str, sections: list[str] | None = None) -> dict:
                return dict(stale_state)

            def resolve_club_key(self, email: str) -> str:
                return email

        import src.helpers as helpers_module

        monkeypatch.setattr(helpers_module, '_storage', lambda: FakeMongoLikeStorage())

        from src.helpers import coin_balance, get_dashboard_state

        state = get_dashboard_state()

        assert state['ledger'] == []
        assert coin_balance(state['ledger']) == 0
        assert state['settings']['coinBalance'] == coin_balance(state['ledger'])
        assert state['settings']['coinBalance'] == 0
        assert state['settings']['coinsSpent'] == 0


def _seed_cart_club(client, monkeypatch, ledger=None, cart=None):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    # get_dashboard_state() unconditionally overwrites state['shopItems'] with
    # the process-global helpers.SHOP_ITEMS catalog (src/helpers.py:882) —
    # the shop catalog is shared across every club, not per-club data, so a
    # 'shopItems' key seeded into this club's session (below) is never read
    # by api_cart_add. Patch the actual catalog the endpoint reads instead,
    # or these tests would exercise the real static/data/shop.json contents
    # (where Sticker Pack costs 0, not 15, and Mystery Box doesn't exist).
    import src.helpers as helpers_module

    monkeypatch.setattr(
        helpers_module,
        'SHOP_ITEMS',
        [
            {
                'id': 'sticker-pack',
                'name': 'Sticker Pack',
                'cost': 15,
                'image_src': '',
                'filter': 'Swag',
            },
            {
                'id': 'mystery-box',
                'name': 'Mystery Box',
                'cost': None,
                'image_src': '',
                'filter': 'Swag',
            },
        ],
    )
    with client.session_transaction() as sess:
        sess['csrf_token'] = 'tok'
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Cart Club', 'coinBalance': 0, 'coinsSpent': 0},
            'members': [],
            'shopItems': [
                {
                    'id': 'sticker-pack',
                    'name': 'Sticker Pack',
                    'cost': 15,
                    'image_src': '',
                    'filter': 'Swag',
                },
                {
                    'id': 'mystery-box',
                    'name': 'Mystery Box',
                    'cost': None,
                    'image_src': '',
                    'filter': 'Swag',
                },
            ],
            'cart': cart or [],
            'orders': [],
            'ledger': ledger or [],
        }


HEADERS = {'X-CSRF-Token': 'tok'}


def test_cart_add_snapshots_coin_cost(auth_client, monkeypatch):
    _seed_cart_club(auth_client, monkeypatch)
    response = auth_client.post(
        '/api/dashboard/cart', headers=HEADERS, json={'itemId': 'sticker-pack', 'quantity': 2}
    )
    assert response.status_code == 200
    cart = response.get_json()['state']['cart']
    assert cart[0]['coinCost'] == 15
    assert cart[0]['quantity'] == 2


def test_cart_add_rejects_unpriced_item(auth_client, monkeypatch):
    _seed_cart_club(auth_client, monkeypatch)
    response = auth_client.post(
        '/api/dashboard/cart', headers=HEADERS, json={'itemId': 'mystery-box'}
    )
    assert response.status_code == 400


def test_checkout_debits_ledger_on_success(auth_client, monkeypatch):
    ledger = [
        {
            'id': 'c1',
            'delta': 50,
            'kind': 'starter_grant',
            'ref': '',
            'note': '',
            'at': '2026-08-07T00:00:00Z',
        }
    ]
    cart = [{'id': 'sticker-pack', 'quantity': 2, 'coinCost': 15}]
    _seed_cart_club(auth_client, monkeypatch, ledger=ledger, cart=cart)
    response = auth_client.post('/api/dashboard/checkout', headers=HEADERS)
    assert response.status_code == 200
    state = response.get_json()['state']
    assert state['settings']['coinBalance'] == 20  # 50 - (15*2)
    assert state['settings']['coinsSpent'] == 30
    assert any(t['kind'] == 'shop_order' for t in state['ledger'])
    assert state['cart'] == []


def test_checkout_rejects_when_over_budget(auth_client, monkeypatch):
    ledger = [
        {
            'id': 'c1',
            'delta': 10,
            'kind': 'starter_grant',
            'ref': '',
            'note': '',
            'at': '2026-08-07T00:00:00Z',
        }
    ]
    cart = [{'id': 'sticker-pack', 'quantity': 2, 'coinCost': 15}]
    _seed_cart_club(auth_client, monkeypatch, ledger=ledger, cart=cart)
    response = auth_client.post('/api/dashboard/checkout', headers=HEADERS)
    assert response.status_code == 400
    with auth_client.session_transaction() as sess:
        assert sess['dashboard_state']['cart'] == cart  # unchanged — nothing was debited
