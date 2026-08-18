"""State loading, persistence, and coin management helpers."""

from typing import cast

from .helpers_types import CoinTransaction, DashboardState, Settings


def utc_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def award_coins(
    state: DashboardState, delta: int, kind: str, ref: str = '', note: str = ''
) -> CoinTransaction:
    import secrets
    settings = state.setdefault('settings', cast(Settings, {}))
    balance = settings.get('coinBalance', 0)
    spent = settings.get('coinsSpent', 0)
    if delta > 0:
        settings['coinBalance'] = balance + delta
    else:
        spent_amount = abs(delta)
        settings['coinBalance'] = max(0, balance - spent_amount)
        settings['coinsSpent'] = spent + spent_amount
    ledger = state.setdefault('ledger', [])
    tx: CoinTransaction = {
        'id': f'tx-{secrets.token_hex(4)}',
        'delta': delta,
        'kind': kind,
        'ref': ref,
        'note': note,
        'at': utc_iso(),
    }
    ledger.insert(0, tx)
    return tx


def award_coins_if_unprocessed(
    state: DashboardState,
    delta: int,
    kind: str,
    ref: str,
    note: str = '',
) -> CoinTransaction | None:
    ledger = state.get('ledger') or []
    if ref and any(tx.get('ref') == ref and tx.get('kind') == kind for tx in ledger):
        return None
    return award_coins(state, delta, kind, ref, note)


def log_action(state: DashboardState, actor: str, action: str, target: str = '') -> dict:
    """Append one audit row to the club's audit log, newest first."""
    import secrets

    entry = {
        'id': f'al-{secrets.token_hex(4)}',
        'actor': (actor or 'admin').strip(),
        'action': action,
        'target': (target or '').strip(),
        'at': utc_iso(),
    }
    log = state.setdefault('auditLog', [])
    log.insert(0, entry)
    return entry
