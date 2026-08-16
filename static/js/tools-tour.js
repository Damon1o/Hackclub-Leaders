(function () {
    'use strict';

    var STORAGE_KEY = 'hc_tools_tour_seen';

    var STEPS = [
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
    ];

    var overlay, tooltip, spotlightEl, stepIndex, positionTimer;

    function buildOverlay() {
        overlay = document.createElement('div');
        overlay.className = 'tools-tour-overlay';

        spotlightEl = document.createElement('div');
        spotlightEl.className = 'tools-tour-spotlight';
        overlay.appendChild(spotlightEl);

        tooltip = document.createElement('div');
        tooltip.className = 'tools-tour-tooltip';
        tooltip.innerHTML =
            '<h3 class="tools-tour-title"></h3>' +
            '<p class="tools-tour-body"></p>' +
            '<div class="tools-tour-actions">' +
            '<button type="button" class="tools-tour-skip">Skip</button>' +
            '<div class="tools-tour-progress"></div>' +
            '<button type="button" class="tools-tour-next">Next</button>' +
            '</div>';
        overlay.appendChild(tooltip);

        document.body.appendChild(overlay);

        tooltip.querySelector('.tools-tour-skip').addEventListener('click', endTour);
        tooltip.querySelector('.tools-tour-next').addEventListener('click', nextStep);
    }

    function positionOn(target) {
        var rect = target.getBoundingClientRect();
        var pad = 8;
        spotlightEl.style.top = (rect.top - pad) + 'px';
        spotlightEl.style.left = (rect.left - pad) + 'px';
        spotlightEl.style.width = (rect.width + pad * 2) + 'px';
        spotlightEl.style.height = (rect.height + pad * 2) + 'px';

        var tooltipTop = rect.bottom + 16;
        var tooltipLeft = Math.min(
            Math.max(rect.left, 16),
            window.innerWidth - 340
        );
        tooltip.style.top = tooltipTop + 'px';
        tooltip.style.left = tooltipLeft + 'px';
    }

    function showStep(index) {
        var step = STEPS[index];
        var target = document.querySelector(step.target);
        if (!target) {
            nextStep();
            return;
        }
        stepIndex = index;
        tooltip.querySelector('.tools-tour-title').textContent = step.title;
        tooltip.querySelector('.tools-tour-body').textContent = step.body;
        tooltip.querySelector('.tools-tour-progress').textContent =
            (index + 1) + ' / ' + STEPS.length;
        tooltip.querySelector('.tools-tour-next').textContent =
            index === STEPS.length - 1 ? 'Done' : 'Next';
        positionOn(target);
        target.scrollIntoView({ block: 'center', behavior: 'smooth' });
        clearTimeout(positionTimer);
        positionTimer = setTimeout(function () {
            positionOn(target);
        }, 350);
    }

    function nextStep() {
        var current = typeof stepIndex === 'number' ? stepIndex : -1;
        if (current >= STEPS.length - 1) {
            endTour();
            return;
        }
        showStep(current + 1);
    }

    function endTour() {
        clearTimeout(positionTimer);
        localStorage.setItem(STORAGE_KEY, '1');
        if (overlay) {
            overlay.remove();
            overlay = null;
        }
    }

    function startTour() {
        if (!overlay) buildOverlay();
        showStep(0);
    }

    document.addEventListener('DOMContentLoaded', function () {
        var replayButton = document.getElementById('toolsTourReplay');
        if (replayButton) {
            replayButton.addEventListener('click', startTour);
        }
        if (!localStorage.getItem(STORAGE_KEY)) {
            startTour();
        }
    });
})();
