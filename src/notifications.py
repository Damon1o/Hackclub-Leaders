"""In-app and email notifications for the Hack Club Leaders Portal."""

from .email import (
    render_event_rsvp_confirmation,
    render_project_submitted,
    render_workshop_application_notification,
    send_email,
)
from .helpers import _item_id, get_dashboard_state, save_dashboard_state, utc_iso


def _club_name():
    return get_dashboard_state().get('settings', {}).get('clubName', 'Your Club')


def add_in_app_notification(user_email, notification_type, title, message, data=None):
    """Add a notification to the user's in-app notification center."""
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
