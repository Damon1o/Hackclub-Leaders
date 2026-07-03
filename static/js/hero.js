(function () {
    const VIDEO_ID = 'vvdoW2gh9YU';
    const EMBED_SRC = `https://www.youtube.com/embed/${VIDEO_ID}?autoplay=1&rel=0`;

    const modal = document.getElementById('videoModal');
    const iframe = document.getElementById('videoIframe');
    const closeBtn = document.getElementById('videoClose');
    const preview = document.getElementById('heroVideoPreview');

    function openModal() {
        iframe.src = EMBED_SRC;
        modal.classList.add('is-open');
        requestAnimationFrame(() => {
            requestAnimationFrame(() => modal.classList.add('is-visible'));
        });
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        modal.classList.remove('is-visible');
        modal.addEventListener('transitionend', function handler() {
            modal.classList.remove('is-open');
            iframe.src = '';
            document.body.style.overflow = '';
            modal.removeEventListener('transitionend', handler);
        });
    }

    preview.addEventListener('click', openModal);
    preview.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') openModal(); });

    closeBtn.addEventListener('click', e => {
        e.stopPropagation();
        closeModal();
    });

    modal.addEventListener('click', e => {
        if (!e.target.closest('.video-inner-container')) closeModal();
    });

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && modal.classList.contains('is-open')) closeModal();
    });
})();

// Email "Join!" CTAs — hand the visitor to the sign-in page to continue with
// Hack Club Auth. The email just personalizes the hand-off.
(function () {
    function wireJoin(inputSelector, buttonSelector) {
        const input = document.querySelector(inputSelector);
        const button = document.querySelector(buttonSelector);
        if (!input || !button) return;

        function join() {
            const email = input.value.trim();
            if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                input.setCustomValidity('Enter a valid email like orpheus@hackclub.com');
                input.reportValidity();
                return;
            }
            input.setCustomValidity('');
            const query = email ? `?email=${encodeURIComponent(email)}` : '';
            window.location.href = `/sign-in${query}`;
        }

        button.addEventListener('click', event => {
            event.preventDefault();
            join();
        });
        input.addEventListener('keydown', event => {
            if (event.key === 'Enter') {
                event.preventDefault();
                join();
            }
        });
        input.addEventListener('input', () => input.setCustomValidity(''));
    }

    wireJoin('.sign-up-input', '.sign-up-button');
    wireJoin('#ready-email-input', '.final-cta-join-button');
})();