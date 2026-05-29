(function () {
    function ysws(event) {
        return {
            ...event,
            type: 'YSWS',
            tags: ['ysws', 'global',].concat(event.tags || []),
            cta: event.cta || 'Explore &rarr;',
            duration: 'FOREVER',
            where: event.where || 'Online'
        };
    }

    const toolboxEvents = [
        ysws({
            title: 'Stack',
            type: 'YSWS',
            tags: ['games'],
            description: 'Build a fun or completely unhinged project, and we’ll send you FREE LEGO sets of your choice.',
            image: '/static/images/events/stack/stack-background.png',
            logo: '/static/images/events/stack/stack.png',
            url: 'https://stack.hackclub.com/?utm_source=toolbox',
            timeline: 'Deadline: N/A',
            where: 'Online',
        }),
        {
            title: 'Macondo',
            type: 'Hackathon',
            tags: ['hackathon', 'travel'],
            description: 'Make projects, win free prizes, and fly to Bogota, Colombia.',
            image: '/static/images/events/macondo/macondo-background.png',
            logo: '/static/images/events/macondo/macondo-icon.png',
            url: 'https://macondo.hackclub.com/?utm_source=toolbox',
            duration: '3-day hackathon',
            timeline: 'Deadline: September 2026',
            where: 'Bogota, Colombia',

        },
        {
            title: 'Fallout',
            type: 'Hackathon',
            tags: ['hackathon', 'hardware', 'travel'],
            description: 'Build hardware projects and visit Shenzhen, China.',
            image: '/static/images/events/fallout/fallout-heidi.gif',
            backgroundColor: '#38c9ff',
            imageFit: 'contain',
            url: 'https://fallout.hackclub.com?utm_source=toolbox',
            duration: '60 hours of hardware projects',
            timeline: 'Deadline: July 1, 2026',
            where: 'Shenzhen, China',

        },
        {
            title: 'Stasis',
            type: 'Hackathon',
            tags: ['hackathon', 'hardware', 'travel'],
            description: 'Build hardware projects and fly out to Austin, TX for a hardware hackathon.',
            image: '/static/images/events/stasis/stasis-banner.png',
            logo: '/static/images/events/stasis/stasis-logo.png',
            url: 'https://stasis.hackclub.com?utm_source=toolbox',
            duration: 'May 15-18 hardware sprint',
            timeline: 'Deadline: May 18, 2026',
            where: 'Austin, TX',

        },
        {
            title: 'Beest',
            type: 'Hackathon',
            tags: ['hackathon', 'travel'],
            description: 'Code projects, fly to the Netherlands, and build a mechanical animal.',
            image: '/static/images/events/beest/beest-background.webp',
            logo: '/static/images/events/beest/beest-icon.webp',
            url: 'https://beest.hackclub.com?utm_source=toolbox',
            duration: 'Week-long hackathon',
            timeline: 'Event: July 10-15',
            where: 'Netherlands',

        },
        {
            title: 'Horizons',
            type: 'Hackathon',
            tags: ['hackathon', 'global'],
            description: 'Seven hackathons run by teenagers across the globe, for teenagers everywhere.',
            image: '/static/images/events/horizons/horizons-background.png',
            logo: '/static/images/events/horizons/horizons-logo.png',
            url: 'https://horizons.hackclub.com?utm_source=toolbox',
            duration: '7 global hackathons',
            timeline: 'Deadline: August 14, 2026',
            where: 'Global',

        },

        ysws({
            title: 'Boba Drops',
            type: 'YSWS',
            tags: ['ysws', 'global', 'web'],
            description: 'Build a website using HTML and CSS, then get free boba.',
            image: '/static/images/ysws/webdev/boba.png',
            backgroundColor: '#C76B0F',
            imageFit: 'contain',
            url: 'https://boba.hackclub.com',

        }),
        ysws({
            title: 'Swirl',
            type: 'YSWS',
            tags: ['ysws', 'global', 'web'],
            description: 'Build a cooler HTML and CSS website with a unique feature, then get free ice cream.',
            image: '/static/images/ysws/webdev/swirl.svg',
            backgroundColor: '#fde09d',
            imageFit: 'contain',
            url: 'https://swirl.hackclub.com',

        }),
        ysws({
            title: 'Toppings',
            type: 'YSWS',
            tags: ['ysws', 'global', 'web'],
            description: 'Add extra flavor to your website with CSS and get toppings for ice cream or boba.',
            image: '/static/images/ysws/webdev/toppings.png',
            backgroundColor: '#ffcc00',
            imageFit: 'contain',
            url: 'https://toppings.hackclub.com',

        }),
        ysws({
            title: 'Flavorless',
            type: 'YSWS',
            tags: ['ysws', 'global', 'web'],
            description: 'Build a website using only HTML and JavaScript. No CSS allowed.',
            image: '/static/images/ysws/webdev/flavorless.png',
            backgroundColor: '#ffffff',
            imageFit: 'contain',
            url: 'https://flavorless.hackclub.com/?utm_source=webdev',

        }),
        ysws({
            title: 'Waffles',
            type: 'YSWS',
            tags: ['ysws', 'global', 'web'],
            description: 'Make a website that uses JavaScript, and get free waffles.',
            image: '/static/images/ysws/webdev/waffles.jpg',
            backgroundColor: '#f8b84f',
            imageFit: 'cover',
            url: 'https://waffles.hackclub.com',

        }),
        ysws({
            title: 'Grub',
            type: 'YSWS',
            tags: ['ysws', 'global', 'web'],
            description: 'Build a website using Tailwind CSS, and get free junk food.',
            image: '/static/images/ysws/webdev/grub.png',
            backgroundColor: '#c10007',
            imageFit: 'contain',
            url: 'https://grub.hackclub.com',

        }),
        ysws({
            title: 'Reactive',
            type: 'YSWS',
            tags: ['ysws', 'global', 'web'],
            description: 'Make a website with React, and get a free domain to host it.',
            image: '/static/images/ysws/webdev/reactive.png',
            backgroundColor: '#112a4f',
            imageFit: 'contain',
            url: 'https://reactive.hackclub.dev',

        }),
        ysws({
            title: 'Slushies',
            type: 'YSWS',
            tags: ['ysws', 'global', 'web'],
            description: 'Make a web app using Flask, and get a slushie or another food item.',
            image: '/static/images/ysws/webdev/slushies.png',
            backgroundColor: '#4E9CDB',
            imageFit: 'contain',
            url: 'https://slushies.hackclub.com',

        }),

        ysws({
            title: 'BakeBuild',
            type: 'YSWS',
            tags: ['ysws', 'global', 'cad'],
            description: 'Design a cookie cutter, then get it shipped to you with a cookie.',
            image: '/static/images/ysws/cad/bakebuild.png',
            backgroundColor: '#C76B0F',
            imageFit: 'contain',
            url: 'https://bakebuild.hackclub.com',

        }),
        ysws({
            title: 'FuseRing',
            type: 'YSWS',
            tags: ['ysws', 'global', 'cad'],
            description: 'Design a keyring, then get your keyring and a clip for your backpack.',
            image: '/static/images/ysws/cad/fusering.svg',
            backgroundColor: '#FFA35E',
            imageFit: 'contain',
            url: 'https://fusering.hackclub.com/',

        }),
        ysws({
            title: 'Enclosure',
            type: 'YSWS',
            tags: ['ysws', 'global', 'cad', 'hardware'],
            description: 'Make enclosures for your devices or hardware and get them printed.',
            image: '/static/images/ysws/cad/enclosure.png',
            backgroundColor: '#341C10',
            imageFit: 'contain',
            url: 'https://enclosure.hackclub.com',

        }),
        ysws({
            title: 'Squeak',
            type: 'YSWS',
            tags: ['ysws', 'global', 'cad', 'hardware'],
            description: 'Design your own mouse case and get parts to build your own mouse.',
            image: '/static/images/ysws/cad/squeak.png',
            backgroundColor: '#0e305b',
            imageFit: 'contain',
            url: 'https://blueprint.hackclub.com/starter-projects/squeak',

        }),
        ysws({
            title: 'Construct',
            type: 'YSWS',
            tags: ['ysws', 'global', 'cad'],
            description: 'As a group, spend 50 hours making CAD projects and get a 3D printer for your club.',
            image: '/static/images/ysws/cad/construct.png',
            backgroundColor: '#b64e07',
            imageFit: 'contain',
            url: 'https://construct.hackclub.com/dashboard/clubs',

        }),

        ysws({
            title: 'Sprig',
            type: 'YSWS',
            tags: ['ysws', 'global', 'games'],
            description: 'Build a JavaScript game and play it on your own console.',
            image: '/static/images/ysws/sprig.png',
            backgroundColor: '#000',
            imageFit: 'contain',
            url: 'https://sprig.hackclub.com',

        }),
        ysws({
            title: 'Vibes',
            type: 'YSWS',
            tags: ['ysws', 'global', 'web'],
            description: 'Build a website with good vibes and throw a club pizza party.',
            image: '/static/images/ysws/vibes.png',
            backgroundColor: '#ffdd58',
            imageFit: 'contain',
            url: 'https://vibes.hackclub.com',

        }),
        ysws({
            title: 'HackCraft',
            type: 'YSWS',
            tags: ['ysws', 'global', 'games'],
            description: 'Make a Minecraft mod, get Minecraft or another game.',
            image: '/static/images/ysws/hackcraft.png',
            backgroundColor: '#30AE1F',
            imageFit: 'contain',
            url: 'https://hackcraft.hackclub.com/',

        }),
        ysws({
            title: 'Carnival',
            type: 'YSWS',
            tags: ['ysws', 'global', 'web'],
            description: 'Build an extension, plugin, or widget and get prizes.',
            image: '/static/images/ysws/carnival.jpg',
            backgroundColor: '#f9dfbd',
            imageFit: 'cover',
            url: 'https://carnival.hackclub.com/',

        }),
        ysws({
            title: 'TrailIt',
            type: 'YSWS',
            tags: ['ysws', 'global', 'web'],
            description: 'Build a web app, produce a trailer, and get production equipment.',
            image: '/static/images/ysws/trailit.png',
            backgroundColor: '#17171D',
            imageFit: 'contain',
            url: 'https://trailit.hackclub.com',

        }),

        ysws({
            title: 'Forge',
            type: 'YSWS',
            tags: ['ysws', 'global', 'hardware'],
            description: 'Design and build hardware projects, and get them funded.',
            image: '/static/images/ysws/catalog/forge-landing.png',
            backgroundColor: '#1f2d3d',
            imageFit: 'cover',
            url: 'https://forge.hackclub.com/',

        }),
        ysws({
            title: 'Shipyard',
            type: 'YSWS',
            tags: ['ysws', 'global', 'web'],
            description: 'Ship 7 weeks of computing and coding challenges and earn prizes from the shop.',
            image: '/static/images/ysws/catalog/shipyard-ship.png',
            backgroundColor: '#80d7ff',
            imageFit: 'contain',
            url: 'https://shipyard.hackclub.com/',

        }),
        ysws({
            title: 'Boot',
            type: 'YSWS',
            tags: ['ysws', 'global', 'hardware'],
            description: 'Make your own OS and get hardware to run it.',
            image: '/static/images/ysws/catalog/boot-hero.png',
            backgroundColor: '#000',
            imageFit: 'cover',
            url: 'https://boot.hackclub.com/',

        }),
        ysws({
            title: 'Remixed',
            type: 'YSWS',
            tags: ['ysws', 'global', 'music'],
            description: 'Ship something music related and get stuff to help you make music.',
            image: '/static/images/ysws/catalog/remixed-og.png',
            backgroundColor: '#8f70ff',
            imageFit: 'cover',
            url: 'https://remixed.hackclub.com/?ref=ysws-catalog',

        }),
        ysws({
            title: 'RaspAPI',
            type: 'YSWS',
            tags: ['ysws', 'global', 'web', 'hardware'],
            description: 'Build a public API and get a Raspberry Pi Zero 2W to host it on.',
            image: '/static/images/ysws/catalog/raspapi-pi.png',
            backgroundColor: '#e7f8ef',
            imageFit: 'contain',
            url: 'https://raspapi.hackclub.com/',

        }),
        ysws({
            title: 'Resolution',
            type: 'YSWS',
            tags: ['ysws', 'global'],
            description: 'Set goals, ship every week, and earn prizes for following through.',
            image: '/static/images/ysws/catalog/resolution-hero.png',
            backgroundColor: '#121217',
            imageFit: 'cover',
            url: 'https://resolution.hackclub.com/ref/ysws-catalog',

        }),
        ysws({
            title: 'Fix Hack Club',
            type: 'YSWS',
            tags: ['ysws', 'global', 'web'],
            description: 'Contribute to Hack Club repositories and get a grant of your choice.',
            image: '/static/images/fix-hack-club.png',
            imageFit: 'cover',
            url: 'https://fix.hackclub.com/',

        }),
        ysws({
            title: 'Lumen',
            type: 'YSWS',
            tags: ['ysws', 'global', 'games'],
            description: 'Make a Minecraft shader pack, get Minecraft and GPUs.',
            image: '/static/images/ysws/catalog/lumen.png',
            imageFit: 'cover',
            url: 'https://lumen.hackcraft.hackclub.com/',

        }),
        ysws({
            title: 'iplace',
            type: 'YSWS',
            tags: ['ysws', 'global', 'web'],
            description: 'Join a collaborative canvas of websites and get hosting and domain credits.',
            image: '/static/images/ysws/catalog/iplace-hero.png',
            backgroundColor: '#efe7d7',
            imageFit: 'cover',
            url: 'https://iplace.hackclub.com/?utm_source=ysws-catalog',

        }),
        ysws({
            title: 'Hacklet v2',
            type: 'YSWS',
            tags: ['ysws', 'global', 'web'],
            description: 'Build a bookmarklet and get food for your club.',
            image: '/static/images/ysws/catalog/hacklet.png',
            backgroundColor: '#000',
            imageFit: 'cover',
            url: 'https://hacklet.hackclub.com',

        }),
        ysws({
            title: 'Syscall x Terminal Craft',
            type: 'YSWS',
            tags: ['ysws', 'global', 'hardware'],
            description: 'Build a real systems project in Zig or C, build a terminal program, or do both.',
            image: '/static/images/ysws/catalog/syscall-hero.png',
            backgroundColor: '#050805',
            imageFit: 'cover',
            url: 'https://syscall.hackclub.com',

        }),
        ysws({
            title: 'Storyboard',
            type: 'YSWS',
            tags: ['ysws', 'global', 'games'],
            description: 'Make a themed visual novel and earn prizes.',
            image: '/static/images/ysws/catalog/storyboard-logo.webp',
            backgroundColor: '#ffeef6',
            imageFit: 'contain',
            url: 'https://storyboard.hackclub.com/',

        }),
        ysws({
            title: 'Rework',
            type: 'YSWS',
            tags: ['ysws', 'global', 'cad', 'hardware'],
            description: 'CAD a 3D printer mod and get funding plus Hack Club filament to build it.',
            image: '/static/images/ysws/cad/rework.png',
            imageFit: 'cover',
            url: 'https://rework.hackclub.com',

        })
    ];

    const searchInput = document.getElementById('search-input');
    const searchForm = document.getElementById('events-search-form');
    const filterTags = document.querySelectorAll('.filter-tag');
    const list = document.getElementById('events-list');

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

    function createCard(event) {
        const card = document.createElement('a');
        card.href = event.url;
        card.target = '_blank';
        card.className = 'event-card';
        card.dataset.tags = event.tags.join(',');

        const style = event.backgroundColor ? `style="--event-image-fit: ${event.imageFit || 'cover'}; background-color: ${event.backgroundColor}; background-image: url('${event.image}');"` : `style="--event-image-fit: ${event.imageFit || 'cover'}; background-image: url('${event.image}');"`;

        card.innerHTML = `
            <div class="event-card-visual" ${style}>
                ${event.logo ? `<img src="${event.logo}" alt="${event.title} logo" class="event-card-logo">` : ''}
            </div>
            <div class="event-card-body">
                <div class="event-card-type">${event.type}</div>
                <h3 class="event-card-title">${event.title}</h3>
                <p class="event-card-description">${event.description}</p>
                <div class="event-card-meta">
                    <div class="event-card-meta-item">
                        ${clockIcon}
                        <span>${event.duration}</span>
                    </div>
                    <div class="event-card-meta-item">
                        ${calendarIcon}
                        <span>${event.timeline || 'Ongoing'}</span>
                    </div>
                    <div class="event-card-meta-item">
                        ${locationIcon}
                        <span>${event.where}</span>
                    </div>
                </div>
            </div>
            <div class="event-card-footer">
                <span class="event-card-register">${event.cta || 'Explore &rarr;'}</span>
            </div>
        `;
        return card;
    }

    function applyFilters() {
        let visibleCount = 0;
        cards.forEach(card => {
            const tags = card.dataset.tags.split(',');
            const title = card.querySelector('.event-card-title').textContent.toLowerCase();
            const desc = card.querySelector('.event-card-description').textContent.toLowerCase();

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
