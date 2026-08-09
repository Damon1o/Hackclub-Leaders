"""Email notification system for the Hack Club Leaders Portal."""

import os
import re
from threading import Thread

from flask import current_app
from flask_mail import Mail, Message
from markupsafe import escape

mail = Mail()


def send_async_email(app, msg):
    """Send email in background thread."""
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            current_app.logger.error(f'Failed to send email: {e}')


def send_email(subject, recipients, template, **kwargs):
    """Send email using a template. Runs in background thread."""
    app = current_app._get_current_object()

    msg = Message(
        subject=subject,
        recipients=recipients if isinstance(recipients, list) else [recipients],
    )
    msg.html = template
    msg.body = _html_to_text(template)

    Thread(target=send_async_email, args=(app, msg), daemon=True).start()


def _html_to_text(html):
    """Convert HTML to plain text (simple version)."""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', html)).strip()


# ── Email templates ────────────────────────────────────────────────────────────

def render_event_rsvp_confirmation(event, club_name, recipient_name, is_rsvp):
    """Render RSVP confirmation email."""
    action = 'RSVPed to' if is_rsvp else 'removed RSVP from'
    return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>RSVP Confirmation</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
        .event-card {{ background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1 style="margin: 0; font-size: 24px;">✅ RSVP Confirmed</h1>
        <p style="margin: 10px 0 0; opacity: 0.9;">{escape(club_name)}</p>
    </div>
    <div class="content">
        <p>Hi {escape(recipient_name)},</p>
        <p>You have {action} the following event:</p>

        <div class="event-card">
            <p style="margin: 0; font-weight: 600;">{escape(event.get('title', 'Untitled Event'))}</p>
            <p style="margin: 10px 0 0; color: #666;">{escape(event.get('date', 'TBD'))} at {escape(event.get('time', 'TBD'))} · {escape(event.get('location', 'TBD'))}</p>
        </div>

        <p style="text-align: center;">
            <a href="{os.environ.get('BASE_URL', '')}/dashboard/events" style="display: inline-block; background: #667eea; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">View Event</a>
        </p>

        <div class="footer">
            <p>You're receiving this because you're a member of {escape(club_name)}.</p>
        </div>
    </div>
</body>
</html>
'''


def render_workshop_application_notification(workshop, club_name, recipient_name, applicant_name, is_applying):
    """Render the email sent to leaders when a member applies to run (or withdraws from) a workshop."""
    action = 'applied to run' if is_applying else 'withdrew their application for'
    return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Workshop Application</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
        .event-card {{ background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1 style="margin: 0; font-size: 24px;">🔔 Workshop Application</h1>
        <p style="margin: 10px 0 0; opacity: 0.9;">{escape(club_name)}</p>
    </div>
    <div class="content">
        <p>Hi {escape(recipient_name)},</p>
        <p>{escape(applicant_name)} has {escape(action)} the following workshop:</p>

        <div class="event-card">
            <p style="margin: 0; font-weight: 600;">{escape(workshop.get('title', 'Untitled Workshop'))}</p>
            <p style="margin: 10px 0 0; color: #666;">{escape(workshop.get('description', ''))}</p>
        </div>

        <p style="text-align: center;">
            <a href="{os.environ.get('BASE_URL', '')}/dashboard/workshops" style="display: inline-block; background: #667eea; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">View Workshops</a>
        </p>

        <div class="footer">
            <p>You're receiving this because you're a leader of {escape(club_name)}.</p>
        </div>
    </div>
</body>
</html>
'''


def render_project_submitted(project, club_name, recipient_name):
    """Render project submission notification email."""
    return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Project Submitted for Review</title>
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
        <h1 style="margin: 0; font-size: 24px;">🚀 Project Submitted for Review</h1>
        <p style="margin: 10px 0 0; opacity: 0.9;">{escape(club_name)}</p>
    </div>
    <div class="content">
        <p>Hi {escape(recipient_name)},</p>
        <p>A member has submitted a project for admin review:</p>

        <div class="project-card">
            <p style="margin: 0 0 10px; font-weight: 600; font-size: 18px;">{escape(project.get('name', 'Untitled Project'))}</p>
            <p style="margin: 0 0 15px; color: #666;">by {escape(project.get('ownerName', 'Unknown Member'))}</p>
            <p style="margin: 0 0 15px;">{escape(project.get('description', 'No description provided.'))}</p>
            <div style="margin: 15px 0;">
                <strong>Repository:</strong> {escape(project.get('repoUrl', 'Not provided'))}<br>
                <strong>Demo:</strong> {escape(project.get('demoUrl', 'Not provided'))}<br>
                <strong>Hackatime Project:</strong> {escape(project.get('hackatimeProject', 'Not provided'))}
            </div>
        </div>

        <p style="text-align: center;">
            <a href="{os.environ.get('BASE_URL', '')}/dashboard/admin" style="display: inline-block; background: #667eea; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">Review in Admin Panel</a>
        </p>

        <div class="footer">
            <p>You're receiving this because you're an admin.</p>
        </div>
    </div>
</body>
</html>
'''
