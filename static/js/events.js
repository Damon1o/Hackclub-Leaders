(function () {
    const toolboxEvents = window.toolboxEvents || [];

    const searchInput = document.getElementById('search-input');
    const searchForm = document.getElementById('events-search-form');
    const filterTags = document.querySelectorAll('.filter-tag');
    const list = document.getElementById('events-list');

    if (!list || !searchInput) return;

    let cards = [];
    let activeFilter = 'all';
    let searchQuery = '';

    const clockIcon = `
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
            stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <polyline points="12 6 12 12 16 14"></polyline>
        </svg>`;

    const calendarIcon = `
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
            stroke-linejoin="round">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="16" y1="2" x2="16" y2="6"></line>
            <line x1="8" y1="2" x2="8" y2="6"></line>
            <line x1="3" y1="10" x2="21" y2="10"></line>
        </svg>`;

    const locationIcon = `
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
            stroke-linejoin="round">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
            <circle cx="12" cy="10" r="3"></circle>
        </svg>`;

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function createCard(event) {
        const card = document.createElement('a');
        card.href = event.url;
        card.target = '_blank';
        card.className = 'event-card';
        card.dataset.tags = event.tags.join(',');

        const style = event.backgroundColor !== 'N/A'
            ? `style="--event-image-fit: ${event.imageFit}; background-color: ${event.backgroundColor};"`
            : `style="--event-image-fit: ${event.imageFit};"`;

        if (event.borderColor !== 'N/A') {
            card.style.border = `2px solid ${event.borderColor}`;
        }

        const visualContent = event.logo !== 'N/A'
            ? `<img src="${escapeHtml(event.logo)}" alt="${escapeHtml(event.title)} logo" class="event-card-logo">`
            : (event.image === 'N/A' ? `<span class="event-card-fallback">${escapeHtml(event.title)}</span>` : '');

        card.innerHTML = `
            <div class="event-card-visual" ${style}>
                ${visualContent}
            </div>
            <div class="event-card-body">
                <div class="event-card-type">${escapeHtml(event.type)}</div>
                <h3 class="event-card-title">${escapeHtml(event.title)}</h3>
                <p class="event-card-description">${escapeHtml(event.description)}</p>
                <div class="event-card-meta">
                    <div class="event-card-meta-item">
                        ${clockIcon}
                        <span>${escapeHtml(event.duration)}</span>
                    </div>
                    <div class="event-card-meta-item">
                        ${calendarIcon}
                        <span>${escapeHtml(event.timeline)}</span>
                    </div>
                    <div class="event-card-meta-item">
                        ${locationIcon}
                        <span>${escapeHtml(event.where)}</span>
                    </div>
                </div>
            </div>
            <div class="event-card-footer">
                <span class="event-card-register">${escapeHtml(event.cta)}</span>
            </div>
        `;

        // Backgrounds are heavy (~100 KB - 2 MB each) — only apply them once
        // the card is about to scroll into view. The background-color above
        // keeps the card filled until then, so there's no layout shift.
        if (event.image !== 'N/A') {
            card.dataset.bg = event.image;
        }
        return card;
    }

    function applyFilters() {
        let visibleCount = 0;
        cards.forEach(card => {
            const tags = card.dataset.tags.split(',');
            const title = (card.querySelector('.event-card-title')?.textContent ?? '').toLowerCase();
            const desc = (card.querySelector('.event-card-description')?.textContent ?? '').toLowerCase();

            const matchesFilter = activeFilter === 'all' || tags.includes(activeFilter);
            const matchesSearch = !searchQuery || title.includes(searchQuery) || desc.includes(searchQuery);

            if (matchesFilter && matchesSearch) {
                card.style.display = 'flex';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });

        let empty = document.getElementById('events-empty');
        if (visibleCount === 0) {
            if (!empty) {
                empty = document.createElement('div');
                empty.id = 'events-empty';
                empty.className = 'events-empty';
                empty.innerHTML = '<p>No events match your search. Try a different filter or keyword.</p>';
                list.appendChild(empty);
            }
        } else if (empty) {
            empty.remove();
        }
    }

    toolboxEvents.forEach(event => {
        const card = createCard(event);
        list.appendChild(card);
        cards.push(card);
    });

    // Reveal a card's deferred background once it nears the viewport.
    const bgObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (!entry.isIntersecting) return;
            const card = entry.target;
            const visual = card.querySelector('.event-card-visual');
            if (visual && card.dataset.bg) {
                visual.style.backgroundImage = `url('${card.dataset.bg}')`;
            }
            delete card.dataset.bg;
            bgObserver.unobserve(card);
        });
    }, { rootMargin: '200px' });
    cards.forEach(card => {
        if (card.dataset.bg) bgObserver.observe(card);
    });

    filterTags.forEach(tag => {
        tag.addEventListener('click', () => {
            filterTags.forEach(t => t.classList.remove('active'));
            tag.classList.add('active');
            activeFilter = tag.dataset.filter;
            applyFilters();
        });
    });

    searchInput.addEventListener('input', () => {
        searchQuery = searchInput.value.trim().toLowerCase();
        applyFilters();
    });

    searchForm.addEventListener('submit', event => event.preventDefault());
})();