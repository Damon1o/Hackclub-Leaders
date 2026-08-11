# Ship Review Coin Award Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When an admin approves a submitted project as "Shipped," award the owner `COINS_PER_APPROVED_SHIP` coins and notify them (email + in-app); when an admin rejects it back to "Draft," notify them without awarding coins. Surface the award in the existing admin toast and the member's own Projects page.

**Architecture:** All the surrounding machinery already exists — `award_coins()` (Spec 1), the admin review queue UI with Approve/Reject buttons, and `PATCH /api/admin/projects/<club_key>/<project_id>` (`src/routes_admin.py`). This plan wires `award_coins()` into that endpoint, adds an owner-facing notification function that operates on the endpoint's already-loaded club `state` (not the ambient `get_dashboard_state()`, which would resolve to the *admin's own* club, not the reviewed club), and threads the awarded amount back to the two frontend surfaces that should mention it.

**Tech Stack:** Flask, pytest, vanilla JS (`static/js/dashboard.js`), existing `flask_mail` email templates.

## Global Constraints

- Coin amount is the existing `COINS_PER_APPROVED_SHIP = 25` constant (`src/helpers.py:30`) — not configurable, not part of this plan's scope.
- Every user-supplied string interpolated into an email template must go through `markupsafe.escape()` (project name, description, owner name, club name) — see `[[email-templates-need-manual-escaping]]` memory; `src/email.py` has no autoescape.
- No coin clawback if a `Shipped` project is later reverted — out of scope.
- Award/notify must be idempotent: re-PATCHing an already-`Shipped` project with `status: Shipped` must not double-award or double-notify.

---

### Task 1: `add_in_app_notification` accepts an explicit `state`

**Files:**
- Modify: `src/notifications.py:17-33`
- Test: `tests/test_notifications.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `add_in_app_notification(user_email, notification_type, title, message, data=None, *, state=None) -> dict`. When `state` is passed, the function mutates and returns from that dict directly and does **not** call `get_dashboard_state()`/`save_dashboard_state()` — the caller owns persistence. When `state` is omitted (all four existing call sites), behavior is unchanged.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_notifications.py`:

```python
def test_add_in_app_notification_with_explicit_state_skips_ambient_lookup():
    from src.notifications import add_in_app_notification

    state = {'notifications': []}
    notification = add_in_app_notification(
        'owner@test.com', 'project_reviewed', 'Title', 'Message', {'k': 'v'}, state=state
    )
    assert state['notifications'] == [notification]
    assert notification['type'] == 'project_reviewed'
    assert notification['read'] is False
    assert notification['data'] == {'k': 'v'}


def test_add_in_app_notification_with_explicit_state_caps_at_100():
    from src.notifications import add_in_app_notification

    state = {'notifications': [{'id': f'old-{i}'} for i in range(100)]}
    add_in_app_notification('owner@test.com', 'type', 'Title', 'Message', state=state)
    assert len(state['notifications']) == 100
    assert state['notifications'][0]['type'] == 'type'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_notifications.py -k explicit_state -v`
Expected: FAIL — `add_in_app_notification() got an unexpected keyword argument 'state'`

- [ ] **Step 3: Implement**

Replace `src/notifications.py:17-33`:

```python
def add_in_app_notification(user_email, notification_type, title, message, data=None, *, state=None):
    """Add a notification to the user's in-app notification center.

    `state` lets a caller already holding a specific club's state (e.g. an
    admin reviewing a *different* club's project) target that club
    directly. Without it, this resolves via the ambient
    `get_dashboard_state()`/`save_dashboard_state()` pair, which always
    means the *current viewer's own* club — wrong for a cross-club caller.
    """
    owns_state = state is None
    if owns_state:
        state = get_dashboard_state()
    notifications = state.setdefault('notifications', [])
    notification = {
        'id': _item_id('notif'),
        'type': notification_type,
        'title': title,
        'message': message,
        'data': data or {},
        'read': False,
        'createdAt': utc_iso(),
    }
    notifications.insert(0, notification)
    state['notifications'] = notifications[:100]
    if owns_state:
        save_dashboard_state(state)
    return notification
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_notifications.py -k explicit_state -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full notifications test file to confirm no regression**

Run: `python -m pytest tests/test_notifications.py -v`
Expected: all pass (existing bell-menu tests use the default `state=None` path, unaffected)

- [ ] **Step 6: Commit**

```bash
git add src/notifications.py tests/test_notifications.py
git commit -m "feat: let add_in_app_notification target an explicit club state"
```

---

### Task 2: Owner review notification + email templates

**Files:**
- Modify: `src/email.py` (append after `render_project_submitted`, which ends at line 227)
- Modify: `src/notifications.py` (append after `notify_admins_of_project_submission`; extend imports)
- Test: `tests/test_notifications.py`

**Interfaces:**
- Consumes: `add_in_app_notification(..., state=...)` (Task 1); `COINS_PER_APPROVED_SHIP` (`src/helpers.py:30`, already defined).
- Produces: `notify_owner_of_project_review(state, project, approved: bool) -> None` in `src/notifications.py`. `render_project_approved(project, club_name, recipient_name, coins_awarded) -> str` and `render_project_rejected(project, club_name, recipient_name) -> str` in `src/email.py`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_notifications.py`:

