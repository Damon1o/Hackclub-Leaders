# Hack Club Leaders Portal

A web portal for Hack Club leaders built with Flask. Sign in with your Hack Club identity to access your dashboard, upcoming events, the shop, newsletters, and settings.

---

## Features

- **Hack Club OAuth 2.0** — sign in via [identity.hackclub.com](https://identity.hackclub.com), no passwords required
- **Protected dashboard** — all `/dashboard/*` routes require authentication
- **Club management** — team roster, event schedule with RSVPs, shop request cart, newsletter dispatches, and club settings, all backed by a JSON API with CSRF protection
- **Dark mode** — toggleable, persisted via JS, with a per-club default in settings
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
│   ├── css/            # base, navigation, hero, events, dashboard, dark-mode, ...
│   ├── js/             # dashboard.js, events.js, hero.js, navigation.js, dark-mode.js, sign-in.js
│   ├── fonts/
│   └── images/
│       ├── events/
│       └── hackclub-site/
└── templates/
    ├── index.html
    ├── events.html
    ├── sign-in.html
    ├── dashboard.html
    ├── dashboard_layout.html
    └── dashboard/
        ├── team.html
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
| `/dashboard/team` | Yes | Team roster management |
| `/dashboard/events` | Yes | Events management |
| `/dashboard/ships` | Yes | Shipped-project tracker |
| `/dashboard/levels` | Yes | Club level progression |
| `/dashboard/tools` | Yes | Leader tools & resources |
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

## Deployment (Vercel)

The repo is set up for Vercel: `vercel.json` builds `app.py` with `@vercel/python` and serves `static/` from the CDN.

1. Import the repo at [vercel.com/new](https://vercel.com/new) (or run `npx vercel`).
2. In **Project Settings → Environment Variables**, set:

| Variable | Value |
|---|---|
| `SECRET_KEY` | A long random string — **required**: without it each serverless instance generates its own key and sessions/CSRF break randomly |
| `HACKCLUB_CLIENT_ID` | OAuth client ID from Hack Club Identity |
| `HACKCLUB_CLIENT_SECRET` | OAuth client secret |
| `BASE_URL` | Your production URL, e.g. `https://your-app.vercel.app` (no trailing slash) |

3. Register `{BASE_URL}/auth/hackclub/callback` as the redirect URI at [identity.hackclub.com](https://identity.hackclub.com).

Preview deployments work without `BASE_URL` (the app falls back to the request host via `ProxyFix`), but sign-in only succeeds on hosts whose callback URL is registered with Hack Club Identity.

Deploying elsewhere (Railway, Render, a VPS) needs no config changes — just the same environment variables.

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
