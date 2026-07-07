(function () {
    'use strict';

    const containers = Array.from(document.querySelectorAll('.ambient-bg'));
    if (!containers.length) return;

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const root = document.documentElement;
    const glows = containers
        .map(function (el) { return el.querySelector('.ambient-cursor-glow'); })
        .filter(Boolean);

    let targetX = 0, targetY = 0;
    let parX = 0, parY = 0;
    let pointerX = 0, pointerY = 0;
    let pointerSeen = false;
    const glowStates = glows.map(function () { return { x: 0, y: 0, seeded: false }; });

    window.addEventListener('pointermove', function (e) {
        pointerX = e.clientX;
        pointerY = e.clientY;
        targetX = (e.clientX / window.innerWidth - 0.5) * 16;
        targetY = (e.clientY / window.innerHeight - 0.5) * 12;

        if (!pointerSeen) {
            pointerSeen = true;
            glows.forEach(function (glow) { glow.classList.add('is-active'); });
        }
    }, { passive: true });

    let rafId = 0;

    function frame() {
        if (!document.hidden) {
            parX += (targetX - parX) * 0.05;
            parY += (targetY - parY) * 0.05;
            root.style.setProperty('--amb-px', parX.toFixed(2) + 'px');
            root.style.setProperty('--amb-py', parY.toFixed(2) + 'px');

            if (pointerSeen) {
                glows.forEach(function (glow, i) {
                    const rect = glow.parentElement.getBoundingClientRect();
                    const state = glowStates[i];
                    const localX = pointerX - rect.left;
                    const localY = pointerY - rect.top;

                    if (!state.seeded) {
                        state.x = localX;
                        state.y = localY;
                        state.seeded = true;
                    }

                    state.x += (localX - state.x) * 0.12;
                    state.y += (localY - state.y) * 0.12;
                    glow.style.setProperty('--glow-x', state.x.toFixed(1) + 'px');
                    glow.style.setProperty('--glow-y', state.y.toFixed(1) + 'px');
                });
            }
        }

        rafId = requestAnimationFrame(frame);
    }

    rafId = requestAnimationFrame(frame);
})();
