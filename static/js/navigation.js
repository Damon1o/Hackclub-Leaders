window.addEventListener('scroll', function () {
    const navbar = document.querySelector('.navigation-bar');

    if (window.scrollY > 50) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }
});

// The dropdown parent link only exists to anchor the hover menu — stop the
// default "#" navigation from jumping the page to the top.
document.querySelectorAll('.dropdown > a[href="#"]').forEach(link => {
    link.addEventListener('click', event => event.preventDefault());
});