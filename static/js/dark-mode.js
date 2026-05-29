document.addEventListener('DOMContentLoaded', () => {
    const modeSwitch = document.getElementById('toggleBtn');
    // Initialize mode from localStorage
    const savedMode = localStorage.getItem('mode');
    const isDark = savedMode === 'dark';
    document.body.classList.toggle('dark-mode', isDark);
    modeSwitch.classList.toggle('active', isDark);
    // Toggle on click
    modeSwitch.addEventListener('click', () => {
        const nowDark = document.body.classList.toggle('dark-mode');
        modeSwitch.classList.toggle('active', nowDark);
        localStorage.setItem('mode', nowDark ? 'dark' : 'light');
    });
});
