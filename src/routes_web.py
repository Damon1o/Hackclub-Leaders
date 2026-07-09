import secrets

import flask
from flask import flash, redirect, request, session, url_for

from .helpers import (
    _item_id,
    _storage,
    clean_text,
    default_dashboard_state,
    get_dashboard_state,
    is_admin,
    json_error,
    leader_required,
    login_required,
    save_dashboard_state,
    viewer_club_lite,
)
from .storage import SessionStorage


def register(app, HACKATIME_CLIENT_ID):
    # ── Public pages ────────────────────────────────────────────────────────

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
        hint_email = clean_text(request.args.get('email', ''), max_len=120)
        return flask.render_template('sign-in.html', hint_email=hint_email)

    @app.route('/sign-out')
    def sign_out():
        session.clear()
        flash('You have been signed out.', 'success')
        return redirect(url_for('index'))

    @app.get('/api/check-email')
    def api_check_email():
        email = clean_text(request.args.get('email', ''), max_len=120).lower()
        if '@' not in email:
            return flask.jsonify({'found': False})
        backend = _storage()
        club_key = backend.find_club_by_member_email(email)
        return flask.jsonify({'found': club_key is not None})

    # ── Club membership gate ───────────────────────────────────────────────

    @app.before_request
    def require_club_membership():
        path = request.path
        if not (path.startswith('/dashboard') or path.startswith('/api/dashboard')):
            return None
        if path.startswith('/dashboard/welcome'):
            return None
        if path.startswith('/dashboard/admin') or path.startswith('/api/admin'):
            return None
        if not session.get('user'):
            return None
        if is_admin() or viewer_club_lite() is not None:
            return None
        if path.startswith('/api/'):
            return json_error('Join or create a club first.', 403)
        return redirect(url_for('dashboard_welcome'))

    def _welcome_csrf_ok():
        token = request.form.get('csrf_token', '')
        expected = session.get('csrf_token', '')
        return bool(token and expected and secrets.compare_digest(token, expected))

    @app.route('/dashboard/welcome')
    @login_required
    def dashboard_welcome():
        code = clean_text(request.args.get('code'), max_len=20)
        backend = _storage()
        has_club = viewer_club_lite() is not None

        target_key = backend.find_club_by_join_code(code) if code else None
        target_name = None
        if target_key:
            target_lite = backend.load_lite(target_key) or {}
            target_name = (target_lite.get('settings') or {}).get('clubName')

        if has_club and not target_key:
            return redirect(url_for('dashboard'))

        is_switch = False
        current_name = None
        if has_club and target_key:
            email = (session.get('user') or {}).get('email') or ''
            if backend.resolve_club_key(email) != target_key:
                is_switch = True
                current_name = ((viewer_club_lite() or {}).get('settings') or {}).get('clubName')

        return flask.render_template(
            'welcome.html',
            prefill_code=code,
            target_name=target_name,
            current_name=current_name,
            is_switch=is_switch,
            shared_backend=not isinstance(backend, SessionStorage),
        )

    @app.post('/dashboard/welcome/join')
    @login_required
    def dashboard_welcome_join():
        if not _welcome_csrf_ok():
            flash('Your session expired. Please try again.', 'error')
            return redirect(url_for('dashboard_welcome'))

        code = clean_text(request.form.get('joinCode'), max_len=20)
        backend = _storage()
        target_key = backend.find_club_by_join_code(code) if code else None
        if not target_key:
            flash('That join code was not found. Double-check it with your club leader.', 'error')
            return redirect(url_for('dashboard_welcome', code=code))

        user = session.get('user') or {}
        email = (user.get('email') or '').strip().lower()
        has_club = viewer_club_lite() is not None
        current_key = backend.resolve_club_key(email) if has_club else None

        if has_club and current_key == target_key:
            flash("You're already a member of this club.", 'success')
            return redirect(url_for('dashboard'))

        if has_club and current_key == email:
            flash("You lead your own club, so you can't join another as a member. "
                  "Transfer or delete your club first.", 'error')
            return redirect(url_for('dashboard'))

        switching = has_club and current_key and current_key != target_key
        if switching:
            old_state = backend.load(current_key)
            if old_state:
                old_state['members'] = [
                    m for m in old_state.get('members', [])
                    if (m.get('email') or '').strip().lower() != email
                ]
                backend.save(current_key, old_state)

        target_state = backend.load(target_key) or {}
        members = target_state.setdefault('members', [])
        if not any((m.get('email') or '').strip().lower() == email for m in members):
            members.append({
                'id': _item_id('member'),
                'name': user.get('name') or email,
                'email': email,
                'role': 'Member',
                'avatar': user.get('avatar') or '',
                'status': 'Active',
            })
            backend.save(target_key, target_state)

        flash("You've switched clubs — welcome to your new club!" if switching
              else 'Welcome to the club!', 'success')
        return redirect(url_for('dashboard'))

    @app.post('/dashboard/welcome/create')
    @login_required
    def dashboard_welcome_create():
        if viewer_club_lite() is not None:
            return redirect(url_for('dashboard'))
        if not _welcome_csrf_ok():
            flash('Your session expired. Please try again.', 'error')
            return redirect(url_for('dashboard_welcome'))

        save_dashboard_state(default_dashboard_state())
        flash('Your club is ready — welcome, leader!', 'success')
        return redirect(url_for('dashboard'))

    @app.route('/join/<code>')
    def join_club(code):
        own_link = False
        club_name = None
        if session.get('user'):
            club = viewer_club_lite()
            if club:
                settings = club.get('settings') or {}
                if settings.get('joinCode') == code:
                    own_link = True
                    club_name = settings.get('clubName')
        return flask.render_template(
            'join.html',
            code=code,
            own_link=own_link,
            club_name=club_name,
            signed_in=bool(session.get('user')),
            shared_backend=not isinstance(_storage(), SessionStorage),
        )

    # ── Dashboard pages ─────────────────────────────────────────────────────

    @app.route('/dashboard')
    @login_required
    def dashboard():
        return flask.render_template('dashboard.html')

    @app.route('/dashboard/team')
    @login_required
    def dashboard_team():
        return flask.render_template('dashboard/team.html')

    @app.route('/dashboard/events')
    @login_required
    def dashboard_events():
        return flask.render_template('dashboard/events.html')

    @app.route('/dashboard/ships')
    @login_required
    def dashboard_ships():
        return flask.render_template('dashboard/ships.html')

    @app.route('/dashboard/projects')
    @login_required
    def dashboard_projects():
        return flask.render_template('dashboard/projects.html')

    @app.route('/dashboard/levels')
    @login_required
    def dashboard_levels():
        return flask.render_template('dashboard/levels.html')

    @app.route('/dashboard/tools')
    @leader_required
    def dashboard_tools():
        return flask.render_template('dashboard/tools.html', dashboard_state=get_dashboard_state())

    @app.route('/dashboard/shop')
    @leader_required
    def dashboard_shop():
        return flask.render_template('dashboard/shop.html')

    @app.route('/dashboard/newsletters')
    @login_required
    def dashboard_newsletters():
        return flask.render_template('dashboard/newsletters.html')

    @app.route('/dashboard/map')
    @login_required
    def dashboard_map():
        return flask.render_template('dashboard/map.html')

    @app.route('/dashboard/settings')
    @leader_required
    def dashboard_settings():
        return flask.render_template('dashboard/settings.html', dashboard_state=get_dashboard_state())

    @app.route('/dashboard/profile')
    @login_required
    def dashboard_profile():
        return flask.render_template('dashboard/profile.html',
                                     dashboard_state=get_dashboard_state(),
                                     hackatime_connect_enabled=bool(HACKATIME_CLIENT_ID))
