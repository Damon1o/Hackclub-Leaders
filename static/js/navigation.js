window.addEventListener('scroll', function () {
    const navbar = document.querySelector('.navigation-bar');
    if (!navbar) return;

    if (window.scrollY > 50) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }
});

// The Tools link is both a hover target and a real toggle for touch and
// keyboard users. Keep the placeholder link from jumping the page to the top.
document.querySelectorAll('.dropdown > a[href="#"]').forEach(link => {
    const dropdown = link.closest('.dropdown');
    const menu = dropdown?.querySelector('.dropdown-menu');
    if (!dropdown || !menu) return;

    link.setAttribute('aria-haspopup', 'true');
    link.setAttribute('aria-expanded', 'false');

    const setOpen = (open) => {
        dropdown.classList.toggle('is-open', open);
        link.setAttribute('aria-expanded', String(open));
    };

    link.addEventListener('click', event => {
        event.preventDefault();
        setOpen(!dropdown.classList.contains('is-open'));
    });

    dropdown.addEventListener('focusout', event => {
        if (!dropdown.contains(event.relatedTarget)) setOpen(false);
    });

    dropdown.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            setOpen(false);
            link.focus();
        }
    });

    document.addEventListener('click', event => {
        if (!dropdown.contains(event.target)) setOpen(false);
    });
});