```python
def test_notify_owner_of_project_review_approved(monkeypatch):
    from src import notifications

    sent = []
    monkeypatch.setattr(
        notifications, 'send_email',
        lambda subject, recipients, template: sent.append((subject, recipients, template)),
    )
    state = {'settings': {'clubName': 'Test Club'}, 'notifications': []}
    project = {'id': 'p1', 'name': 'Tide Tracker', 'ownerEmail': 'Owner@Test.com', 'ownerName': 'Owner'}

    notifications.notify_owner_of_project_review(state, project, approved=True)

    assert len(sent) == 1
    subject, recipients, template = sent[0]
    assert 'Tide Tracker' in subject
    assert recipients == 'Owner@Test.com'
    assert '25' in template

    assert len(state['notifications']) == 1
    note = state['notifications'][0]
    assert note['type'] == 'project_reviewed'
    assert note['data'] == {'projectId': 'p1', 'approved': True}


def test_notify_owner_of_project_review_rejected(monkeypatch):
    from src import notifications

    sent = []
    monkeypatch.setattr(
        notifications, 'send_email',
        lambda subject, recipients, template: sent.append((subject, recipients, template)),
    )
    state = {'settings': {'clubName': 'Test Club'}, 'notifications': []}
    project = {'id': 'p1', 'name': 'Tide Tracker', 'ownerEmail': 'owner@test.com', 'ownerName': 'Owner'}

    notifications.notify_owner_of_project_review(state, project, approved=False)

    assert len(sent) == 1
    assert 'Draft' in state['notifications'][0]['title']
    assert state['notifications'][0]['data']['approved'] is False


def test_notify_owner_of_project_review_skips_ownerless_project(monkeypatch):
    from src import notifications

    sent = []
    monkeypatch.setattr(
        notifications, 'send_email',
        lambda subject, recipients, template: sent.append((subject, recipients, template)),
    )
    state = {'settings': {'clubName': 'Test Club'}, 'notifications': []}
    project = {'id': 'p1', 'name': 'Orphan Project', 'ownerEmail': ''}

    notifications.notify_owner_of_project_review(state, project, approved=True)

    assert sent == []
    assert state['notifications'] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_notifications.py -k notify_owner_of_project_review -v`
Expected: FAIL — `module 'src.notifications' has no attribute 'notify_owner_of_project_review'`

- [ ] **Step 3: Implement the email templates**

Append to `src/email.py` after `render_project_submitted` (after line 227):

