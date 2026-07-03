from urllib.parse import urlencode
from datetime import date
import base64
import json
import os
import secrets
import zlib
import requests
import flask
from flask import Flask, redirect, url_for, session, request, flash
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
# Vercel terminates TLS at its proxy — trust X-Forwarded-* so request.url_root
# (the OAuth redirect fallback) is https:// with the real deployment host.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

HACKCLUB_CLIENT_ID     = os.environ.get('HACKCLUB_CLIENT_ID', '')
HACKCLUB_CLIENT_SECRET = os.environ.get('HACKCLUB_CLIENT_SECRET', '')
BASE_URL               = os.environ.get('BASE_URL', '')


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
            {
                'id': 'member-sarah',
                'name': 'Sarah J.',
                'email': 'sarah@example.com',
                'role': 'Member',
                'avatar': '',
                'status': 'Active',
            },
            {
                'id': 'member-alex',
                'name': 'Alex Chen',
                'email': 'alex@example.com',
                'role': 'Member',
                'avatar': '',
                'status': 'Active',
            },
        ],
        'events': [
            {
                'id': 'event-hackathon-prep',
                'title': 'Hackathon Prep Meeting',
                'date': '2026-10-24',
                'time': '15:30',
                'location': 'Room 402',
                'type': 'Workshop',
                'rsvp': True,
                'attendees': 18,
            },
            {
                'id': 'event-web-dev',
                'title': 'Web Dev Workshop: Build a Personal Site',
                'date': '2026-11-02',
                'time': '15:30',
                'location': 'Room 402',
                'type': 'Workshop',
                'rsvp': False,
                'attendees': 24,
            },
            {
                'id': 'event-demo-day',
                'title': 'End of Semester Pizza Party and Demo Day',
                'date': '2026-12-15',
                'time': '16:00',
                'location': 'Library',
                'type': 'Demo Day',
                'rsvp': False,
                'attendees': 31,
            },
        ],
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
        'ships': [
            {
                'id': 'ship-portfolio',
                'title': 'Personal Portfolio Site',
                'member': 'Sarah J.',
                'url': 'https://sarah.hackclub.dev',
                'date': '2026-06-14',
            },
            {
                'id': 'ship-sprig-game',
                'title': 'Sprig Maze Game',
                'member': 'Alex Chen',
                'url': 'https://sprig.hackclub.com/share/maze',
                'date': '2026-06-21',
            },
        ],
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
                'read': True,
            },
        ],
        'settings': {
            'joinCode': secrets.token_hex(3),
            'clubName': 'Hack Club at State High',
            'location': 'State College, PA',
            'website': 'https://statehigh.hackclub.com',
            'avatar': '',
            'publicDirectory': True,
            'emailNotifications': True,
            'darkModeDefault': False,
            'newsletterSubscribed': True,
        },
    }


def get_dashboard_state():
    state = session.get('dashboard_state')
    if state is None:
        state = default_dashboard_state()
        session['dashboard_state'] = state
        return state

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

    if changed:
        session.modified = True
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
    if _state_cookie_size(state) > MAX_STATE_COOKIE_BYTES:
        raise StateTooLarge()
    session['dashboard_state'] = state
    session.modified = True


@app.errorhandler(StateTooLarge)
def handle_state_too_large(_error):
    return flask.jsonify({
        'error': 'Your club data is full — this demo stores everything in a browser cookie. '
                 'Remove an old dispatch, event, or member before adding more.'
    }), 413


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


# ── Dashboard pages ───────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    return flask.render_template('dashboard.html', dashboard_state=get_dashboard_state())

@app.route('/dashboard/team')
@login_required
def dashboard_team():
    return flask.render_template('dashboard/team.html', dashboard_state=get_dashboard_state())

@app.route('/dashboard/events')
@login_required
def dashboard_events():
    return flask.render_template('dashboard/events.html', dashboard_state=get_dashboard_state())

@app.route('/dashboard/ships')
@login_required
def dashboard_ships():
    return flask.render_template('dashboard/ships.html', dashboard_state=get_dashboard_state())

@app.route('/dashboard/levels')
@login_required
def dashboard_levels():
    return flask.render_template('dashboard/levels.html', dashboard_state=get_dashboard_state())

@app.route('/dashboard/tools')
@login_required
def dashboard_tools():
    return flask.render_template('dashboard/tools.html', dashboard_state=get_dashboard_state())

@app.route('/dashboard/shop')
@login_required
def dashboard_shop():
    return flask.render_template('dashboard/shop.html', dashboard_state=get_dashboard_state())

@app.route('/dashboard/newsletters')
@login_required
def dashboard_newsletters():
    return flask.render_template('dashboard/newsletters.html', dashboard_state=get_dashboard_state())

@app.route('/dashboard/settings')
@login_required
def dashboard_settings():
    return flask.render_template('dashboard/settings.html', dashboard_state=get_dashboard_state())


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

    state = get_dashboard_state()
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
    }
    state['ships'].insert(0, ship)
    save_dashboard_state(state)
    return flask.jsonify({'ship': ship, 'state': state})


@app.delete('/api/dashboard/ships/<ship_id>')
@login_required
def api_ships_delete(ship_id):
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error

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

    state = get_dashboard_state()
    event = find_by_id(state['events'], event_id)
    if not event:
        return json_error('Event not found.', 404)

    event_data, error = event_from_payload(json_payload(), event)
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


@app.post('/api/dashboard/newsletters')
@login_required
def api_newsletters_add():
    csrf_error = require_dashboard_csrf()
    if csrf_error:
        return csrf_error

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
    return dict(
        current_user=session.get('user'),
        csrf_token=get_csrf_token() if session.get('user') else '',
    )


if __name__ == '__main__':
    app.run(debug=True)

