from urllib.parse import urlencode
from datetime import date
import base64
import json
import os
import secrets
import zlib
import requests
import flask
from flask import Flask, g, redirect, url_for, session, request, flash
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

from storage import make_storage, SessionStorage, StorageError

load_dotenv()

app = Flask(__name__)
# Vercel terminates TLS at its proxy — trust X-Forwarded-* so request.url_root
# (the OAuth redirect fallback) is https:// with the real deployment host.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

HACKCLUB_CLIENT_ID     = os.environ.get('HACKCLUB_CLIENT_ID', '')
HACKCLUB_CLIENT_SECRET = os.environ.get('HACKCLUB_CLIENT_SECRET', '')
BASE_URL               = os.environ.get('BASE_URL', '')

# Comma-separated allowlist of admin emails. Admins see and edit every club and
# review shipped projects. Kept in env (not the database) so there is no
# in-app way to grant oneself admin.
ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.environ.get('ADMIN_EMAILS', '').split(',')
    if email.strip()
}


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


LEADER_ROLES = {'Leader', 'Mentor'}


def viewer_role():
    """The signed-in user's club role, from their roster entry (matched by
    email). Accounts with no roster entry lead the club they created."""
    user = session.get('user') or {}
    email = (user.get('email') or '').strip().lower()
    state = (viewer_club_lite() or {}) if user else {}
    for member in state.get('members', []):
        if (member.get('email') or '').strip().lower() == email:
            return member.get('role') or 'Member'
    return 'Leader'


def viewer_is_leader():
    return viewer_role() in LEADER_ROLES


