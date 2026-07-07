(function () {
    'use strict';

    const targets = Array.from(document.querySelectorAll('.reveal'));
    if (!targets.length) return;

    if (!('IntersectionObserver' in window) ||
        window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        targets.forEach(function (el) { el.classList.add('is-visible'); });
        return;
    }

    const observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.12 });

    targets.forEach(function (el, i) {
        el.style.transitionDelay = (i % 5) * 60 + 'ms';
        observer.observe(el);
    });
})();
