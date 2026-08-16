(function () {
    'use strict';

    var MASCOT_SRC = '/static/images/Stickers/find%20out.webp';

    function isVisible(el) {
        if (!el || el.hidden) return false;
        var rect = el.getBoundingClientRect();
        return el.offsetParent !== null && rect.width > 0 && rect.height > 0;
    }

    function reducedMotion() {
        return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    }

    function TourController(pageKey, steps) {
        this.pageKey = pageKey;
        this.steps = steps;
        this.storageKey = 'hc_tour_seen_' + pageKey;
        this.overlay = null;
        this.tooltip = null;
        this.spotlightEl = null;
        this.stepIndex = -1;
        this.positionTimer = null;
    }

    TourController.prototype.buildOverlay = function () {
        var overlay = document.createElement('div');
        overlay.className = 'tour-overlay';

        var spotlightEl = document.createElement('div');
        spotlightEl.className = 'tour-spotlight';
        overlay.appendChild(spotlightEl);

        var tooltip = document.createElement('div');
        tooltip.className = 'tour-tooltip';
        tooltip.innerHTML =
            '<img class="tour-mascot" src="' + MASCOT_SRC + '" alt="" aria-hidden="true">' +
            '<div class="tour-tooltip-body">' +
            '<h3 class="tour-title"></h3>' +
            '<p class="tour-body"></p>' +
            '<div class="tour-actions">' +
            '<button type="button" class="tour-skip">Skip</button>' +
            '<div class="tour-progress"></div>' +
            '<button type="button" class="tour-next">Next</button>' +
            '</div>' +
            '</div>';
        overlay.appendChild(tooltip);

        document.body.appendChild(overlay);

        tooltip.querySelector('.tour-skip').addEventListener('click', this.end.bind(this));
        tooltip.querySelector('.tour-next').addEventListener('click', function () {
            this.next(this.stepIndex);
        }.bind(this));

        this.overlay = overlay;
        this.tooltip = tooltip;
        this.spotlightEl = spotlightEl;
    };

    TourController.prototype.positionOn = function (target) {
        var rect = target.getBoundingClientRect();
        var pad = 8;
        this.spotlightEl.style.top = (rect.top - pad) + 'px';
        this.spotlightEl.style.left = (rect.left - pad) + 'px';
        this.spotlightEl.style.width = (rect.width + pad * 2) + 'px';
        this.spotlightEl.style.height = (rect.height + pad * 2) + 'px';

        var tooltipTop = rect.bottom + 16;
        var tooltipLeft = Math.min(Math.max(rect.left, 16), window.innerWidth - 360);
        this.tooltip.style.top = tooltipTop + 'px';
        this.tooltip.style.left = tooltipLeft + 'px';
    };

    TourController.prototype.showStep = function (index) {
        var step = this.steps[index];
        var target = step ? document.querySelector(step.target) : null;
        if (!step || !isVisible(target)) {
            this.next(index);
            return;
        }
        this.stepIndex = index;
        this.tooltip.querySelector('.tour-title').textContent = step.title;
        this.tooltip.querySelector('.tour-body').textContent = step.body;
        this.tooltip.querySelector('.tour-progress').textContent = (index + 1) + ' / ' + this.steps.length;
        this.tooltip.querySelector('.tour-next').textContent = index === this.steps.length - 1 ? 'Done' : 'Next';
        this.positionOn(target);
        target.scrollIntoView({ block: 'center', behavior: reducedMotion() ? 'auto' : 'smooth' });
        clearTimeout(this.positionTimer);
        var self = this;
        this.positionTimer = setTimeout(function () {
            self.positionOn(target);
        }, 350);
    };

    TourController.prototype.next = function (fromIndex) {
        var current = typeof fromIndex === 'number' ? fromIndex : this.stepIndex;
        if (current >= this.steps.length - 1) {
            this.end();
            return;
        }
        this.showStep(current + 1);
    };

    TourController.prototype.end = function () {
        clearTimeout(this.positionTimer);
        if (this.overlay) {
            this.overlay.remove();
            this.overlay = null;
        }
        try {
            localStorage.setItem(this.storageKey, '1');
        } catch (error) {
            /* storage full or unavailable — non-fatal */
        }
    };

    TourController.prototype.start = function () {
        if (!this.overlay) this.buildOverlay();
        this.showStep(0);
    };

    TourController.prototype.hasBeenSeen = function () {
        try {
            return !!localStorage.getItem(this.storageKey);
        } catch (error) {
            return false;
        }
    };

    document.addEventListener('DOMContentLoaded', function () {
        var pageKey = document.body.getAttribute('data-tour-page');
        var allSteps = window.HC_TOUR_STEPS || {};
        var steps = (pageKey && allSteps[pageKey]) || [];
        var replayButton = document.getElementById('tourReplayButton');

        if (!steps.length) {
            if (replayButton) replayButton.hidden = true;
            return;
        }

        var controller = new TourController(pageKey, steps);

        if (replayButton) {
            replayButton.hidden = false;
            replayButton.addEventListener('click', function () {
                controller.start();
            });
        }

        if (!controller.hasBeenSeen()) {
            controller.start();
        }
    });
})();