```python


def render_project_approved(project, club_name, recipient_name, coins_awarded):
    """Render the email sent to a member when their shipped project is approved."""
    return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Project Approved</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
        .project-card {{ background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .coin-banner {{ background: #fff8e1; border-radius: 8px; padding: 16px; margin: 20px 0; text-align: center; font-weight: 600; font-size: 18px; }}
        .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1 style="margin: 0; font-size: 24px;">🎉 Project Approved</h1>
        <p style="margin: 10px 0 0; opacity: 0.9;">{escape(club_name)}</p>
    </div>
    <div class="content">
        <p>Hi {escape(recipient_name)},</p>
        <p>Your project shipped:</p>

        <div class="project-card">
            <p style="margin: 0; font-weight: 600; font-size: 18px;">{escape(project.get('name', 'Untitled Project'))}</p>
        </div>

        <div class="coin-banner">+{escape(str(coins_awarded))} coins awarded 🪙</div>

        <p style="text-align: center;">
            <a href="{os.environ.get('BASE_URL', '')}/dashboard/projects" style="display: inline-block; background: #667eea; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">View Your Projects</a>
        </p>

        <div class="footer">
            <p>You're receiving this because you submitted a project.</p>
        </div>
    </div>
</body>
</html>
'''


def render_project_rejected(project, club_name, recipient_name):
    """Render the email sent to a member when their submitted project is sent back to Draft."""
    return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Project Needs Changes</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
        .project-card {{ background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1 style="margin: 0; font-size: 24px;">Project Sent Back to Draft</h1>
        <p style="margin: 10px 0 0; opacity: 0.9;">{escape(club_name)}</p>
    </div>
    <div class="content">
        <p>Hi {escape(recipient_name)},</p>
        <p>A club leader reviewed your project and sent it back to Draft:</p>

        <div class="project-card">
            <p style="margin: 0; font-weight: 600; font-size: 18px;">{escape(project.get('name', 'Untitled Project'))}</p>
        </div>

        <p>Make any changes it needs and resubmit when it's ready.</p>

        <p style="text-align: center;">
            <a href="{os.environ.get('BASE_URL', '')}/dashboard/projects" style="display: inline-block; background: #667eea; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">View Your Projects</a>
        </p>

        <div class="footer">
            <p>You're receiving this because you submitted a project.</p>
        </div>
    </div>
</body>
</html>
'''
```

- [ ] **Step 4: Implement the notification function**

In `src/notifications.py`, change the import block at the top (lines 3-10) to:

```python
from .email import (
    render_event_rsvp_confirmation,
    render_project_approved,
    render_project_rejected,
    render_project_submitted,
    render_workshop_application_notification,
    render_workshop_scheduled_confirmation,
    send_email,
)
from .helpers import COINS_PER_APPROVED_SHIP, _item_id, get_dashboard_state, save_dashboard_state, utc_iso
```

Append after `notify_admins_of_project_submission` (end of file, after line 147):

```python


def notify_owner_of_project_review(state, project, approved):
    """Notify a project's owner once a leader/admin reviews their submission.

    Takes the reviewed club's already-loaded `state` and mutates it in
    place — the caller persists once, together with the status change and
    (on approval) the coin award. Silently no-ops for a project with no
    owner email (shouldn't happen for a real submission, but a review
    action should never 500 over it).
    """
    owner_email = (project.get('ownerEmail') or '').strip().lower()
    if not owner_email:
        return
    club_name = (state.get('settings') or {}).get('clubName') or 'Your Club'
    owner_name = project.get('ownerName') or 'there'
    title = project.get('name') or 'Untitled'

    if approved:
        send_email(
            subject=f'🎉 "{title}" was approved — +{COINS_PER_APPROVED_SHIP} coins!',
            recipients=owner_email,
            template=render_project_approved(project, club_name, owner_name, COINS_PER_APPROVED_SHIP),
        )
        add_in_app_notification(
            owner_email,
            'project_reviewed',
            f'"{title}" was approved!',
            f'You earned {COINS_PER_APPROVED_SHIP} coins for shipping this project.',
            {'projectId': project.get('id'), 'approved': True},
            state=state,
        )
    else:
        send_email(
            subject=f'"{title}" needs changes before it can ship',
            recipients=owner_email,
            template=render_project_rejected(project, club_name, owner_name),
        )
        add_in_app_notification(
            owner_email,
            'project_reviewed',
            f'"{title}" was sent back to Draft',
            'A club leader reviewed your project and sent it back to Draft. Make changes and resubmit when ready.',
            {'projectId': project.get('id'), 'approved': False},
            state=state,
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_notifications.py -k notify_owner_of_project_review -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Run the full notifications test file to confirm no regression**

Run: `python -m pytest tests/test_notifications.py -v`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add src/email.py src/notifications.py tests/test_notifications.py
git commit -m "feat: add owner notification and email templates for project review"
```

---

### Task 3: Wire coin award + notification into the review endpoint

**Files:**
- Modify: `src/routes_admin.py:1-2` (imports), `:102-128` (`api_admin_project_review`)
- Test: `tests/test_admin_shop.py`

