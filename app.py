from urllib.parse import urlencode
import os
import secrets
import requests
import flask
from flask import Flask, redirect, url_for, session, request, flash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

HACKCLUB_CLIENT_ID     = os.environ.get('HACKCLUB_CLIENT_ID', '')
HACKCLUB_CLIENT_SECRET = os.environ.get('HACKCLUB_CLIENT_SECRET', '')
BASE_URL               = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')


# ── Helpers ───────────────────────────────────────────────────────────────────

def login_required(f):
    """Decorator: redirect unauthenticated users to sign-in."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user'):
            return redirect(url_for('sign_in'))
        return f(*args, **kwargs)
    return decorated


# ── Public pages ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return flask.render_template('index.html')

@app.route('/events')
def events():
    return flask.render_template('events.html')

@app.route('/sign-in')
def sign_in():
    if session.get('user'):
        return redirect(url_for('index'))
    return flask.render_template('sign-in.html')

@app.route('/sign-out')
def sign_out():
    session.clear()
    flash('You have been signed out.', 'success')
    return redirect(url_for('index'))


# ── Dashboard pages ───────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    return flask.render_template('dashboard.html')

@app.route('/dashboard/events')
@login_required
def dashboard_events():
    return flask.render_template('dashboard/events.html')

@app.route('/dashboard/shop')
@login_required
def dashboard_shop():
    return flask.render_template('dashboard/shop.html')

@app.route('/dashboard/newsletters')
@login_required
def dashboard_newsletters():
    return flask.render_template('dashboard/newsletters.html')

@app.route('/dashboard/settings')
@login_required
def dashboard_settings():
    return flask.render_template('dashboard/settings.html')


# ── Hack Club OAuth ───────────────────────────────────────────────────────────

@app.route('/auth/hackclub')
def hackclub_login():
    """Redirect the user to Hack Club's OAuth authorization page."""
    if not HACKCLUB_CLIENT_ID:
        flash('Hack Club Auth is not configured. Please set HACKCLUB_CLIENT_ID.', 'error')
        return redirect(url_for('sign_in'))

    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state

    params = {
        'client_id':     HACKCLUB_CLIENT_ID,
        'redirect_uri':  f'{BASE_URL}/auth/hackclub/callback',
        'response_type': 'code',
        'scope':         'openid profile email',
        'state':         state,
    }
    return redirect(f'https://identity.hackclub.com/oauth/authorize?{urlencode(params)}')


@app.route('/auth/hackclub/callback')
def hackclub_callback():
    """Handle Hack Club's redirect after the user authorizes or denies."""
    error = request.args.get('error')
    if error:
        flash(f'Hack Club sign-in was cancelled ({error}).', 'error')
        return redirect(url_for('sign_in'))

    returned_state = request.args.get('state', '')
    expected_state = session.pop('oauth_state', None)
    if not expected_state or returned_state != expected_state:
        flash('Invalid state parameter. Please try signing in again.', 'error')
        return redirect(url_for('sign_in'))

    code = request.args.get('code')
    if not code:
        flash('No authorization code returned from Hack Club.', 'error')
        return redirect(url_for('sign_in'))

    token_response = requests.post(
        'https://identity.hackclub.com/oauth/token',
        data={
            'client_id':     HACKCLUB_CLIENT_ID,
            'client_secret': HACKCLUB_CLIENT_SECRET,
            'code':          code,
            'redirect_uri':  f'{BASE_URL}/auth/hackclub/callback',
            'grant_type':    'authorization_code',
        },
        timeout=10,
    )
    token_data = token_response.json()

    if 'access_token' not in token_data:
        flash(f'Hack Club token exchange failed: {token_data.get("error", "unknown error")}', 'error')
        return redirect(url_for('sign_in'))

    user_response = requests.get(
        'https://identity.hackclub.com/oauth/userinfo',
        headers={'Authorization': f'Bearer {token_data["access_token"]}'},
        timeout=10,
    )
    user_data = user_response.json()

    if 'sub' not in user_data:
        flash('Could not retrieve your Hack Club profile. Please try again.', 'error')
        return redirect(url_for('sign_in'))

    session['user'] = {
        'id':       user_data.get('sub'),
        'name':     user_data.get('name'),
        'email':    user_data.get('email'),
        'avatar':   user_data.get('picture'),
        'provider': 'hackclub',
    }

    flash(f'Welcome, {user_data.get("name", "leader")}!', 'success')
    return redirect(url_for('dashboard'))


# ── Context processor ─────────────────────────────────────────────────────────

@app.context_processor
def inject_user():
    return dict(current_user=session.get('user'))


if __name__ == '__main__':
    app.run(debug=True)