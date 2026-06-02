const toggle = document.getElementById('sidenavToggle');
const sidenav = document.getElementById('sidenav');
const main = document.getElementById('dashboardMain');

toggle?.addEventListener('click', () => {
    sidenav.classList.toggle('sidenav--open');
});

document.addEventListener('click', (e) => {
    if (window.innerWidth <= 768 &&
        !sidenav.contains(e.target) &&
        !toggle.contains(e.target)) {
        sidenav.classList.remove('sidenav--open');
    }
});