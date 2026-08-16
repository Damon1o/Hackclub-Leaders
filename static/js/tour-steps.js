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
                target: '#teamRoster',
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
                target: '#workshopGrid',
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
                target: '#eventList',
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
        ]
    };
})(window);
