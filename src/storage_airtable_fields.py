"""Airtable column mappings for the Hack Club Leaders Portal storage layer."""

from typing import Final

MEMBER_FIELDS: Final[list[tuple[str, str]]] = [
    ('name', 'Name'),
    ('email', 'Email'),
    ('role', 'Role'),
    ('status', 'Status'),
    ('avatar', 'Avatar'),
]
EVENT_FIELDS: Final[list[tuple[str, str]]] = [
    ('title', 'Title'),
    ('date', 'Date'),
    ('time', 'Time'),
    ('location', 'Location'),
    ('type', 'Type'),
    ('repeat', 'Repeat'),
    ('rsvp', 'RSVP'),
    ('attendees', 'Attendees'),
]
NEWSLETTER_FIELDS: Final[list[tuple[str, str]]] = [
    ('title', 'Title'),
    ('excerpt', 'Excerpt'),
    ('body', 'Body'),
    ('date', 'Date'),
    ('readTime', 'Read Time'),
    ('read', 'Read'),
]
ORDER_FIELDS: Final[list[tuple[str, str]]] = [('date', 'Date'), ('status', 'Status')]
ITEM_REQUEST_FIELDS: Final[list[tuple[str, str]]] = [
    ('name', 'Name'),
    ('note', 'Note'),
    ('date', 'Date'),
    ('status', 'Status'),
]
PROJECT_FIELDS: Final[list[tuple[str, str]]] = [
    ('name', 'Name'),
    ('description', 'Description'),
    ('url', 'URL'),
    ('repoUrl', 'Repo URL'),
    ('demoUrl', 'Demo URL'),
    ('thumbnail', 'Thumbnail'),
    ('hackatimeProject', 'Hackatime Project'),
    ('status', 'Status'),
    ('ownerEmail', 'Owner Email'),
    ('ownerName', 'Owner Name'),
    ('date', 'Date'),
]
LEDGER_FIELDS: Final[list[tuple[str, str]]] = [
    ('delta', 'Delta'),
    ('kind', 'Kind'),
    ('ref', 'Ref'),
    ('note', 'Note'),
    ('at', 'At'),
]
WORKSHOP_FIELDS: Final[list[tuple[str, str]]] = [
    ('title', 'Title'),
    ('description', 'Description'),
    ('status', 'Status'),
    ('proposerEmail', 'Proposer Email'),
    ('proposerName', 'Proposer Name'),
    ('runnerEmail', 'Runner Email'),
    ('runnerName', 'Runner Name'),
    ('eventId', 'Event Id'),
    ('createdAt', 'Created At'),
]
CHANNEL_FIELDS: Final[list[tuple[str, str]]] = [
    ('name', 'Name'),
    ('description', 'Description'),
    ('topic', 'Topic'),
    ('createdBy', 'Created By'),
    ('lastMessageAt', 'Last Message At'),
]
MESSAGE_FIELDS: Final[list[tuple[str, str]]] = [
    ('channelId', 'Channel Id'),
    ('authorEmail', 'Author Email'),
    ('authorName', 'Author Name'),
    ('authorAvatar', 'Author Avatar'),
    ('body', 'Body'),
    ('createdAt', 'Created At'),
    ('linkPreview', 'Metadata'),
]
NOTIFICATION_FIELDS: Final[list[tuple[str, str]]] = [
    ('type', 'Type'),
    ('title', 'Title'),
    ('message', 'Message'),
    ('read', 'Read'),
    ('createdAt', 'Created At'),
]
SETTINGS_FIELDS: Final[list[tuple[str, str]]] = [
    ('clubName', 'Club Name'),
    ('venue', 'Venue'),
    ('location', 'Location'),
    ('addressLine1', 'Address Line 1'),
    ('addressLine2', 'Address Line 2'),
    ('city', 'City'),
    ('state', 'State'),
    ('zip', 'Zip'),
    ('country', 'Country'),
    ('meetingDay', 'Meeting Day'),
    ('clubBio', 'Club Bio'),
    ('website', 'Website'),
    ('avatar', 'Avatar'),
    ('joinCode', 'Join Code'),
    ('publicDirectory', 'Public Directory'),
    ('emailNotifications', 'Email Notifications'),
    ('darkModeDefault', 'Dark Mode Default'),
    ('chatEnabledForMembers', 'Chat Enabled For Members'),
    ('newsletterSubscribed', 'Newsletter Subscribed'),
    ('language', 'Language'),
    ('coinBalance', 'Coin Balance'),
    ('coinsSpent', 'Coins Spent'),
]
SETTINGS_INT_KEYS: Final[set[str]] = {'coinBalance', 'coinsSpent'}
