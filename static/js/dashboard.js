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
            ${orders().slice(0, 3).map((order) => `
                <div class="order-row">
                    <span>${escapeHtml(formatDate(order.date))}</span>
                    <strong>${order.items.reduce((total, item) => total + Number(item.quantity || 0), 0)} items</strong>
                </div>
            `).join('')}
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

    function prepareNewDispatch() {
        const form = $('#dispatchForm');
        if (!form) return;
        form.reset();
        form.elements.readTime.value = '2 min read';
        setFormError('dispatchFormError', '');
    }

    function renderSettings() {
        if (page !== 'settings') return;
        const prefs = settings();
        const avatar = $('#clubPreviewAvatar');
        $('#clubPreviewName').textContent = prefs.clubName || 'Hack Club';
        $('#clubPreviewLocation').textContent = prefs.location || 'Location TBD';
        if (avatar) {
            avatar.textContent = initials(prefs.clubName || 'Hack Club');
            avatar.style.backgroundImage = prefs.avatar ? `url("${prefs.avatar}")` : '';
            avatar.classList.toggle('has-image', Boolean(prefs.avatar));
        }
    }

    function renderPage() {
        renderTeam();
        renderEvents();
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
            try {
                await apiRequest('/api/dashboard/newsletter-subscription', {
                    method: 'PATCH',
                    body: { subscribed: event.currentTarget.checked },
                });
                showToast(event.currentTarget.checked ? 'Subscription enabled.' : 'Subscription paused.');
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
                if (data.darkModeDefault) {
                    localStorage.setItem('mode', 'dark');
                    document.body.classList.add('dark-mode');
                    $('#toggleBtn')?.classList.add('active');
                }
                if (stateLabel) stateLabel.textContent = 'Saved';
                showToast('Settings saved.');
            } catch (error) {
                setFormError('settingsFormError', error.message);
                if (stateLabel) stateLabel.textContent = '';
            }
        });
    }

    function init() {
        setupGlobalEvents();
        setupForms();
        renderPage();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}());
