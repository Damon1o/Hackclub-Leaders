# Hack Club Leaders Portal

A web portal for Hack Club leaders built with Flask. Sign in with your Hack Club identity to access your dashboard, upcoming events, the shop, newsletters, and settings.

---

## Features

- **Hack Club OAuth 2.0** — sign in via [identity.hackclub.com](https://identity.hackclub.com), no passwords required
- **Protected dashboard** — all `/dashboard/*` routes require authentication
- **Collapsible sidebar** — icon-only rail by default, expands on hover
- **Dark mode** — toggleable, persisted via JS
- **Flash messages** — success/error feedback on auth events
- **Jinja2 templating** — `current_user` injected into every template via context processor

---

## Project Structure

```
.
├── app.py                  # Flask app, routes, OAuth logic
├── .env                    # Environment variables (never commit this)
├── requirements.txt
├── static/
│   ├── css/
│   │   ├── base.css
│   │   ├── borders.css
│   │   ├── dashboard.css
│   │   ├── dark-mode.css
│   │   ├── footer.css
│   │   └── sidenav.css
│   ├── js/
│   │   ├── dark-mode.js
│   │   ├── navigation.js
│   │   └── sign-in.js
│   └── images/
│       └── hackclub-site/
└── templates/
    ├── index.html
    ├── events.html
    ├── sign-in.html
    ├── dashboard.html
    └── dashboard/
        ├── events.html
        ├── shop.html
        ├── newsletters.html
        └── settings.html
```

---

## Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/your-username/hackclub-leaders-portal.git
cd hackclub-leaders-portal
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-random-secret-key
HACKCLUB_CLIENT_ID=your-hackclub-client-id
HACKCLUB_CLIENT_SECRET=your-hackclub-client-secret
BASE_URL=http://127.0.0.1:5000
```

| Variable | Description |
|---|---|
| `SECRET_KEY` | Flask session secret — use a long random string |
| `HACKCLUB_CLIENT_ID` | OAuth client ID from Hack Club Identity |
| `HACKCLUB_CLIENT_SECRET` | OAuth client secret from Hack Club Identity |
| `BASE_URL` | Base URL of your app — used to build the OAuth redirect URI |

To get OAuth credentials, register your app at [identity.hackclub.com](https://identity.hackclub.com). Set the redirect URI to `{BASE_URL}/auth/hackclub/callback`.

### 4. Run the app

```bash
python app.py
```

The app will be available at [http://127.0.0.1:5000](http://127.0.0.1:5000).

---

## Routes

| Route | Auth required | Description |
|---|---|---|
| `/` | No | Home / landing page |
| `/events` | No | Public events page |
| `/sign-in` | No | Sign-in page |
| `/sign-out` | No | Clears session, redirects home |
| `/dashboard` | Yes | Leader dashboard |
| `/dashboard/events` | Yes | Events management |
| `/dashboard/shop` | Yes | Shop |
| `/dashboard/newsletters` | Yes | Newsletters |
| `/dashboard/settings` | Yes | Account settings |
| `/auth/hackclub` | No | Starts OAuth flow |
| `/auth/hackclub/callback` | No | OAuth callback |

---

## OAuth Flow

```
User clicks "Sign in with Hack Club"
    → /auth/hackclub
    → identity.hackclub.com/oauth/authorize  (user approves)
    → /auth/hackclub/callback
    → exchange code for access token
    → fetch user profile from /oauth/userinfo
    → store in session['user']
    → redirect to /dashboard
```

CSRF is prevented using a `state` parameter stored in the session and verified on callback.

---

## Deployment

When deploying (e.g. to Railway, Render, or a VPS), update your `.env`:

```env
BASE_URL=https://your-production-domain.com
```

Make sure `SECRET_KEY` is a strong, stable value in production — rotating it will invalidate all existing sessions.

---

## Requirements

```
flask
python-dotenv
requests
```

Generate a `requirements.txt` with:

```bash
pip freeze > requirements.txt
```

---

## License

MIT
