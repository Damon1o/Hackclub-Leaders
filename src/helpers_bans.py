"""Site-wide banned-email list, stored in a JSON file like the shop catalog.

Admins add and remove addresses; join-code signup and chat posting both
check the list. The file lives next to the shop JSON so the same deployment
mechanism (mount/commit the file) applies.
"""

import json
import os
import tempfile
import threading
from typing import Any, Final

PROJECT_ROOT: Final[str] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANS_JSON_PATH: Final[str] = os.environ.get(
    'BANS_JSON_PATH', os.path.join(PROJECT_ROOT, 'banned_emails.json')
)
_BANS_LOCK: Final[threading.Lock] = threading.Lock()


def _read_raw() -> list[str]:
    try:
        with open(BANS_JSON_PATH, encoding='utf-8') as fh:
            raw: Any = json.load(fh)
    except (OSError, ValueError):
        return []
    return [e for e in raw if isinstance(e, str)]


def _write_raw(raw: list[str]) -> None:
    directory = os.path.dirname(BANS_JSON_PATH)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(sorted(set(e.strip().lower() for e in raw if e.strip())), fh, indent=2)
            fh.write('\n')
        os.replace(tmp, BANS_JSON_PATH)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def load_banned_emails() -> list[str]:
    with _BANS_LOCK:
        return sorted(set(e.strip().lower() for e in _read_raw() if e.strip()))


def is_banned_email(email: str) -> bool:
    email = (email or '').strip().lower()
    if not email or '@' not in email:
        return False
    return email in load_banned_emails()


def ban_email(email: str) -> bool:
    """Add an address to the ban list. Returns True if it was newly added."""
    email = (email or '').strip().lower()
    if not email or '@' not in email:
        raise ValueError('Enter a valid email address.')
    with _BANS_LOCK:
        raw = _read_raw()
        if email in raw:
            return False
        raw.append(email)
        _write_raw(raw)
    return True


def unban_email(email: str) -> bool:
    """Remove an address from the ban list. Returns True if it was removed."""
    email = (email or '').strip().lower()
    with _BANS_LOCK:
        raw = _read_raw()
        remaining = [e for e in raw if e != email]
        if len(remaining) == len(raw):
            return False
        _write_raw(remaining)
    return True


__all__ = [
    'BANS_JSON_PATH',
    'ban_email',
    'is_banned_email',
    'load_banned_emails',
    'unban_email',
]
