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
        ]
    };
})(window);