**Interfaces:**
- Consumes: `award_coins(state, delta, kind, ref, note) -> CoinTransaction` (existing, `src/helpers.py`); `COINS_PER_APPROVED_SHIP` (existing); `notify_owner_of_project_review(state, project, approved)` (Task 2).
- Produces: `PATCH /api/admin/projects/<club_key>/<project_id>` response gains a `coinsAwarded: int` field (0 when no coins were awarded this call — already-Shipped re-PATCH, or a Draft rejection).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_admin_shop.py`, after the existing "Admin API routes" section (after line 187):

```python
# ── Ship review (coin award) ─────────────────────────────────────────────────


def _seed_project(admin_client, status='Submitted', ledger=None, notifications=None):
    with admin_client.session_transaction() as sess:
        sess['csrf_token'] = 'tok'
        sess['dashboard_state'] = {
            'settings': {'clubName': 'Ship Club', 'coinBalance': 0, 'coinsSpent': 0},
            'members': [],
            'projects': [
                {
                    'id': 'p1',
                    'name': 'Tide Tracker',
                    'status': status,
                    'ownerEmail': 'owner@test.com',
                    'ownerName': 'Owner',
                    'date': '2026-08-01',
                }
            ],
            'ledger': ledger or [],
            'notifications': notifications or [],
        }


