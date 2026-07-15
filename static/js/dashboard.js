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

    function setState(nextState) {
        dashboardState = nextState || dashboardState;
        cacheState(dashboardState);
        renderPage();
        initAvatarUploads();
    }

    async function refreshState() {
        // Pull the authoritative state in the background; apiRequest calls
        // setState (which caches + re-renders) when the payload carries state.
        try {
            await apiRequest('/api/dashboard/state');
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
            throw new Error(payload.error || 'Request failed.');
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
            return `<img src="${escapeHtml(person.avatar)}" class="${className}" alt="${name}">`;
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
                    primaryAction = '<span class="project-shipped-note"><i class="fa-solid fa-rocket"></i> Shipped — counts toward your club level</span>';
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
                        <span class="shop-price">${escapeHtml(item.cost)}</span>
                        <button class="btn-secondary small" type="button" data-add-cart="${escapeHtml(item.id)}">Add</button>
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
                            <span>${escapeHtml(item.cost || '')}</span>
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

        if (empty) empty.hidden = cart().length > 0;
        if (checkoutButton) checkoutButton.disabled = cart().length === 0;
        renderOrders();
        renderItemRequests();
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

    function renderNewsletters() {
        if (page !== 'newsletters') return;
        removeSkeletons('newsletters');
        const list = $('#newsletterList');
        const archive = newsletters();
        const prefs = settings();
        if (!selectedNewsletterId && archive.length) {
            selectedNewsletterId = archive[0].id;
        }
        $('#newsletterSubscribe').checked = Boolean(prefs.newsletterSubscribed);

        if (list) {
            list.innerHTML = archive.map((dispatch, index) => `
                <button class="newsletter-row ${dispatch.id === selectedNewsletterId ? 'active' : ''}" type="button" data-open-dispatch="${escapeHtml(dispatch.id)}" style="--card-index: ${index}">
                    <span class="read-dot ${dispatch.read ? 'read' : ''}" aria-hidden="true"></span>
                    <span>
                        <strong>${escapeHtml(dispatch.title)}</strong>
                        <small>${escapeHtml(dispatch.excerpt)}</small>
                    </span>
                    <em>${escapeHtml(dispatch.readTime)}</em>
                </button>
            `).join('');
        }
        renderNewsletterReader();
    }

    function renderNewsletterReader() {
        const dispatch = newsletters().find((item) => item.id === selectedNewsletterId);
        const button = $('#toggleReadButton');
        if (!dispatch) return;
        $('#newsletterReadTime').textContent = dispatch.readTime || 'Dispatch';
        $('#newsletterTitle').textContent = dispatch.title || 'Untitled dispatch';
        $('#newsletterDate').textContent = formatDate(dispatch.date);
        $('#newsletterBody').textContent = dispatch.body || dispatch.excerpt || '';
        if (button) {
            button.hidden = false;
            button.textContent = dispatch.read ? 'Mark unread' : 'Mark read';
        }
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
            icon: 'fa-solid fa-right-to-bracket',
            tone: 'green',
            title: 'Sign in to the Leaders Portal',
            subtitle: "You're in! Your Hack Club identity is connected.",
            link: null,
        },
        {
            id: 'slack',
            icon: 'fa-brands fa-slack',
            tone: 'red',
            title: 'Set up your club on Slack',
            subtitle: 'Join the Hack Club Slack and connect with other leaders.',
            link: 'https://hackclub.slack.com/',
        },
        {
            id: 'ysws',
            icon: 'fa-solid fa-rocket',
            tone: 'blue',
            title: 'Apply for a YSWS grant',
            subtitle: 'Run a project and earn hardware for your club.',
            link: 'https://ysws.hackclub.com/',
        },
        {
            id: 'hcb',
            icon: 'fa-solid fa-piggy-bank',
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
                        <i class="fa-solid fa-calendar-check"></i>
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
                    <i class="${done[item.id] ? 'fa-solid fa-check' : item.icon}"></i>
                </button>
                <div class="activity-content">
                    <h4 class="activity-title">${item.title}</h4>
                    <p class="activity-subtitle">${item.subtitle}</p>
                </div>
                ${item.link ? `
                    <a class="badge badge-up" href="${item.link}" target="_blank" rel="noopener noreferrer">
                        <i class="fa-solid fa-arrow-up-right-from-square"></i> Go
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

    // ── Chat ─────────────────────────────────────────────────────────────────
    // Channels + messages. All members read/post; leaders manage channels.
    // Live-ish via a 4s poll that pauses when the tab is hidden. Unread state
    // is per-device, kept in localStorage (not shared server state).

    const CHAT_READS_KEY = 'hcl:chatReads';
    const CHAT_POLL_MS = 4000;
    const CHAT_GROUP_MS = 5 * 60 * 1000;   // same-author messages within 5min render grouped
    const chatBaseTitle = document.title;  // restored when the tab regains focus
    let chatChannels = [];
    let chatActiveId = null;
    let chatLastFetch = null;   // newest message createdAt seen in active channel
    let chatPollTimer = null;
    let chatVisibilityBound = false;
    let chatLastMsgMeta = null; // { key, time } of last rendered message, for grouping
    let chatHiddenCount = 0;    // messages that arrived while the tab was hidden
    let chatJumpBtn = null;     // floating "jump to newest" button (created lazily)
    let chatJumpCount = 0;      // new messages accumulated while scrolled up
    let chatScrollBound = false;

    function chatReads() {
        try {
            return JSON.parse(localStorage.getItem(CHAT_READS_KEY) || '{}') || {};
        } catch (error) {
            return {};
        }
    }

    function markChannelRead(id, iso) {
        const reads = chatReads();
        reads[id] = iso || new Date().toISOString();
        try {
            localStorage.setItem(CHAT_READS_KEY, JSON.stringify(reads));
        } catch (error) {
            /* storage unavailable — non-fatal */
        }
    }

    function channelUnread(channel) {
        if (!channel.lastMessageAt || channel.id === chatActiveId) return false;
        const seen = chatReads()[channel.id];
        return !seen || channel.lastMessageAt > seen;
    }

    function chatTime(iso) {
        if (!iso) return '';
        const date = new Date(iso);
        if (Number.isNaN(date.getTime())) return '';
        return new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(date);
    }

    function chatFullTime(iso) {
        if (!iso) return '';
        const date = new Date(iso);
        if (Number.isNaN(date.getTime())) return '';
        return new Intl.DateTimeFormat(undefined, { dateStyle: 'full', timeStyle: 'short' }).format(date);
    }

    function renderChatTitle() {
        document.title = chatHiddenCount > 0 ? `(${chatHiddenCount}) ${chatBaseTitle}` : chatBaseTitle;
    }

    function clearChatUnreadTitle() {
        if (!chatHiddenCount) return;
        chatHiddenCount = 0;
        renderChatTitle();
    }

    function resetJumpButton() {
        chatJumpCount = 0;
        if (chatJumpBtn) chatJumpBtn.hidden = true;
    }

    function showJumpButton() {
        const btn = ensureJumpButton();
        if (!btn) return;
        btn.textContent = `↓ ${chatJumpCount} new`;
        btn.hidden = false;
    }

    function ensureJumpButton() {
        if (chatJumpBtn) return chatJumpBtn;
        const box = document.getElementById('chatMessages');
        if (!box) return null;
        const host = box.parentElement || box;
        if (window.getComputedStyle(host).position === 'static') host.style.position = 'relative';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'chat-jump-new';
        btn.hidden = true;
        btn.style.cssText = 'position:absolute;left:50%;transform:translateX(-50%);bottom:16px;'
            + 'z-index:5;padding:6px 14px;border:none;border-radius:999px;background:#ec3750;'
            + 'color:#fff;font:inherit;font-size:.82rem;font-weight:600;cursor:pointer;'
            + 'box-shadow:0 4px 12px rgba(0,0,0,.18);';
        btn.addEventListener('click', () => {
            scrollChatToBottom(true);
            resetJumpButton();
        });
        host.appendChild(btn);
        if (!chatScrollBound) {
            chatScrollBound = true;
            box.addEventListener('scroll', () => {
                if (box.scrollHeight - box.scrollTop - box.clientHeight < 40) resetJumpButton();
            });
        }
        chatJumpBtn = btn;
        return btn;
    }

    function renderChat() {
        if (page !== 'chat') return;
        removeSkeletons('chat');
        if (Array.isArray(dashboardState.channels)) chatChannels = dashboardState.channels;
        renderChannelList();

        if (chatActiveId && !chatChannels.some((channel) => channel.id === chatActiveId)) {
            chatActiveId = null;
            closeChatThread();
        }
        if (!chatActiveId && chatChannels.length) {
            selectChannel(chatChannels[0].id);
        }
        startChatPolling();
        bindChatVisibility();
        ensureJumpButton();
    }

    function renderChannelList() {
        const list = document.getElementById('chatChannelList');
        const emptyBox = document.getElementById('chatChannelsEmpty');
        if (!list) return;
        if (!chatChannels.length) {
            list.innerHTML = '';
            if (emptyBox) emptyBox.hidden = false;
            return;
        }
        if (emptyBox) emptyBox.hidden = true;
        list.innerHTML = chatChannels.map((channel) => {
            const active = channel.id === chatActiveId ? ' is-active' : '';
            const unread = channelUnread(channel)
                ? '<span class="chat-unread-dot" aria-label="Unread messages"></span>' : '';
            return `<button class="chat-channel${active}" type="button" data-channel="${escapeHtml(channel.id)}">
                <span class="chat-channel-name">#&nbsp;${escapeHtml(channel.name)}</span>${unread}
            </button>`;
        }).join('');
    }

    function selectChannel(id) {
        if (id === chatActiveId) return;
        chatActiveId = id;
        chatLastFetch = null;
        chatLastMsgMeta = null;
        resetJumpButton();
        const channel = chatChannels.find((item) => item.id === id);
        const msgs = document.getElementById('chatMessages');
        const head = document.getElementById('chatThreadHead');
        const composer = document.getElementById('chatComposer');
        const empty = document.getElementById('chatEmpty');
        if (empty) empty.hidden = true;
        if (head) head.hidden = false;
        if (msgs) { msgs.hidden = false; msgs.innerHTML = ''; }
        if (composer) composer.hidden = false;
        const nameEl = document.getElementById('chatThreadName');
        const descEl = document.getElementById('chatThreadDesc');
        if (nameEl) nameEl.textContent = '# ' + (channel?.name || '');
        if (descEl) descEl.textContent = channel?.description || '';
        renderChannelList();
        fetchMessages(id, true);
    }

    function closeChatThread() {
        const msgs = document.getElementById('chatMessages');
        const head = document.getElementById('chatThreadHead');
        const composer = document.getElementById('chatComposer');
        const empty = document.getElementById('chatEmpty');
        if (head) head.hidden = true;
        if (msgs) { msgs.hidden = true; msgs.innerHTML = ''; }
        if (composer) composer.hidden = true;
        if (empty) empty.hidden = false;
        chatLastFetch = null;
        chatLastMsgMeta = null;
        resetJumpButton();
    }

    function scrollChatToBottom(smooth) {
        const box = document.getElementById('chatMessages');
        if (!box) return;
        const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (smooth && !reduce && typeof box.scrollTo === 'function') {
            box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' });
        } else {
            box.scrollTop = box.scrollHeight;
        }
    }

    function appendMessage(message, opts) {
        opts = opts || {};
        const box = document.getElementById('chatMessages');
        if (!box) return null;
        // Skip messages already on screen (e.g. an optimistic send the poll re-fetches).
        if (message.id) {
            const existing = box.querySelector(`[data-mid="${window.CSS.escape(String(message.id))}"]`);
            if (existing) return null;
        }
        const person = { name: message.authorName, avatar: message.authorAvatar };
        const mine = (message.authorEmail || '').toLowerCase() === viewerEmail ? ' is-mine' : '';
        const authorKey = String(message.authorEmail || message.authorName || '').toLowerCase();
        const msgTime = new Date(message.createdAt).getTime();
        const grouped = chatLastMsgMeta
            && chatLastMsgMeta.key === authorKey
            && Number.isFinite(msgTime) && Number.isFinite(chatLastMsgMeta.time)
            && (msgTime - chatLastMsgMeta.time) >= 0
            && (msgTime - chatLastMsgMeta.time) <= CHAT_GROUP_MS;
        const row = document.createElement('div');
        row.className = 'chat-message' + mine + (grouped ? ' chat-message--grouped' : '')
            + (opts.pending ? ' chat-message--pending' : '');
        if (message.id) row.dataset.mid = String(message.id);
        if (opts.pending) row.style.opacity = '0.6';
        if (grouped) {
            row.innerHTML = `
            <div class="chat-message-body">
                <p class="chat-message-text">${escapeHtml(message.body)}</p>
            </div>`;
        } else {
            row.innerHTML = `
            ${avatarMarkup(person, 'avatar-sm')}
            <div class="chat-message-body">
                <div class="chat-message-meta">
                    <span class="chat-message-author">${escapeHtml(message.authorName || message.authorEmail || 'Member')}</span>
                    <span class="chat-message-time" title="${escapeHtml(chatFullTime(message.createdAt))}">${escapeHtml(chatTime(message.createdAt))}</span>
                </div>
                <p class="chat-message-text">${escapeHtml(message.body)}</p>
            </div>`;
        }
        box.appendChild(row);
        chatLastMsgMeta = { key: authorKey, time: Number.isFinite(msgTime) ? msgTime : Date.now() };
        return row;
    }

    async function fetchMessages(id, initial) {
        try {
            const query = chatLastFetch ? `?since=${encodeURIComponent(chatLastFetch)}` : '';
            const payload = await apiRequest(
                `/api/dashboard/chat/channels/${encodeURIComponent(id)}/messages${query}`);
            if (id !== chatActiveId) return;   // user switched channels mid-flight
            const incoming = payload.messages || [];
            if (!incoming.length) return;
            const box = document.getElementById('chatMessages');
            const distance = box
                ? (box.scrollHeight - box.scrollTop - box.clientHeight) : 0;
            const nearBottom = box ? (distance < 80) : true;
            const added = incoming.map((message) => appendMessage(message)).filter(Boolean);
            chatLastFetch = incoming[incoming.length - 1].createdAt || chatLastFetch;
            // Badge the tab title with messages that landed while it was hidden.
            if (document.hidden && added.length) {
                const others = added.filter(
                    (row) => !row.classList.contains('is-mine')).length;
                if (others) {
                    chatHiddenCount += others;
                    renderChatTitle();
                }
            }
            if (initial || nearBottom) {
                scrollChatToBottom();
                resetJumpButton();
            } else if (distance > 150 && added.length) {
                chatJumpCount += added.length;
                showJumpButton();
            }
            markChannelRead(id, chatLastFetch);
            const channel = chatChannels.find((item) => item.id === id);
            if (channel) channel.lastMessageAt = chatLastFetch;
            renderChannelList();
        } catch (error) {
            /* keep showing what we have; the next poll retries */
        }
    }

    async function refreshChannels() {
        try {
            const payload = await apiRequest('/api/dashboard/chat/channels');
            chatChannels = payload.channels || chatChannels;
            renderChannelList();
            if (chatActiveId && !chatChannels.some((channel) => channel.id === chatActiveId)) {
                chatActiveId = null;
                closeChatThread();
                if (chatChannels.length) selectChannel(chatChannels[0].id);
            }
        } catch (error) {
            /* transient — retry next tick */
        }
    }

    async function chatPoll() {
        if (document.hidden || page !== 'chat') return;
        await refreshChannels();
        if (chatActiveId) await fetchMessages(chatActiveId);
    }

    function startChatPolling() {
        if (chatPollTimer || page !== 'chat') return;
        chatPollTimer = window.setInterval(chatPoll, CHAT_POLL_MS);
    }

    function stopChatPolling() {
        if (chatPollTimer) {
            window.clearInterval(chatPollTimer);
            chatPollTimer = null;
        }
    }

    function bindChatVisibility() {
        if (chatVisibilityBound) return;
        chatVisibilityBound = true;
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                stopChatPolling();
            } else {
                clearChatUnreadTitle();
                if (page === 'chat') {
                    startChatPolling();
                    chatPoll();
                }
            }
        });
        window.addEventListener('focus', clearChatUnreadTitle);
    }

    function setChatDrawer(open) {
        const sidebar = document.querySelector('.chat-sidebar');
        const backdrop = document.getElementById('chatBackdrop');
        const toggle = document.getElementById('chatDrawerToggle');
        if (!sidebar) return;
        sidebar.classList.toggle('open', open);
        if (backdrop) backdrop.hidden = !open;
        if (toggle) toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    function toggleChatDrawer() {
        const sidebar = document.querySelector('.chat-sidebar');
        setChatDrawer(!(sidebar && sidebar.classList.contains('open')));
    }

    function closeChatDrawer() {
        setChatDrawer(false);
    }

    function prepareNewChannel() {
        const form = $('#channelForm');
        if (!form) return;
        form.reset();
        form.elements.id.value = '';
        $('#channelModalTitle').textContent = 'New channel';
        $('#deleteChannelButton').hidden = true;
        setFormError('channelFormError', '');
    }

    function prepareEditChannel(id) {
        const channel = chatChannels.find((item) => item.id === id);
        const form = $('#channelForm');
        if (!channel || !form) return;
        form.elements.id.value = channel.id;
        form.elements.name.value = channel.name || '';
        form.elements.description.value = channel.description || '';
        $('#channelModalTitle').textContent = 'Edit channel';
        $('#deleteChannelButton').hidden = false;
        setFormError('channelFormError', '');
    }

    function renderPage() {
        renderHome();
        renderTeam();
        renderEvents();
        renderShips();
        renderProjects();
        renderLevels();
        renderJoinLink();
        renderShop();
        renderNewsletters();
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

    async function adminProjectAction(trigger, status, message) {
        const [clubKey, projectId] = String(trigger.dataset.adminProject || '').split('::');
        if (!clubKey || !projectId) return;
        trigger.disabled = true;
        try {
            await apiRequest(`/api/admin/projects/${encodeURIComponent(clubKey)}/${encodeURIComponent(projectId)}`, {
                method: 'PATCH',
                body: { status },
            });
            showToast(message);
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
                await adminProjectAction(approveProject, 'Shipped', 'Project approved — shipped!');
                return;
            }
            const rejectProject = event.target.closest('[data-reject-project]');
            if (rejectProject) {
                await adminProjectAction(rejectProject, 'Draft', 'Project sent back to draft.');
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
                if (!chatActiveId) return;
                prepareEditChannel(chatActiveId);
                openModal('channelModal');
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
                const dispatch = newsletters().find((item) => item.id === selectedNewsletterId);
                renderNewsletters();
                if (dispatch && !dispatch.read) {
                    try {
                        await apiRequest(`/api/dashboard/newsletters/${dispatch.id}`, {
                            method: 'PATCH',
                            body: { read: true },
                        });
                    } catch (error) {
                        showToast(error.message, 'error');
                    }
                }
            }
        });

        document.addEventListener('keydown', (event) => {
            if (event.key !== 'Escape') return;
            $$('.modal-backdrop.is-open').forEach(closeModal);
            closeChatDrawer();
        });
    }

    function setupForms() {
        $('#chatComposer')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const input = event.currentTarget.elements.body;
            const body = (input.value || '').trim();
            if (!body || !chatActiveId) return;
            const channelId = chatActiveId;
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
                if (channelId !== chatActiveId) return;   // switched channels mid-flight
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
                if (real && real.createdAt && (!chatLastFetch || real.createdAt > chatLastFetch)) {
                    chatLastFetch = real.createdAt;
                    markChannelRead(channelId, chatLastFetch);
                }
            } catch (error) {
                if (pending) pending.remove();
                input.value = body;   // restore so the user doesn't lose their text
                showToast(error.message, 'error');
            }
        });

        $('#channelForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const id = form.elements.id.value;
            const body = {
                name: form.elements.name.value,
                description: form.elements.description.value,
            };
            setFormError('channelFormError', '');
            try {
                if (id) {
                    await apiRequest(`/api/dashboard/chat/channels/${encodeURIComponent(id)}`, {
                        method: 'PATCH', body,
                    });
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
                if (chatActiveId === id) {
                    chatActiveId = null;
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
            const dispatch = newsletters().find((item) => item.id === selectedNewsletterId);
            if (!dispatch) return;
            try {
                await apiRequest(`/api/dashboard/newsletters/${dispatch.id}`, {
                    method: 'PATCH',
                    body: { read: !dispatch.read },
                });
                showToast(dispatch.read ? 'Marked unread.' : 'Marked read.');
            } catch (error) {
                showToast(error.message, 'error');
            }
        });

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
            window.i18n.apply(pref);
        }
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
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}());
