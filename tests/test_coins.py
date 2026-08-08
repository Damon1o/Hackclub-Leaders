from src.helpers import CoinTransaction, award_coins, coin_balance, coins_spent, reconcile_coins
from src.storage import AirtableStorage
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
