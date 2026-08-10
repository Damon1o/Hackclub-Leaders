"""In-app and email notifications for the Hack Club Leaders Portal."""

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


def _club_name():
    return get_dashboard_state().get('settings', {}).get('clubName', 'Your Club')


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


def send_event_rsvp_confirmation(event, recipient_email, recipient_name, is_rsvp):
    """Send RSVP confirmation email to the member who RSVPed."""
    club_name = _club_name()
    action = 'RSVPed to' if is_rsvp else 'removed RSVP from'
    send_email(
        subject=f'✅ You {action} "{event.get("title", "Event")}" - {club_name}',
        recipients=recipient_email,
        template=render_event_rsvp_confirmation(event, club_name, recipient_name, is_rsvp),
    )


def notify_leaders_of_event_rsvp(event, user_email, user_name, is_rsvp):
    """Notify club leaders when a member RSVPs to an event."""
    state = get_dashboard_state()
    leaders = [m for m in state.get('members', []) if m.get('role') in ('Leader', 'Mentor')]
    club_name = _club_name()
    action = 'RSVPed to' if is_rsvp else 'removed their RSVP from'

    for leader in leaders:
        leader_email = leader.get('email', '').lower()
        if leader_email and leader_email != user_email:
            template = render_event_rsvp_confirmation(
                event, club_name, leader.get('name', 'Leader'), is_rsvp
            )
            send_email(
                subject=f'🔔 {user_name} {action} "{event.get("title", "Event")}"',
                recipients=leader_email,
                template=template,
            )
            add_in_app_notification(
                leader_email,
                'event_rsvp',
                f'{user_name} {action} "{event.get("title", "Event")}"',
                f'{user_name} has {action.lower()} the event on {event.get("date", "TBD")}.',
                {'eventId': event.get('id'), 'userEmail': user_email, 'isRsvp': is_rsvp},
            )


def notify_leaders_of_workshop_application(workshop, user_email, user_name, is_applying):
    """Notify club leaders when a member applies to run (or withdraws from) a workshop."""
    state = get_dashboard_state()
    leaders = [m for m in state.get('members', []) if m.get('role') in ('Leader', 'Mentor')]
    club_name = _club_name()
    title = workshop.get('title', 'Workshop')
    if is_applying:
        subject_action = 'applied to run'
        body = f'{user_name} applied to run this workshop.'
    else:
        subject_action = 'withdrew their application for'
        body = f'{user_name} withdrew their application to run this workshop.'

    for leader in leaders:
        leader_email = leader.get('email', '').lower()
        if leader_email and leader_email != user_email:
            template = render_workshop_application_notification(
                workshop, club_name, leader.get('name', 'Leader'), user_name, is_applying
            )
            send_email(
                subject=f'🔔 {user_name} {subject_action} "{title}"',
                recipients=leader_email,
                template=template,
            )
            add_in_app_notification(
                leader_email,
                'workshop_application',
                f'{user_name} {subject_action} "{title}"',
                body,
                {
                    'workshopId': workshop.get('id'),
                    'userEmail': user_email,
                    'isApplying': is_applying,
                },
            )


def notify_runner_of_workshop_selection(workshop, runner_email, runner_name):
    """Notify the member picked to run a workshop once a leader schedules it."""
    club_name = _club_name()
    title = workshop.get('title', 'Workshop')
    send_email(
        subject=f'🎉 You\'re running "{title}" - {club_name}',
        recipients=runner_email,
        template=render_workshop_scheduled_confirmation(workshop, club_name, runner_name),
    )
    add_in_app_notification(
        runner_email,
        'workshop_scheduled',
        f'You\'re running "{title}"',
        'Check the Events page for the date and time.',
        {'workshopId': workshop.get('id'), 'eventId': workshop.get('eventId')},
    )


def notify_admins_of_project_submission(project):
    """Notify admins when a project is submitted for review."""
    from .helpers import ADMIN_EMAILS, _club_key

    club_name = _club_name()
    for admin_email in ADMIN_EMAILS:
        if admin_email:
            send_email(
                subject=f'🚀 Project Submitted for Review: {project.get("name", "Untitled")}',
                recipients=admin_email,
                template=render_project_submitted(project, club_name, admin_email),
            )
            add_in_app_notification(
                admin_email,
                'project_submitted',
                f'Project submitted: {project.get("name", "Untitled")}',
                f'{project.get("ownerName", "A member")} submitted a project for review.',
                {'projectId': project.get('id'), 'clubKey': _club_key()},
            )


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
