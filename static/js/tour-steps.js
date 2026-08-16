(function (global) {
    'use strict';

    global.HC_TOUR_STEPS = {
        tools: [
            {
                target: '.dashboard-header',
                title: 'Your club tools',
                body: 'Everything here helps you run your Hack Club — from special programs to everyday resources.'
            },
            {
                target: '[data-tour="featured-row"]',
                title: 'Featured programs',
                body: 'Apply for special Hack Club programs like custom YSWS projects, Spaces, and Canva Pro.'
            },
            {
                target: '[data-tour="standard-grid"]',
                title: 'Everyday resources',
                body: 'Workshops, HCB, posters, and guides for running your club day to day.'
            },
            {
                target: '[data-tour="placeholder-card"]',
                title: 'More coming soon',
                body: "We're adding more tools over time. Got a request? Let us know in Slack."
            }
        ],
        home: [
            {
                target: '.home-hero',
                title: 'Your club HQ',
                body: "Your club's name and quick stats: members, events, RSVPs, ships, and shop orders."
            },
            {
                target: '.home-team',
                title: 'Your roster at a glance',
                body: 'See how your club splits across leaders, members, and mentors.'
            },
            {
                target: '.level-band',
                title: "Your club's level",
                body: 'Ship projects to level up and unlock new perks.'
            },
            {
                target: '.home-coins',
                title: 'Coins earned',
                body: 'Every approved ship earns your club coins — track the last 30 days here.'
            },
            {
                target: '.home-events',
                title: "What's next",
                body: 'Your upcoming meetings and events, right on the home page.'
            }
        ],
        team: [
            {
                target: '.dashboard-metrics',
                title: 'Your team, counted',
                body: 'Members, leaders, and pending invites, all at a glance.'
            },
            {
                target: '.join-link-card',
                title: 'Invite with a link',
                body: 'Share this link — anyone who opens it joins your club instantly.'
            },
            {
                target: '[data-tour="team-roster"]',
                title: 'Your roster',
                body: "Everyone in your club. Click a member to edit their role or status."
            }
        ],
        workshops: [
            {
                target: '#workshopFilters',
                title: 'Browse by type',
                body: 'Filter the workshop board by category.'
            },
            {
                target: '[data-tour="workshops-board"]',
                title: 'Propose or run one',
                body: "Propose a topic for your club, or apply to run one that's already open."
            }
        ],
        events: [
            {
                target: '.dashboard-metrics',
                title: 'Your event stats',
                body: "Upcoming meetings, RSVPs, and how many people you're expecting."
            },
            {
                target: '[data-tour="events-schedule"]',
                title: 'Your schedule',
                body: 'Every meeting, workshop, and demo day your club has planned.'
            }
        ],
        shop: [
            {
                target: '#shopFilters',
                title: 'Browse the shop',
                body: 'Stickers, posters, and hardware — filter by category.'
            },
            {
                target: '#cartPanel',
                title: 'Your cart',
                body: "Add items here, then check out when you're ready."
            },
            {
                target: '.request-item-block',
                title: "Don't see it?",
                body: "Request an item and we'll consider adding it to the shop."
            }
        ],
        levels: [
            {
                target: '.level-status-card',
                title: 'Where you stand',
                body: "Your club's current level and progress to the next one."
            },
            {
                target: '.levels-grid',
                title: 'What you unlock',
                body: 'See what perks each level brings.'
            },
            {
                target: '.level-cta',
                title: 'Ready to level up?',
                body: 'Log a shipped project and watch the perks unlock.'
            }
        ],
        map: [
            {
                target: '.map-card',
                title: 'Every Hack Club, worldwide',
                body: 'Make sure your club shows up here too.'
            }
        ],
        projects: [
            {
                target: '[data-tour="projects-mine"]',
                title: 'Your projects',
                body: 'Track your own projects here — only you can edit them.'
            },
            {
                target: '[data-tour="projects-submitted"]',
                title: 'Club submissions',
                body: 'Once you submit a project, it lands here for a leader to review.'
            }
        ],
        ships: [
            {
                target: '.dashboard-metrics',
                title: 'Your ship stats',
                body: 'Total ships, current level, and members shipped toward the next one.'
            },
            {
                target: '[data-tour="ships-list"]',
                title: "What's shipped",
                body: 'Every approved project your club has shipped.'
            }
        ],
        chat: [
            {
                target: '.chat-sidebar',
                title: 'Your channels',
                body: "Jump between your club's channels, or create a new one if you're a leader."
            },
            {
                target: '.chat-empty',
                title: 'Start chatting',
                body: 'Pick a channel from the sidebar to join the conversation.'
            }
        ],
        notifications: [
            {
                target: '.newsletter-list-panel',
                title: 'Dispatches from HQ',
                body: 'Updates from Hack Club HQ, plus anything you send your own club.'
            },
            {
                target: '#notificationsMarkAllReadBtn',
                title: 'Stay caught up',
                body: 'Mark everything as read in one click.'
            },
            {
                target: '[data-open-modal="dispatchModal"]',
                title: 'Send an update',
                body: 'Write a dispatch to your whole club.'
            }
        ],
        settings: [
            {
                target: '#settingsNav',
                title: 'Jump to a section',
                body: 'Club profile, members, appearance, privacy, notifications — organized in one place.'
            },
            {
                target: '#danger-zone',
                title: 'Careful in here',
                body: 'Irreversible stuff lives in the danger zone — read twice before you click.'
            }
        ],
        profile: [
            {
                target: '#profileForm',
                title: 'Your details',
                body: 'Name, email, avatar, and bio — how you show up across the portal.'
            },
            {
                target: '.hackatime-connect',
                title: 'Track your coding time',
                body: 'Connect Hackatime to show your coding time on Projects.'
            },
            {
                target: '#profilePreview',
                title: 'How others see you',
                body: 'A live preview of your profile card.'
            }
        ],
        admin: [
            {
                target: '.dashboard-metrics',
                title: 'Platform at a glance',
                body: 'Total clubs, projects waiting on review, and members across Hack Club.'
            },
            {
                target: '.admin-review-list',
                title: 'Review queue',
                body: "Approve or reject shipped projects — approved ones count toward a club's level."
            },
            {
                target: '.admin-table',
                title: 'Every club',
                body: 'Browse all clubs, or open one to manage it directly.'
            }
        ],
        'admin-club': [
            {
                target: '#adminClubForm',
                title: 'Edit on their behalf',
                body: "Update this club's profile as an admin."
            },
            {
                target: '.timeline-list',
                title: 'Their shipped projects',
                body: 'Approve, reject, or un-ship a project for this club.'
            }
        ]
    };
})(window);
