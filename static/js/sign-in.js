// sign-in.js
// Handles any client-side sign-in page interactions.
// The actual OAuth flow is handled server-side in app.py.

(function () {
    // Animate the card in on load
    const card = document.querySelector('.sign-in-card');
    if (card) {
        card.style.opacity = '0';
        card.style.transform = 'translateY(16px)';
        card.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            });
        });
    }

    // Auto-dismiss flash messages after 5 seconds
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