def test_approve_project_awards_coins(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_project(admin_client)
    response = admin_client.patch(
        '/api/admin/projects/admin@test.com/p1', json={'status': 'Shipped'}, headers=HEADERS
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body['project']['status'] == 'Shipped'
    assert body['coinsAwarded'] == 25
    with admin_client.session_transaction() as sess:
        state = sess['dashboard_state']
        assert state['settings']['coinBalance'] == 25
        assert any(t['kind'] == 'ship_approved' and t['ref'] == 'p1' for t in state['ledger'])
        assert state['notifications'][0]['type'] == 'project_reviewed'
        assert state['notifications'][0]['data']['approved'] is True


def test_reapproving_shipped_project_does_not_double_award(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_project(admin_client, status='Shipped', ledger=[
        {'id': 'c1', 'delta': 25, 'kind': 'ship_approved', 'ref': 'p1', 'note': '', 'at': '2026-08-01T00:00:00Z'}
    ])
    response = admin_client.patch(
        '/api/admin/projects/admin@test.com/p1', json={'status': 'Shipped'}, headers=HEADERS
    )
    assert response.status_code == 200
    assert response.get_json()['coinsAwarded'] == 0
    with admin_client.session_transaction() as sess:
        state = sess['dashboard_state']
        assert len(state['ledger']) == 1
        assert state['settings']['coinBalance'] == 25
        assert state['notifications'] == []


def test_reject_project_notifies_without_coins(admin_client, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'session')
    _seed_project(admin_client)
    response = admin_client.patch(
        '/api/admin/projects/admin@test.com/p1', json={'status': 'Draft'}, headers=HEADERS
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body['project']['status'] == 'Draft'
    assert body['coinsAwarded'] == 0
    with admin_client.session_transaction() as sess:
        state = sess['dashboard_state']
        assert state['ledger'] == []
        assert state['notifications'][0]['data']['approved'] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_admin_shop.py -k "approve_project or reapproving or reject_project" -v`
Expected: FAIL — `assert 'coinsAwarded' in {}` / KeyError, since the endpoint doesn't return that field yet and doesn't award coins.

- [ ] **Step 3: Implement**

In `src/routes_admin.py`, change the top imports (lines 1-22) to:

```python
import flask
from flask import current_app, flash, redirect, url_for

from .helpers import (
    ADMIN_REVIEW_STATUSES,
    COINS_PER_APPROVED_SHIP,
    _find_club_by_project,
    _load_admin_club,
    _persist_club,
    _positive_int,
    _storage,
    add_shop_item,
    admin_required,
    award_coins,
    clean_text,
    find_by_id,
    json_error,
    json_payload,
    paginate,
    parse_bool,
    remove_shop_item,
    require_admin_api,
    require_dashboard_csrf,
)
from .notifications import notify_owner_of_project_review
```

Replace the body of `api_admin_project_review` (`src/routes_admin.py:102-128`, from `project['status'] = status` to the end of the function):

```python
        payload = json_payload()
        status = clean_text(payload.get('status')).title()
        if status not in ADMIN_REVIEW_STATUSES:
            return json_error('Status must be Shipped or Draft.')

        old_status = project.get('status')
        project['status'] = status

        coins_awarded = 0
        if status != old_status:
            if status == 'Shipped':
                coins_awarded = COINS_PER_APPROVED_SHIP
                award_coins(
                    state,
                    coins_awarded,
                    'ship_approved',
                    project_id,
                    f'Approved: {project.get("name", "Untitled")}',
                )
            try:
                notify_owner_of_project_review(state, project, status == 'Shipped')
            except Exception as exc:
                current_app.logger.error(f'Failed to send project review notification: {exc}')

        _persist_club(backend, club_key, state)
        return flask.jsonify({'project': project, 'coinsAwarded': coins_awarded})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_admin_shop.py -k "approve_project or reapproving or reject_project" -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest -q`
Expected: all pass, same count as before plus these 3 new tests (no regressions)

- [ ] **Step 6: Commit**

```bash
git add src/routes_admin.py tests/test_admin_shop.py
git commit -m "feat: award coins and notify owner on ship review"
```

---

### Task 4: Frontend — surface the coin award

**Files:**
- Modify: `static/js/dashboard.js:1644-1660` (`adminProjectAction`), `:1723-1731` (its call sites), `:928-929` (shipped project note)

**Interfaces:**
- Consumes: `coinsAwarded` field on the `PATCH /api/admin/projects/...` response (Task 3).
- Produces: no new interface — UI text only.

- [ ] **Step 1: Update `adminProjectAction` to build the toast from the response**

Replace `static/js/dashboard.js:1644-1660`:

```javascript
    async function adminProjectAction(trigger, status, buildMessage) {
        const [clubKey, projectId] = String(trigger.dataset.adminProject || '').split('::');
        if (!clubKey || !projectId) return;
        trigger.disabled = true;
        try {
            const response = await apiRequest(`/api/admin/projects/${encodeURIComponent(clubKey)}/${encodeURIComponent(projectId)}`, {
                method: 'PATCH',
                body: { status },
            });
            showToast(buildMessage(response.coinsAwarded || 0));
            // Admin pages are server-rendered outside dashboardState — reload.
            setTimeout(() => window.location.reload(), 350);
        } catch (error) {
            trigger.disabled = false;
            showToast(error.message, 'error');
        }
    }
```

Replace the call sites at `static/js/dashboard.js:1723-1731`:

```javascript
            const approveProject = event.target.closest('[data-approve-project]');
            if (approveProject) {
                await adminProjectAction(approveProject, 'Shipped', (coins) =>
                    coins > 0 ? `Project approved — shipped! +${coins} coins awarded 🎉` : 'Project approved — shipped!');
                return;
            }
            const rejectProject = event.target.closest('[data-reject-project]');
            if (rejectProject) {
                await adminProjectAction(rejectProject, 'Draft', () => 'Project sent back to draft.');
                return;
            }
```

- [ ] **Step 2: Update the member-facing shipped note**

In `static/js/dashboard.js` around line 928-929, replace:

```javascript
                if (isShipped) {
                    primaryAction = '<span class="project-shipped-note"><span data-hc-icon="rocket" data-hc-size="14" data-hc-color="currentColor" aria-hidden="true"></span> Shipped — counts toward your club level</span>';
```

with:

```javascript
                if (isShipped) {
                    primaryAction = '<span class="project-shipped-note"><span data-hc-icon="rocket" data-hc-size="14" data-hc-color="currentColor" aria-hidden="true"></span> Shipped — counts toward your club level and earned you coins</span>';
```

- [ ] **Step 3: Manual verification (no JS test harness in this repo)**

Run: `python app.py` (or the existing dev-server command), sign in as an admin (email in `ADMIN_EMAILS`), submit a project as a regular member in another session, then approve it from `/dashboard/admin`.
Expected: toast reads "Project approved — shipped! +25 coins awarded 🎉"; the member's Projects page shows the updated shipped note; the member's coin balance chip reflects +25 on next load.

- [ ] **Step 4: Run the full test suite one more time**

Run: `python -m pytest -q`
Expected: all pass (JS changes don't affect Python tests, this just confirms nothing else broke)

- [ ] **Step 5: Commit**

```bash
git add static/js/dashboard.js
git commit -m "feat: show coin award in ship review toast and shipped note"
```