def leader_required(f):
    """Decorator: pages only leaders and mentors may open."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user'):
            return redirect(url_for('sign_in'))
        if not viewer_is_leader():
            flash('That page is for club leaders and mentors.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


def require_leader_api():
    """JSON guard for API actions members may not perform."""
    if not viewer_is_leader():
        return flask.jsonify({'error': 'Only leaders and mentors can do that.'}), 403
    return None


def is_admin():
    """True when the signed-in email is in the ADMIN_EMAILS allowlist."""
    email = ((session.get('user') or {}).get('email') or '').strip().lower()
    return bool(email) and email in ADMIN_EMAILS


def admin_required(f):
    """Decorator: pages only site admins may open."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user'):
            return redirect(url_for('sign_in'))
        if not is_admin():
            flash('That page is for site administrators.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


def require_admin_api():
    """JSON guard for admin-only API actions."""
    if not is_admin():
        return flask.jsonify({'error': 'Admins only.'}), 403
    return None


def _item_id(prefix):
    return f'{prefix}-{secrets.token_hex(4)}'


def get_csrf_token():
    token = session.get('csrf_token')
    if not token:
        token = secrets.token_urlsafe(24)
        session['csrf_token'] = token
    return token


def default_dashboard_state():
    user = session.get('user') or {}
    leader_name = user.get('name') or 'Club Leader'
    leader_email = user.get('email') or 'leader@hackclub.com'

    return {
        'members': [
            {
                'id': 'member-leader',
                'name': leader_name,
                'email': leader_email,
                'role': 'Leader',
                'avatar': user.get('avatar') or '',
                'status': 'Active',
            },
        ],
        # New clubs start empty — events, ships, and members are added by
        # the club itself, so levels and stats reflect real activity.
        'events': [],
        'shopItems': [
            {
                'id': 'stickers',
                'name': 'Sticker Pack',
                'description': 'A fresh batch of Hack Club laptop stickers for your members.',
                'price': 'Free',
                'action': 'Add to Cart',
                'icon': 'note-sticky',
                'accent': 'red',
            },
            {
                'id': 'posters',
                'name': 'Meeting Posters',
                'description': 'Fill-in-the-blank posters to hang up around your school.',
                'price': 'Free',
                'action': 'Add to Cart',
                'icon': 'scroll',
                'accent': 'blue',
            },
            {
                'id': 'arduino',
                'name': 'Arduino Kit',
                'description': 'Basic electronics kit for running a hardware workshop.',
                'price': '$25.00',
                'action': 'Request Grant',
                'icon': 'microchip',
                'accent': 'purple',
            },
        ],
        'cart': [],
        'orders': [],
        'itemRequests': [],
        'projects': [],
        'ships': [],
        'newsletters': [
            {
                'id': 'dispatch-hardware-grants',
                'title': 'Winter Hardware Grants are Open',
                'excerpt': 'Apply for up to $500 to buy Raspberry Pis and Arduinos for your club. Plus, check out the new Sprig game engine.',
                'body': 'Hardware grant applications are open for clubs planning electronics workshops this winter. Tell us what you want to build, how many members will participate, and what parts your club needs.',
                'date': '2026-10-12',
                'readTime': '3 min read',
                'read': False,
            },
            {
                'id': 'dispatch-hackathon-guide',
                'title': 'How to host your first hackathon',
                'excerpt': 'A step-by-step guide from leaders who just hosted an event with 50+ students at their high school.',
                'body': 'Start with a short theme, pick a realistic schedule, and recruit mentors before opening registration. The best first hackathons keep scope tight and make demo time feel celebratory.',
                'date': '2026-09-28',
                'readTime': '5 min read',
                'read': False,
            },
            {
                'id': 'dispatch-school-year',
                'title': 'Welcome to the new school year',
                'excerpt': 'Updates on Hack Club Bank, new sticker designs, and how to recruit members.',
                'body': 'The new school year kit includes updated posters, refreshed stickers, and a checklist for reaching your first ten members.',
                'date': '2026-08-15',
                'readTime': '2 min read',
                'read': False,
            },
        ],
        'settings': {
            'joinCode': secrets.token_hex(3),
            'clubName': f"{leader_name}'s Hack Club",
            'location': '',
            'website': '',
            'avatar': '',
            'publicDirectory': True,
            'emailNotifications': True,
            'darkModeDefault': False,
            'newsletterSubscribed': True,
        },
    }


# ── Storage layer ─────────────────────────────────────────────────────────────
# All persistence goes through a backend from storage.py, selected by the
# STORAGE_BACKEND env var. "session" (default) keeps the classic cookie
# behavior; "airtable" shares one state per club in an Airtable base.
# Never touch session['dashboard_state'] directly outside this section.

def _storage():
    if 'storage_backend' not in g:
        g.storage_backend = make_storage(session)
    return g.storage_backend


def _club_key():
    """Which club's state this request operates on (the leader's email)."""
    if 'club_key' not in g:
        email = (session.get('user') or {}).get('email') or ''
        g.club_key = _storage().resolve_club_key(email)
    return g.club_key


def viewer_club_state():
    """The viewer's full stored club state, or None if they have no club yet.
    Loads at most once per request."""
    if 'club_state_loaded' not in g:
        g.club_state_loaded = True
        g.club_state = _storage().load(_club_key())
    return g.club_state


def viewer_club_lite():
    """Club settings + members only — enough to gate access and resolve the
    viewer's role, without the full multi-table load. Page shells use this so
    the heavy sections can stream in client-side."""
    if 'club_lite' in g:
        return g.club_lite
    # If the full state is already loaded this request, reuse it.
    if g.get('club_state_loaded') and g.get('club_state') is not None:
        g.club_lite = g.club_state
    else:
        g.club_lite = _storage().load_lite(_club_key())
    return g.club_lite


def get_dashboard_state():
    if 'dashboard_state' in g:
        return g.dashboard_state

    backend = _storage()
    state = viewer_club_state()
    if state is None:
        # No club yet — serve defaults in memory without persisting them.
        # A club record is only created when the user explicitly starts one
        # (or joins one) on the welcome page.
        state = default_dashboard_state()
        g.dashboard_state = state
        return state

    # Hydrate sections/settings added since this state was first saved.
    defaults = default_dashboard_state()
    changed = False
    for key, value in defaults.items():
        if key not in state:
            state[key] = value
            changed = True

    settings = state.setdefault('settings', {})
    for key, value in defaults['settings'].items():
        if key not in settings:
            settings[key] = value
            changed = True

    if isinstance(backend, SessionStorage):
        if changed:
            session.modified = True
    else:
        # Shared backends don't store the static catalog or the per-visitor
        # cart; the defaults merge above restored the catalog, the session
        # keeps the cart.
        state['cart'] = session.get('cart_items') or []

    g.dashboard_state = state
    return state


# The whole dashboard state lives in the (signed) session cookie. Browsers cap
# cookies at ~4093 bytes, and Werkzeug silently drops the Set-Cookie header
# past that — the API would report success while nothing persists. Keep a
# margin for the signature, the user dict, and base64 overhead.
MAX_STATE_COOKIE_BYTES = 2800


class StateTooLarge(Exception):
    pass


def _state_cookie_size(state):
    raw = json.dumps(state, separators=(',', ':')).encode()
    return len(base64.urlsafe_b64encode(zlib.compress(raw)))


def save_dashboard_state(state):
    backend = _storage()
    if isinstance(backend, SessionStorage):
        if _state_cookie_size(state) > MAX_STATE_COOKIE_BYTES:
            raise StateTooLarge()
        backend.save(_club_key(), state)
    else:
        session['cart_items'] = state.get('cart') or []
        session.modified = True
        persisted = {key: value for key, value in state.items()
                     if key not in ('shopItems', 'cart')}
        backend.save(_club_key(), persisted)
    g.dashboard_state = state
    g.club_state = state
    g.club_state_loaded = True


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


def require_dashboard_csrf():
    token = request.headers.get('X-CSRF-Token', '')
    expected = session.get('csrf_token', '')
    if not token or not expected or not secrets.compare_digest(token, expected):
        return flask.jsonify({'error': 'Your session token expired. Refresh and try again.'}), 403
    return None


def json_payload():
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def json_error(message, status=400):
    return flask.jsonify({'error': message}), status


def find_by_id(items, item_id):
    return next((item for item in items if item.get('id') == item_id), None)


def clean_text(value, fallback='', max_len=300):
    if value is None:
        return fallback
    return str(value).strip()[:max_len]


def parse_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() in {'1', 'true', 'yes', 'on'}


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


# ── Club membership gate ─────────────────────────────────────────────────────
# Signed-in users whose identity isn't in the database yet (no club of their
# own, not on any roster) must join with a code or start a club before the
# dashboard opens.

@app.before_request
def require_club_membership():
    path = request.path
    if not (path.startswith('/dashboard') or path.startswith('/api/dashboard')):
        return None
    if path.startswith('/dashboard/welcome'):
        return None
    # Admin area is club-agnostic — admins operate across every club and may
    # have no club of their own.
    if path.startswith('/dashboard/admin') or path.startswith('/api/admin'):
        return None
    if not session.get('user'):
        return None  # login_required on the view handles the redirect
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
    if viewer_club_lite() is not None:
        return redirect(url_for('dashboard'))
    return flask.render_template(
        'welcome.html',
        prefill_code=clean_text(request.args.get('code'), max_len=20),
        shared_backend=not isinstance(_storage(), SessionStorage),
    )


@app.post('/dashboard/welcome/join')
@login_required
def dashboard_welcome_join():
    if viewer_club_lite() is not None:
        return redirect(url_for('dashboard'))
    if not _welcome_csrf_ok():
        flash('Your session expired. Please try again.', 'error')
        return redirect(url_for('dashboard_welcome'))

    code = clean_text(request.form.get('joinCode'), max_len=20)
    backend = _storage()
    club_key = backend.find_club_by_join_code(code) if code else None
    if not club_key:
        flash('That join code was not found. Double-check it with your club leader.', 'error')
        return redirect(url_for('dashboard_welcome'))

    user = session.get('user') or {}
    email = (user.get('email') or '').strip().lower()
    club_state = backend.load(club_key) or {}
    members = club_state.setdefault('members', [])
    if not any((m.get('email') or '').strip().lower() == email for m in members):
        members.append({
            'id': _item_id('member'),
            'name': user.get('name') or email,
            'email': email,
            'role': 'Member',
            'avatar': user.get('avatar') or '',
            'status': 'Active',
        })
        backend.save(club_key, club_state)
    flash('Welcome to the club!', 'success')
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


# ── Dashboard pages ───────────────────────────────────────────────────────────

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

@app.route('/join/<code>')
def join_club(code):
    # Join links never write into the roster — they greet the visitor and
    # point them onward; leaders see their own club when opening their link.
    state = get_dashboard_state() if session.get('user') else {}
    club_settings = state.get('settings') or {}
    own_link = bool(session.get('user')) and club_settings.get('joinCode') == code
    return flask.render_template(
        'join.html',
        own_link=own_link,
        club_name=club_settings.get('clubName') if own_link else None,
    )

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
    return flask.render_template('dashboard/profile.html', dashboard_state=get_dashboard_state())


# ── Admin ─────────────────────────────────────────────────────────────────────
# Site admins (ADMIN_EMAILS) work across every club: view/edit any club and
# approve the shipped projects that count toward club levels.

def _persist_club(club_key, state):
    """Save a full state dict for an arbitrary club through the backend,
    stripping the static catalog / transient cart on shared backends."""
    backend = _storage()
    if isinstance(backend, SessionStorage):
        backend.save(club_key, state)
    else:
        persisted = {key: value for key, value in state.items()
                     if key not in ('shopItems', 'cart')}
        backend.save(club_key, persisted)


def _load_admin_club(club_key):
    """(state, error_response) for an admin acting on a specific club."""
    state = _storage().load(club_key)
    if state is None:
        return None, json_error('Club not found.', 404)
    return state, None


@app.route('/dashboard/admin')
@admin_required
def dashboard_admin():
    backend = _storage()
    return flask.render_template(
        'dashboard/admin.html',
        clubs=backend.list_clubs(),
        pending_ships=backend.list_pending_ships(),
    )


@app.route('/dashboard/admin/club/<club_key>')
@admin_required
def dashboard_admin_club(club_key):
    club_key = (club_key or '').strip().lower()
    state = _storage().load(club_key)
    if state is None:
        flash('That club no longer exists.', 'error')
        return redirect(url_for('dashboard_admin'))
    return flask.render_template(
        'dashboard/admin_club.html',
        club_key=club_key,
        club=state,
    )


@app.patch('/api/admin/clubs/<club_key>')
@login_required
def api_admin_club_update(club_key):
    admin_error = require_admin_api()
    if admin_error:
        return admin_error
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    club_key = (club_key or '').strip().lower()
    state, error = _load_admin_club(club_key)
    if error:
        return error

    payload = json_payload()
    club_name = clean_text(payload.get('clubName'))
    website = clean_text(payload.get('website'))
    avatar = clean_text(payload.get('avatar'))
    if not club_name:
        return json_error('Club name is required.')
    if website and not website.startswith(('http://', 'https://')):
        return json_error('Club website must start with http:// or https://.')
    if avatar and not avatar.startswith(('http://', 'https://')):
        return json_error('Avatar URL must start with http:// or https://.')

    settings = state.setdefault('settings', {})
    settings['clubName'] = club_name
    settings['location'] = clean_text(payload.get('location'))
    settings['website'] = website
    settings['avatar'] = avatar
    if 'publicDirectory' in payload:
        settings['publicDirectory'] = parse_bool(payload.get('publicDirectory'))
    _persist_club(club_key, state)
    return flask.jsonify({'club': state})


@app.patch('/api/admin/ships/<club_key>/<ship_id>')
@login_required
def api_admin_ship_update(club_key, ship_id):
    admin_error = require_admin_api()
    if admin_error:
        return admin_error
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    club_key = (club_key or '').strip().lower()
    state, error = _load_admin_club(club_key)
    if error:
        return error

    ship = find_by_id(state.get('ships') or [], ship_id)
    if not ship:
        return json_error('Ship not found.', 404)

    payload = json_payload()
    # Approve / reject is the common case; admins may also fix fields.
    if 'approved' in payload:
        ship['approved'] = parse_bool(payload.get('approved'))
    if 'title' in payload:
        title = clean_text(payload.get('title'), ship.get('title', ''), max_len=120)
        if not title:
            return json_error('Project title is required.')
        ship['title'] = title
    if 'member' in payload:
        member = clean_text(payload.get('member'), ship.get('member', ''), max_len=80)
        if not member:
            return json_error('Who shipped it? Add a member name.')
        ship['member'] = member
    if 'url' in payload:
        url = clean_text(payload.get('url'), ship.get('url', ''))
        if url and not url.startswith(('http://', 'https://')):
            return json_error('Project URL must start with http:// or https://.')
        ship['url'] = url

    _persist_club(club_key, state)
    return flask.jsonify({'ship': ship})


@app.delete('/api/admin/ships/<club_key>/<ship_id>')
@login_required
def api_admin_ship_delete(club_key, ship_id):
    admin_error = require_admin_api()
    if admin_error:
        return admin_error
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    club_key = (club_key or '').strip().lower()
    state, error = _load_admin_club(club_key)
    if error:
        return error

    ships = state.get('ships') or []
    remaining = [s for s in ships if s.get('id') != ship_id]
    if len(remaining) == len(ships):
        return json_error('Ship not found.', 404)
    state['ships'] = remaining
    _persist_club(club_key, state)
    return flask.jsonify({'ok': True})


# Dashboard JSON API

@app.get('/api/dashboard/state')
@login_required
def api_dashboard_state():
    return flask.jsonify({'state': get_dashboard_state()})


@app.post('/api/dashboard/team')
@login_required
def api_team_add():
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    role_error = require_leader_api()
    if role_error:
        return role_error

    payload = json_payload()
    name = clean_text(payload.get('name'))
    email = clean_text(payload.get('email')).lower()
    role = clean_text(payload.get('role'), 'Member').title()
    avatar = clean_text(payload.get('avatar'))

    if not name:
        return json_error('Member name is required.')
    if '@' not in email:
        return json_error('Enter a valid member email.')
    if role not in {'Leader', 'Member', 'Mentor'}:
        return json_error('Choose Leader, Member, or Mentor.')

    state = get_dashboard_state()
    member = {
        'id': _item_id('member'),
        'name': name,
        'email': email,
        'role': role,
        'avatar': avatar,
        'status': 'Invited',
    }
    state['members'].append(member)
    save_dashboard_state(state)
    return flask.jsonify({'member': member, 'state': state})


@app.patch('/api/dashboard/team/<member_id>')
@login_required
def api_team_update(member_id):
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    role_error = require_leader_api()
    if role_error:
        return role_error

    state = get_dashboard_state()
    member = find_by_id(state['members'], member_id)
    if not member:
        return json_error('Member not found.', 404)

    payload = json_payload()
    name = clean_text(payload.get('name'), member['name'])
    email = clean_text(payload.get('email'), member['email']).lower()
    role = clean_text(payload.get('role'), member['role']).title()
    avatar = clean_text(payload.get('avatar'), member.get('avatar', ''))
    status = clean_text(payload.get('status'), member.get('status', 'Active')).title()

    if not name:
        return json_error('Member name is required.')
    if '@' not in email:
        return json_error('Enter a valid member email.')
    if role not in {'Leader', 'Member', 'Mentor'}:
        return json_error('Choose Leader, Member, or Mentor.')
    if status not in {'Active', 'Invited'}:
        return json_error('Choose Active or Invited status.')

    leaders = [m for m in state['members'] if m.get('role') == 'Leader']
    if member.get('role') == 'Leader' and role != 'Leader' and len(leaders) == 1:
        return json_error('A club needs at least one leader.')

    member.update({
        'name': name,
        'email': email,
        'role': role,
        'avatar': avatar,
        'status': status,
    })
    save_dashboard_state(state)
    return flask.jsonify({'member': member, 'state': state})


@app.delete('/api/dashboard/team/<member_id>')
@login_required
def api_team_delete(member_id):
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    role_error = require_leader_api()
    if role_error:
        return role_error

    state = get_dashboard_state()
    target = find_by_id(state['members'], member_id)
    leaders = [m for m in state['members'] if m.get('role') == 'Leader']
    if target and target.get('role') == 'Leader' and len(leaders) == 1:
        return json_error('A club needs at least one leader.')
    original_count = len(state['members'])
    state['members'] = [member for member in state['members'] if member.get('id') != member_id]
    if len(state['members']) == original_count:
        return json_error('Member not found.', 404)
    save_dashboard_state(state)
    return flask.jsonify({'state': state})


@app.post('/api/dashboard/ships')
@login_required
def api_ships_add():
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error

    payload = json_payload()
    title = clean_text(payload.get('title'), max_len=120)
    member = clean_text(payload.get('member'), max_len=80)
    url = clean_text(payload.get('url'))
    ship_date = clean_text(payload.get('date'), date.today().isoformat(), max_len=10)

    if not title:
        return json_error('Project title is required.')
    if not member:
        return json_error('Who shipped it? Add a member name.')
    if url and not url.startswith(('http://', 'https://')):
        return json_error('Project URL must start with http:// or https://.')
    try:
        date.fromisoformat(ship_date)
    except ValueError:
        return json_error('Choose a valid ship date.')

    state = get_dashboard_state()
    ship = {
        'id': _item_id('ship'),
        'title': title,
        'member': member,
        'url': url,
        'date': ship_date,
        # Ships start unapproved and only count toward the club level once an
        # admin approves them.
        'approved': False,
    }
    state['ships'].insert(0, ship)
    save_dashboard_state(state)
    return flask.jsonify({'ship': ship, 'state': state})


@app.patch('/api/dashboard/ships/<ship_id>')
@login_required
def api_ships_update(ship_id):
    # Members may edit shipped projects — no leader gate here.
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error

    state = get_dashboard_state()
    ship = find_by_id(state['ships'], ship_id)
    if not ship:
        return json_error('Ship not found.', 404)

    payload = json_payload()
    title = clean_text(payload.get('title'), ship.get('title', ''), max_len=120)
    member = clean_text(payload.get('member'), ship.get('member', ''), max_len=80)
    url = clean_text(payload.get('url'), ship.get('url', ''))
    ship_date = clean_text(payload.get('date'), ship.get('date', ''), max_len=10)

    if not title:
        return json_error('Project title is required.')
    if not member:
        return json_error('Who shipped it? Add a member name.')
    if url and not url.startswith(('http://', 'https://')):
        return json_error('Project URL must start with http:// or https://.')
    try:
        date.fromisoformat(ship_date)
    except ValueError:
        return json_error('Choose a valid ship date.')

    # Editing a project sends it back to the review queue.
    ship.update({'title': title, 'member': member, 'url': url,
                 'date': ship_date, 'approved': False})
    save_dashboard_state(state)
    return flask.jsonify({'ship': ship, 'state': state})


@app.delete('/api/dashboard/ships/<ship_id>')
@login_required
def api_ships_delete(ship_id):
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    role_error = require_leader_api()
    if role_error:
        return role_error

    state = get_dashboard_state()
    original_count = len(state['ships'])
    state['ships'] = [ship for ship in state['ships'] if ship.get('id') != ship_id]
    if len(state['ships']) == original_count:
        return json_error('Ship not found.', 404)
    save_dashboard_state(state)
    return flask.jsonify({'state': state})


def event_from_payload(payload, existing=None):
    existing = existing or {}
    title = clean_text(payload.get('title'), existing.get('title', ''))
    event_date = clean_text(payload.get('date'), existing.get('date', ''))
    event_time = clean_text(payload.get('time'), existing.get('time', ''))
    location = clean_text(payload.get('location'), existing.get('location', ''))
    event_type = clean_text(payload.get('type'), existing.get('type', 'Workshop'))
    attendees = payload.get('attendees', existing.get('attendees', 0))

    if not title:
        return None, 'Event title is required.'
    try:
        date.fromisoformat(event_date)
    except ValueError:
        return None, 'Choose a valid event date.'
    if not event_time:
        return None, 'Event time is required.'
    if not location:
        return None, 'Event location is required.'
    try:
        attendees = max(0, int(attendees))
    except (TypeError, ValueError):
        attendees = existing.get('attendees', 0)

    return {
        'title': title,
        'date': event_date,
        'time': event_time,
        'location': location,
        'type': event_type,
        'rsvp': parse_bool(payload.get('rsvp', existing.get('rsvp', False))),
        'attendees': attendees,
    }, None


@app.post('/api/dashboard/events')
@login_required
def api_events_add():
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    role_error = require_leader_api()
    if role_error:
        return role_error

    event_data, error = event_from_payload(json_payload())
    if error:
        return json_error(error)

    state = get_dashboard_state()
    event = {'id': _item_id('event'), **event_data}
    state['events'].append(event)
    state['events'].sort(key=lambda item: (item.get('date', ''), item.get('time', '')))
    save_dashboard_state(state)
    return flask.jsonify({'event': event, 'state': state})


@app.patch('/api/dashboard/events/<event_id>')
@login_required
def api_events_update(event_id):
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error

    payload = json_payload()
    # Members may RSVP, but only leaders and mentors may edit event details.
    if not viewer_is_leader() and set(payload.keys()) - {'rsvp'}:
        return flask.jsonify({'error': 'Only leaders and mentors can edit events.'}), 403

    state = get_dashboard_state()
    event = find_by_id(state['events'], event_id)
    if not event:
        return json_error('Event not found.', 404)

    event_data, error = event_from_payload(payload, event)
    if error:
        return json_error(error)

    event.update(event_data)
    state['events'].sort(key=lambda item: (item.get('date', ''), item.get('time', '')))
    save_dashboard_state(state)
    return flask.jsonify({'event': event, 'state': state})


@app.delete('/api/dashboard/events/<event_id>')
@login_required
def api_events_delete(event_id):
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    role_error = require_leader_api()
    if role_error:
        return role_error

    state = get_dashboard_state()
    original_count = len(state['events'])
    state['events'] = [event for event in state['events'] if event.get('id') != event_id]
    if len(state['events']) == original_count:
        return json_error('Event not found.', 404)
    save_dashboard_state(state)
    return flask.jsonify({'state': state})


@app.post('/api/dashboard/cart')
@login_required
def api_cart_add():
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    role_error = require_leader_api()
    if role_error:
        return role_error

    payload = json_payload()
    item_id = clean_text(payload.get('itemId'))
    state = get_dashboard_state()
    item = find_by_id(state['shopItems'], item_id)
    if not item:
        return json_error('Shop item not found.', 404)

    try:
        quantity = max(1, int(payload.get('quantity', 1) or 1))
    except (TypeError, ValueError):
        return json_error('Cart quantity must be a number.')
    cart_item = find_by_id(state['cart'], item_id)
    if cart_item:
        cart_item['quantity'] += quantity
    else:
        state['cart'].append({'id': item_id, 'quantity': quantity})
    save_dashboard_state(state)
    return flask.jsonify({'state': state})


@app.patch('/api/dashboard/cart/<item_id>')
@login_required
def api_cart_update(item_id):
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    role_error = require_leader_api()
    if role_error:
        return role_error

    payload = json_payload()
    try:
        quantity = max(0, int(payload.get('quantity', 1)))
    except (TypeError, ValueError):
        return json_error('Cart quantity must be a number.')

    state = get_dashboard_state()
    cart_item = find_by_id(state['cart'], item_id)
    if not cart_item:
        return json_error('Cart item not found.', 404)

    if quantity == 0:
        state['cart'] = [item for item in state['cart'] if item.get('id') != item_id]
    else:
        cart_item['quantity'] = quantity
    save_dashboard_state(state)
    return flask.jsonify({'state': state})


@app.delete('/api/dashboard/cart/<item_id>')
@login_required
def api_cart_delete(item_id):
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    role_error = require_leader_api()
    if role_error:
        return role_error

    state = get_dashboard_state()
    state['cart'] = [item for item in state['cart'] if item.get('id') != item_id]
    save_dashboard_state(state)
    return flask.jsonify({'state': state})


@app.post('/api/dashboard/checkout')
@login_required
def api_cart_checkout():
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    role_error = require_leader_api()
    if role_error:
        return role_error

    state = get_dashboard_state()
    if not state['cart']:
        return json_error('Add at least one item before submitting a request.')

    order = {
        'id': _item_id('order'),
        'date': date.today().isoformat(),
        'status': 'Requested',
        'items': [dict(item) for item in state['cart']],
    }
    state['orders'].insert(0, order)
    state['cart'] = []
    save_dashboard_state(state)
    return flask.jsonify({'order': order, 'state': state})


@app.post('/api/dashboard/item-requests')
@login_required
def api_item_request_add():
    """Suggest a product that isn't in the shop yet."""
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    role_error = require_leader_api()
    if role_error:
        return role_error

    payload = json_payload()
    name = clean_text(payload.get('name'), max_len=120)
    note = clean_text(payload.get('note'), max_len=300)
    if not name:
        return json_error('What item would you like added?')

    state = get_dashboard_state()
    item_request = {
        'id': _item_id('itemreq'),
        'name': name,
        'note': note,
        'date': date.today().isoformat(),
        'status': 'Submitted',
    }
    state.setdefault('itemRequests', []).insert(0, item_request)
    save_dashboard_state(state)
    return flask.jsonify({'itemRequest': item_request, 'state': state})


@app.delete('/api/dashboard/item-requests/<request_id>')
@login_required
def api_item_request_delete(request_id):
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    role_error = require_leader_api()
    if role_error:
        return role_error

    state = get_dashboard_state()
    requests_list = state.get('itemRequests') or []
    remaining = [r for r in requests_list if r.get('id') != request_id]
    if len(remaining) == len(requests_list):
        return json_error('Request not found.', 404)
    state['itemRequests'] = remaining
    save_dashboard_state(state)
    return flask.jsonify({'state': state})


# ── Projects (member-owned) ───────────────────────────────────────────────────
# Any member can create and manage their OWN projects and submit them to the
# club. Ownership is keyed to the account email — you can only edit or delete
# projects you created.

def _viewer_email():
    return ((session.get('user') or {}).get('email') or '').strip().lower()


def _owned_project_or_error(state, project_id):
    """(project, None) if the viewer owns it, else (None, error_response)."""
    project = find_by_id(state.get('projects') or [], project_id)
    if not project:
        return None, json_error('Project not found.', 404)
    if (project.get('ownerEmail') or '').strip().lower() != _viewer_email():
        return None, json_error('You can only change your own projects.', 403)
    return project, None


@app.post('/api/dashboard/projects')
@login_required
def api_project_add():
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error

    payload = json_payload()
    name = clean_text(payload.get('name'), max_len=120)
    description = clean_text(payload.get('description'), max_len=500)
    url = clean_text(payload.get('url'))
    if not name:
        return json_error('Project name is required.')
    if url and not url.startswith(('http://', 'https://')):
        return json_error('Project URL must start with http:// or https://.')

    user = session.get('user') or {}
    state = get_dashboard_state()
    project = {
        'id': _item_id('project'),
        'name': name,
        'description': description,
        'url': url,
        'status': 'Draft',
        'ownerEmail': _viewer_email(),
        'ownerName': user.get('name') or _viewer_email(),
        'date': date.today().isoformat(),
    }
    state.setdefault('projects', []).insert(0, project)
    save_dashboard_state(state)
    return flask.jsonify({'project': project, 'state': state})


@app.patch('/api/dashboard/projects/<project_id>')
@login_required
def api_project_update(project_id):
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error

    state = get_dashboard_state()
    project, error = _owned_project_or_error(state, project_id)
    if error:
        return error

    payload = json_payload()
    if 'name' in payload:
        name = clean_text(payload.get('name'), project.get('name', ''), max_len=120)
        if not name:
            return json_error('Project name is required.')
        project['name'] = name
    if 'description' in payload:
        project['description'] = clean_text(payload.get('description'),
                                            project.get('description', ''), max_len=500)
    if 'url' in payload:
        url = clean_text(payload.get('url'), project.get('url', ''))
        if url and not url.startswith(('http://', 'https://')):
            return json_error('Project URL must start with http:// or https://.')
        project['url'] = url
    if 'status' in payload:
        status = clean_text(payload.get('status'), project.get('status', 'Draft')).title()
        if status not in {'Draft', 'Submitted'}:
            return json_error('Status must be Draft or Submitted.')
        project['status'] = status

    save_dashboard_state(state)
    return flask.jsonify({'project': project, 'state': state})


@app.delete('/api/dashboard/projects/<project_id>')
@login_required
def api_project_delete(project_id):
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error

    state = get_dashboard_state()
    _project, error = _owned_project_or_error(state, project_id)
    if error:
        return error
    state['projects'] = [p for p in state.get('projects') or []
                         if p.get('id') != project_id]
    save_dashboard_state(state)
    return flask.jsonify({'state': state})


@app.post('/api/dashboard/newsletters')
@login_required
def api_newsletters_add():
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    role_error = require_leader_api()
    if role_error:
        return role_error

    payload = json_payload()
    title = clean_text(payload.get('title'))
    excerpt = clean_text(payload.get('excerpt'))
    body = clean_text(payload.get('body'), max_len=1000)
    read_time = clean_text(payload.get('readTime'), '2 min read', max_len=20)

    if not title:
        return json_error('Dispatch title is required.')
    if not excerpt:
        return json_error('Dispatch excerpt is required.')
    if not body:
        return json_error('Dispatch body is required.')

    state = get_dashboard_state()
    newsletter = {
        'id': _item_id('dispatch'),
        'title': title,
        'excerpt': excerpt,
        'body': body,
        'date': date.today().isoformat(),
        'readTime': read_time,
        'read': False,
    }
    state['newsletters'].insert(0, newsletter)
    save_dashboard_state(state)
    return flask.jsonify({'newsletter': newsletter, 'state': state})


@app.patch('/api/dashboard/newsletters/<newsletter_id>')
@login_required
def api_newsletters_update(newsletter_id):
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error

    state = get_dashboard_state()
    newsletter = find_by_id(state['newsletters'], newsletter_id)
    if not newsletter:
        return json_error('Dispatch not found.', 404)

    payload = json_payload()
    if 'read' in payload:
        newsletter['read'] = parse_bool(payload.get('read'))
    save_dashboard_state(state)
    return flask.jsonify({'newsletter': newsletter, 'state': state})


@app.patch('/api/dashboard/newsletter-subscription')
@login_required
def api_newsletter_subscription_update():
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    role_error = require_leader_api()
    if role_error:
        return role_error

    state = get_dashboard_state()
    state['settings']['newsletterSubscribed'] = parse_bool(json_payload().get('subscribed'))
    save_dashboard_state(state)
    return flask.jsonify({'state': state})


@app.patch('/api/dashboard/settings')
@login_required
def api_settings_update():
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error
    role_error = require_leader_api()
    if role_error:
        return role_error

    payload = json_payload()
    club_name = clean_text(payload.get('clubName'))
    location = clean_text(payload.get('location'))
    website = clean_text(payload.get('website'))
    avatar = clean_text(payload.get('avatar'))

    if not club_name:
        return json_error('Club name is required.')
    if not location:
        return json_error('School or location is required.')
    if website and not website.startswith(('http://', 'https://')):
        return json_error('Club website must start with http:// or https://.')
    if avatar and not avatar.startswith(('http://', 'https://')):
        return json_error('Avatar URL must start with http:// or https://.')

    state = get_dashboard_state()
    state['settings'].update({
        'clubName': club_name,
        'location': location,
        'website': website,
        'avatar': avatar,
        'publicDirectory': parse_bool(payload.get('publicDirectory')),
        'emailNotifications': parse_bool(payload.get('emailNotifications')),
        'darkModeDefault': parse_bool(payload.get('darkModeDefault')),
        'newsletterSubscribed': parse_bool(payload.get('newsletterSubscribed')),
    })
    save_dashboard_state(state)
    return flask.jsonify({'state': state})


@app.patch('/api/dashboard/profile')
@login_required
def api_profile_update():
    """Personal details for the signed-in user (any role, own account only)."""
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error

    payload = json_payload()
    name = clean_text(payload.get('name'), max_len=80)
    email = clean_text(payload.get('email'), max_len=120)
    avatar = clean_text(payload.get('avatar'), max_len=300)
    bio = clean_text(payload.get('bio'), max_len=500)
    hackatime_id = clean_text(payload.get('hackatimeId'), max_len=40)

    if not name:
        return json_error('Name is required.')
    if not email or '@' not in email:
        return json_error('A valid email is required.')
    if avatar and not avatar.startswith(('http://', 'https://')):
        return json_error('Avatar URL must start with http:// or https://.')
    if hackatime_id and not hackatime_id.isdigit():
        return json_error('Hackatime user ID should be just the number from your profile URL.')

    old_email = ((session.get('user') or {}).get('email') or '').strip().lower()
    user = dict(session.get('user') or {})
    user.update({'name': name, 'email': email, 'avatar': avatar, 'bio': bio,
                 'hackatimeId': hackatime_id})
    session['user'] = user

    # Keep the Team page roster in step: your roster entry is matched by the
    # email you signed in with, so profile edits carry over to it.
    state = get_dashboard_state()
    for member in state.get('members', []):
        if (member.get('email') or '').strip().lower() == old_email:
            member.update({'name': name, 'email': email.lower(), 'avatar': avatar})
            save_dashboard_state(state)
            return flask.jsonify({'user': user, 'state': state})

    return flask.jsonify({'user': user})


# ── HackTime (Hackatime) coding stats ─────────────────────────────────────────
# Proxies each member's PUBLIC Hackatime stats so the browser doesn't hit CORS
# or need the third-party host directly. Public profiles need no API key —
# members supply the numeric user ID from their hackatime.hackclub.com profile.

HACKATIME_API = 'https://hackatime.hackclub.com/api/v1'


@app.get('/api/dashboard/hackatime')
@login_required
def api_hackatime_stats():
    user_id = (request.args.get('userId')
               or (session.get('user') or {}).get('hackatimeId') or '').strip()
    if not user_id:
        return json_error('Add your Hackatime user ID on your profile first.', 400)
    if not user_id.isdigit():
        return json_error('That Hackatime user ID is not valid.', 400)

    try:
        response = requests.get(
            f'{HACKATIME_API}/users/{user_id}/stats',
            params={'features': 'projects,languages'},
            headers={'Accept': 'application/json'},
            timeout=8,
        )
    except requests.RequestException:
        return json_error('Could not reach Hackatime right now.', 502)

    if response.status_code == 404:
        return json_error('No public Hackatime profile for that ID.', 404)
    if response.status_code >= 400:
        return json_error('Hackatime returned an error.', 502)

    data = (response.json() or {}).get('data') or {}
    if not data.get('is_coding_activity_visible', True):
        return json_error('That Hackatime profile is private.', 403)

    languages = [
        {'name': lang.get('name'), 'text': lang.get('text'),
         'totalSeconds': lang.get('total_seconds')}
        for lang in (data.get('languages') or [])[:5]
    ]
    return flask.jsonify({
        'username': data.get('username'),
        'totalSeconds': data.get('total_seconds'),
        'humanReadableTotal': data.get('human_readable_total'),
        'humanReadableDailyAverage': data.get('human_readable_daily_average'),
        'languages': languages,
    })


# ── Hack Club OAuth ───────────────────────────────────────────────────────────

def oauth_redirect_uri():
    """Callback URL registered with Hack Club — falls back to the current host
    when BASE_URL is not configured (e.g. local development)."""
    base = BASE_URL or request.url_root.rstrip('/')
    return f'{base}/auth/hackclub/callback'


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
        'redirect_uri':  oauth_redirect_uri(),
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

    try:
        token_response = requests.post(
            'https://identity.hackclub.com/oauth/token',
            data={
                'client_id':     HACKCLUB_CLIENT_ID,
                'client_secret': HACKCLUB_CLIENT_SECRET,
                'code':          code,
                'redirect_uri':  oauth_redirect_uri(),
                'grant_type':    'authorization_code',
            },
            timeout=10,
        )
        token_data = token_response.json()
    except (requests.RequestException, ValueError):
        flash('Could not reach Hack Club to finish signing in. Please try again.', 'error')
        return redirect(url_for('sign_in'))

    if 'access_token' not in token_data:
        flash(f'Hack Club token exchange failed: {token_data.get("error", "unknown error")}', 'error')
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
    signed_in = bool(session.get('user'))
    return dict(
        current_user=session.get('user'),
        csrf_token=get_csrf_token() if signed_in else '',
        viewer_role=viewer_role() if signed_in else '',
        is_leader=viewer_is_leader() if signed_in else False,
        is_admin=is_admin() if signed_in else False,
    )


if __name__ == '__main__':
    app.run(debug=True)

