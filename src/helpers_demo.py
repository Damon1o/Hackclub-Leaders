"""Demo and default initial state builders for Hack Club Leaders Portal."""

from datetime import date

from .helpers_types import DashboardState, ShopItem
from .helpers_validation import DEFAULT_LANGUAGE


def generate_join_code() -> str:
    import secrets
    return secrets.token_hex(3).upper()


def default_dashboard_state(shop_items: list[ShopItem]) -> DashboardState:
    from flask import session

    from .helpers import STARTER_GRANT_COINS, award_coins
    user = session.get('user') or {}
    leader_name = user.get('name') or 'Club Leader'
    leader_email = user.get('email') or 'leader@hackclub.com'

    state: DashboardState = {
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
        'events': [],
        'shopItems': [dict(item) for item in shop_items],  # type: ignore[misc]
        'cart': [],
        'orders': [],
        'itemRequests': [],
        'projects': [],
        'channels': [],
        'messages': [],
        'notifications': [],
        'ledger': [],
        'workshops': [],
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
            'joinCode': generate_join_code(),
            'clubName': f"{leader_name}'s Hack Club",
            'venue': '',
            'location': '',
            'addressLine1': '',
            'addressLine2': '',
            'city': '',
            'state': '',
            'zip': '',
            'country': '',
            'meetingDay': '',
            'clubBio': '',
            'website': '',
            'avatar': '',
            'publicDirectory': True,
            'emailNotifications': True,
            'darkModeDefault': False,
            'chatEnabledForMembers': True,
            'newsletterSubscribed': True,
            'language': DEFAULT_LANGUAGE,
            'coinBalance': 0,
            'coinsSpent': 0,
        },
    }
    award_coins(
        state,
        STARTER_GRANT_COINS,
        'starter_grant',
        '',
        'Welcome to Hack Club — here are your first coins.',
    )
    return state


def playtest_state(shop_items: list[ShopItem] | None = None) -> DashboardState:
    from .helpers_shop import SHOP_ITEMS
    if shop_items is None:
        shop_items = SHOP_ITEMS
    today = date.today().isoformat()
    leader_email = 'playtest.leader@hackclub.com'
    member_email = 'playtest.member@hackclub.com'
    return {
        'settings': {
            'joinCode': 'PLAYTEST',
            'clubName': 'Playtest Hack Club',
            'venue': 'Playtest High School',
            'location': 'Burlington, VT',
            'addressLine1': '',
            'addressLine2': '',
            'city': 'Burlington',
            'state': 'VT',
            'zip': '',
            'country': 'US',
            'meetingDay': 'Wednesday',
            'clubBio': '',
            'website': 'https://hackclub.com',
            'avatar': '',
            'publicDirectory': True,
            'emailNotifications': True,
            'darkModeDefault': False,
            'chatEnabledForMembers': True,
            'newsletterSubscribed': True,
            'language': 'en',
            'coinBalance': 0,
            'coinsSpent': 0,
        },
        'members': [
            {
                'id': 'playtest-leader',
                'name': 'Test Leader',
                'email': leader_email,
                'role': 'Leader',
                'avatar': '',
                'status': 'Active',
            },
            {
                'id': 'playtest-member',
                'name': 'Test Member',
                'email': member_email,
                'role': 'Member',
                'avatar': '',
                'status': 'Active',
            },
        ],
        'events': [
            {
                'id': 'playtest-event-1',
                'title': 'First Club Meeting',
                'date': today,
                'time': '15:30',
                'location': 'Room 101',
                'repeat': '',
                'type': 'Workshop',
                'attendees': 8,
                'rsvp': True,
            },
            {
                'id': 'playtest-event-2',
                'title': 'Build Night',
                'date': today,
                'time': '18:00',
                'location': 'Library Makerspace',
                'repeat': '',
                'type': 'Hackathon',
                'attendees': 12,
                'rsvp': False,
            },
        ],
        'projects': [
            {
                'id': 'playtest-proj-1',
                'name': 'LED Blinker',
                'description': 'My first Arduino project — a blinking LED circuit.',
                'url': '',
                'repoUrl': '',
                'demoUrl': '',
                'thumbnail': '',
                'hackatimeProject': '',
                'ownerEmail': leader_email,
                'ownerName': 'Test Leader',
                'status': 'Shipped',
                'date': today,
                'publicId': 'showcase-playtest-led',
                'isPublic': False,
                'category': '',
            },
            {
                'id': 'playtest-proj-2',
                'name': 'Club Website',
                'description': 'A simple React site for club announcements.',
                'url': 'https://example.com',
                'repoUrl': 'https://github.com/playtest/club-site',
                'demoUrl': '',
                'thumbnail': '',
                'hackatimeProject': '',
                'ownerEmail': member_email,
                'ownerName': 'Test Member',
                'status': 'Submitted',
                'date': today,
                'publicId': 'showcase-playtest-site',
                'isPublic': False,
                'category': '',
            },
        ],
        'shopItems': [dict(item) for item in shop_items],  # type: ignore[misc]
        'cart': [],
        'orders': [],
        'itemRequests': [],
        'newsletters': default_dashboard_state(shop_items)['newsletters'],
    }
