"""Shared type definitions for Hack Club Leaders Portal."""

from typing import Any, TypedDict


class Member(TypedDict):
    id: str
    name: str
    email: str
    role: str
    avatar: str
    status: str


class Event(TypedDict):
    id: str
    title: str
    date: str
    time: str
    location: str
    type: str
    repeat: str
    rsvp: bool
    attendees: int


class Project(TypedDict):
    id: str
    name: str
    description: str
    url: str
    repoUrl: str
    demoUrl: str
    thumbnail: str
    hackatimeProject: str
    status: str
    ownerEmail: str
    ownerName: str
    date: str


class Workshop(TypedDict):
    id: str
    title: str
    description: str
    status: str  # 'Proposed' | 'Scheduled' | 'Run'
    proposerEmail: str
    proposerName: str
    applicants: list[str]  # member emails who applied to run it
    runnerEmail: str  # '' until Scheduled
    runnerName: str  # '' until Scheduled
    eventId: str  # '' until Scheduled; id of the linked Event
    createdAt: str


class ShopItem(TypedDict):
    id: str
    name: str
    cost: int | None
    image_src: str
    filter: str


class Newsletter(TypedDict):
    id: str
    title: str
    excerpt: str
    body: str
    date: str
    readTime: str
    read: bool


class OrderItem(TypedDict):
    id: str
    quantity: int
    coinCost: int


class CoinTransaction(TypedDict):
    id: str
    delta: int
    kind: str
    ref: str
    note: str
    at: str


class Order(TypedDict):
    id: str
    date: str
    status: str
    items: list[OrderItem]


class ItemRequest(TypedDict):
    id: str
    name: str
    note: str
    date: str
    status: str


class Channel(TypedDict):
    id: str
    name: str
    description: str
    createdBy: str
    lastMessageAt: str


class Message(TypedDict):
    id: str
    channelId: str
    authorEmail: str
    authorName: str
    authorAvatar: str
    body: str
    createdAt: str


class Settings(TypedDict):
    joinCode: str
    clubName: str
    venue: str
    location: str
    addressLine1: str
    addressLine2: str
    city: str
    state: str
    zip: str
    country: str
    meetingDay: str
    clubBio: str
    website: str
    avatar: str
    publicDirectory: bool
    emailNotifications: bool
    darkModeDefault: bool
    chatEnabledForMembers: bool
    newsletterSubscribed: bool
    language: str
    coinBalance: int
    coinsSpent: int


class Notification(TypedDict):
    id: str
    type: str
    title: str
    message: str
    data: dict[str, Any]
    read: bool
    createdAt: str


class DashboardState(TypedDict, total=False):
    members: list[Member]
    events: list[Event]
    projects: list[Project]
    shopItems: list[ShopItem]
    cart: list[OrderItem]
    orders: list[Order]
    itemRequests: list[ItemRequest]
    channels: list[Channel]
    messages: list[Message]
    newsletters: list[Newsletter]
    ledger: list[CoinTransaction]
    workshops: list[Workshop]
    notifications: list[Notification]
    settings: Settings


class ClubStateLite(TypedDict, total=False):
    settings: Settings
    members: list[Member]
    _lite: bool


class ClubState(TypedDict, total=False):
    settings: Settings
    members: list[Member]
    events: list[Event]
    newsletters: list[Newsletter]
    orders: list[Order]
    itemRequests: list[ItemRequest]
    projects: list[Project]
    channels: list[Channel]
    messages: list[Message]
