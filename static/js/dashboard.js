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
    let shopSearch = '';

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

    function ledger() {
        return dashboardState.ledger || [];
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

    const COIN_ICON_SVG = '<img src="/static/images/hackclub-site/coin.svg" alt="" width="14" height="14" class="coin-icon">';

    function coinLabel(cost) {
        if (cost === null || cost === undefined) return 'TBD';
        if (Number(cost) === 0) return `${COIN_ICON_SVG}<span>Free</span>`;
        return `${COIN_ICON_SVG}<span>${Number(cost).toLocaleString()}</span>`;
    }

    function shopPhotoUrl(item, index = 0) {
        const supplied = item?.image_src || item?.['image-src'];
        if (supplied) return supplied;
        return '';
    }

    function shopMedia(item) {
        return [0, 1, 2].map((index) => shopPhotoUrl(item, index));
    }

    function shopDescription(item) {
        const categoryCopy = {
            Hardware: 'A useful piece of kit for your club’s next build, workshop, or experiment.',
            Merch: 'A little Hack Club energy for your club room, desk, or next meetup.',
            Digital: 'A digital boost to help your club make, publish, and ship more.',
            Grants: 'Support for the real-world costs that help your club keep moving.',
            Credits: 'Flexible project support for trying something ambitious with your club.',
            Games: 'A playful pick for a club hangout, game night, or creative break.',
        };
        return `${item.name} — ${categoryCopy[item.filter] || 'A club-ready pick for your next project.'}`;
    }

    function renderShopItemDetail(item) {
        const title = $('#shopItemDetailTitle');
        const category = $('#shopItemDetailCategory');
        const body = $('#shopItemDetailBody');
        if (!title || !category || !body || !item) return;
        const media = shopMedia(item);
        title.textContent = item.name;
        category.textContent = item.filter || 'Shop item';
        body.innerHTML = `
            <div class="shop-detail-grid">
                <div class="shop-detail-gallery">
                    <div class="shop-detail-main-image"><img src="${escapeHtml(media[0])}" alt="${escapeHtml(item.name)}" decoding="async" referrerpolicy="no-referrer"></div>
                    <div class="shop-detail-thumbs" role="list" aria-label="More photos of this item">
                        ${media.slice(1).map((src, index) => `<div class="shop-detail-thumb" role="listitem"><img src="${escapeHtml(src)}" alt="${escapeHtml(item.name)} photo ${index + 2}" loading="lazy" referrerpolicy="no-referrer"></div>`).join('')}
                    </div>
                </div>
                <div class="shop-detail-copy">
                    <div class="shop-detail-price">${coinLabel(item.cost)}</div>
                    <p>${escapeHtml(shopDescription(item))}</p>
                    <p class="shop-detail-note">Prices are shown in Hack Club Coins.</p>
                    <button class="btn-primary full-width" type="button" data-add-cart="${escapeHtml(item.id)}" ${item.cost == null ? 'disabled' : ''}>Add to cart</button>
                </div>
            </div>`;
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
        dashboard: ['events', 'projects', 'newsletters', 'workshops', 'ledger'],
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
        // Two frames so the hidden base state paints before the transition runs.
        window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
            toast.setAttribute('data-mounted', 'true');
        }));
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
        modal.classList.remove('is-closing');
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
        modal.setAttribute('aria-hidden', 'true');
        if (!modal.classList.contains('is-open')) return;
        modal.classList.add('is-closing');
        window.setTimeout(() => {
            modal.classList.remove('is-open', 'is-closing');
        }, 150);
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
            // view are worth a request. A shimmer placeholder sits behind the
            // image until it decodes.
            return `<span class="avatar-img-wrap" style="position:relative;display:inline-flex;">
                <span class="skeleton" style="position:absolute;inset:0;border-radius:14px;" aria-hidden="true"></span>
                <img src="${escapeHtml(person.avatar)}" class="${className}" alt="${name}" loading="lazy" decoding="async" style="position:relative;"
                    onload="this.parentElement.querySelector('.skeleton')?.remove()"
                    onerror="this.parentElement.querySelector('.skeleton')?.remove()">
            </span>`;
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

    // Shimmer pills shown while the Hackatime project list loads; mirrors the
    // initial markup in projects.html.
    const HACKTIME_PICKER_SKELETON = `
        <div class="hacktime-picker-skeleton" aria-hidden="true" style="display:flex;gap:8px;flex-wrap:wrap;">
            <div class="skeleton skeleton-badge" style="width:140px;"></div>
            <div class="skeleton skeleton-badge" style="width:96px;"></div>
            <div class="skeleton skeleton-badge" style="width:160px;"></div>
        </div>`;
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

    // Shared crop/zoom step between "file picked" and "upload". `aspect` is
    // width/height for the crop frame (1 = square, 16/9 = project thumbnail).
    // `onCropped` receives the exported Blob; nothing is uploaded here.
    let cropState = null;

    function openCropModal({ file, aspect, onCropped }) {
        const frame = $('#cropFrame');
        const img = $('#cropImage');
        const slider = $('#cropZoomSlider');
        if (!frame || !img || !slider) return;

        const frameWidth = 280;
        const frameHeight = Math.round(frameWidth / aspect);
        frame.style.height = `${frameHeight}px`;

        const objectUrl = URL.createObjectURL(file);
        cropState = {
            objectUrl, aspect, onCropped,
            naturalWidth: 0, naturalHeight: 0,
            scale: 1, minScale: 1,
            offsetX: 0, offsetY: 0,
            dragging: false, dragStartX: 0, dragStartY: 0, dragOffsetX: 0, dragOffsetY: 0,
        };

        img.onload = function () {
            cropState.naturalWidth = img.naturalWidth;
            cropState.naturalHeight = img.naturalHeight;
            // The smallest scale that still fully covers the frame in both dimensions.
            cropState.minScale = Math.max(frameWidth / img.naturalWidth, frameHeight / img.naturalHeight);
            cropState.scale = cropState.minScale;
            cropState.offsetX = 0;
            cropState.offsetY = 0;
            slider.min = String(cropState.minScale);
            slider.max = String(cropState.minScale * 3);
            slider.step = String(cropState.minScale / 100);
            slider.value = String(cropState.minScale);
            applyCropTransform();
        };
        img.src = objectUrl;

        setFormError('cropModalError', '');
        openModal('imageCropModal');
    }

    function applyCropTransform() {
        const img = $('#cropImage');
        if (!img || !cropState) return;
        const w = cropState.naturalWidth * cropState.scale;
        const h = cropState.naturalHeight * cropState.scale;
        img.style.width = `${w}px`;
        img.style.height = `${h}px`;
        img.style.transform =
            `translate(-50%, -50%) translate(${cropState.offsetX}px, ${cropState.offsetY}px)`;
    }

    function clampCropOffsets() {
        if (!cropState) return;
        const frame = $('#cropFrame');
        if (!frame) return;
        const frameWidth = frame.clientWidth;
        const frameHeight = frame.clientHeight;
        const w = cropState.naturalWidth * cropState.scale;
        const h = cropState.naturalHeight * cropState.scale;
        const maxX = Math.max(0, (w - frameWidth) / 2);
        const maxY = Math.max(0, (h - frameHeight) / 2);
        cropState.offsetX = Math.min(maxX, Math.max(-maxX, cropState.offsetX));
        cropState.offsetY = Math.min(maxY, Math.max(-maxY, cropState.offsetY));
    }

    function exportCroppedBlob() {
        return new Promise((resolve, reject) => {
            const frame = $('#cropFrame');
            if (!cropState || !frame) return reject(new Error('Nothing to crop.'));
            const frameWidth = frame.clientWidth;
            const frameHeight = frame.clientHeight;
            const outputWidth = cropState.aspect === 1 ? 512 : 800;
            const outputHeight = Math.round(outputWidth / cropState.aspect);

            const canvas = document.createElement('canvas');
            canvas.width = outputWidth;
            canvas.height = outputHeight;
            const ctx = canvas.getContext('2d');

            // Map frame-space (what's visible) to the source image's natural pixels.
            const visibleLeft = (cropState.naturalWidth * cropState.scale - frameWidth) / 2 - cropState.offsetX;
            const visibleTop = (cropState.naturalHeight * cropState.scale - frameHeight) / 2 - cropState.offsetY;
            const sx = visibleLeft / cropState.scale;
            const sy = visibleTop / cropState.scale;
            const sw = frameWidth / cropState.scale;
            const sh = frameHeight / cropState.scale;

            const img = $('#cropImage');
            ctx.drawImage(img, sx, sy, sw, sh, 0, 0, outputWidth, outputHeight);
            canvas.toBlob((blob) => {
                if (!blob) return reject(new Error('Could not export image.'));
                resolve(blob);
            }, 'image/jpeg', 0.9);
        });
    }

    function closeCropModal() {
        if (cropState) {
            URL.revokeObjectURL(cropState.objectUrl);
            cropState = null;
        }
        closeModal('imageCropModal');
    }

    function initCropModal() {
        const frame = $('#cropFrame');
        const slider = $('#cropZoomSlider');
        const saveButton = $('#cropSaveButton');
        const modal = $('#imageCropModal');
        if (!frame || !slider || !saveButton || !modal) return;

        frame.addEventListener('pointerdown', (event) => {
            if (!cropState) return;
            cropState.dragging = true;
            frame.classList.add('is-dragging');
            frame.setPointerCapture(event.pointerId);
            cropState.dragStartX = event.clientX;
            cropState.dragStartY = event.clientY;
            cropState.dragOffsetX = cropState.offsetX;
            cropState.dragOffsetY = cropState.offsetY;
        });
        frame.addEventListener('pointermove', (event) => {
            if (!cropState || !cropState.dragging) return;
            cropState.offsetX = cropState.dragOffsetX + (event.clientX - cropState.dragStartX);
            cropState.offsetY = cropState.dragOffsetY + (event.clientY - cropState.dragStartY);
            clampCropOffsets();
            applyCropTransform();
        });
        frame.addEventListener('pointerup', () => {
            if (!cropState) return;
            cropState.dragging = false;
            frame.classList.remove('is-dragging');
        });

        slider.addEventListener('input', () => {
            if (!cropState) return;
            cropState.scale = Number(slider.value);
            clampCropOffsets();
            applyCropTransform();
        });

        saveButton.addEventListener('click', async () => {
            if (!cropState) return;
            const onCropped = cropState.onCropped;
            try {
                const blob = await exportCroppedBlob();
                closeCropModal();
                onCropped(blob);
            } catch (error) {
                setFormError('cropModalError', error.message);
            }
        });

        // The modal's own [data-modal-close]/backdrop-click handlers are wired
        // generically in setupGlobalEvents() via [data-modal-close]; hook the
        // object-URL cleanup onto that same generic path.
        modal.addEventListener('click', (event) => {
            if (event.target === modal || event.target.closest('[data-modal-close]')) {
                closeCropModal();
            }
        });
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

    // Wires dragover/dragleave/drop on `dropzone` so dropping an image file
    // behaves like picking one via the hidden file input. `onFile` receives
    // the single dropped File.
    function wireDropzone(dropzone, onFile) {
        if (!dropzone) return;
        ['dragenter', 'dragover'].forEach((type) => {
            dropzone.addEventListener(type, (event) => {
                event.preventDefault();
                dropzone.classList.add('drag-over');
            });
        });
        dropzone.addEventListener('dragleave', (event) => {
            if (!dropzone.contains(event.relatedTarget)) {
                dropzone.classList.remove('drag-over');
            }
        });
        dropzone.addEventListener('dragend', () => dropzone.classList.remove('drag-over'));
        dropzone.addEventListener('drop', (event) => {
            event.preventDefault();
            dropzone.classList.remove('drag-over');
            const file = event.dataTransfer?.files?.[0];
            if (file) onFile(file);
        });
    }

    // Guards against the browser navigating the tab to display a dropped
    // file when a drag misses every dropzone and lands on the page itself.
    ['dragover', 'drop'].forEach((type) => {
        window.addEventListener(type, (event) => {
            if (event.dataTransfer && Array.from(event.dataTransfer.types || []).includes('Files')) {
                event.preventDefault();
            }
        });
    });

    function handleThumbFileChange(event) {
        const input = event.target;
        const file = input.files && input.files[0];
        input.value = '';  // let the same file be re-picked later regardless of outcome
        if (!file) return;
        processThumbFile(file);
    }

    function processThumbFile(file) {
        setFormError('projectThumbError', '');
        if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
            setFormError('projectThumbError', 'Only PNG, JPEG, WebP, or GIF images are allowed.');
            return;
        }
        if (file.size > 4 * 1024 * 1024) {
            setFormError('projectThumbError', 'Image must be 4 MB or smaller.');
            return;
        }

        openCropModal({
            file,
            aspect: 16 / 9,
            onCropped: async (blob) => {
                const cta = $('#projectThumbUpload .image-upload-cta');
                if (cta) cta.textContent = 'Uploading…';
                const form = $('#projectForm');
                try {
                    const url = await uploadProjectImage(blob);
                    if (form) form.elements.thumbnail.value = url;
                    updateThumbPreview(url);
                    refreshProjectRequirements();
                } catch (error) {
                    setFormError('projectThumbError', error.message);
                    updateThumbPreview(form ? form.elements.thumbnail.value : '');
                }
            },
        });
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

            function processAvatarFile(file) {
                if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
                    statusText.textContent = 'Only PNG, JPEG, WebP, or GIF.';
                    return;
                }
                if (file.size > 4 * 1024 * 1024) {
                    statusText.textContent = 'Max 4 MB.';
                    return;
                }

                openCropModal({
                    file,
                    aspect: 1,
                    onCropped: async (blob) => {
                        uploadBtn.disabled = true;
                        statusText.textContent = 'Uploading...';
                        try {
                            const body = new FormData();
                            body.append('image', blob);
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
                        }
                    },
                });
            }

            fileInput.addEventListener('change', function () {
                const file = fileInput.files && fileInput.files[0];
                fileInput.value = '';
                if (file) processAvatarFile(file);
            });
            wireDropzone(row, processAvatarFile);

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

    function initSettingsScrollspy() {
        const nav = $('#settingsNav');
        const sections = document.querySelectorAll('[data-settings-section]');
        if (!nav || !sections.length || !window.IntersectionObserver) return;

        const links = new Map();
        nav.querySelectorAll('.settings-nav-link').forEach((link) => {
            links.set(link.getAttribute('href').slice(1), link);
        });

        const setActive = (id) => {
            links.forEach((link, sectionId) => {
                link.classList.toggle('active', sectionId === id);
            });
        };

        const observer = new IntersectionObserver(
            (entries) => {
                const visible = entries
                    .filter((entry) => entry.isIntersecting)
                    .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
                if (visible.length) setActive(visible[0].target.id);
            },
            { rootMargin: '-96px 0px -60% 0px', threshold: 0.01 }
        );
        sections.forEach((section) => observer.observe(section));

        nav.querySelectorAll('.settings-nav-link').forEach((link) => {
            link.addEventListener('click', (event) => {
                event.preventDefault();
                const target = document.getElementById(link.getAttribute('href').slice(1));
                if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        });
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
        picker.innerHTML = HACKTIME_PICKER_SKELETON;
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
    const SHOP_FILTERS = ['All', 'Hardware', 'Merch', 'Digital', 'Grants', 'Credits', 'Games'];
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
            const term = shopSearch.trim().toLowerCase();
            const visibleItems = shopItems().filter((item) =>
                (shopFilter === 'All' || item.filter === shopFilter) &&
                (!term || item.name.toLowerCase().includes(term))
            ).sort((a, b) => {
                const aCost = a.cost === null || a.cost === undefined ? Number.POSITIVE_INFINITY : Number(a.cost);
                const bCost = b.cost === null || b.cost === undefined ? Number.POSITIVE_INFINITY : Number(b.cost);
                return aCost - bCost;
            });
            grid.innerHTML = visibleItems.map((item, index) => `
                <article class="item-card shop-card" style="--card-index: ${index}" data-open-shop-item="${escapeHtml(item.id)}" tabindex="0" role="button" aria-label="View details for ${escapeHtml(item.name)}">
                    <div class="shop-card-media" style="position:relative;">
                        <span class="skeleton" style="position:absolute;inset:0;border-radius:10px;" aria-hidden="true"></span>
                        <img src="${escapeHtml(shopMedia(item)[0])}" alt="${escapeHtml(item.name)}" loading="lazy" referrerpolicy="no-referrer" style="position:relative;"
                            onload="this.previousElementSibling?.remove()"
                            onerror="this.previousElementSibling?.remove(); this.style.display='none'">
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

    function coinsEarnedByDay(days) {
        const buckets = new Map();
        const now = new Date();
        for (let i = days - 1; i >= 0; i -= 1) {
            const d = new Date(now);
            d.setUTCDate(d.getUTCDate() - i);
            buckets.set(d.toISOString().slice(0, 10), 0);
        }
        ledger().forEach((tx) => {
            if (!tx || tx.delta <= 0) return;
            const day = String(tx.at || '').slice(0, 10);
            if (buckets.has(day)) buckets.set(day, buckets.get(day) + tx.delta);
        });
        return Array.from(buckets.values());
    }

    function renderCoinsWidget() {
        const days = coinsEarnedByDay(30);
        const total = days.reduce((sum, value) => sum + value, 0);
        const totalEl = $('#homeCoinsTotal');
        if (totalEl) totalEl.textContent = total;

        const line = $('#homeCoinsSparkline .home-coins-line');
        if (!line) return;
        const max = Math.max(1, ...days);
        const stepX = 120 / (days.length - 1 || 1);
        const points = days.map((value, index) => {
            const x = index * stepX;
            const y = 32 - (value / max) * 30 - 1;
            return `${x.toFixed(2)},${y.toFixed(2)}`;
        }).join(' ');
        line.setAttribute('points', points);
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
        renderCoinsWidget();
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
        const previewName = $('#clubPreviewName');
        if (previewName) previewName.textContent = prefs.clubName || 'Hack Club';
        const previewLocation = $('#clubPreviewLocation');
        if (previewLocation) previewLocation.textContent = prefs.location || 'Location TBD';
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
        typingThrottleUntil: 0,   // Date.now() ms before which notifyTyping() is a no-op
        onlineMembers: [],        // emails online per the last GET .../channels poll
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
                    $: $,
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
    function notifyTyping(...args) { return chat && chat.notifyTyping(...args); }
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
        document.addEventListener('input', (event) => {
            if (event.target.id === 'shopSearch') {
                shopSearch = event.target.value;
                renderShop();
            }
        });
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

            const openShopItem = event.target.closest('[data-open-shop-item]');
            if (openShopItem && !event.target.closest('[data-add-cart]')) {
                const item = shopItem(openShopItem.dataset.openShopItem);
                if (!item) return;
                renderShopItemDetail(item);
                openModal('shopItemDetailModal');
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
            const shopCard = event.target.closest?.('[data-open-shop-item]');
            if (page === 'shop' && shopCard && !event.target.closest('[data-add-cart]')
                && (event.key === 'Enter' || event.key === ' ')) {
                event.preventDefault();
                const item = shopItem(shopCard.dataset.openShopItem);
                if (item) {
                    renderShopItemDetail(item);
                    openModal('shopItemDetailModal');
                }
                return;
            }
            if (event.key === 'Escape') {
                // Cancel any in-progress inline edit first (when focus left the input).
                $$('#chatMessages .chat-edit-form').forEach((editor) => {
                    cancelInlineEdit(editor.closest('.chat-message'));
                });
                // Close only the topmost modal first: the crop modal can be
                // stacked over another open modal (e.g. the project form),
                // and closing both at once would silently reset that form.
                const cropModal = $('#imageCropModal');
                if (cropModal && cropModal.classList.contains('is-open')) {
                    closeCropModal();
                    return;
                }
                $$('.modal-backdrop.is-open').forEach((modal) => closeModal(modal));
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
            chatComposerInput.addEventListener('input', () => {
                updateCmdMenu(chatComposerInput.value);
                notifyTyping();
            });
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
        wireDropzone($('#projectThumbUpload'), processThumbFile);

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

        $('#signOutEverywhereBtn')?.addEventListener('click', async () => {
            const ok = window.confirm(
                'Sign out of every device, including this one? '
                + "You'll need to sign in again."
            );
            if (!ok) return;
            try {
                await apiRequest('/api/dashboard/account/sign-out-everywhere', { method: 'POST' });
                window.location.href = '/sign-in';
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
                    let img = rail.querySelector('img');
                    const fallback = rail.querySelector('.sidebar-profile-fallback');
                    if (user.avatar) {
                        if (!img) {
                            if (fallback) fallback.remove();
                            img = document.createElement('img');
                            img.alt = user.name || '';
                            rail.appendChild(img);
                        }
                        img.src = user.avatar;
                    } else if (fallback) {
                        fallback.textContent = (user.name || 'U').charAt(0).toUpperCase();
                    }
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
    let notifications = [];

    // Read from the live state rather than re-parsing the server-rendered
    // <script id="dashboard-state">, which never changes after page load and so
    // left the badge showing a stale count after every refresh.
    function loadNotifications() {
        notifications = Array.isArray(dashboardState.notifications)
            ? dashboardState.notifications
            : [];
        updateNotificationsNavBadge(notificationFeedItems());
        if (page === 'notifications') renderNotificationFeed();
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

    function markAllNotificationsRead() {
        const wasUnreadNotifs = new Set();
        notifications.forEach(notif => {
            if (!notif.read) {
                notif.read = true;
                wasUnreadNotifs.add(notif.id);
            }
        });
        const wasUnreadDispatches = new Set();
        newsletters().forEach(dispatch => {
            if (!dispatch.read) {
                dispatch.read = true;
                wasUnreadDispatches.add(dispatch.id);
            }
        });

        if (!wasUnreadNotifs.size && !wasUnreadDispatches.size) return;
        renderNotificationFeed();

        const requests = [];
        if (wasUnreadNotifs.size) {
            requests.push(apiRequest('/api/dashboard/notifications/mark-all-read', { method: 'PATCH' }));
        }
        wasUnreadDispatches.forEach((id) => {
            requests.push(apiRequest(`/api/dashboard/newsletters/${id}`, { method: 'PATCH', body: { read: true } }));
        });

        Promise.all(requests).catch((error) => {
            // Put the unread flags back rather than leaving the badge lying.
            notifications.forEach((notif) => {
                if (wasUnreadNotifs.has(notif.id)) notif.read = false;
            });
            newsletters().forEach((dispatch) => {
                if (wasUnreadDispatches.has(dispatch.id)) dispatch.read = false;
            });
            renderNotificationFeed();
            showToast(error.message || 'Could not mark all as read.', 'error');
        });
    }

    function initNotificationData() {
        loadNotifications();
    }

    function init() {
        setupGlobalEvents();
        setupForms();
        applyDarkModeDefault();
        applyLanguageDefault();
        initBackground();
        initCropModal();
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
        initSettingsScrollspy();
        if (clientDataPage) refreshState();
        if (page === 'admin') renderAdminItemRequests();
        // The chat module is a separate file; renderPage()'s renderChat() call
        // above no-ops until it lands, so paint chat again once it has.
        if (page === 'chat') loadChat().then((loaded) => loaded && renderChat());
        initNotificationData();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}());
