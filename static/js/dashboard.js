(function () {
    const stateNode = document.getElementById('dashboard-state');
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const pageNode = document.querySelector('[data-dashboard-page]');
    const page = pageNode?.dataset.dashboardPage || '';
    // Server-rendered role: 'Leader' | 'Mentor' | 'Member'. The API enforces
    // this independently — hiding controls here is purely cosmetic.
    const viewerRole = document.body.dataset.viewerRole || 'Leader';
    const isLeader = viewerRole !== 'Member';
    const viewerEmail = (document.body.dataset.viewerEmail || '').trim().toLowerCase();

    let dashboardState = {};
    let selectedNewsletterId = '';
    let shopFilter = 'All';

    try {
        dashboardState = JSON.parse(stateNode?.textContent || '{}') || {};
    } catch (error) {
        dashboardState = {};
    }

    // Client-rendered pages ship an empty shell (fast) and hydrate from the
    // cache + a background fetch. Server-rendered pages embed their full state.
    const hadEmbeddedData = dashboardState && Object.keys(dashboardState).length > 0;

    const $ = (selector, root = document) => root.querySelector(selector);
    const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

    function members() {
        return dashboardState.members || [];
    }

    function events() {
        return dashboardState.events || [];
    }

    function shopItems() {
        return dashboardState.shopItems || [];
    }

    function cart() {
        return dashboardState.cart || [];
    }

    function itemRequests() {
        return dashboardState.itemRequests || [];
    }

    function orders() {
        return dashboardState.orders || [];
    }

    function workshops() {
        return dashboardState.workshops || [];
    }

    function newsletters() {
        return dashboardState.newsletters || [];
    }

    function projects() {
        return dashboardState.projects || [];
    }

    // A "ship" is a project an admin approved (status "Shipped"); only these
    // count toward the club level.
    function shippedProjects() {
        return projects().filter((project) => project.status === 'Shipped');
    }

    // Club levels mirror levels.md: 4 ships → Level 2, 8 → Level 3, and ships
    // must come from 4+ different members (including the leader) to advance.
    const LEVEL_THRESHOLDS = [0, 4, 8];
    const SHIPPERS_REQUIRED = 4;

    function shipperCount() {
        const unique = new Set();
        shippedProjects().forEach((project) => {
            const key = String(project.ownerEmail || project.ownerName || '').trim().toLowerCase();
            if (key) unique.add(key);
        });
        return unique.size;
    }

    function clubLevel() {
        const count = shippedProjects().length;
        const shippers = shipperCount();
        if (shippers >= SHIPPERS_REQUIRED && count >= LEVEL_THRESHOLDS[2]) return 3;
        if (shippers >= SHIPPERS_REQUIRED && count >= LEVEL_THRESHOLDS[1]) return 2;
        return 1;
    }

    function levelProgress() {
        const count = shippedProjects().length;
        const shippers = shipperCount();
        const level = clubLevel();
        if (level === 3) {
            return { level, count, shippers, next: null, remaining: 0, remainingShippers: 0, percent: 100 };
        }
        const floor = LEVEL_THRESHOLDS[level - 1];
        const ceiling = LEVEL_THRESHOLDS[level];
        const remaining = Math.max(0, ceiling - count);
        // The distinct-member requirement only gates Level 2 — once 4 members
        // have shipped, Level 3 is purely about total ships.
        const remainingShippers = level === 1 ? Math.max(0, SHIPPERS_REQUIRED - shippers) : 0;
        const shipFraction = Math.min(1, (count - floor) / (ceiling - floor));
        const shipperFraction = level === 1 ? Math.min(1, shippers / SHIPPERS_REQUIRED) : 1;
        return {
            level,
            count,
            shippers,
            next: level + 1,
            remaining,
            remainingShippers,
            percent: Math.round(Math.min(shipFraction, shipperFraction) * 100),
        };
    }

    function levelRequirementText(progress) {
        const parts = [];
        if (progress.remaining > 0) {
            parts.push(`${progress.remaining} more ${progress.remaining === 1 ? 'ship' : 'ships'}`);
        }
        if (progress.remainingShippers > 0) {
            parts.push(`${progress.remainingShippers} more ${progress.remainingShippers === 1 ? 'member' : 'members'} shipping`);
        }
        return parts.join(' and ');
    }

    function settings() {
        dashboardState.settings = dashboardState.settings || {};
        return dashboardState.settings;
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    const COIN_ICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14" class="coin-icon" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 6.5v11"/><path d="M15 9a3 3 0 0 0-3-1h-.5a2 2 0 0 0 0 4h1a2 2 0 0 1 0 4H12a3 3 0 0 1-3-1"/></svg>';

    function coinLabel(cost) {
        if (cost === null || cost === undefined) return 'TBD';
        return `${COIN_ICON_SVG}<span>${Number(cost)}</span>`;
    }

    function initials(name) {
        return String(name || 'User')
            .trim()
            .split(/\s+/)
            .slice(0, 2)
            .map((part) => part[0]?.toUpperCase() || '')
            .join('') || 'U';
    }

    function formatDate(value) {
        if (!value) return 'Date TBD';
        const date = new Date(`${value}T12:00:00`);
        if (Number.isNaN(date.getTime())) return value;
        return new Intl.DateTimeFormat(undefined, {
            month: 'long',
            day: 'numeric',
            year: 'numeric',
        }).format(date);
    }

    function formatTime(value) {
        if (!value) return '';
        const date = new Date(`1970-01-01T${value}`);
        if (Number.isNaN(date.getTime())) return value;
        return new Intl.DateTimeFormat(undefined, {
            hour: 'numeric',
            minute: '2-digit',
        }).format(date);
    }

    // Stale-while-revalidate cache: the page shell no longer waits on the full
    // data load, so we paint instantly from the last-known state in
    // localStorage, then refresh from the network.
    const CACHE_KEY = 'hcl:state:' + (viewerEmail || 'anon');

    function cacheState(state) {
        try {
            localStorage.setItem(CACHE_KEY, JSON.stringify(state));
        } catch (error) {
            /* storage full or unavailable — non-fatal */
        }
    }

    function readCachedState() {
        try {
            return JSON.parse(localStorage.getItem(CACHE_KEY) || 'null');
        } catch (error) {
            return null;
        }
    }

    // Which state sections each page actually renders. Mirrors PAGE_SECTIONS in
    // src/helpers.py — the server drops everything else, so a page fetches only
    // what it paints. Pages missing from this map get the full state.
    const PAGE_SECTIONS = {
        dashboard: ['events', 'projects', 'newsletters', 'workshops'],
        team: [],
        events: ['events'],
        ships: ['projects'],
        projects: ['projects'],
        levels: ['projects'],
        tools: [],
        shop: ['orders', 'itemRequests'],
        workshops: ['workshops'],
        chat: ['channels', 'messages'],
        notifications: ['newsletters', 'notifications'],
        map: [],
        settings: [],
        profile: ['projects'],
    };

    function pageSections() {
        const sections = PAGE_SECTIONS[page];
        // `members` rides along everywhere: avatars and role checks need it.
        return sections ? ['members'].concat(sections) : null;
    }

    function setState(nextState) {
        if (nextState) {
            // A section-scoped response only carries the keys it was asked for,
            // so merge rather than replace — otherwise a partial refresh would
            // blank out sections this page happens not to render.
            dashboardState = Object.assign({}, dashboardState, nextState);
        }
        cacheState(dashboardState);
        renderPage();
        initAvatarUploads();
        // New state can carry new notifications — keep the bell honest.
        loadNotifications();
    }

    async function refreshState() {
        // Pull the authoritative state in the background; apiRequest calls
        // setState (which caches + re-renders) when the payload carries state.
        const sections = pageSections();
        const query = sections ? `?sections=${encodeURIComponent(sections.join(','))}` : '';
        try {
            await apiRequest(`/api/dashboard/state${query}`);
        } catch (error) {
            /* keep showing cached data if the refresh fails */
        }
    }

    async function apiRequest(path, options = {}) {
        const method = options.method || 'GET';
        const headers = { Accept: 'application/json' };
        if (method !== 'GET') {
            headers['Content-Type'] = 'application/json';
            headers['X-CSRF-Token'] = csrfToken;
        }

        const response = await fetch(path, {
            method,
            headers,
            credentials: 'same-origin',
            body: options.body ? JSON.stringify(options.body) : undefined,
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            const error = new Error(payload.error || 'Request failed.');
            error.status = response.status;
            if (payload.retryAfter != null) error.retryAfter = payload.retryAfter;
            throw error;
        }
        if (payload.state) {
            setState(payload.state);
        }
        return payload;
    }

    function showToast(message, tone = 'success') {
        const region = $('#toastRegion');
        if (!region) return;
        const toast = document.createElement('div');
        toast.className = `toast toast-${tone}`;
        toast.textContent = message;
        toast.setAttribute('role', 'alert');
        region.appendChild(toast);
        window.setTimeout(() => {
            toast.classList.add('toast-leaving');
            window.setTimeout(() => toast.remove(), 220);
        }, 2600);
    }

    function setFormError(id, message) {
        const node = document.getElementById(id);
        if (!node) return;
        node.textContent = message || '';
        node.hidden = !message;
    }

    function openModal(id) {
        const modal = document.getElementById(id);
        if (!modal) return;
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
        const firstInput = $('input, select, textarea, button', modal);
        firstInput?.focus();
    }

    function closeModal(target) {
        const modal = typeof target === 'string'
            ? document.getElementById(target)
            : target?.closest('.modal-backdrop');
        if (!modal) return;
        modal.classList.remove('is-open');
        modal.setAttribute('aria-hidden', 'true');
    }

    function roleClass(role) {
        if (role === 'Leader') return 'badge-leader';
        if (role === 'Mentor') return 'badge-mentor';
        return 'badge-member';
    }

    function avatarMarkup(person, className = 'avatar-lg') {
        const name = escapeHtml(person.name || settings().clubName || 'User');
        if (person.avatar) {
            // Rosters can run long; only the avatars actually scrolled into
            // view are worth a request.
            return `<img src="${escapeHtml(person.avatar)}" class="${className}" alt="${name}" loading="lazy" decoding="async">`;
        }
        return `<div class="${className} avatar-fallback">${escapeHtml(initials(person.name))}</div>`;
    }

    function shopItem(itemId) {
        return shopItems().find((item) => item.id === itemId);
    }

    function prepareNewMember() {
        const form = $('#memberForm');
        if (!form) return;
        form.reset();
        form.elements.id.value = '';
        form.elements.role.value = 'Member';
        form.elements.status.value = 'Invited';
        $('#memberModalTitle').textContent = 'Invite member';
        $('#memberStatusGroup').hidden = true;
        $('#deleteMemberButton').hidden = true;
        setFormError('memberFormError', '');
    }

    function prepareEditMember(id) {
        const member = members().find((item) => item.id === id);
        const form = $('#memberForm');
        if (!member || !form) return;
        form.elements.id.value = member.id;
        form.elements.name.value = member.name || '';
        form.elements.email.value = member.email || '';
        form.elements.role.value = member.role || 'Member';
        form.elements.avatar.value = member.avatar || '';
        form.elements.status.value = member.status || 'Active';
        $('#memberModalTitle').textContent = 'Edit member';
        $('#memberStatusGroup').hidden = false;
        $('#deleteMemberButton').hidden = false;
        setFormError('memberFormError', '');
        openModal('memberModal');
    }

    function removeSkeletons(pageName) {
        const sk = document.querySelector(`[data-skeleton="${pageName}"]`);
        if (sk) sk.classList.add('skeleton-hidden');
    }

    function renderTeam() {
        if (page !== 'team') return;
        removeSkeletons('team');
        const roster = $('#teamRoster');
        const empty = $('#teamEmpty');
        const people = members();
        const leaders = people.filter((member) => member.role === 'Leader').length;
        const invites = people.filter((member) => member.status === 'Invited').length;

        $('#memberTotal').textContent = people.length;
        $('#leaderTotal').textContent = leaders;
        $('#inviteTotal').textContent = invites;
        $('#memberCountLabel').textContent = `${people.length} ${people.length === 1 ? 'person' : 'people'}`;

        if (!roster) return;
        roster.innerHTML = people.map((member, index) => `
            <article class="item-card member-card" style="--card-index: ${index}">
                <div class="member-card-top">
                    ${avatarMarkup(member)}
                    <span class="badge-role ${roleClass(member.role)}">${escapeHtml(member.role)}</span>
                </div>
                <h3>${escapeHtml(member.name)}</h3>
                <p>${escapeHtml(member.email)}</p>
                <div class="card-footer-line">
                    <span class="status-chip">${escapeHtml(member.status || 'Active')}</span>
                    ${isLeader ? `<button class="text-button" type="button" data-edit-member="${escapeHtml(member.id)}">Edit</button>` : ''}
                </div>
            </article>
        `).join('');
        if (empty) empty.hidden = people.length > 0;
    }

    function prepareNewEvent() {
        const form = $('#eventForm');
        if (!form) return;
        form.reset();
        form.elements.id.value = '';
        form.elements.type.value = 'Workshop';
        form.elements.attendees.value = '12';
        form.elements.repeat.value = '';
        form.elements.rsvp.checked = false;
        $('#eventModalTitle').textContent = 'New event';
        $('#deleteEventButton').hidden = true;
        setFormError('eventFormError', '');
    }

    function prepareEditEvent(id) {
        const event = events().find((item) => item.id === id);
        const form = $('#eventForm');
        if (!event || !form) return;
        form.elements.id.value = event.id;
        form.elements.title.value = event.title || '';
        form.elements.date.value = event.date || '';
        form.elements.time.value = event.time || '';
        form.elements.location.value = event.location || '';
        form.elements.type.value = event.type || '';
        form.elements.attendees.value = event.attendees || 0;
        form.elements.repeat.value = event.repeat || '';
        form.elements.rsvp.checked = Boolean(event.rsvp);
        $('#eventModalTitle').textContent = 'Edit event';
        $('#deleteEventButton').hidden = false;
        setFormError('eventFormError', '');
        openModal('eventModal');
    }

    function prepareNewWorkshop() {
        const form = $('#workshopProposeForm');
        if (!form) return;
        form.reset();
        setFormError('workshopProposeFormError', '');
    }

    const REPEAT_LABELS = {
        daily: 'Daily',
        weekdays: 'Weekdays',
        weekly: 'Weekly',
        biweekly: 'Every 2 weeks',
        monthly: 'Monthly',
    };

    function isoDate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    // Roll a repeating event forward to its first occurrence on/after `today`, so
    // a weekly meeting always shows its next date instead of drifting into the
    // past. Non-repeating (or future) events keep their stored date.
    function nextOccurrenceISO(event, today) {
        if (!event.date) return '';
        const date = new Date(event.date + 'T00:00:00');
        if (Number.isNaN(date.getTime())) return event.date;
        const repeat = REPEAT_LABELS[event.repeat] ? event.repeat : '';
        if (!repeat || date >= today) return isoDate(date);
        let guard = 0;
        while (date < today && guard < 1000) {
            guard += 1;
            if (repeat === 'daily') date.setDate(date.getDate() + 1);
            else if (repeat === 'weekly') date.setDate(date.getDate() + 7);
            else if (repeat === 'biweekly') date.setDate(date.getDate() + 14);
            else if (repeat === 'monthly') date.setMonth(date.getMonth() + 1);
            else if (repeat === 'weekdays') {
                do { date.setDate(date.getDate() + 1); }
                while (date.getDay() === 0 || date.getDay() === 6);
            }
        }
        return isoDate(date);
    }

    function renderEvents() {
        if (page !== 'events') return;
        removeSkeletons('events');
        const list = $('#eventList');
        const empty = $('#eventsEmpty');
        const upcoming = events();
        const rsvps = upcoming.filter((event) => event.rsvp).length;
        const attendees = upcoming.reduce((total, event) => total + Number(event.attendees || 0), 0);

        $('#eventTotal').textContent = upcoming.length;
        $('#rsvpTotal').textContent = rsvps;
        $('#attendeeTotal').textContent = attendees;

        const today = new Date();
        today.setHours(0, 0, 0, 0);
        function eventStatusClass(dateStr) {
            if (!dateStr) return 'is-upcoming';
            const eventDate = new Date(dateStr + 'T00:00:00');
            eventDate.setHours(0, 0, 0, 0);
            const diff = Math.round((eventDate - today) / 86400000);
            if (diff < 0) return 'is-past';
            if (diff === 0) return 'is-today';
            if (diff <= 7) return 'is-soon';
            return 'is-upcoming';
        }
        if (!list) return;

        // Sort by the *effective* (next-occurrence) date so a rolled-forward
        // repeating event lands in its true position on the timeline.
        const ordered = upcoming
            .map((event) => ({ event, effDate: nextOccurrenceISO(event, today) }))
            .sort((a, b) => (a.effDate + (a.event.time || '')).localeCompare(b.effDate + (b.event.time || '')));

        list.innerHTML = ordered.map(({ event, effDate }, index) => {
            const statusClass = eventStatusClass(effDate);
            const repeatBadge = REPEAT_LABELS[event.repeat]
                ? `<span class="badge badge-repeat">↻ ${escapeHtml(REPEAT_LABELS[event.repeat])}</span>`
                : '';
            const badge = index === 0
                ? `<span class="badge badge-up">Next up</span>`
                : (statusClass === 'is-today' ? `<span class="badge badge-pending">Today</span>` : '');
            return `
            <article class="timeline-item ${event.rsvp ? 'is-rsvped' : ''} ${statusClass}" style="--card-index: ${index}">
                <div class="timeline-date">
                    <strong>${escapeHtml(formatDate(effDate).split(',')[0])}</strong>
                    <span>${escapeHtml(formatTime(event.time))}</span>
                </div>
                <div class="timeline-body">
                    <div>
                        <h3>${escapeHtml(event.title)}</h3>
                        <p>${escapeHtml(event.location)} · ${escapeHtml(event.type || 'Event')} · ${Number(event.attendees || 0)} expected</p>
                    </div>
                    <div class="timeline-actions">
                        ${repeatBadge}
                        ${badge}
                        <button class="btn-secondary small" type="button" data-toggle-rsvp="${escapeHtml(event.id)}">${event.rsvp ? 'RSVPed' : 'RSVP'}</button>
                        ${isLeader ? `<button class="text-button" type="button" data-edit-event="${escapeHtml(event.id)}">Edit</button>` : ''}
                    </div>
                </div>
            </article>
            `;
        }).join('');
        if (empty) empty.hidden = upcoming.length > 0;
    }

    function renderShips() {
        if (page !== 'ships') return;
        removeSkeletons('ships');
        const list = $('#shipList');
        const empty = $('#shipsEmpty');
        const progress = levelProgress();
        const shipped = shippedProjects();

        // Ships are admin-approved projects; the level credits every one of them.
        $('#shipTotal').textContent = shipped.length;
        $('#shipLevel').textContent = progress.level;
        $('#shipToNext').textContent = `${progress.shippers} / ${SHIPPERS_REQUIRED}`;

        if (!list) return;
        list.innerHTML = shipped.map((project, index) => `
            <article class="timeline-item ship-item" style="--card-index: ${index}">
                <div class="timeline-date">
                    <strong>${escapeHtml(formatDate(project.date).split(',')[0])}</strong>
                    <span>${escapeHtml(project.ownerName || project.ownerEmail || '')}</span>
                </div>
                <div class="timeline-body">
                    <div>
                        <h3>${escapeHtml(project.name)}</h3>
                        ${project.description ? `<p class="project-desc">${escapeHtml(project.description)}</p>` : ''}
                        ${projectLinks(project)}
                    </div>
                    <div class="timeline-actions">
                        <span class="badge badge-up">Shipped</span>
                    </div>
                </div>
            </article>
        `).join('');
        if (empty) empty.hidden = shipped.length > 0;
    }

    async function initHacktime() {
        if (page !== 'projects') return;
        const card = $('#hacktimeCard');
        const body = $('#hacktimeBody');
        const pageNode = document.querySelector('[data-hackatime-id]');
        const hasId = Boolean((pageNode?.dataset.hackatimeId || '').trim());
        if (!card || !body) return;

        if (!hasId) {
            card.hidden = false;
            body.innerHTML = `<p class="hacktime-empty">Add your Hackatime user ID on your
                <a class="text-button" href="/dashboard/profile">profile</a> to show your coding time here.</p>`;
            return;
        }

        card.hidden = false;
        try {
            const stats = await apiRequest('/api/dashboard/hackatime');
            const langs = (stats.languages || [])
                .filter((l) => l.name)
                .map((l) => `<span class="hacktime-lang">${escapeHtml(l.name)} · ${escapeHtml(l.text || '')}</span>`)
                .join('');
            body.innerHTML = `
                <div class="hacktime-stats">
                    <div class="hacktime-total">
                        <strong>${escapeHtml(stats.humanReadableTotal || '0m')}</strong>
                        <span>total on HackTime</span>
                    </div>
                    ${stats.humanReadableDailyAverage ? `<div class="hacktime-avg">
                        <strong>${escapeHtml(stats.humanReadableDailyAverage)}</strong>
                        <span>daily average</span>
                    </div>` : ''}
                </div>
                ${langs ? `<div class="hacktime-langs">${langs}</div>` : ''}`;
        } catch (error) {
            body.innerHTML = `<p class="hacktime-empty">${escapeHtml(error.message)}</p>`;
        }
    }

    // A project may only be submitted for review once all four are set.
    const PROJECT_REQUIREMENTS = ['repoUrl', 'demoUrl', 'hackatimeProject'];
    // Cached per session so reopening the modal doesn't refetch. `null` = not
    // loaded yet, `[]` = loaded and empty, array = loaded projects.
    let hacktimeProjectsCache = null;

    function updateThumbPreview(value) {
        const url = String(value || '').trim();
        const img = $('#projectThumbPreview');
        if (img) {
            if (url) {
                img.src = url;
                img.hidden = false;
            } else {
                img.removeAttribute('src');
                img.hidden = true;
            }
        }
        const cta = $('#projectThumbUpload .image-upload-cta');
        if (cta) cta.textContent = url ? 'Change image…' : 'Choose image…';
    }

    const ALLOWED_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif'];

    // Send the picked file to the server, which stores it in Vercel Blob and
    // returns a public URL we drop into the hidden `thumbnail` field.
    async function uploadProjectImage(file) {
        const body = new FormData();
        body.append('image', file);
        // No Content-Type header — the browser sets the multipart boundary.
        const response = await fetch('/api/dashboard/projects/upload-image', {
            method: 'POST',
            headers: { Accept: 'application/json', 'X-CSRF-Token': csrfToken },
            credentials: 'same-origin',
            body,
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.error || 'Upload failed.');
        return payload.url;
    }

    async function handleThumbFileChange(event) {
        const input = event.target;
        const file = input.files && input.files[0];
        if (!file) return;
        setFormError('projectThumbError', '');
        if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
            setFormError('projectThumbError', 'Only PNG, JPEG, WebP, or GIF images are allowed.');
            input.value = '';
            return;
        }
        if (file.size > 4 * 1024 * 1024) {
            setFormError('projectThumbError', 'Image must be 4 MB or smaller.');
            input.value = '';
            return;
        }
        const cta = $('#projectThumbUpload .image-upload-cta');
        if (cta) cta.textContent = 'Uploading…';
        const form = $('#projectForm');
        try {
            const url = await uploadProjectImage(file);
            if (form) form.elements.thumbnail.value = url;
            updateThumbPreview(url);
            refreshProjectRequirements();
        } catch (error) {
            setFormError('projectThumbError', error.message);
            updateThumbPreview(form ? form.elements.thumbnail.value : '');
        } finally {
            input.value = '';  // let the same file be re-selected after an error
        }
    }

    function initAvatarUploads() {
        $$('input[name="avatar"]').forEach(function (input) {
            const formGroup = input.closest('.form-group');
            if (!formGroup) return;
            if (formGroup.querySelector('.avatar-upload-btn')) return;

            const row = document.createElement('div');
            row.className = 'avatar-upload-row';

            const fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.accept = 'image/png,image/jpeg,image/webp,image/gif';
            fileInput.hidden = true;

            const uploadBtn = document.createElement('button');
            uploadBtn.type = 'button';
            uploadBtn.className = 'btn-secondary small avatar-upload-btn';
            uploadBtn.textContent = 'Upload photo';

            const statusText = document.createElement('span');
            statusText.className = 'avatar-upload-status';

            uploadBtn.addEventListener('click', function () { fileInput.click(); });

            fileInput.addEventListener('change', async function () {
                const file = fileInput.files && fileInput.files[0];
                if (!file) return;
                if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
                    statusText.textContent = 'Only PNG, JPEG, WebP, or GIF.';
                    fileInput.value = '';
                    return;
                }
                if (file.size > 4 * 1024 * 1024) {
                    statusText.textContent = 'Max 4 MB.';
                    fileInput.value = '';
                    return;
                }
                uploadBtn.disabled = true;
                statusText.textContent = 'Uploading...';
                try {
                    const body = new FormData();
                    body.append('image', file);
                    const response = await fetch('/api/dashboard/upload-image', {
                        method: 'POST',
                        headers: { Accept: 'application/json', 'X-CSRF-Token': csrfToken },
                        credentials: 'same-origin',
                        body,
                    });
                    const payload = await response.json().catch(() => ({}));
                    if (!response.ok) throw new Error(payload.error || 'Upload failed.');
                    input.value = payload.url;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    statusText.textContent = 'Uploaded.';
                    updateNearbyAvatarPreview(input);
                } catch (error) {
                    statusText.textContent = error.message;
                } finally {
                    uploadBtn.disabled = false;
                    fileInput.value = '';
                }
            });

            row.appendChild(uploadBtn);
            row.appendChild(fileInput);
            row.appendChild(statusText);
            formGroup.appendChild(row);
        });
    }

    function updateNearbyAvatarPreview(input) {
        const url = String(input.value || '').trim();
        const page = document.querySelector('[data-dashboard-page]')?.dataset.dashboardPage;
        const img =
            $('#profilePreviewAvatar') ||
            $('#clubPreviewAvatar') ||
            document.querySelector('.club-preview-avatar');
        if (!img) return;
        img.textContent = url ? '' : 'H';
        const safeUrl = url.replace(/\\/g, '%5C').replace(/"/g, '%22');
        img.style.backgroundImage = safeUrl ? `url("${safeUrl}")` : '';
        img.classList.toggle('has-image', Boolean(url));
    }

    function renderHacktimePicker(list, selected) {
        const picker = $('#hackatimePicker');
        if (!picker) return;
        const selectedName = String(selected || '');
        const projectsList = list || [];
        let html = projectsList.map((proj) => {
            const name = String(proj.name || '');
            const hours = Number(proj.hours || 0);
            const label = hours ? `${name} (${hours}h)` : name;
            return `<button class="hacktime-pill ${name === selectedName ? 'is-selected' : ''}" type="button"
                data-hacktime-name="${escapeHtml(name)}">${escapeHtml(label)}</button>`;
        }).join('');
        // Keep a previously-linked project visible even if it's not in the
        // fetched list (e.g. no longer tracked), so editing doesn't drop it.
        if (selectedName && !projectsList.some((p) => String(p.name || '') === selectedName)) {
            html += `<button class="hacktime-pill is-selected" type="button"
                data-hacktime-name="${escapeHtml(selectedName)}">${escapeHtml(selectedName)}</button>`;
        }
        picker.innerHTML = html
            || '<p class="hacktime-picker-empty">No Hackatime projects yet. Log some coding time, then come back.</p>';
    }

    async function loadHacktimeProjects() {
        const picker = $('#hackatimePicker');
        const form = $('#projectForm');
        if (!picker || !form) return;
        const selected = form.elements.hackatimeProject?.value || '';
        if (hacktimeProjectsCache) {
            renderHacktimePicker(hacktimeProjectsCache, selected);
            return;
        }
        picker.innerHTML = '<p class="hacktime-picker-loading">Loading your Hackatime projects…</p>';
        try {
            const data = await apiRequest('/api/dashboard/hackatime/projects');
            hacktimeProjectsCache = data.projects || [];
            // Re-read the selection in case the form changed while awaiting.
            renderHacktimePicker(hacktimeProjectsCache, form.elements.hackatimeProject?.value || '');
        } catch (error) {
            // No Hackatime ID (400) or a transient failure — let them still
            // save a draft; the hidden input keeps any existing selection.
            picker.innerHTML = `<p class="hacktime-picker-empty">Add your Hackatime ID on your
                <a class="text-button" href="/dashboard/profile">profile</a> to link a project.
                You can still save a draft.</p>`;
        }
    }

    // Toggles the live checklist and the Submit-for-Review button. Submit is
    // enabled once all four requirements are set; the handler saves the draft
    // (POSTing a brand-new project) before flipping status, so new projects
    // don't need to be saved separately first.
    function refreshProjectRequirements() {
        const form = $('#projectForm');
        if (!form) return;
        const values = {
            repoUrl: (form.elements.repoUrl?.value || '').trim(),
            demoUrl: (form.elements.demoUrl?.value || '').trim(),
            thumbnail: (form.elements.thumbnail?.value || '').trim(),
            hackatimeProject: (form.elements.hackatimeProject?.value || '').trim(),
        };
        let allMet = true;
        $$('.req-item', form).forEach((item) => {
            const met = Boolean(values[item.dataset.req]);
            item.classList.toggle('is-met', met);
            if (!met) allMet = false;
        });
        const submitBtn = $('#projectSubmitReview');
        if (submitBtn) submitBtn.disabled = !allMet;
    }

    // Which requirement fields a project is still missing, as short labels.
    function projectMissing(project) {
        const labels = {
            repoUrl: 'repo',
            demoUrl: 'demo',
            thumbnail: 'thumbnail',
            hackatimeProject: 'Hackatime project',
        };
        return PROJECT_REQUIREMENTS
            .filter((key) => !String(project[key] || '').trim())
            .map((key) => labels[key]);
    }

    // Repo / demo links shown on a project card. Falls back to a legacy `url`
    // field for projects created before the submit-for-review fields existed.
    function projectLinks(project) {
        const links = [];
        if (project.repoUrl) {
            links.push(`<a class="text-button" href="${escapeHtml(project.repoUrl)}" target="_blank" rel="noopener noreferrer">Repo</a>`);
        }
        if (project.demoUrl) {
            links.push(`<a class="text-button" href="${escapeHtml(project.demoUrl)}" target="_blank" rel="noopener noreferrer">Demo</a>`);
        }
        if (!links.length && project.url) {
            links.push(`<a class="text-button" href="${escapeHtml(project.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(project.url)}</a>`);
        }
        return links.length ? `<div class="project-links">${links.join('')}</div>` : '';
    }

    // Persist just the project fields (shared by Save draft and Submit for
    // Review). POSTs a new project or PATCHes an existing one; returns the
    // API payload and whether it was an edit.
    async function saveProjectFields(form) {
        const data = formObject(form);
        const isEdit = Boolean(data.id);
        const response = await apiRequest(
            isEdit ? `/api/dashboard/projects/${data.id}` : '/api/dashboard/projects',
            {
                method: isEdit ? 'PATCH' : 'POST',
                body: {
                    name: data.name,
                    description: data.description,
                    repoUrl: data.repoUrl,
                    demoUrl: data.demoUrl,
                    thumbnail: data.thumbnail,
                    hackatimeProject: data.hackatimeProject,
                },
            });
        return { response, isEdit };
    }

    function projectStatusBadge(status) {
        if (status === 'Shipped') return '<span class="badge badge-up">Shipped</span>';
        if (status === 'Submitted') return '<span class="badge badge-up">Submitted</span>';
        return '<span class="badge badge-pending">Draft</span>';
    }

    function renderProjects() {
        if (page !== 'projects') return;
        removeSkeletons('projects');
        const mineList = $('#projectMineList');
        const submittedList = $('#projectSubmittedList');
        const mine = projects().filter(
            (p) => String(p.ownerEmail || '').trim().toLowerCase() === viewerEmail);
        const submitted = projects().filter((p) => p.status === 'Submitted');

        if (mineList) {
            mineList.innerHTML = mine.map((project, index) => {
                const isSubmitted = project.status === 'Submitted';
                const isShipped = project.status === 'Shipped';
                const missing = projectMissing(project);
                // Readiness only matters while a project is still a draft.
                const readiness = (isSubmitted || isShipped)
                    ? ''
                    : (missing.length === 0
                        ? '<p class="project-readiness is-ready">Ready to submit</p>'
                        : `<p class="project-readiness">Needs ${escapeHtml(missing.join(', '))}</p>`);
                let primaryAction = '';
                if (isShipped) {
                    primaryAction = '<span class="project-shipped-note"><span data-hc-icon="rocket" data-hc-size="14" data-hc-color="currentColor" aria-hidden="true"></span> Shipped — counts toward your club level and earned you coins</span>';
                } else if (isSubmitted) {
                    primaryAction = `<button class="btn-secondary small" type="button" data-project-status="Draft" data-project-id="${escapeHtml(project.id)}">Unsubmit</button>`;
                } else {
                    primaryAction = `<button class="btn-primary small" type="button" data-submit-project="${escapeHtml(project.id)}">Submit to club</button>`;
                }
                return `
                <article class="project-card" style="--card-index: ${index}">
                    <div class="project-card-head">
                        <h3>${escapeHtml(project.name)}</h3>
                        ${projectStatusBadge(project.status)}
                    </div>
                    ${project.description ? `<p class="project-desc">${escapeHtml(project.description)}</p>` : ''}
                    ${projectLinks(project)}
                    ${readiness}
                    <div class="project-card-actions">
                        ${primaryAction}
                        <button class="text-button" type="button" data-edit-project="${escapeHtml(project.id)}">Edit</button>
                        <button class="text-button" type="button" data-delete-project="${escapeHtml(project.id)}">Delete</button>
                    </div>
                </article>`;
            }).join('');
        }
        var projectsEmpty = $('#projectsEmpty');
        if (projectsEmpty) projectsEmpty.hidden = mine.length > 0;

        if (submittedList) {
            submittedList.innerHTML = submitted.map((project, index) => `
                <article class="project-card is-readonly" style="--card-index: ${index}">
                    <div class="project-card-head">
                        <h3>${escapeHtml(project.name)}</h3>
                        <span class="badge badge-up">Submitted</span>
                    </div>
                    ${project.description ? `<p class="project-desc">${escapeHtml(project.description)}</p>` : ''}
                    <p class="project-owner">by ${escapeHtml(project.ownerName || project.ownerEmail || 'Member')}</p>
                    ${projectLinks(project)}
                </article>
            `).join('');
        }
        var projectSubmittedEmpty = $('#projectSubmittedEmpty');
        if (projectSubmittedEmpty) projectSubmittedEmpty.hidden = submitted.length > 0;
    }

    function renderLevels() {
        if (page !== 'levels') return;
        removeSkeletons('levels');
        const progress = levelProgress();

        $('#levelCurrentName').textContent = `Level ${progress.level}`;
        $('#levelShipCount').textContent = `${progress.count} ${progress.count === 1 ? 'ship' : 'ships'} completed`;
        $('#levelProgressFill').style.width = `${progress.percent}%`;
        $('#levelProgressTrack')?.setAttribute('aria-valuenow', progress.percent);
        $('#levelProgressText').textContent = progress.next
            ? `${levelRequirementText(progress) || 'Almost there'} to reach Level ${progress.next}.`
            : 'Max level reached — your club is thriving!';

        $$('[data-level]').forEach((card) => {
            const level = Number(card.dataset.level);
            card.classList.toggle('is-current', level === progress.level);
            card.classList.toggle('is-past', level < progress.level);
            card.classList.toggle('is-future', level > progress.level);
            const badge = $(`[data-level-badge="${level}"]`, card);
            if (!badge) return;
            if (level === progress.level) {
                badge.textContent = 'Current';
                badge.className = 'badge level-badge badge-up';
            } else if (level < progress.level) {
                badge.textContent = 'Completed';
                badge.className = 'badge level-badge badge-past';
            } else {
                badge.textContent = `${LEVEL_THRESHOLDS[level - 1]} ships needed`;
                badge.className = 'badge level-badge badge-future';
            }
        });
    }

    function joinLink() {
        const code = settings().joinCode || 'hackclub';
        return `${window.location.origin}/join/${code}`;
    }

    function renderJoinLink() {
        const node = $('#joinLinkCode');
        if (node) node.textContent = joinLink();
    }

    function renderCoinBalance() {
        const amount = $('#coinBalanceAmount');
        if (amount) amount.textContent = Number(settings().coinBalance || 0);
    }

    // Shop filters shown in the catalog. "All" is special (shows everything);
    // the rest match a shop item's `filter` field. Each renders an image from
    // SHOP_FILTER_IMAGE_BASE + "<filter>.png".
    const SHOP_FILTERS = ['All', 'Hardware', 'Swag', 'Digital'];
    const SHOP_FILTER_IMAGE_BASE = '/static/images/shop/filters/';

    function renderShopFilters() {
        const bar = $('#shopFilters');
        if (!bar) return;
        bar.innerHTML = SHOP_FILTERS.map((filter) => {
            const active = filter === shopFilter;
            const src = `${SHOP_FILTER_IMAGE_BASE}${filter}.png`;
            return `
                <button class="shop-filter-chip${active ? ' is-active' : ''}" type="button" role="tab"
                    aria-selected="${active}" data-shop-filter="${escapeHtml(filter)}">
                    <img class="shop-filter-image" src="${escapeHtml(src)}" alt="" loading="lazy" onerror="this.remove()">
                    <span>${escapeHtml(filter)}</span>
                </button>
            `;
        }).join('');
    }

    function renderShop() {
        if (page !== 'shop') return;
        removeSkeletons('shop');
        const grid = $('#shopGrid');
        const list = $('#cartList');
        const empty = $('#cartEmpty');
        const checkoutButton = $('#checkoutButton');
        const totalQuantity = cart().reduce((total, item) => total + Number(item.quantity || 0), 0);

        $('#cartCount').textContent = totalQuantity;
        $('#cartSummary').textContent = totalQuantity
            ? `${totalQuantity} ${totalQuantity === 1 ? 'item' : 'items'} in your cart.`
            : 'No items yet.';

        renderShopFilters();

        if (grid) {
            const visibleItems = shopFilter === 'All'
                ? shopItems()
                : shopItems().filter((item) => item.filter === shopFilter);
            grid.innerHTML = visibleItems.map((item, index) => `
                <article class="item-card shop-card" style="--card-index: ${index}">
                    <div class="shop-card-media">
                        <img src="${escapeHtml(item['image-src'] || '')}" alt="${escapeHtml(item.name)}" loading="lazy" onerror="this.style.display='none'">
                    </div>
                    <h3>${escapeHtml(item.name)}</h3>
                    <div class="card-footer-line">
                        <span class="shop-price">${coinLabel(item.cost)}</span>
                        <button class="btn-secondary small" type="button" data-add-cart="${escapeHtml(item.id)}" ${item.cost == null ? 'disabled' : ''}>Add</button>
                    </div>
                </article>
            `).join('');
            const shopEmpty = $('#shopEmpty');
            if (shopEmpty) shopEmpty.hidden = visibleItems.length > 0;
        }

        if (list) {
            list.innerHTML = cart().map((entry) => {
                const item = shopItem(entry.id) || {};
                return `
                    <article class="cart-item">
                        <div>
                            <strong>${escapeHtml(item.name || entry.id)}</strong>
                            <span>${coinLabel(entry.coinCost)}</span>
                        </div>
                        <div class="quantity-control">
                            <button class="icon-button" type="button" data-cart-step="-1" data-cart-item="${escapeHtml(entry.id)}">-</button>
                            <span>${Number(entry.quantity || 0)}</span>
                            <button class="icon-button" type="button" data-cart-step="1" data-cart-item="${escapeHtml(entry.id)}">+</button>
                            <button class="text-button" type="button" data-remove-cart="${escapeHtml(entry.id)}">Remove</button>
                        </div>
                    </article>
                `;
            }).join('');
        }

        const subtotal = cart().reduce((total, entry) => total + Number(entry.coinCost || 0) * Number(entry.quantity || 0), 0);
        const subtotalNode = $('#cartSubtotal');
        const subtotalAmount = $('#cartSubtotalAmount');
        if (subtotalNode) subtotalNode.hidden = cart().length === 0;
        if (subtotalAmount) subtotalAmount.innerHTML = coinLabel(subtotal);

        if (empty) empty.hidden = cart().length > 0;
        if (checkoutButton) checkoutButton.disabled = cart().length === 0 || subtotal > Number(settings().coinBalance || 0);
        renderOrders();
        renderItemRequests();
    }

    const WORKSHOP_FILTERS = ['All', 'Proposed', 'Scheduled', 'Run'];
    let workshopFilter = 'All';
    let openWorkshopId = '';

    function renderWorkshopFilters() {
        const bar = $('#workshopFilters');
        if (!bar) return;
        bar.innerHTML = WORKSHOP_FILTERS.map((filter) => {
            const active = filter === workshopFilter;
            return `
                <button class="shop-filter-chip${active ? ' is-active' : ''}" type="button" role="tab"
                    aria-selected="${active}" data-workshop-filter="${escapeHtml(filter)}">
                    <span>${escapeHtml(filter)}</span>
                </button>
            `;
        }).join('');
    }

    function renderWorkshopDetail(workshop) {
        const titleNode = $('#workshopDetailTitle');
        if (titleNode) titleNode.textContent = workshop.title;
        const body = $('#workshopDetailBody');
        const actionsNode = $('#workshopDetailActions');
        if (!body || !actionsNode) return;

        const applied = workshop.applicants.includes(viewerEmail);
        const applicantRows = workshop.applicants.map((email) => {
            const person = members().find((m) => m.email === email);
            const name = person ? person.name : email;
            return `
                <div class="order-row">
                    <span>${escapeHtml(name)}</span>
                    ${isLeader && workshop.status === 'Proposed'
                        ? `<button class="btn-secondary small" type="button" data-schedule-workshop="${escapeHtml(workshop.id)}::${escapeHtml(email)}">Schedule</button>`
                        : ''}
                </div>
            `;
        }).join('');

        const runnerLine = workshop.runnerName
            ? `<p><strong>Run by:</strong> ${escapeHtml(workshop.runnerName)}</p>`
            : '';

        body.innerHTML = `
            <span class="status-chip">${escapeHtml(workshop.status)}</span>
            <p>${escapeHtml(workshop.description)}</p>
            <p><strong>Proposed by:</strong> ${escapeHtml(workshop.proposerName)}</p>
            ${runnerLine}
            ${isLeader ? `<h3>Applicants</h3><div class="workshop-applicant-list" style="display:grid; gap:8px;">${applicantRows || '<p>No applicants yet.</p>'}</div>` : ''}
        `;

        let actionsHtml = '';
        if (workshop.status === 'Proposed') {
            actionsHtml = applied
                ? `<button class="btn-secondary" type="button" data-withdraw-workshop="${escapeHtml(workshop.id)}">Withdraw application</button>`
                : `<button class="btn-primary" type="button" data-apply-workshop="${escapeHtml(workshop.id)}">Apply to run</button>`;
            if (isLeader) {
                actionsHtml = `<button class="text-button" type="button" data-delete-workshop="${escapeHtml(workshop.id)}">Delete proposal</button>` + actionsHtml;
            }
        } else if (workshop.status === 'Scheduled' && isLeader) {
            actionsHtml = `<button class="btn-primary" type="button" data-mark-run-workshop="${escapeHtml(workshop.id)}">Mark as run</button>`;
        }
        actionsNode.innerHTML = actionsHtml;
    }

    function renderWorkshops() {
        if (page !== 'workshops') return;
        removeSkeletons('workshops');
        const grid = $('#workshopGrid');
        const empty = $('#workshopsEmpty');
        renderWorkshopFilters();

        const all = workshops();
        const visible = workshopFilter === 'All' ? all : all.filter((w) => w.status === workshopFilter);

        if (grid) {
            grid.innerHTML = visible.map((workshop, index) => `
                <article class="item-card workshop-card" style="--card-index: ${index}" data-open-workshop="${escapeHtml(workshop.id)}">
                    <span class="status-chip">${escapeHtml(workshop.status)}</span>
                    <h3>${escapeHtml(workshop.title)}</h3>
                    <p>${escapeHtml(workshop.description)}</p>
                    <div class="card-footer-line">
                        <span>${workshop.applicants.length} applicant${workshop.applicants.length === 1 ? '' : 's'}</span>
                    </div>
                </article>
            `).join('');
        }
        if (empty) empty.hidden = visible.length > 0;

        if (openWorkshopId) {
            const current = all.find((w) => w.id === openWorkshopId);
            if (current) renderWorkshopDetail(current);
            else closeModal('workshopDetailModal');
        }
    }

    function renderItemRequests() {
        const list = $('#itemRequestList');
        if (!list) return;
        if (!itemRequests().length) {
            list.innerHTML = '';
            return;
        }
        list.innerHTML = `
            <h3>Your requests</h3>
            ${itemRequests().map((req) => `
                <div class="request-item-row">
                    <div>
                        <strong>${escapeHtml(req.name)}</strong>
                        ${req.note ? `<span>${escapeHtml(req.note)}</span>` : ''}
                    </div>
                    <div class="request-item-row-actions">
                        <span class="status-chip">${escapeHtml(req.status || 'Submitted')}</span>
                        <button class="text-button" type="button" data-remove-item-request="${escapeHtml(req.id)}">Remove</button>
                    </div>
                </div>
            `).join('')}
        `;
    }

    function renderOrders() {
        const history = $('#orderHistory');
        if (!history) return;
        if (!orders().length) {
            history.innerHTML = '';
            return;
        }
        history.innerHTML = `
            <h3>Recent orders</h3>
            ${orders().slice(0, 3).map((order) => {
                const summary = (order.items || [])
                    .map((item) => `${Number(item.quantity || 0)}× ${(shopItem(item.id) || {}).name || item.id}`)
                    .join(', ');
                return `
                    <div class="order-row">
                        <span>${escapeHtml(formatDate(order.date))} · ${escapeHtml(summary)}</span>
                        <strong class="status-chip">${escapeHtml(order.status || 'Requested')}</strong>
                    </div>
                `;
            }).join('')}
        `;
    }

    function renderNotificationFeed() {
        if (page !== 'notifications') return;
        removeSkeletons('newsletters');
        const list = $('#newsletterList');
        const archive = notificationFeedItems();
        const prefs = settings();
        if (!selectedNewsletterId && archive.length) {
            selectedNewsletterId = archive[0].id;
        }
        $('#newsletterSubscribe').checked = Boolean(prefs.newsletterSubscribed);

        if (list) {
            list.innerHTML = archive.map((item, index) => `
                <button class="newsletter-row ${item.id === selectedNewsletterId ? 'active' : ''}" type="button" data-open-dispatch="${escapeHtml(item.id)}" style="--card-index: ${index}">
                    <span class="read-dot ${item.read ? 'read' : ''}" aria-hidden="true"></span>
                    <span>
                        <strong>${escapeHtml(item.title)}</strong>
                        <small>${escapeHtml(item.excerpt)}</small>
                    </span>
                    <em>${escapeHtml(item.readLabel)}</em>
                </button>
            `).join('');
        }
        renderNotificationReader();
        updateNotificationsNavBadge(archive);
    }

    // Merges the two independent state sections into one chronological feed
    // for display only — `notifications` and `newsletters` stay separate in
    // storage. `kind` tells the reader pane and the read/unread toggle which
    // shape (and which API endpoint) a given row is.
    function notificationFeedItems() {
        const dispatchRows = newsletters().map((n) => ({
            kind: 'dispatch',
            id: n.id,
            title: n.title,
            excerpt: n.excerpt,
            body: n.body,
            readLabel: n.readTime,
            read: Boolean(n.read),
            sortKey: n.date || '',
        }));
        const notificationRows = (dashboardState.notifications || []).map((n) => ({
            kind: 'notification',
            id: n.id,
            title: n.title,
            excerpt: n.message,
            body: n.message,
            readLabel: formatRelativeTime(n.createdAt),
            read: Boolean(n.read),
            sortKey: n.createdAt || '',
        }));
        return dispatchRows.concat(notificationRows).sort((a, b) => (b.sortKey || '').localeCompare(a.sortKey || ''));
    }

    function renderNotificationReader() {
        const item = notificationFeedItems().find((row) => row.id === selectedNewsletterId);
        const button = $('#toggleReadButton');
        if (!item) return;
        $('#newsletterReadTime').textContent = item.readLabel || (item.kind === 'dispatch' ? 'Dispatch' : 'Notification');
        $('#newsletterTitle').textContent = item.title || 'Untitled';
        $('#newsletterDate').textContent = item.kind === 'dispatch'
            ? formatDate(newsletters().find((n) => n.id === item.id)?.date)
            : item.readLabel;
        $('#newsletterBody').textContent = item.body || item.excerpt || '';
        if (button) {
            button.hidden = false;
            button.textContent = item.read ? 'Mark unread' : 'Mark read';
        }
    }

    function updateNotificationsNavBadge(feedItems) {
        const link = $('#sidebarNotificationsLink');
        if (!link) return;
        let badge = link.querySelector('.notification-badge');
        const unread = feedItems.filter((row) => !row.read).length;
        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'notification-badge';
            badge.setAttribute('aria-hidden', 'true');
            link.appendChild(badge);
        }
        badge.textContent = unread > 9 ? '9+' : String(unread);
        badge.style.display = unread > 0 ? 'flex' : 'none';
    }

    function prepareNewProject() {
        const form = $('#projectForm');
        if (!form) return;
        form.reset();
        form.elements.id.value = '';
        form.elements.hackatimeProject.value = '';
        $('#projectModalTitle').textContent = 'New project';
        setFormError('projectFormError', '');
        setFormError('projectThumbError', '');
        updateThumbPreview('');
        refreshProjectRequirements();
        loadHacktimeProjects();
    }

    function prepareEditProject(projectId) {
        const form = $('#projectForm');
        const project = projects().find((item) => item.id === projectId);
        if (!form || !project) return;
        form.reset();
        form.elements.id.value = project.id;
        form.elements.name.value = project.name || '';
        form.elements.description.value = project.description || '';
        form.elements.repoUrl.value = project.repoUrl || '';
        form.elements.demoUrl.value = project.demoUrl || '';
        form.elements.thumbnail.value = project.thumbnail || '';
        form.elements.hackatimeProject.value = project.hackatimeProject || '';
        $('#projectModalTitle').textContent = 'Edit project';
        setFormError('projectFormError', '');
        setFormError('projectThumbError', '');
        updateThumbPreview(project.thumbnail || '');
        refreshProjectRequirements();
        loadHacktimeProjects();
        openModal('projectModal');
    }

    function prepareNewDispatch() {
        const form = $('#dispatchForm');
        if (!form) return;
        form.reset();
        form.elements.readTime.value = '2 min read';
        setFormError('dispatchFormError', '');
    }

const CHECKLIST_ITEMS = [
        {
            id: 'signin',
            icon: 'enter',
            tone: 'green',
            title: 'Sign in to the Leaders Portal',
            subtitle: "You're in! Your Hack Club identity is connected.",
            link: null,
        },
        {
            id: 'slack',
            icon: 'slack',
            tone: 'red',
            title: 'Set up your club on Slack',
            subtitle: 'Join the Hack Club Slack and connect with other leaders.',
            link: 'https://hackclub.slack.com/',
        },
        {
            id: 'ysws',
            icon: 'rocket',
            tone: 'blue',
            title: 'Apply for a YSWS grant',
            subtitle: 'Run a project and earn hardware for your club.',
            link: 'https://ysws.hackclub.com/',
        },
        {
            id: 'hcb',
            icon: 'purse',
            tone: 'orange',
            title: 'Set up HCB for your finances',
            subtitle: 'HCB gives your club a nonprofit bank account.',
            link: 'https://hcb.hackclub.com/',
        },
    ];

    function checklistState() {
        let saved = {};
        try {
            saved = JSON.parse(localStorage.getItem('leadersChecklist') || '{}') || {};
        } catch (error) {
            saved = {};
        }
        // Signing in is done by definition — you're looking at the dashboard.
        saved.signin = true;
        return saved;
    }

    function renderHome() {
        if (page !== 'home') return;
        removeSkeletons('home');
        const prefs = settings();
        const people = members();
        const upcoming = events();

        $('#homeClubName').textContent = prefs.clubName || 'Your club';
        $('#homeMemberTotal').textContent = people.length;
        $('#homeClubMeta').textContent = `${people.length === 1 ? 'member' : 'members'} at ${prefs.location || 'your school'}`;
        $('#homeEventTotal').textContent = upcoming.length;
        $('#homeRsvpTotal').textContent = upcoming.filter((event) => event.rsvp).length;
        $('#homeOrderTotal').textContent = orders().length;
        $('#homeWorkshopTotal').textContent = workshops().filter((w) => w.status === 'Run').length;
        $('#homeShipTotal').textContent = shippedProjects().length;

        const progress = levelProgress();
        $('#homeLevelName').textContent = `Level ${progress.level}`;
        $('#homeLevelFill').style.width = `${progress.percent}%`;
        $('#homeLevelText').textContent = progress.next
            ? `${levelRequirementText(progress) || 'Almost there'} to Level ${progress.next}`
            : 'Max level reached!';

        $('#homeRosterTotal').textContent = people.length;
        const leaders = people.filter((member) => member.role === 'Leader').length;
        const mentors = people.filter((member) => member.role === 'Mentor').length;
        const plain = people.length - leaders - mentors;

        const donut = $('#homeTeamDonut');
        if (donut) {
            const total = people.length || 1;
            const circum = 2 * Math.PI * 38;
            let offset = 0;
            const setSlice = (selector, count) => {
                const slice = $(selector, donut);
                if (!slice || !count) {
                    if (slice) slice.setAttribute('stroke-dasharray', '0 999');
                    return;
                }
                const dash = (count / total) * circum;
                slice.setAttribute('stroke-dasharray', `${dash} ${circum - dash}`);
                slice.setAttribute('stroke-dashoffset', String(-offset));
                offset += dash;
            };
            setSlice('.seg-leaders', leaders);
            setSlice('.seg-members', plain);
            setSlice('.seg-mentors', mentors);
        }

        const breakdown = $('#homeRosterBreakdown');
        if (breakdown) {
            breakdown.innerHTML = people.length
                ? `
                    <span class="legend-item"><span class="legend-dot dot-red" aria-hidden="true"></span>${leaders} ${leaders === 1 ? 'leader' : 'leaders'}</span>
                    <span class="legend-item"><span class="legend-dot dot-orange" aria-hidden="true"></span>${plain} ${plain === 1 ? 'member' : 'members'}</span>
                    <span class="legend-item"><span class="legend-dot dot-purple" aria-hidden="true"></span>${mentors} ${mentors === 1 ? 'mentor' : 'mentors'}</span>
                `
                : 'Invite your first member from the Team page.';
        }

        // Legend <-> donut segment sync
        const segs = ['.seg-leaders', '.seg-members', '.seg-mentors'];
        const allSegs = document.querySelectorAll('.home-team .donut-seg');
        const legendItems = document.querySelectorAll('.home-team .legend-item');

        function spotlightSeg(i) {
            allSegs.forEach(function (s) { s.classList.add('is-ghost'); });
            var seg = document.querySelector('.home-team ' + segs[i]);
            if (seg) { seg.classList.remove('is-ghost'); seg.classList.add('is-spotlit'); }
            legendItems.forEach(function (l, j) { if (j !== i) l.classList.add('is-muted'); });
        }
        function clearSegs() {
            allSegs.forEach(function (s) { s.classList.remove('is-ghost', 'is-spotlit'); });
            legendItems.forEach(function (l) { l.classList.remove('is-muted'); });
        }

        legendItems.forEach(function (item, i) {
            item.addEventListener('mouseenter', function () { spotlightSeg(i); });
            item.addEventListener('mouseleave', clearSegs);
        });

        if (!window._donutSegListenersSet) {
            window._donutSegListenersSet = true;
            allSegs.forEach(function (seg, i) {
                seg.addEventListener('mouseenter', function () { spotlightSeg(i); });
                seg.addEventListener('mouseleave', clearSegs);
            });
        }

        const list = $('#homeUpcomingEvents');
        const empty = $('#homeEventsEmpty');
        if (list) {
            const tones = ['orange', 'blue', 'red'];
            list.innerHTML = upcoming.slice(0, 3).map((event, index) => `
                <a href="/dashboard/events" class="activity-item">
                    <div class="activity-icon ${tones[index % tones.length]}">
                        <span data-hc-icon="calendar-check" data-hc-size="18" data-hc-color="currentColor" aria-hidden="true"></span>
                    </div>
                    <div class="activity-content">
                        <h4 class="activity-title">${escapeHtml(event.title)}</h4>
                        <p class="activity-subtitle">${escapeHtml(formatDate(event.date))} · ${escapeHtml(event.location || '')}</p>
                    </div>
                    ${index === 0 ? '<span class="badge badge-up">Next</span>' : ''}
                </a>
            `).join('');
        }
        if (empty) empty.hidden = upcoming.length > 0;

        renderChecklist();
    }

    function renderChecklist() {
        const container = $('#homeChecklist');
        if (!container) return;
        const done = checklistState();
        const doneCount = CHECKLIST_ITEMS.filter((item) => done[item.id]).length;
        $('#homeChecklistCount').textContent = `${doneCount} / ${CHECKLIST_ITEMS.length} Done`;

        container.innerHTML = CHECKLIST_ITEMS.map((item) => `
            <div class="activity-item ${done[item.id] ? 'is-done' : ''}">
                <button class="activity-icon ${done[item.id] ? 'green' : item.tone} checklist-toggle" type="button"
                    data-check-item="${item.id}" ${item.id === 'signin' ? 'disabled' : ''}
                    aria-label="${done[item.id] ? 'Mark not done' : 'Mark done'}" aria-pressed="${Boolean(done[item.id])}">
                    <span data-hc-icon="${done[item.id] ? 'checkmark' : item.icon}" data-hc-size="18" data-hc-color="currentColor" aria-hidden="true"></span>
                </button>
                <div class="activity-content">
                    <h4 class="activity-title">${item.title}</h4>
                    <p class="activity-subtitle">${item.subtitle}</p>
                </div>
                ${item.link ? `
                    <a class="badge badge-up" href="${item.link}" target="_blank" rel="noopener noreferrer">
                        <span data-hc-icon="external-link" data-hc-size="12" data-hc-color="currentColor" aria-hidden="true"></span> Go
                    </a>
                ` : ''}
            </div>
        `).join('');
    }

    function renderSettings() {
        if (page !== 'settings') return;
        const prefs = settings();
        const avatar = $('#clubPreviewAvatar');
        $('#clubPreviewName').textContent = prefs.clubName || 'Hack Club';
        $('#clubPreviewLocation').textContent = prefs.location || 'Location TBD';
        if (avatar) {
            avatar.textContent = initials(prefs.clubName || 'Hack Club');
            const safeAvatar = String(prefs.avatar || '').replace(/\\/g, '%5C').replace(/"/g, '%22');
            avatar.style.backgroundImage = safeAvatar ? `url("${safeAvatar}")` : '';
            avatar.classList.toggle('has-image', Boolean(prefs.avatar));
        }
    }

    // ── Chat (polling) ───────────────────────────────────────────────────────
    // Channels + messages. All members read/post; leaders manage channels.
    //
    // The implementation lives in dashboard-chat.js and is fetched only on the
    // chat page — see loadChat(). `chatState` stays here because the delegated
    // event handlers further down this file read and write the active channel
    // directly, and both sides need the same object.

    const chatState = {
        channels: [],
        activeId: null,
        lastFetch: null,    // newest message createdAt seen in active channel
        pollTimer: null,
        visibilityBound: false,
        lastMsgMeta: null,  // { key, time } of last rendered message, for grouping
        hiddenCount: 0,     // messages that arrived while the tab was hidden
        jumpBtn: null,      // floating "jump to newest" button (created lazily)
        jumpCount: 0,       // new messages accumulated while scrolled up
        scrollBound: false,
        cmdMenu: null,     // command autocomplete menu element (created lazily)
    };
    const S = chatState;

    // Resolved while this script is executing, when document.currentScript is
    // still valid; loadChat() runs later, by which point it is null.
    const CHAT_SCRIPT_URL = ((document.currentScript && document.currentScript.src) || '')
        .replace(/dashboard\.js(\?.*)?$/, 'dashboard-chat.js');

    // Set by loadChat(); until then every forwarder below is a no-op, which is
    // exactly right for the pages that never load the chat module.
    let chat = null;

    function loadChat() {
        if (chat) return Promise.resolve(chat);
        return new Promise((resolve) => {
            const script = document.createElement('script');
            script.src = CHAT_SCRIPT_URL;
            script.onload = () => {
                chat = window.DashboardChat({
                    state: chatState,
                    page: page,
                    isLeader: isLeader,
                    viewerEmail: viewerEmail,
                    getState: () => dashboardState,
                    apiRequest: apiRequest,
                    avatarMarkup: avatarMarkup,
                    escapeHtml: escapeHtml,
                    removeSkeletons: removeSkeletons,
                    setFormError: setFormError,
                    showToast: showToast,
                });
                resolve(chat);
            };
            // If the module fails to load the page stays usable, just without
            // chat — better than a half-wired composer.
            script.onerror = () => resolve(null);
            document.head.appendChild(script);
        });
    }

    // Thin forwarders, so the rest of this file calls chat features exactly as
    // it did when they lived here.
    function appendMessage(...args) { return chat && chat.appendMessage(...args); }
    function cancelInlineEdit(...args) { return chat && chat.cancelInlineEdit(...args); }
    function chatReads(...args) { return chat && chat.chatReads(...args); }
    function closeChatDrawer(...args) { return chat && chat.closeChatDrawer(...args); }
    function closeChatThread(...args) { return chat && chat.closeChatThread(...args); }
    function deleteMessage(...args) { return chat && chat.deleteMessage(...args); }
    function hideCmdMenu(...args) { return chat && chat.hideCmdMenu(...args); }
    function hideEphemeral(...args) { return chat && chat.hideEphemeral(...args); }
    function markChannelRead(...args) { return chat && chat.markChannelRead(...args); }
    function prepareEditChannel(...args) { return chat && chat.prepareEditChannel(...args); }
    function prepareNewChannel(...args) { return chat && chat.prepareNewChannel(...args); }
    function reactionsMarkup(...args) { return chat && chat.reactionsMarkup(...args); }
    function renderChat(...args) { return chat && chat.renderChat(...args); }
    function resetJumpButton(...args) { return chat && chat.resetJumpButton(...args); }
    function runChatCommand(...args) { return chat && chat.runChatCommand(...args); }
    function saveInlineEdit(...args) { return chat && chat.saveInlineEdit(...args); }
    function scrollChatToBottom(...args) { return chat && chat.scrollChatToBottom(...args); }
    function selectChannel(...args) { return chat && chat.selectChannel(...args); }
    function startInlineEdit(...args) { return chat && chat.startInlineEdit(...args); }
    function toggleChatDrawer(...args) { return chat && chat.toggleChatDrawer(...args); }
    function updateCmdMenu(...args) { return chat && chat.updateCmdMenu(...args); }

    function renderPage() {
        renderHome();
        renderTeam();
        renderEvents();
        renderWorkshops();
        renderShips();
        renderProjects();
        renderLevels();
        renderJoinLink();
        renderCoinBalance();
        renderShop();
        renderNotificationFeed();
        renderChat();
        renderSettings();
    }

    function formObject(form) {
        const data = Object.fromEntries(new FormData(form).entries());
        Array.from(form.elements).forEach((input) => {
            if (input.type !== 'checkbox') return;
            data[input.name] = input.checked;
        });
        return data;
    }

    async function adminProjectAction(trigger, status, buildMessage) {
        const [clubKey, projectId] = String(trigger.dataset.adminProject || '').split('::');
        if (!clubKey || !projectId) return;
        trigger.disabled = true;
        try {
            const response = await apiRequest(`/api/admin/projects/${encodeURIComponent(clubKey)}/${encodeURIComponent(projectId)}`, {
                method: 'PATCH',
                body: { status },
            });
            showToast(buildMessage(response.coinsAwarded || 0));
            // Admin pages are server-rendered outside dashboardState — reload.
            setTimeout(() => window.location.reload(), 350);
        } catch (error) {
            trigger.disabled = false;
            showToast(error.message, 'error');
        }
    }

    // ── Admin: item requests ─────────────────────────────────────────────────
    // The admin page is server-rendered outside dashboardState, so this panel
    // fetches its own data and paints the pending requests from every club.

    async function renderAdminItemRequests() {
        const list = $('#adminItemRequestList');
        if (!list) return;
        try {
            const payload = await apiRequest('/api/admin/item-requests');
            const pending = (payload.itemRequests || []).filter(
                (entry) => (entry.request?.status || 'Submitted') === 'Submitted');
            if (!pending.length) {
                list.innerHTML = `<div class="empty-state"><p>${
                    escapeHtml(list.dataset.emptyText || 'No pending item requests.')}</p></div>`;
                return;
            }
            list.innerHTML = pending.map((entry) => {
                const req = entry.request || {};
                const key = `${entry.clubKey}::${req.id}`;
                const note = req.note ? ` — ${escapeHtml(req.note)}` : '';
                const when = req.date ? ` · ${escapeHtml(req.date)}` : '';
                return `
                <article class="admin-review-item">
                    <div class="admin-review-main">
                        <h3>${escapeHtml(req.name || 'Item')}</h3>
                        <p class="admin-review-meta">
                            <strong>${escapeHtml(entry.clubName || 'Club')}</strong>${note}${when}
                        </p>
                    </div>
                    <div class="admin-review-actions">
                        <button class="btn-primary small" type="button"
                            data-approve-item-request data-admin-item-request="${escapeHtml(key)}">Approve</button>
                        <button class="btn-secondary small" type="button"
                            data-reject-item-request data-admin-item-request="${escapeHtml(key)}">Reject</button>
                    </div>
                </article>`;
            }).join('');
        } catch (error) {
            list.innerHTML = `<div class="empty-state"><p>${escapeHtml(error.message)}</p></div>`;
        }
    }

    async function adminItemRequestAction(trigger, status, message) {
        const [clubKey, requestId] = String(trigger.dataset.adminItemRequest || '').split('::');
        if (!clubKey || !requestId) return;
        trigger.disabled = true;
        try {
            await apiRequest(`/api/admin/item-requests/${encodeURIComponent(clubKey)}/${encodeURIComponent(requestId)}`, {
                method: 'PATCH',
                body: { status },
            });
            showToast(message);
            renderAdminItemRequests();
        } catch (error) {
            trigger.disabled = false;
            showToast(error.message, 'error');
        }
    }

    function setupGlobalEvents() {
        document.addEventListener('click', async (event) => {
            const approveProject = event.target.closest('[data-approve-project]');
            if (approveProject) {
                await adminProjectAction(approveProject, 'Shipped', (coins) =>
                    coins > 0 ? `Project approved — shipped! +${coins} coins awarded 🎉` : 'Project approved — shipped!');
                return;
            }
            const rejectProject = event.target.closest('[data-reject-project]');
            if (rejectProject) {
                await adminProjectAction(rejectProject, 'Draft', () => 'Project sent back to draft.');
                return;
            }

            const approveItemRequest = event.target.closest('[data-approve-item-request]');
            if (approveItemRequest) {
                await adminItemRequestAction(approveItemRequest, 'approved', 'Item approved — added to the shop.');
                return;
            }
            const rejectItemRequest = event.target.closest('[data-reject-item-request]');
            if (rejectItemRequest) {
                await adminItemRequestAction(rejectItemRequest, 'rejected', 'Item request rejected.');
                return;
            }

            const openTrigger = event.target.closest('[data-open-modal]');
            if (openTrigger) {
                const modalId = openTrigger.dataset.openModal;
                if (modalId === 'memberModal') prepareNewMember();
                if (modalId === 'eventModal') prepareNewEvent();
                if (modalId === 'dispatchModal') prepareNewDispatch();
                if (modalId === 'projectModal') prepareNewProject();
                if (modalId === 'channelModal') prepareNewChannel();
                if (modalId === 'workshopProposeModal') prepareNewWorkshop();
                openModal(modalId);
                return;
            }

            const closeTrigger = event.target.closest('[data-modal-close]');
            if (closeTrigger) {
                closeModal(closeTrigger);
                return;
            }

            if (event.target.classList.contains('modal-backdrop')) {
                closeModal(event.target);
                return;
            }

            const drawerToggle = event.target.closest('#chatDrawerToggle');
            if (drawerToggle) {
                toggleChatDrawer();
                return;
            }

            if (event.target.closest('#chatBackdrop')) {
                closeChatDrawer();
                return;
            }

            const channelBtn = event.target.closest('[data-channel]');
            if (channelBtn) {
                selectChannel(channelBtn.dataset.channel);
                closeChatDrawer();
                return;
            }

            const editChannel = event.target.closest('#chatEditChannel');
            if (editChannel) {
                if (!S.activeId) return;
                prepareEditChannel(S.activeId);
                openModal('channelModal');
                return;
            }

            const hideEphBtn = event.target.closest('[data-hide-eph]');
            if (hideEphBtn) {
                hideEphemeral(hideEphBtn.dataset.hideEph, hideEphBtn.closest('.chat-ephemeral'));
                return;
            }

            const reactBtn = event.target.closest('[data-react]');
            if (reactBtn) {
                const row = reactBtn.closest('.chat-message');
                const mid = row?.dataset.mid;
                if (!mid || !S.activeId) return;
                try {
                    const payload = await apiRequest(
                        `/api/dashboard/chat/channels/${encodeURIComponent(S.activeId)}/messages/${encodeURIComponent(mid)}/reactions`,
                        { method: 'POST', body: { emoji: reactBtn.dataset.react } });
                    const pillBox = row.querySelector('.chat-reactions');
                    if (pillBox && payload.message) pillBox.outerHTML = reactionsMarkup(payload.message);
                } catch (error) {
                    showToast(error.message, 'error');
                }
                return;
            }

            const editMsgBtn = event.target.closest('[data-edit-msg]');
            if (editMsgBtn) {
                startInlineEdit(editMsgBtn.closest('.chat-message'));
                return;
            }

            const deleteMsgBtn = event.target.closest('[data-delete-msg]');
            if (deleteMsgBtn) {
                await deleteMessage(deleteMsgBtn.closest('.chat-message'));
                return;
            }

            const editSaveBtn = event.target.closest('[data-edit-save]');
            if (editSaveBtn) {
                await saveInlineEdit(editSaveBtn.closest('.chat-message'));
                return;
            }

            const editCancelBtn = event.target.closest('[data-edit-cancel]');
            if (editCancelBtn) {
                cancelInlineEdit(editCancelBtn.closest('.chat-message'));
                return;
            }

            const editMember = event.target.closest('[data-edit-member]');
            if (editMember) {
                prepareEditMember(editMember.dataset.editMember);
                return;
            }

            const editEvent = event.target.closest('[data-edit-event]');
            if (editEvent) {
                prepareEditEvent(editEvent.dataset.editEvent);
                return;
            }

            const rsvpButton = event.target.closest('[data-toggle-rsvp]');
            if (rsvpButton) {
                const item = events().find((eventItem) => eventItem.id === rsvpButton.dataset.toggleRsvp);
                if (!item) return;
                try {
                    await apiRequest(`/api/dashboard/events/${item.id}`, {
                        method: 'PATCH',
                        body: { rsvp: !item.rsvp },
                    });
                    showToast(item.rsvp ? 'RSVP removed.' : 'RSVP saved.');
                } catch (error) {
                    showToast(error.message, 'error');
                }
                return;
            }

            const shopFilterChip = event.target.closest('[data-shop-filter]');
            if (shopFilterChip) {
                shopFilter = shopFilterChip.dataset.shopFilter;
                renderShop();
                return;
            }

            const workshopFilterChip = event.target.closest('[data-workshop-filter]');
            if (workshopFilterChip) {
                workshopFilter = workshopFilterChip.dataset.workshopFilter;
                renderWorkshops();
                return;
            }

            const openWorkshop = event.target.closest('[data-open-workshop]');
            if (openWorkshop) {
                openWorkshopId = openWorkshop.dataset.openWorkshop;
                const workshop = workshops().find((w) => w.id === openWorkshopId);
                if (!workshop) return;
                renderWorkshopDetail(workshop);
                openModal('workshopDetailModal');
                return;
            }

            const applyWorkshop = event.target.closest('[data-apply-workshop]');
            if (applyWorkshop) {
                try {
                    await apiRequest(`/api/dashboard/workshops/${applyWorkshop.dataset.applyWorkshop}`, {
                        method: 'PATCH',
                        body: { applying: true },
                    });
                    showToast('Applied to run this workshop.');
                } catch (error) {
                    showToast(error.message, 'error');
                }
                return;
            }

            const withdrawWorkshop = event.target.closest('[data-withdraw-workshop]');
            if (withdrawWorkshop) {
                try {
                    await apiRequest(`/api/dashboard/workshops/${withdrawWorkshop.dataset.withdrawWorkshop}`, {
                        method: 'PATCH',
                        body: { applying: false },
                    });
                    showToast('Application withdrawn.');
                } catch (error) {
                    showToast(error.message, 'error');
                }
                return;
            }

            const markRunWorkshop = event.target.closest('[data-mark-run-workshop]');
            if (markRunWorkshop) {
                try {
                    await apiRequest(`/api/dashboard/workshops/${markRunWorkshop.dataset.markRunWorkshop}`, {
                        method: 'PATCH',
                        body: { status: 'Run' },
                    });
                    showToast('Workshop marked as run.');
                } catch (error) {
                    showToast(error.message, 'error');
                }
                return;
            }

            const deleteWorkshop = event.target.closest('[data-delete-workshop]');
            if (deleteWorkshop) {
                try {
                    await apiRequest(`/api/dashboard/workshops/${deleteWorkshop.dataset.deleteWorkshop}`, { method: 'DELETE' });
                    closeModal('workshopDetailModal');
                    showToast('Proposal deleted.');
                } catch (error) {
                    showToast(error.message, 'error');
                }
                return;
            }

            const scheduleWorkshopTrigger = event.target.closest('[data-schedule-workshop]');
            if (scheduleWorkshopTrigger) {
                const [workshopId, runnerEmail] = String(scheduleWorkshopTrigger.dataset.scheduleWorkshop).split('::');
                const runner = members().find((m) => m.email === runnerEmail);
                const form = $('#workshopScheduleForm');
                if (form) {
                    form.reset();
                    form.elements.workshopId.value = workshopId;
                    form.elements.runnerEmail.value = runnerEmail;
                }
                const nameLine = $('#workshopScheduleRunnerName');
                if (nameLine) nameLine.textContent = `Running: ${runner ? runner.name : runnerEmail}`;
                setFormError('workshopScheduleFormError', '');
                openModal('workshopScheduleModal');
                return;
            }

            const addCart = event.target.closest('[data-add-cart]');
            if (addCart) {
                try {
                    await apiRequest('/api/dashboard/cart', {
                        method: 'POST',
                        body: { itemId: addCart.dataset.addCart, quantity: 1 },
                    });
                    showToast('Added to cart.');
                } catch (error) {
                    showToast(error.message, 'error');
                }
                return;
            }

            const removeItemRequest = event.target.closest('[data-remove-item-request]');
            if (removeItemRequest) {
                try {
                    await apiRequest(`/api/dashboard/item-requests/${removeItemRequest.dataset.removeItemRequest}`, { method: 'DELETE' });
                    showToast('Request removed.');
                } catch (error) {
                    showToast(error.message, 'error');
                }
                return;
            }

            const cartStep = event.target.closest('[data-cart-step]');
            if (cartStep) {
                const entry = cart().find((item) => item.id === cartStep.dataset.cartItem);
                if (!entry) return;
                const quantity = Number(entry.quantity || 0) + Number(cartStep.dataset.cartStep);
                try {
                    if (quantity <= 0) {
                        await apiRequest(`/api/dashboard/cart/${entry.id}`, { method: 'DELETE' });
                    } else {
                        await apiRequest(`/api/dashboard/cart/${entry.id}`, {
                            method: 'PATCH',
                            body: { quantity },
                        });
                    }
                } catch (error) {
                    showToast(error.message, 'error');
                }
                return;
            }

            const removeCart = event.target.closest('[data-remove-cart]');
            if (removeCart) {
                try {
                    await apiRequest(`/api/dashboard/cart/${removeCart.dataset.removeCart}`, { method: 'DELETE' });
                } catch (error) {
                    showToast(error.message, 'error');
                }
                return;
            }

            const hacktimePill = event.target.closest('.hacktime-pill');
            if (hacktimePill) {
                const form = $('#projectForm');
                if (!form) return;
                const name = hacktimePill.dataset.hacktimeName || '';
                // Toggle off if the selected pill is clicked again.
                const clearing = form.elements.hackatimeProject.value === name;
                form.elements.hackatimeProject.value = clearing ? '' : name;
                $$('.hacktime-pill', form).forEach((pill) => {
                    pill.classList.toggle('is-selected', !clearing && pill === hacktimePill);
                });
                refreshProjectRequirements();
                return;
            }

            const editProject = event.target.closest('[data-edit-project]');
            if (editProject) {
                prepareEditProject(editProject.dataset.editProject);
                return;
            }

            // Card "Submit to club" opens the modal so the member can complete
            // (and see) the requirements before actually submitting.
            const submitProject = event.target.closest('[data-submit-project]');
            if (submitProject) {
                prepareEditProject(submitProject.dataset.submitProject);
                return;
            }

            const projectStatus = event.target.closest('[data-project-status]');
            if (projectStatus) {
                try {
                    await apiRequest(`/api/dashboard/projects/${projectStatus.dataset.projectId}`, {
                        method: 'PATCH',
                        body: { status: projectStatus.dataset.projectStatus },
                    });
                    showToast(projectStatus.dataset.projectStatus === 'Submitted'
                        ? 'Project submitted to your club.' : 'Project moved back to draft.');
                } catch (error) {
                    showToast(error.message, 'error');
                }
                return;
            }

            const deleteProject = event.target.closest('[data-delete-project]');
            if (deleteProject) {
                try {
                    await apiRequest(`/api/dashboard/projects/${deleteProject.dataset.deleteProject}`, { method: 'DELETE' });
                    showToast('Project deleted.');
                } catch (error) {
                    showToast(error.message, 'error');
                }
                return;
            }

            const checkToggle = event.target.closest('[data-check-item]');
            if (checkToggle) {
                const saved = checklistState();
                const id = checkToggle.dataset.checkItem;
                const wasDone = saved[id];
                saved[id] = !saved[id];
                localStorage.setItem('leadersChecklist', JSON.stringify(saved));
                renderChecklist();
                if (!wasDone) {
                    const row = document.querySelector(`.activity-item [data-check-item="${id}"]`)?.closest('.activity-item');
                    if (row) {
                        row.classList.add('celebrated');
                        row.addEventListener('animationend', () => row.classList.remove('celebrated'), { once: true });
                    }
                }
                return;
            }

            const dispatchRow = event.target.closest('[data-open-dispatch]');
            if (dispatchRow) {
                selectedNewsletterId = dispatchRow.dataset.openDispatch;
                const feedItem = notificationFeedItems().find((row) => row.id === selectedNewsletterId);
                renderNotificationFeed();
                if (feedItem && !feedItem.read) {
                    const endpoint = feedItem.kind === 'notification'
                        ? `/api/dashboard/notifications/${feedItem.id}`
                        : `/api/dashboard/newsletters/${feedItem.id}`;
                    try {
                        await apiRequest(endpoint, { method: 'PATCH', body: { read: true } });
                    } catch (error) {
                        showToast(error.message, 'error');
                    }
                }
            }
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                // Cancel any in-progress inline edit first (when focus left the input).
                $$('#chatMessages .chat-edit-form').forEach((editor) => {
                    cancelInlineEdit(editor.closest('.chat-message'));
                });
                $$('.modal-backdrop.is-open').forEach(closeModal);
                closeChatDrawer();
                return;
            }
            if (page === 'chat') handleChatShortcuts(event);
        });
    }

    function handleChatShortcuts(event) {
        const el = event.target;
        const typing = el && (
            (el.matches && el.matches('input, textarea, select')) || el.isContentEditable);
        if (event.altKey && (event.key === 'ArrowUp' || event.key === 'ArrowDown')) {
            if (!S.channels.length) return;
            event.preventDefault();
            const current = S.channels.findIndex((channel) => channel.id === S.activeId);
            const delta = event.key === 'ArrowUp' ? -1 : 1;
            const start = current < 0 ? 0 : current + delta;
            const next = ((start % S.channels.length) + S.channels.length) % S.channels.length;
            selectChannel(S.channels[next].id);
            closeChatDrawer();
            return;
        }
        if (event.key === '/' && !typing) {
            const composer = document.getElementById('chatComposer');
            const input = document.querySelector('.chat-composer-input');
            if (input && composer && !composer.hidden) {
                event.preventDefault();
                input.focus();
            }
        }
    }

    function setupForms() {
        const chatComposerInput = $('#chatComposer')?.elements.body;
        if (chatComposerInput) {
            chatComposerInput.addEventListener('input', () => updateCmdMenu(chatComposerInput.value));
            chatComposerInput.addEventListener('blur', () => window.setTimeout(hideCmdMenu, 150));
            chatComposerInput.addEventListener('keydown', (event) => {
                if (event.key === 'Escape' && S.cmdMenu && !S.cmdMenu.hidden) {
                    event.stopPropagation();
                    hideCmdMenu();
                }
            });
        }

        $('#chatComposer')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const input = event.currentTarget.elements.body;
            const body = (input.value || '').trim();
            if (!body || !S.activeId) return;
            hideCmdMenu();
            if (body.startsWith('/')) {
                input.value = '';
                await runChatCommand(body);
                return;
            }
            const channelId = S.activeId;
            input.value = '';
            // Optimistically show the message; reconcile (or roll back) on response.
            const pending = appendMessage(
                { authorEmail: viewerEmail, body, createdAt: new Date().toISOString() },
                { pending: true });
            scrollChatToBottom();
            resetJumpButton();
            try {
                const response = await apiRequest(
                    `/api/dashboard/chat/channels/${encodeURIComponent(channelId)}/messages`, {
                        method: 'POST',
                        body: { body },
                    });
                const real = response && response.message;
                if (channelId !== S.activeId) return;   // switched channels mid-flight
                if (pending) {
                    const dup = real && real.id
                        ? document.querySelector(`#chatMessages [data-mid="${window.CSS.escape(String(real.id))}"]`)
                        : null;
                    if (dup && dup !== pending) {
                        pending.remove();   // a poll already rendered the server copy
                    } else {
                        pending.classList.remove('chat-message--pending');
                        pending.style.opacity = '';
                        if (real && real.id) pending.dataset.mid = String(real.id);
                    }
                }
                if (real && real.createdAt && (!S.lastFetch || real.createdAt > S.lastFetch)) {
                    S.lastFetch = real.createdAt;
                    markChannelRead(channelId, S.lastFetch);
                }
            } catch (error) {
                if (pending) pending.remove();
                input.value = body;   // restore so the user doesn't lose their text
                const notice = error.retryAfter != null
                    ? `${error.message} Try again in ${error.retryAfter}s.`
                    : error.message;
                showToast(notice, 'error');
            }
        });

        $('#channelForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const id = form.elements.id.value;
            const body = {
                name: form.elements.name.value,
                description: form.elements.description.value,
                topic: form.elements.topic.value,
            };
            setFormError('channelFormError', '');
            try {
                if (id) {
                    const payload = await apiRequest(`/api/dashboard/chat/channels/${encodeURIComponent(id)}`, {
                        method: 'PATCH', body,
                    });
                    const local = S.channels.find((item) => item.id === id);
                    if (local && payload.channel) Object.assign(local, payload.channel);
                    if (id === S.activeId) { S.activeId = null; selectChannel(id); }
                } else {
                    const payload = await apiRequest('/api/dashboard/chat/channels', {
                        method: 'POST', body,
                    });
                    if (payload.channel) selectChannel(payload.channel.id);
                }
                closeModal('channelModal');
                showToast('Channel saved.');
            } catch (error) {
                setFormError('channelFormError', error.message);
            }
        });

        $('#deleteChannelButton')?.addEventListener('click', async () => {
            const id = $('#channelForm')?.elements.id.value;
            if (!id) return;
            try {
                await apiRequest(`/api/dashboard/chat/channels/${encodeURIComponent(id)}`, {
                    method: 'DELETE',
                });
                if (S.activeId === id) {
                    S.activeId = null;
                    closeChatThread();
                }
                closeModal('channelModal');
                showToast('Channel deleted.');
            } catch (error) {
                setFormError('channelFormError', error.message);
            }
        });

        $('#memberForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const data = formObject(form);
            const isEdit = Boolean(data.id);
            setFormError('memberFormError', '');
            try {
                await apiRequest(isEdit ? `/api/dashboard/team/${data.id}` : '/api/dashboard/team', {
                    method: isEdit ? 'PATCH' : 'POST',
                    body: data,
                });
                closeModal('memberModal');
                showToast(isEdit ? 'Member saved.' : 'Invite added.');
            } catch (error) {
                setFormError('memberFormError', error.message);
            }
        });

        $('#deleteMemberButton')?.addEventListener('click', async () => {
            const id = $('#memberForm')?.elements.id.value;
            if (!id) return;
            try {
                await apiRequest(`/api/dashboard/team/${id}`, { method: 'DELETE' });
                closeModal('memberModal');
                showToast('Member removed.');
            } catch (error) {
                setFormError('memberFormError', error.message);
            }
        });

        $('#eventForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const data = formObject(form);
            const isEdit = Boolean(data.id);
            setFormError('eventFormError', '');
            try {
                await apiRequest(isEdit ? `/api/dashboard/events/${data.id}` : '/api/dashboard/events', {
                    method: isEdit ? 'PATCH' : 'POST',
                    body: data,
                });
                closeModal('eventModal');
                showToast(isEdit ? 'Event saved.' : 'Event scheduled.');
            } catch (error) {
                setFormError('eventFormError', error.message);
            }
        });

        $('#deleteEventButton')?.addEventListener('click', async () => {
            const id = $('#eventForm')?.elements.id.value;
            if (!id) return;
            try {
                await apiRequest(`/api/dashboard/events/${id}`, { method: 'DELETE' });
                closeModal('eventModal');
                showToast('Event deleted.');
            } catch (error) {
                setFormError('eventFormError', error.message);
            }
        });

        $('#workshopProposeForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const data = formObject(form);
            setFormError('workshopProposeFormError', '');
            try {
                await apiRequest('/api/dashboard/workshops', { method: 'POST', body: data });
                closeModal('workshopProposeModal');
                showToast('Workshop proposed.');
            } catch (error) {
                setFormError('workshopProposeFormError', error.message);
            }
        });

        $('#workshopScheduleForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const data = formObject(form);
            setFormError('workshopScheduleFormError', '');
            try {
                await apiRequest(`/api/dashboard/workshops/${data.workshopId}`, {
                    method: 'PATCH',
                    body: {
                        status: 'Scheduled',
                        runnerEmail: data.runnerEmail,
                        date: data.date,
                        time: data.time,
                        location: data.location,
                    },
                });
                closeModal('workshopScheduleModal');
                closeModal('workshopDetailModal');
                showToast('Workshop scheduled.');
            } catch (error) {
                setFormError('workshopScheduleFormError', error.message);
            }
        });

        // Recompute the checklist / submit-button state as fields change.
        $('#projectForm')?.addEventListener('input', () => {
            refreshProjectRequirements();
        });

        // Upload the picked thumbnail file, then fill the hidden thumbnail URL.
        $('#projectThumbFile')?.addEventListener('change', handleThumbFileChange);

        // "Save draft" — persist the fields; the draft transition is never gated.
        $('#projectForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            setFormError('projectFormError', '');
            try {
                const { isEdit } = await saveProjectFields(form);
                closeModal('projectModal');
                showToast(isEdit ? 'Draft saved.' : 'Draft created.');
            } catch (error) {
                setFormError('projectFormError', error.message);
            }
        });

        // "Submit for Review" — save the fields first (POST if new), then flip
        // status. A gated 400 from the status PATCH is surfaced inline.
        $('#projectSubmitReview')?.addEventListener('click', async () => {
            const form = $('#projectForm');
            const button = $('#projectSubmitReview');
            if (!form) return;
            setFormError('projectFormError', '');
            button.disabled = true;
            try {
                const { response } = await saveProjectFields(form);
                const projectId = form.elements.id.value
                    || response.project?.id
                    || response.projectId;
                if (!projectId) throw new Error('Could not find the saved project.');
                // Persist the resolved id so a later status error leaves the
                // form editing the now-saved project rather than a phantom new one.
                form.elements.id.value = projectId;
                await apiRequest(`/api/dashboard/projects/${projectId}`, {
                    method: 'PATCH',
                    body: { status: 'Submitted' },
                });
                closeModal('projectModal');
                showToast('Submitted for review.');
            } catch (error) {
                setFormError('projectFormError', error.message);
                refreshProjectRequirements();
            }
        });

        $('#itemRequestForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            setFormError('itemRequestFormError', '');
            try {
                await apiRequest('/api/dashboard/item-requests', {
                    method: 'POST',
                    body: formObject(form),
                });
                form.reset();
                showToast('Item request submitted.');
            } catch (error) {
                setFormError('itemRequestFormError', error.message);
            }
        });

        $('#copyJoinLink')?.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(joinLink());
                showToast('Join link copied.');
            } catch (error) {
                showToast('Could not copy — copy it manually.', 'error');
            }
        });

        $('#refreshJoinLink')?.addEventListener('click', async () => {
            const ok = window.confirm(
                'Generate a new join link? The current link will stop working, '
                + 'so anyone you already shared it with will need the new one.');
            if (!ok) return;
            try {
                // The returned state re-renders #joinLinkCode via renderJoinLink().
                await apiRequest('/api/dashboard/settings/join-code/refresh', { method: 'POST' });
                showToast('New join link generated. The old link is now disabled.');
            } catch (error) {
                showToast(error.message, 'error');
            }
        });

        $('#checkoutButton')?.addEventListener('click', async () => {
            try {
                await apiRequest('/api/dashboard/checkout', { method: 'POST' });
                showToast('Order placed.');
            } catch (error) {
                showToast(error.message, 'error');
            }
        });

        $('#viewCartButton')?.addEventListener('click', () => {
            $('#cartPanel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });

        $('#dispatchForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            setFormError('dispatchFormError', '');
            try {
                const response = await apiRequest('/api/dashboard/newsletters', {
                    method: 'POST',
                    body: formObject(form),
                });
                selectedNewsletterId = response.newsletter.id;
                closeModal('dispatchModal');
                showToast('Dispatch added.');
            } catch (error) {
                setFormError('dispatchFormError', error.message);
            }
        });

        $('#toggleReadButton')?.addEventListener('click', async () => {
            const feedItem = notificationFeedItems().find((row) => row.id === selectedNewsletterId);
            if (!feedItem) return;
            const endpoint = feedItem.kind === 'notification'
                ? `/api/dashboard/notifications/${feedItem.id}`
                : `/api/dashboard/newsletters/${feedItem.id}`;
            try {
                await apiRequest(endpoint, { method: 'PATCH', body: { read: !feedItem.read } });
                showToast(feedItem.read ? 'Marked unread.' : 'Marked read.');
            } catch (error) {
                showToast(error.message, 'error');
            }
        });

        $('#notificationsMarkAllReadBtn')?.addEventListener('click', markAllNotificationsRead);

        $('#newsletterSubscribe')?.addEventListener('change', async (event) => {
            // currentTarget is null after the await — read it up front.
            const subscribed = event.currentTarget.checked;
            try {
                await apiRequest('/api/dashboard/newsletter-subscription', {
                    method: 'PATCH',
                    body: { subscribed },
                });
                showToast(subscribed ? 'Subscription enabled.' : 'Subscription paused.');
            } catch (error) {
                showToast(error.message, 'error');
            }
        });

        $('#settingsForm')?.addEventListener('input', (event) => {
            const form = event.currentTarget;
            const data = formObject(form);
            settings().clubName = data.clubName;
            settings().location = data.location;
            settings().avatar = data.avatar;
            renderSettings();
        });

        $('#settingsForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const stateLabel = $('#settingsSaveState');
            setFormError('settingsFormError', '');
            if (stateLabel) stateLabel.textContent = 'Saving...';
            try {
                const data = formObject(event.currentTarget);
                await apiRequest('/api/dashboard/settings', {
                    method: 'PATCH',
                    body: data,
                });
                const wantsDark = Boolean(data.darkModeDefault);
                localStorage.setItem('mode', wantsDark ? 'dark' : 'light');
                document.body.classList.toggle('dark-mode', wantsDark);
                $('#toggleBtn')?.classList.toggle('active', wantsDark);
                if (data.language && window.i18n) {
                    window.i18n.setLanguage(data.language);
                }
                if (stateLabel) stateLabel.textContent = 'Saved';
                showToast('Settings saved.');
            } catch (error) {
                setFormError('settingsFormError', error.message);
                if (stateLabel) stateLabel.textContent = '';
            }
        });

        $('#profileForm')?.addEventListener('input', (event) => {
            const data = formObject(event.currentTarget);
            const avatarBox = $('#profilePreviewAvatar');
            const nameNode = $('#profilePreviewName');
            const emailNode = $('#profilePreviewEmail');
            if (nameNode) nameNode.textContent = data.name || 'You';
            if (emailNode) emailNode.textContent = data.email || '';
            if (avatarBox) {
                avatarBox.textContent = initials(data.name || 'You');
                const safeAvatar = String(data.avatar || '').replace(/\\/g, '%5C').replace(/"/g, '%22');
                avatarBox.style.backgroundImage = safeAvatar ? `url("${safeAvatar}")` : '';
                avatarBox.classList.toggle('has-image', Boolean(data.avatar));
            }
        });

        $('#profileForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const stateLabel = $('#profileSaveState');
            setFormError('profileFormError', '');
            if (stateLabel) stateLabel.textContent = 'Saving...';
            try {
                const data = formObject(event.currentTarget);
                const result = await apiRequest('/api/dashboard/profile', {
                    method: 'PATCH',
                    body: data,
                });
                const user = result.user || {};
                const rail = $('#sidebarProfile');
                if (rail) {
                    rail.title = user.name || 'Your profile';
                    const img = rail.querySelector('img');
                    const fallback = rail.querySelector('.sidebar-profile-fallback');
                    if (img && user.avatar) img.src = user.avatar;
                    if (fallback) fallback.textContent = (user.name || 'U').charAt(0).toUpperCase();
                }
                if (stateLabel) stateLabel.textContent = 'Saved';
                showToast('Profile saved.');
            } catch (error) {
                setFormError('profileFormError', error.message);
                if (stateLabel) stateLabel.textContent = '';
            }
        });

        $('#adminClubForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const clubKey = form.dataset.clubKey;
            const stateLabel = $('#adminClubSaveState');
            setFormError('adminClubFormError', '');
            if (stateLabel) stateLabel.textContent = 'Saving...';
            try {
                await apiRequest(`/api/admin/clubs/${encodeURIComponent(clubKey)}`, {
                    method: 'PATCH',
                    body: formObject(form),
                });
                if (stateLabel) stateLabel.textContent = 'Saved';
                showToast('Club updated.');
            } catch (error) {
                setFormError('adminClubFormError', error.message);
                if (stateLabel) stateLabel.textContent = '';
            }
        });

        $('#adminShopItemForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const stateLabel = $('#adminShopItemSaveState');
            setFormError('adminShopItemFormError', '');
            if (stateLabel) stateLabel.textContent = 'Adding...';
            try {
                const { shopItem } = await apiRequest('/api/admin/shop-items', {
                    method: 'POST',
                    body: formObject(form),
                });
                if (stateLabel) stateLabel.textContent = 'Added';
                showToast(`${shopItem.name} added to the shop.`);
                form.reset();
            } catch (error) {
                setFormError('adminShopItemFormError', error.message);
                if (stateLabel) stateLabel.textContent = '';
            }
        });
    }

    // ── Reactive background ──────────────────────────────────────────────────
    // Dot grid that breathes and lights up in Hack Club colors around the
    // cursor. Skips animation entirely for prefers-reduced-motion.

    function initBackground() {
        const canvas = document.getElementById('dashboardBg');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        const GAP = 30;
        const RADIUS = 170;
        const ACCENTS = ['236, 55, 80', '255, 140, 55', '51, 142, 218', '51, 214, 166', '166, 51, 214'];

        let width = 0;
        let height = 0;
        let dots = [];
        const pointer = { x: -9999, y: -9999, tx: -9999, ty: -9999 };

        function rebuild() {
            const dpr = window.devicePixelRatio || 1;
            width = window.innerWidth;
            height = window.innerHeight;
            canvas.width = width * dpr;
            canvas.height = height * dpr;
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

            dots = [];
            for (let x = GAP / 2; x < width; x += GAP) {
                for (let y = GAP / 2; y < height; y += GAP) {
                    dots.push({
                        x,
                        y,
                        // ~1 in 14 dots carries a brand color revealed near the cursor
                        accent: Math.random() < 0.07
                            ? ACCENTS[Math.floor(Math.random() * ACCENTS.length)]
                            : null,
                        phase: Math.random() * Math.PI * 2,
                    });
                }
            }
        }

        function draw(time) {
            const dark = document.body.classList.contains('dark-mode');
            const base = dark ? '242, 242, 238' : '31, 45, 61';
            const ease = reducedMotion ? 1 : 0.12;
            pointer.x += (pointer.tx - pointer.x) * ease;
            pointer.y += (pointer.ty - pointer.y) * ease;

            ctx.clearRect(0, 0, width, height);
            for (const dot of dots) {
                const dx = dot.x - pointer.x;
                const dy = dot.y - pointer.y;
                const dist = Math.hypot(dx, dy);
                const near = Math.max(0, 1 - dist / RADIUS);
                const breathe = reducedMotion ? 0 : (Math.sin(time / 1600 + dot.phase) + 1) / 2;
                const alpha = (dark ? 0.05 : 0.08) + breathe * 0.03 + near * 0.55;
                const size = 1.1 + breathe * 0.3 + near * 2.2;
                const color = near > 0.05 && dot.accent ? dot.accent : base;

                ctx.beginPath();
                ctx.arc(dot.x, dot.y, size, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(${color}, ${alpha})`;
                ctx.fill();
            }

            if (pointer.x > 0 && pointer.y > 0) {
                const glowRadius = 50;
                const gradient = ctx.createRadialGradient(pointer.x, pointer.y, 0, pointer.x, pointer.y, glowRadius);
                const glowColor = dark ? '255, 255, 255' : '236, 55, 80';
                gradient.addColorStop(0, `rgba(${glowColor}, 0.06)`);
                gradient.addColorStop(0.5, `rgba(${glowColor}, 0.02)`);
                gradient.addColorStop(1, `rgba(${glowColor}, 0)`);
                ctx.beginPath();
                ctx.arc(pointer.x, pointer.y, glowRadius, 0, Math.PI * 2);
                ctx.fillStyle = gradient;
                ctx.fill();
            }
        }

        function loop(time) {
            if (!document.hidden) draw(time);
            window.requestAnimationFrame(loop);
        }

        window.addEventListener('pointermove', (event) => {
            pointer.tx = event.clientX;
            pointer.ty = event.clientY;
        }, { passive: true });
        window.addEventListener('pointerleave', () => {
            pointer.tx = -9999;
            pointer.ty = -9999;
        });
        window.addEventListener('resize', rebuild);

        rebuild();
        if (reducedMotion) {
            // Static grid, redrawn only when the pointer or theme changes.
            draw(0);
            window.addEventListener('pointermove', () => draw(0), { passive: true });
            document.getElementById('toggleBtn')?.addEventListener('click', () => draw(0));
            window.addEventListener('resize', () => draw(0));
        } else {
            window.requestAnimationFrame(loop);
        }
    }

    function initHeroSpotlight() {
        const hero = document.querySelector('.home-hero');
        if (!hero) return;

        let raf = 0;
        let targetX = 0, targetY = 0;
        let currentX = 0, currentY = 0;

        hero.addEventListener('mousemove', function (e) {
            const rect = hero.getBoundingClientRect();
            targetX = ((e.clientX - rect.left) / rect.width) * 100;
            targetY = ((e.clientY - rect.top) / rect.height) * 100;
        });

        hero.addEventListener('mouseleave', function () {
            hero.style.removeProperty('--spot-x');
            hero.style.removeProperty('--spot-y');
        });

        function frame() {
            currentX += (targetX - currentX) * 0.1;
            currentY += (targetY - currentY) * 0.1;
            hero.style.setProperty('--spot-x', currentX.toFixed(1) + '%');
            hero.style.setProperty('--spot-y', currentY.toFixed(1) + '%');
            raf = requestAnimationFrame(frame);
        }

        raf = requestAnimationFrame(frame);
    }

    function applyDarkModeDefault() {
        // dark-mode.js only knows localStorage; when the visitor has no saved
        // preference yet, fall back to the club's saved setting.
        if (localStorage.getItem('mode') === null && settings().darkModeDefault) {
            document.body.classList.add('dark-mode');
            $('#toggleBtn')?.classList.add('active');
        }
    }

    function applyLanguageDefault() {
        // i18n.js only knows localStorage; when the visitor has not picked a
        // language yet, fall back to the club's saved default.
        if (localStorage.getItem('lang') !== null || !window.i18n) return;
        const pref = settings().language;
        if (pref && window.i18n.isSupported(pref)) {
            // Translations are fetched per language, so make sure this one has
            // landed before painting with it.
            window.i18n.load(pref).then(() => window.i18n.apply(pref));
        }
    }

    // ── Notification Center ──────────────────────────────────────────────────────
    let notificationCenterOpen = false;
    let notifications = [];

    // Read from the live state rather than re-parsing the server-rendered
    // <script id="dashboard-state">, which never changes after page load and so
    // left the bell showing a stale count after every refresh.
    function loadNotifications() {
        notifications = Array.isArray(dashboardState.notifications)
            ? dashboardState.notifications
            : [];
        updateNotificationBadge();
        if (notificationCenterOpen) renderNotificationCenter();
    }

    function updateNotificationBadge() {
        const badge = $('#notificationBadge');
        const bell = $('#notificationBell');
        const unread = notifications.filter(n => !n.read).length;
        if (bell) {
            // The badge is aria-hidden, so the count has to reach assistive
            // tech through the button's own label.
            bell.setAttribute(
                'aria-label',
                unread ? `Notifications (${unread} unread)` : 'Notifications');
        }
        if (!badge) return;
        badge.textContent = unread > 9 ? '9+' : String(unread);
        badge.style.display = unread > 0 ? 'flex' : 'none';
    }

    function renderNotificationCenter() {
        const list = $('#notificationCenterList');
        if (!list) return;

        if (!notifications.length) {
            list.innerHTML = `
                <div class="notification-center-empty">
                    <p data-i18n="notifications.noNotifications">No notifications yet.</p>
                </div>
            `;
            return;
        }

        list.innerHTML = notifications.slice(0, 50).map(notif => `
            <button class="notification-item${notif.read ? ' is-read' : ''}" type="button" data-notification-id="${escapeHtml(notif.id)}">
                <div class="notification-icon">
                    ${getNotificationIcon(notif.type)}
                </div>
                <div class="notification-content">
                    <div class="notification-header">
                        <span class="notification-title">${escapeHtml(notif.title)}</span>
                        <time class="notification-time" datetime="${escapeHtml(notif.createdAt)}">${formatRelativeTime(notif.createdAt)}</time>
                    </div>
                    <p class="notification-message">${escapeHtml(notif.message)}</p>
                </div>
                ${!notif.read ? '<span class="notification-unread-dot" aria-hidden="true"></span>' : ''}
            </button>
        `).join('');

        // Add click handlers
        list.querySelectorAll('.notification-item').forEach(item => {
            item.addEventListener('click', () => {
                const id = item.dataset.notificationId;
                markNotificationRead(id);
            });
        });
    }

    function getNotificationIcon(type) {
        const icons = {
            'event_reminder': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
            'event_rsvp': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>',
            'order_placed': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg>',
            'project_submitted': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
            'member_invited': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
            'default': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
        };
        return icons[type] || icons.default;
    }

    function formatRelativeTime(iso) {
        if (!iso) return '';
        const date = new Date(iso);
        if (isNaN(date.getTime())) return '';
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
    }

    function openNotificationCenter() {
        const center = $('#notificationCenter');
        const backdrop = $('#notificationCenterBackdrop');
        if (!center) return;

        center.classList.add('is-open');
        center.setAttribute('aria-hidden', 'false');
        if (backdrop) backdrop.classList.add('is-open');
        notificationCenterOpen = true;

        loadNotifications();
        renderNotificationCenter();
        // Focus first item
        const firstItem = center.querySelector('.notification-item');
        firstItem?.focus();

        // Trap focus
        document.addEventListener('keydown', handleNotificationCenterKeydown);
    }

    function closeNotificationCenter() {
        const center = $('#notificationCenter');
        const backdrop = $('#notificationCenterBackdrop');
        if (!center) return;

        center.classList.remove('is-open');
        center.setAttribute('aria-hidden', 'true');
        if (backdrop) backdrop.classList.remove('is-open');
        notificationCenterOpen = false;
        // Send focus back to the control that opened the panel.
        $('#notificationBell')?.focus();

        document.removeEventListener('keydown', handleNotificationCenterKeydown);
    }

    function handleNotificationCenterKeydown(event) {
        if (event.key === 'Escape') {
            closeNotificationCenter();
        }
    }

    function markNotificationRead(notificationId) {
        const notif = notifications.find(n => n.id === notificationId);
        if (!notif || notif.read) return;

        notif.read = true;
        updateNotificationBadge();
        renderNotificationCenter();

        // Sync with server, rolling the optimistic update back on failure so
        // the badge can't drift away from what is actually stored.
        apiRequest(`/api/dashboard/notifications/${encodeURIComponent(notificationId)}`, {
            method: 'PATCH',
            body: { read: true },
        }).catch((error) => {
            notif.read = false;
            updateNotificationBadge();
            renderNotificationCenter();
            showToast(error.message || 'Could not mark that as read.', 'error');
        });
    }

    function markAllNotificationsRead() {
        const wasUnread = new Set();
        notifications.forEach(notif => {
            if (!notif.read) {
                notif.read = true;
                wasUnread.add(notif.id);
            }
        });
        const changed = wasUnread.size > 0;

        if (!changed) return;
        updateNotificationBadge();
        renderNotificationCenter();

        apiRequest('/api/dashboard/notifications/mark-all-read', {
            method: 'PATCH',
        }).catch((error) => {
            // Put the unread flags back rather than leaving the badge lying.
            notifications.forEach((notif) => {
                if (wasUnread.has(notif.id)) notif.read = false;
            });
            updateNotificationBadge();
            renderNotificationCenter();
            showToast(error.message || 'Could not mark all as read.', 'error');
        });
    }

    function initNotificationCenter() {
        const bell = $('#notificationBell');
        const backdrop = $('#notificationCenterBackdrop');
        const markAllReadBtn = $('#markAllReadBtn');

        if (bell) {
            bell.addEventListener('click', (e) => {
                e.stopPropagation();
                if (notificationCenterOpen) {
                    closeNotificationCenter();
                } else {
                    openNotificationCenter();
                }
            });
        }

        if (backdrop) {
            backdrop.addEventListener('click', closeNotificationCenter);
        }

        if (markAllReadBtn) {
            markAllReadBtn.addEventListener('click', markAllNotificationsRead);
        }

        // Load initial notifications
        loadNotifications();
    }

    function init() {
        setupGlobalEvents();
        setupForms();
        applyDarkModeDefault();
        applyLanguageDefault();
        initBackground();
        initHeroSpotlight();
        // Club-data pages ship an empty shell; admin pages have their own data.
        const clientDataPage = !hadEmbeddedData && page
            && page !== 'admin' && page !== 'admin-club';
        if (clientDataPage) {
            // Paint instantly from the last-known state, then revalidate.
            const cached = readCachedState();
            if (cached) dashboardState = cached;
        }
        renderPage();
        initHacktime();
        initAvatarUploads();
        if (clientDataPage) refreshState();
        if (page === 'admin') renderAdminItemRequests();
        // The chat module is a separate file; renderPage()'s renderChat() call
        // above no-ops until it lands, so paint chat again once it has.
        if (page === 'chat') loadChat().then((loaded) => loaded && renderChat());
        initNotificationCenter();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}());
