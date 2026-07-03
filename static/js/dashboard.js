(function () {
    const stateNode = document.getElementById('dashboard-state');
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const pageNode = document.querySelector('[data-dashboard-page]');
    const page = pageNode?.dataset.dashboardPage || '';

    let dashboardState = {};
    let selectedNewsletterId = '';

    try {
        dashboardState = JSON.parse(stateNode?.textContent || '{}') || {};
    } catch (error) {
        dashboardState = {};
    }

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

    function orders() {
        return dashboardState.orders || [];
    }

    function newsletters() {
        return dashboardState.newsletters || [];
    }

    function ships() {
        return dashboardState.ships || [];
    }

    // Club levels mirror leaders.hackclub.com: 4 ships → Level 2, 8 → Level 3.
    const LEVEL_THRESHOLDS = [0, 4, 8];

    function clubLevel() {
        const count = ships().length;
        if (count >= LEVEL_THRESHOLDS[2]) return 3;
        if (count >= LEVEL_THRESHOLDS[1]) return 2;
        return 1;
    }

    function levelProgress() {
        const count = ships().length;
        const level = clubLevel();
        if (level === 3) {
            return { level, count, next: null, remaining: 0, percent: 100 };
        }
        const floor = LEVEL_THRESHOLDS[level - 1];
        const ceiling = LEVEL_THRESHOLDS[level];
        return {
            level,
            count,
            next: level + 1,
            remaining: ceiling - count,
            percent: Math.round(((count - floor) / (ceiling - floor)) * 100),
        };
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

    function setState(nextState) {
        dashboardState = nextState || dashboardState;
        renderPage();
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

    function renderTeam() {
        if (page !== 'team') return;
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
        roster.innerHTML = people.map((member) => `
            <article class="item-card member-card">
                <div class="member-card-top">
                    ${avatarMarkup(member)}
                    <span class="badge-role ${roleClass(member.role)}">${escapeHtml(member.role)}</span>
                </div>
                <h3>${escapeHtml(member.name)}</h3>
                <p>${escapeHtml(member.email)}</p>
                <div class="card-footer-line">
                    <span class="status-chip">${escapeHtml(member.status || 'Active')}</span>
                    <button class="text-button" type="button" data-edit-member="${escapeHtml(member.id)}">Edit</button>
                </div>
            </article>
        `).join('');
        empty.hidden = people.length > 0;
    }

    function prepareNewEvent() {
        const form = $('#eventForm');
        if (!form) return;
        form.reset();
        form.elements.id.value = '';
        form.elements.type.value = 'Workshop';
        form.elements.attendees.value = '12';
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
        form.elements.rsvp.checked = Boolean(event.rsvp);
        $('#eventModalTitle').textContent = 'Edit event';
        $('#deleteEventButton').hidden = false;
        setFormError('eventFormError', '');
        openModal('eventModal');
    }

    function renderEvents() {
        if (page !== 'events') return;
        const list = $('#eventList');
        const empty = $('#eventsEmpty');
        const upcoming = events();
        const rsvps = upcoming.filter((event) => event.rsvp).length;
        const attendees = upcoming.reduce((total, event) => total + Number(event.attendees || 0), 0);

        $('#eventTotal').textContent = upcoming.length;
        $('#rsvpTotal').textContent = rsvps;
        $('#attendeeTotal').textContent = attendees;

        if (!list) return;
        list.innerHTML = upcoming.map((event, index) => `
            <article class="timeline-item ${event.rsvp ? 'is-rsvped' : ''}">
                <div class="timeline-date">
                    <strong>${escapeHtml(formatDate(event.date).split(',')[0])}</strong>
                    <span>${escapeHtml(formatTime(event.time))}</span>
                </div>
                <div class="timeline-body">
                    <div>
                        <h3>${escapeHtml(event.title)}</h3>
                        <p>${escapeHtml(event.location)} · ${escapeHtml(event.type || 'Event')} · ${Number(event.attendees || 0)} expected</p>
                    </div>
                    <div class="timeline-actions">
                        ${index === 0 ? '<span class="badge badge-up">Next up</span>' : ''}
                        <button class="btn-secondary small" type="button" data-toggle-rsvp="${escapeHtml(event.id)}">${event.rsvp ? 'RSVPed' : 'RSVP'}</button>
                        <button class="text-button" type="button" data-edit-event="${escapeHtml(event.id)}">Edit</button>
                    </div>
                </div>
            </article>
        `).join('');
        empty.hidden = upcoming.length > 0;
    }

    function renderShips() {
        if (page !== 'ships') return;
        const list = $('#shipList');
        const empty = $('#shipsEmpty');
        const progress = levelProgress();

        $('#shipTotal').textContent = progress.count;
        $('#shipLevel').textContent = progress.level;
        $('#shipToNext').textContent = progress.next ? progress.remaining : '—';

        if (!list) return;
        list.innerHTML = ships().map((ship) => `
            <article class="timeline-item ship-item">
                <div class="timeline-date">
                    <strong>${escapeHtml(formatDate(ship.date).split(',')[0])}</strong>
                    <span>${escapeHtml(ship.member)}</span>
                </div>
                <div class="timeline-body">
                    <div>
                        <h3>${escapeHtml(ship.title)}</h3>
                        ${ship.url ? `<p><a class="text-button" href="${escapeHtml(ship.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(ship.url)}</a></p>` : ''}
                    </div>
                    <div class="timeline-actions">
                        <span class="badge badge-up">Shipped</span>
                        <button class="text-button" type="button" data-delete-ship="${escapeHtml(ship.id)}">Remove</button>
                    </div>
                </div>
            </article>
        `).join('');
        empty.hidden = ships().length > 0;
    }

    function renderLevels() {
        if (page !== 'levels') return;
        const progress = levelProgress();

        $('#levelCurrentName').textContent = `Level ${progress.level}`;
        $('#levelShipCount').textContent = `${progress.count} ${progress.count === 1 ? 'ship' : 'ships'} completed`;
        $('#levelProgressFill').style.width = `${progress.percent}%`;
        $('#levelProgressTrack')?.setAttribute('aria-valuenow', progress.percent);
        $('#levelProgressText').textContent = progress.next
            ? `Ship ${progress.remaining} more project${progress.remaining === 1 ? '' : 's'} to reach Level ${progress.next}.`
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

    function renderShop() {
        if (page !== 'shop') return;
        const grid = $('#shopGrid');
        const list = $('#cartList');
        const empty = $('#cartEmpty');
        const checkoutButton = $('#checkoutButton');
        const totalQuantity = cart().reduce((total, item) => total + Number(item.quantity || 0), 0);

        $('#cartCount').textContent = totalQuantity;
        $('#cartSummary').textContent = totalQuantity
            ? `${totalQuantity} ${totalQuantity === 1 ? 'item' : 'items'} ready to request.`
            : 'No items yet.';

        if (grid) {
            grid.innerHTML = shopItems().map((item) => `
                <article class="item-card shop-card">
                    <div class="product-mark product-${escapeHtml(item.accent || 'red')}">${escapeHtml(initials(item.name))}</div>
                    <h3>${escapeHtml(item.name)}</h3>
                    <p>${escapeHtml(item.description)}</p>
                    <div class="card-footer-line">
                        <span class="shop-price">${escapeHtml(item.price)}</span>
                        <button class="btn-secondary small" type="button" data-add-cart="${escapeHtml(item.id)}">${escapeHtml(item.action || 'Add')}</button>
                    </div>
                </article>
            `).join('');
        }

        if (list) {
            list.innerHTML = cart().map((entry) => {
                const item = shopItem(entry.id) || {};
                return `
                    <article class="cart-item">
                        <div>
                            <strong>${escapeHtml(item.name || entry.id)}</strong>
                            <span>${escapeHtml(item.price || '')}</span>
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

        empty.hidden = cart().length > 0;
        checkoutButton.disabled = cart().length === 0;
        renderOrders();
    }

    function renderOrders() {
        const history = $('#orderHistory');
        if (!history) return;
        if (!orders().length) {
            history.innerHTML = '';
            return;
        }
        history.innerHTML = `
            <h3>Recent requests</h3>
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
        const list = $('#newsletterList');
        const archive = newsletters();
        const prefs = settings();
        if (!selectedNewsletterId && archive.length) {
            selectedNewsletterId = archive[0].id;
        }
        $('#newsletterSubscribe').checked = Boolean(prefs.newsletterSubscribed);

        if (list) {
            list.innerHTML = archive.map((dispatch) => `
                <button class="newsletter-row ${dispatch.id === selectedNewsletterId ? 'active' : ''}" type="button" data-open-dispatch="${escapeHtml(dispatch.id)}">
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
        button.hidden = false;
        button.textContent = dispatch.read ? 'Mark unread' : 'Mark read';
    }

    function prepareNewShip() {
        const form = $('#shipForm');
        if (!form) return;
        form.reset();
        form.elements.date.value = new Date().toISOString().slice(0, 10);
        setFormError('shipFormError', '');
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
        const prefs = settings();
        const people = members();
        const upcoming = events();

        $('#homeClubName').textContent = prefs.clubName || 'Your club';
        $('#homeMemberTotal').textContent = people.length;
        $('#homeClubMeta').textContent = `${people.length === 1 ? 'member' : 'members'} at ${prefs.location || 'your school'}`;
        $('#homeEventTotal').textContent = upcoming.length;
        $('#homeRsvpTotal').textContent = upcoming.filter((event) => event.rsvp).length;
        $('#homeOrderTotal').textContent = orders().length;
        $('#homeShipTotal').textContent = ships().length;

        const progress = levelProgress();
        $('#homeLevelName').textContent = `Level ${progress.level}`;
        $('#homeLevelFill').style.width = `${progress.percent}%`;
        $('#homeLevelText').textContent = progress.next
            ? `${progress.remaining} more ${progress.remaining === 1 ? 'ship' : 'ships'} to Level ${progress.next}`
            : 'Max level reached!';

        $('#homeRosterTotal').textContent = people.length;
        const leaders = people.filter((member) => member.role === 'Leader').length;
        const mentors = people.filter((member) => member.role === 'Mentor').length;
        const plain = people.length - leaders - mentors;
        $('#homeRosterBreakdown').textContent = people.length
            ? `${leaders} ${leaders === 1 ? 'leader' : 'leaders'} · ${plain} ${plain === 1 ? 'member' : 'members'} · ${mentors} ${mentors === 1 ? 'mentor' : 'mentors'}`
            : 'Invite your first member from the Team page.';
        const donut = $('#homeRosterDonut');
        if (donut && people.length) {
            const leaderPct = Math.round((leaders / people.length) * 100);
            const memberPct = leaderPct + Math.round((plain / people.length) * 100);
            donut.style.background = `conic-gradient(var(--hackclub-red) 0% ${leaderPct}%, #ff8c37 ${leaderPct}% ${memberPct}%, #338eda ${memberPct}% 100%)`;
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

    function renderPage() {
        renderHome();
        renderTeam();
        renderEvents();
        renderShips();
        renderLevels();
        renderJoinLink();
        renderShop();
        renderNewsletters();
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

    function setupGlobalEvents() {
        document.addEventListener('click', async (event) => {
            const openTrigger = event.target.closest('[data-open-modal]');
            if (openTrigger) {
                const modalId = openTrigger.dataset.openModal;
                if (modalId === 'memberModal') prepareNewMember();
                if (modalId === 'eventModal') prepareNewEvent();
                if (modalId === 'dispatchModal') prepareNewDispatch();
                if (modalId === 'shipModal') prepareNewShip();
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

            const addCart = event.target.closest('[data-add-cart]');
            if (addCart) {
                try {
                    await apiRequest('/api/dashboard/cart', {
                        method: 'POST',
                        body: { itemId: addCart.dataset.addCart, quantity: 1 },
                    });
                    showToast('Added to request cart.');
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

            const deleteShip = event.target.closest('[data-delete-ship]');
            if (deleteShip) {
                try {
                    await apiRequest(`/api/dashboard/ships/${deleteShip.dataset.deleteShip}`, { method: 'DELETE' });
                    showToast('Ship removed.');
                } catch (error) {
                    showToast(error.message, 'error');
                }
                return;
            }

            const checkToggle = event.target.closest('[data-check-item]');
            if (checkToggle) {
                const saved = checklistState();
                const id = checkToggle.dataset.checkItem;
                saved[id] = !saved[id];
                localStorage.setItem('leadersChecklist', JSON.stringify(saved));
                renderChecklist();
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
        });
    }

    function setupForms() {
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

        $('#shipForm')?.addEventListener('submit', async (event) => {
            event.preventDefault();
            setFormError('shipFormError', '');
            try {
                await apiRequest('/api/dashboard/ships', {
                    method: 'POST',
                    body: formObject(event.currentTarget),
                });
                closeModal('shipModal');
                showToast('Ship logged. 🚀');
            } catch (error) {
                setFormError('shipFormError', error.message);
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

        $('#checkoutButton')?.addEventListener('click', async () => {
            try {
                await apiRequest('/api/dashboard/checkout', { method: 'POST' });
                showToast('Request submitted.');
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
                if (stateLabel) stateLabel.textContent = 'Saved';
                showToast('Settings saved.');
            } catch (error) {
                setFormError('settingsFormError', error.message);
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

    function applyDarkModeDefault() {
        // dark-mode.js only knows localStorage; when the visitor has no saved
        // preference yet, fall back to the club's saved setting.
        if (localStorage.getItem('mode') === null && settings().darkModeDefault) {
            document.body.classList.add('dark-mode');
            $('#toggleBtn')?.classList.add('active');
        }
    }

    function init() {
        setupGlobalEvents();
        setupForms();
        applyDarkModeDefault();
        initBackground();
        renderPage();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}());
