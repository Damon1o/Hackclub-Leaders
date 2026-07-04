(function () {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Fade the copy in, then drop the stickers in one by one
    if (!reduceMotion) {
        const copy = document.querySelector('.sign-in-copy');
        if (copy) {
            copy.style.opacity = '0';
            copy.style.transform = 'translateY(16px)';
            copy.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    copy.style.opacity = '1';
                    copy.style.transform = 'translateY(0)';
                });
            });
        }

        document.querySelectorAll('.pile-sticker').forEach(function (el, i) {
            el.style.opacity = '0';
            el.style.scale = '0.7';
            el.style.transition = 'opacity 0.35s ease, scale 0.35s cubic-bezier(0.34, 1.56, 0.64, 1)';
            setTimeout(function () {
                el.style.opacity = '1';
                el.style.scale = '1';
            }, 250 + i * 110);
        });
    }

    document.querySelectorAll('.sign-in-flash').forEach(function (el) {
        setTimeout(function () {
            el.style.transition = 'opacity 0.4s ease, max-height 0.4s ease';
            el.style.opacity = '0';
            el.style.maxHeight = '0';
            el.style.overflow = 'hidden';
            el.style.marginBottom = '0';
            el.style.padding = '0';
        }, 5000);
    });
})();
