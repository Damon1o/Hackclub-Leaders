import os
import secrets

import flask
from dotenv import load_dotenv
from flask import Flask, flash, redirect, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from helpers import (
    StateTooLarge,
    get_csrf_token,
    is_admin,
    json_error,
    viewer_is_leader,
    viewer_role,
)
from storage import StorageError

load_dotenv()

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

HACKCLUB_CLIENT_ID     = os.environ.get('HACKCLUB_CLIENT_ID', '')
HACKCLUB_CLIENT_SECRET = os.environ.get('HACKCLUB_CLIENT_SECRET', '')
BASE_URL               = os.environ.get('BASE_URL', '')

HACKATIME_CLIENT_ID     = os.environ.get('HACKATIME_CLIENT_ID', '')
HACKATIME_CLIENT_SECRET = os.environ.get('HACKATIME_CLIENT_SECRET', '')

MAX_IMAGE_BYTES = 4 * 1024 * 1024
app.config['MAX_CONTENT_LENGTH'] = MAX_IMAGE_BYTES + 512 * 1024


# ── Error handlers ────────────────────────────────────────────────────────────

@app.errorhandler(StateTooLarge)
def handle_state_too_large(_error):
    return flask.jsonify({
        'error': 'Your club data is full — this demo stores everything in a browser cookie. '
                 'Remove an old dispatch, event, or member before adding more.'
    }), 413


@app.errorhandler(StorageError)
def handle_storage_error(error):
    if request.path.startswith('/api/'):
        return flask.jsonify({'error': f'Database error: {error}'}), 502
    flash(f'Database error: {error}', 'error')
    return redirect(url_for('index'))


@app.errorhandler(413)
def _payload_too_large(_error):
    return json_error('That file is too large — images must be 4 MB or smaller.', 413)


# ── Context processor ─────────────────────────────────────────────────────────

@app.context_processor
def inject_user():
    signed_in = bool(session.get('user'))
    return dict(
        current_user=session.get('user'),
        csrf_token=get_csrf_token() if signed_in else '',
        viewer_role=viewer_role() if signed_in else '',
        is_leader=viewer_is_leader() if signed_in else False,
        is_admin=is_admin() if signed_in else False,
    )


# ── Route registration (imported at bottom to avoid circular deps) ───────────

from routes_admin import register as register_admin  # noqa: E402
from routes_api import register as register_api  # noqa: E402
from routes_auth import register as register_auth  # noqa: E402
from routes_club import register as register_club  # noqa: E402
from routes_web import register as register_web  # noqa: E402

register_web(app, HACKATIME_CLIENT_ID)
register_admin(app)
register_api(app, MAX_IMAGE_BYTES)
register_club(app, HACKATIME_CLIENT_ID)
register_auth(app, HACKCLUB_CLIENT_ID, HACKCLUB_CLIENT_SECRET, BASE_URL,
              HACKATIME_CLIENT_ID, HACKATIME_CLIENT_SECRET)


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', '').lower() == 'true')
