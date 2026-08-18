import secrets
import time
from typing import Any, cast

import flask
from flask import flash, redirect, request, session, url_for

from .helpers import (
    _item_id,
    _storage,
    clean_text,
    default_dashboard_state,
    get_dashboard_state,
    is_admin,
    is_banned_email,
    json_error,
    leader_required,
    login_required,
    save_dashboard_state,
    sections_for_request,
    viewer_club_lite,
)
from .storage import SessionStorage, StorageError

EXPLORE_CATEGORIES = ('Web', 'Game', 'Hardware', 'Mobile', 'Art & Design', 'Music', 'Other')
EXPLORE_PAGE_SIZE = 12

# How often (seconds) the shared-backend session-staleness check re-hits the
# Users table. Below this, we trust the last check — the chat UI polls
# /api/dashboard* every 4s, and hitting Airtable that often is unnecessary
# cost/latency for a value that rarely changes.
SESSION_VERSION_CHECK_INTERVAL = 60


def register(app, HACKATIME_CLIENT_ID):
    # ── Public pages ────────────────────────────────────────────────────────

    @app.route('/sitemap.xml')
    def sitemap():
        base = request.host_url.rstrip('/')
        pages = [
            {'loc': base + '/', 'changefreq': 'weekly', 'priority': '1.0'},
            {'loc': base + '/events', 'changefreq': 'weekly', 'priority': '0.8'},
            {'loc': base + '/sign-in', 'changefreq': 'monthly', 'priority': '0.5'},
        ]
        xml = flask.render_template_string(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            '{% for p in pages %}'
            '  <url>\n'
            '    <loc>{{ p.loc }}</loc>\n'
            '    <changefreq>{{ p.changefreq }}</changefreq>\n'
            '    <priority>{{ p.priority }}</priority>\n'
            '  </url>\n'
            '{% endfor %}'
            '</urlset>',
            pages=pages,
        )
        return flask.Response(xml, mimetype='application/xml')

    @app.route('/robots.txt')
    def robots():
        base = request.host_url.rstrip('/')
        content = (
            'User-agent: *\n'
            'Allow: /\n'
            'Disallow: /dashboard\n'
            'Disallow: /api/\n'
            'Disallow: /auth/\n'
            f'\nSitemap: {base}/sitemap.xml\n'
        )
        return flask.Response(content, mimetype='text/plain')

    @app.route('/')
    def index():
        return flask.render_template('index.html')

    @app.route('/events')
    def events():
        return flask.render_template('events.html')

    def _public_projects(club_key: str = '') -> list[dict[str, Any]] | None:
        """The cookie-backed demo has no safe cross-club data source."""
        backend = _storage()
        if isinstance(backend, SessionStorage):
            return None
        return backend.list_public_projects(club_key)

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
        if not (
            path.startswith('/dashboard')
            or path.startswith('/api/dashboard')
            or path.startswith('/api/admin')
        ):
            return None
        user = session.get('user')
        if not user:
            return None

        # Staleness check runs for EVERY matched path, including admin and
        # welcome — a stale/revoked session must not keep access to the
        # admin panel just because it's exempt from the membership check
        # below. Throttled to once per SESSION_VERSION_CHECK_INTERVAL so the
        # 4s-polling chat UI doesn't hit the shared backend on every request.
        backend = _storage()
        if not isinstance(backend, SessionStorage):
            last_checked = session.get('_sv_checked_at')
            now = time.time()
            if last_checked is None or now - last_checked >= SESSION_VERSION_CHECK_INTERVAL:
                try:
                    stored_version = backend.get_user_record(
                        user.get('email') or '', strict=True
                    ).get('sessionVersion', 0)
                except StorageError:
                    # Availability failure, not a real version mismatch —
                    # fail open rather than force-signing-out every user on
                    # a transient Airtable blip. Don't stamp _sv_checked_at
                    # so the next request retries rather than trusting a
                    # skipped check for a full interval.
                    stored_version = None
                if stored_version is not None:
                    session['_sv_checked_at'] = now
                    if int(user.get('sessionVersion', 0)) != int(stored_version):
                        session.clear()
                        if path.startswith('/api/'):
                            return json_error(
                                'Your session was signed out from another device. Please sign in again.',
                                401,
                            )
                        return redirect(url_for('sign_in'))

        if path.startswith('/dashboard/welcome'):
            return None
        if path.startswith('/dashboard/admin') or path.startswith('/api/admin'):
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
                lite = cast(dict[str, Any], viewer_club_lite() or {})
                current_name = (lite.get('settings') or {}).get('clubName')

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

        user = session.get('user') or {}
        email = (user.get('email') or '').strip().lower()
        if is_banned_email(email):
            flash('This account is not allowed to join clubs.', 'error')
            return redirect(url_for('dashboard_welcome'))

        code = clean_text(request.form.get('joinCode'), max_len=20)
        backend = _storage()
        target_key = backend.find_club_by_join_code(code) if code else None
        if not target_key:
            flash('That join code was not found. Double-check it with your club leader.', 'error')
            return redirect(url_for('dashboard_welcome', code=code))

        has_club = viewer_club_lite() is not None
        current_key = backend.resolve_club_key(email) if has_club else None

        if has_club and current_key == target_key:
            flash("You're already a member of this club.", 'success')
            return redirect(url_for('dashboard'))

        if has_club and current_key == email:
            flash(
                "You lead your own club, so you can't join another as a member. "
                'Transfer or delete your club first.',
                'error',
            )
            return redirect(url_for('dashboard'))

        switching = has_club and current_key and current_key != target_key
        if switching:
            old_state = backend.load(current_key)
            if old_state:
                old_state['members'] = [
                    m
                    for m in old_state.get('members', [])
                    if (m.get('email') or '').strip().lower() != email
                ]
                backend.save(current_key, old_state)

        target_state = backend.load(target_key) or {}
        members = target_state.setdefault('members', [])
        if not any((m.get('email') or '').strip().lower() == email for m in members):
            members.append(
                {
                    'id': _item_id('member'),
                    'name': user.get('name') or email,
                    'email': email,
                    'role': 'Member',
                    'avatar': user.get('avatar') or '',
                    'status': 'Active',
                }
            )
            backend.save(target_key, target_state)

        flash(
            "You've switched clubs — welcome to your new club!"
            if switching
            else 'Welcome to the club!',
            'success',
        )
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
                settings: dict[str, Any] = cast(dict[str, Any], club.get('settings')) or {}
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

    @app.route('/dashboard/workshops')
    @login_required
    def dashboard_workshops():
        return flask.render_template('dashboard/workshops.html')

    @app.route('/dashboard/projects')
    @login_required
    def dashboard_projects():
        return flask.render_template('dashboard/projects.html')

    @app.route('/dashboard/explore')
    @login_required
    def dashboard_explore():
        only_club = request.args.get('club') == '1'
        club_key = ''
        if only_club:
            email = (session.get('user') or {}).get('email') or ''
            club_key = _storage().resolve_club_key(email)
        projects = _public_projects(club_key)
        if projects is None:
            return flask.render_template('dashboard/explore.html', unavailable=True, projects=[]), 503

        query = clean_text(request.args.get('q'), max_len=100)
        category = clean_text(request.args.get('category'), max_len=40)
        if category not in EXPLORE_CATEGORIES:
            category = ''
        term = query.casefold()
        filtered = [
            project for project in projects
            if (not category or project['category'] == category)
            and (
                not term
                or term in ' '.join(
                    [project['name'], project['description'], project['ownerName'], project['clubName']]
                ).casefold()
            )
        ]
        try:
            page = max(1, int(request.args.get('page', '1')))
        except (TypeError, ValueError):
            page = 1
        total_pages = max(1, (len(filtered) + EXPLORE_PAGE_SIZE - 1) // EXPLORE_PAGE_SIZE)
        page = min(page, total_pages)
        start = (page - 1) * EXPLORE_PAGE_SIZE
        return flask.render_template(
            'dashboard/explore.html', unavailable=False,
            projects=filtered[start : start + EXPLORE_PAGE_SIZE],
            categories=EXPLORE_CATEGORIES, query=query, selected_category=category,
            page=page, total_pages=total_pages, total=len(filtered), only_club=only_club,
        )

    @app.route('/dashboard/explore/projects/<public_id>')
    @login_required
    def dashboard_explore_project(public_id: str):
        projects = _public_projects()
        if projects is None:
            return flask.render_template('dashboard/explore_project.html', unavailable=True, project=None), 503
        project = next((item for item in projects if item['publicId'] == public_id), None)
        if project is None:
            flask.abort(404)
        return flask.render_template('dashboard/explore_project.html', unavailable=False, project=project)

    @app.route('/dashboard/levels')
    @login_required
    def dashboard_levels():
        return flask.render_template('dashboard/levels.html')

    @app.route('/dashboard/tools')
    @leader_required
    def dashboard_tools():
        return flask.render_template('dashboard/tools.html', dashboard_state=get_dashboard_state(sections_for_request()))

    @app.route('/dashboard/shop')
    @leader_required
    def dashboard_shop():
        return flask.render_template('dashboard/shop.html')

    @app.route('/dashboard/chat')
    @login_required
    def dashboard_chat():
        return flask.render_template('dashboard/chat.html')

    @app.route('/dashboard/notifications')
    @login_required
    def dashboard_notifications():
        return flask.render_template('dashboard/notifications.html')

    @app.route('/dashboard/newsletters')
    @login_required
    def dashboard_newsletters_redirect():
        return redirect(url_for('dashboard_notifications'), code=301)

    @app.route('/dashboard/map')
    @login_required
    def dashboard_map():
        return flask.render_template('dashboard/map.html')

    @app.route('/dashboard/settings')
    @leader_required
    def dashboard_settings():
        backend = _storage()
        return flask.render_template(
            'dashboard/settings.html',
            dashboard_state=get_dashboard_state(sections_for_request()),
            shared_backend=not isinstance(backend, SessionStorage),
            hackatime_connect_enabled=bool(HACKATIME_CLIENT_ID),
        )

    @app.route('/dashboard/profile')
    @login_required
    def dashboard_profile():
        return flask.render_template(
            'dashboard/profile.html',
            dashboard_state=get_dashboard_state(sections_for_request()),
            hackatime_connect_enabled=bool(HACKATIME_CLIENT_ID),
        )
