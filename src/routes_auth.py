import os
import secrets
from urllib.parse import urlencode

import requests
from flask import flash, redirect, request, session, url_for

from .helpers import clean_text, login_required, playtest_state


def register(
    app,
    HACKCLUB_CLIENT_ID,
    HACKCLUB_CLIENT_SECRET,
    BASE_URL,
    HACKATIME_CLIENT_ID,
    HACKATIME_CLIENT_SECRET,
):
    # ── Hack Club OAuth ─────────────────────────────────────────────────────

    def _oauth_redirect_uri():
        base = BASE_URL or request.url_root.rstrip('/')
        return f'{base}/auth/hackclub/callback'

    @app.route('/auth/hackclub')
    def hackclub_login():
        if not HACKCLUB_CLIENT_ID:
            flash('Hack Club Auth is not configured. Please set HACKCLUB_CLIENT_ID.', 'error')
            return redirect(url_for('sign_in'))

        state = secrets.token_urlsafe(16)
        session['oauth_state'] = state

        join_code = clean_text(request.args.get('join'), max_len=20)
        if join_code:
            session['pending_join_code'] = join_code
        else:
            session.pop('pending_join_code', None)
        if request.args.get('intent') in {'leader', 'member'}:
            session['pending_intent'] = request.args.get('intent')
        else:
            session.pop('pending_intent', None)

        login_hint = clean_text(request.args.get('login_hint'), max_len=120)

        params = {
            'client_id': HACKCLUB_CLIENT_ID,
            'redirect_uri': _oauth_redirect_uri(),
            'response_type': 'code',
            'scope': 'openid profile email',
            'state': state,
        }
        if login_hint and '@' in login_hint:
            params['login_hint'] = login_hint
        return redirect(f'https://identity.hackclub.com/oauth/authorize?{urlencode(params)}')

    @app.route('/auth/hackclub/callback')
    def hackclub_callback():
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

        try:
            token_response = requests.post(
                'https://identity.hackclub.com/oauth/token',
                data={
                    'client_id': HACKCLUB_CLIENT_ID,
                    'client_secret': HACKCLUB_CLIENT_SECRET,
                    'code': code,
                    'redirect_uri': _oauth_redirect_uri(),
                    'grant_type': 'authorization_code',
                },
                timeout=10,
            )
            token_data = token_response.json()
        except (requests.RequestException, ValueError):
            flash('Could not reach Hack Club to finish signing in. Please try again.', 'error')
            return redirect(url_for('sign_in'))

        if 'access_token' not in token_data:
            flash(
                f'Hack Club token exchange failed: {token_data.get("error", "unknown error")}',
                'error',
            )
            return redirect(url_for('sign_in'))

        try:
            user_response = requests.get(
                'https://identity.hackclub.com/oauth/userinfo',
                headers={'Authorization': f'Bearer {token_data["access_token"]}'},
                timeout=10,
            )
            user_data = user_response.json()
        except (requests.RequestException, ValueError):
            flash('Could not retrieve your Hack Club profile. Please try again.', 'error')
            return redirect(url_for('sign_in'))

        if 'sub' not in user_data:
            flash('Could not retrieve your Hack Club profile. Please try again.', 'error')
            return redirect(url_for('sign_in'))

        session['user'] = {
            'id': user_data.get('sub'),
            'name': user_data.get('name'),
            'email': user_data.get('email'),
            'avatar': user_data.get('picture'),
            'provider': 'hackclub',
        }

        flash(f'Welcome, {user_data.get("name", "leader")}!', 'success')

        pending_code = session.pop('pending_join_code', None)
        session.pop('pending_intent', None)
        target = (
            url_for('dashboard_welcome', code=pending_code)
            if pending_code
            else url_for('dashboard')
        )

        if not HACKATIME_CLIENT_ID:
            return redirect(target)
        if (session['user'].get('hackatimeId') or '').strip():
            return redirect(target)

        session['hackatime_auto_target'] = target
        return redirect(url_for('hackatime_login', auto='1'))

    # ── Playtest login (dev only) ──────────────────────────────────────────

    @app.route('/auth/playtest', methods=['POST'])
    def playtest_login():
        if os.environ.get('PLAYTEST_ENABLED', '').lower() != 'true':
            flash('Playtest mode is not enabled.', 'error')
            return redirect(url_for('sign_in'))

        role = clean_text(request.form.get('role'), max_len=10)
        if role not in ('leader', 'member'):
            flash('Invalid playtest role.', 'error')
            return redirect(url_for('sign_in'))

        state = playtest_state()
        if role == 'leader':
            session['user'] = {
                'id': 'playtest-leader',
                'name': 'Test Leader',
                'email': 'playtest.leader@hackclub.com',
                'avatar': '',
                'provider': 'playtest',
                'hackatimeId': 'playtest',
            }
            session['dashboard_state'] = state
            flash('Signed in as a playtest leader!', 'success')
            return redirect(url_for('dashboard'))

        session['user'] = {
            'id': 'playtest-member',
            'name': 'Test Member',
            'email': 'playtest.member@hackclub.com',
            'avatar': '',
            'provider': 'playtest',
            'hackatimeId': 'playtest',
        }
        session['dashboard_state'] = state
        session['pending_join_code'] = 'PLAYTEST'
        session['pending_intent'] = 'member'
        flash('Signed in as a playtest member!', 'success')
        return redirect(url_for('dashboard'))

    # ── Hackatime OAuth ─────────────────────────────────────────────────────

    HACKATIME_AUTHORIZE_URL = 'https://hackatime.hackclub.com/oauth/authorize'  # noqa: N806
    HACKATIME_TOKEN_URL = 'https://hackatime.hackclub.com/oauth/token'  # noqa: N806
    HACKATIME_ME_URL = 'https://hackatime.hackclub.com/api/v1/authenticated/me'  # noqa: N806

    def _hackatime_redirect_uri():
        base = BASE_URL or request.url_root.rstrip('/')
        return f'{base}/auth/hackatime/callback'

    @app.route('/auth/hackatime')
    @login_required
    def hackatime_login():
        if not HACKATIME_CLIENT_ID:
            flash(
                'Hackatime connect is not configured yet. Enter your Hackatime '
                'user ID manually for now.',
                'error',
            )
            return redirect(url_for('dashboard_profile'))

        state = secrets.token_urlsafe(16)
        session['hackatime_oauth_state'] = state
        params = {
            'client_id': HACKATIME_CLIENT_ID,
            'redirect_uri': _hackatime_redirect_uri(),
            'response_type': 'code',
            'scope': 'profile',
            'state': state,
        }
        return redirect(f'{HACKATIME_AUTHORIZE_URL}?{urlencode(params)}')

    @app.route('/auth/hackatime/callback')
    @login_required
    def hackatime_callback():
        auto_target = session.pop('hackatime_auto_target', None)
        fallback = auto_target or url_for('dashboard_profile')

        error = request.args.get('error')
        if error:
            flash(f'Hackatime connection was cancelled ({error}).', 'error')
            return redirect(fallback)

        returned_state = request.args.get('state', '')
        expected_state = session.pop('hackatime_oauth_state', None)
        if not expected_state or returned_state != expected_state:
            flash('Hackatime connection expired. Please try again.', 'error')
            return redirect(fallback)

        code = request.args.get('code')
        if not code:
            flash('No authorization code returned from Hackatime.', 'error')
            return redirect(fallback)

        try:
            token_response = requests.post(
                HACKATIME_TOKEN_URL,
                data={
                    'client_id': HACKATIME_CLIENT_ID,
                    'client_secret': HACKATIME_CLIENT_SECRET,
                    'code': code,
                    'redirect_uri': _hackatime_redirect_uri(),
                    'grant_type': 'authorization_code',
                },
                timeout=10,
            )
            token_data = token_response.json()
        except (requests.RequestException, ValueError):
            flash('Could not reach Hackatime to finish connecting. Please try again.', 'error')
            return redirect(fallback)

        access_token = token_data.get('access_token')
        if not access_token:
            flash(
                f'Hackatime connection failed: {token_data.get("error", "unknown error")}', 'error'
            )
            return redirect(fallback)

        try:
            me_response = requests.get(
                HACKATIME_ME_URL,
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10,
            )
            me_data = me_response.json()
        except (requests.RequestException, ValueError):
            flash('Could not read your Hackatime profile. Please try again.', 'error')
            return redirect(fallback)

        hackatime_id = me_data.get('id')
        if not hackatime_id:
            flash('Hackatime did not return your account id. Please try again.', 'error')
            return redirect(fallback)

        user = dict(session.get('user') or {})
        user['hackatimeId'] = str(hackatime_id)
        session['user'] = user

        flash('Hackatime connected — your coding time will show up on Projects.', 'success')
        return redirect(fallback)
