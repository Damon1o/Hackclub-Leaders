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
        // tiny delay lets display:flex render before opacity transition kicks in
        requestAnimationFrame(() => {
            requestAnimationFrame(() => modal.classList.add('is-visible'));
        });
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        modal.classList.remove('is-visible');
        modal.addEventListener('transitionend', function handler() {
            modal.classList.remove('is-open');
            iframe.src = '';           // stop video playback
            document.body.style.overflow = '';
            modal.removeEventListener('transitionend', handler);
        });
    }

    preview.addEventListener('click', openModal);
    preview.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') openModal(); });

    closeBtn.addEventListener('click', e => {
        e.stopPropagation();   // don't bubble to overlay
        closeModal();
    });

    // clicking the dark overlay (outside the iframe container) also closes
    modal.addEventListener('click', e => {
        if (!e.target.closest('.video-inner-container')) closeModal();
    });

    // Escape key closes
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && modal.classList.contains('is-open')) closeModal();
    });
})();