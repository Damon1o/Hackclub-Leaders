(function () {
    function ysws(event) {
        return {
            ...event,
            type: 'YSWS',
            tags: ['ysws', 'global'].concat(event.tags || []),
            cta: event.cta || 'Explore &rarr;',
            duration: 'FOREVER',
            where: event.where || 'Online'
        };
    }

    const toolboxEvents = [
        ysws({
            title: 'Stack',
            tags: ['games'],
            description: 'Build a fun or completely unhinged project, and we’ll send you FREE LEGO sets of your choice.',
            image: '/static/images/events/stack-background.png',
            logo: '/static/images/events/stack.png',
            url: 'https://stack.hackclub.com/?utm_source=toolbox',
            timeline: 'Deadline: N/A',
            where: 'Online',
        }),
        {
            title: 'Macondo',
            type: 'Hackathon',
            tags: ['hackathon', 'travel'],
            description: 'Make projects, win free prizes, and fly to Bogota, Colombia.',
            image: '/static/images/events/macondo-background.png',
            logo: '/static/images/events/macondo-icon.png',
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
            image: '/static/images/events/fallout-heidi.gif',
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
            image: '/static/images/events/stasis-banner.png',
            logo: '/static/images/events/stasis-logo.png',
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
            image: '/static/images/events/beest-hero.webp',
            logo: '/static/images/events/beest-icon.webp',
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
            image: '/static/images/events/horizons-background.png',
            logo: '/static/images/events/horizons-logo.png',
            url: 'https://horizons.hackclub.com?utm_source=toolbox',
            duration: '7 global hackathons',
            timeline: 'Deadline: August 14, 2026',
            where: 'Global',

        },

        ysws({
            title: 'Boba Drops',
            tags: ['web'],
            description: 'Build a website using HTML and CSS, then get free boba.',
            image: '/static/images/ysws/webdev/boba.png',
            backgroundColor: '#C76B0F',
            imageFit: 'contain',
            url: 'https://boba.hackclub.com',

        }),
        ysws({
            title: 'Swirl',
            tags: ['web'],
            description: 'Build a cooler HTML and CSS website with a unique feature, then get free ice cream.',
            image: '/static/images/ysws/webdev/swirl.svg',
            backgroundColor: '#fde09d',
            imageFit: 'contain',
            url: 'https://swirl.hackclub.com',

        }),
        ysws({
            title: 'Toppings',
            tags: ['web'],
            description: 'Add extra flavor to your website with CSS and get toppings for ice cream or boba.',
            image: '/static/images/ysws/webdev/toppings.png',
            backgroundColor: '#ffcc00',
            imageFit: 'contain',
            url: 'https://toppings.hackclub.com',

        }),
        ysws({
            title: 'Flavorless',
            tags: ['web'],
            description: 'Build a website using only HTML and JavaScript. No CSS allowed.',
            image: '/static/images/ysws/webdev/flavorless.png',
            backgroundColor: '#ffffff',
            imageFit: 'contain',
            url: 'https://flavorless.hackclub.com/?utm_source=webdev',

        }),
        ysws({
            title: 'Waffles',
            tags: ['web'],
            description: 'Make a website that uses JavaScript, and get free waffles.',
            image: '/static/images/ysws/webdev/waffles.jpg',
            backgroundColor: '#f8b84f',
            imageFit: 'cover',
            url: 'https://waffles.hackclub.com',

        }),
        ysws({
            title: 'Grub',
            tags: ['web'],
            description: 'Build a website using Tailwind CSS, and get free junk food.',
            image: '/static/images/ysws/webdev/grub.png',
            backgroundColor: '#c10007',
            imageFit: 'contain',
            url: 'https://grub.hackclub.com',

        }),
        ysws({
            title: 'Reactive',
            tags: ['web'],
            description: 'Make a website with React, and get a free domain to host it.',
            image: '/static/images/ysws/webdev/reactive.png',
            backgroundColor: '#112a4f',
            imageFit: 'contain',
            url: 'https://reactive.hackclub.dev',

        }),
        ysws({
            title: 'Slushies',
            tags: ['web'],
            description: 'Make a web app using Flask, and get a slushie or another food item.',
            image: '/static/images/ysws/webdev/slushies.png',
            backgroundColor: '#4E9CDB',
            imageFit: 'contain',
            url: 'https://slushies.hackclub.com',

        }),

        ysws({
            title: 'BakeBuild',
            tags: ['cad'],
            description: 'Design a cookie cutter, then get it shipped to you with a cookie.',
            image: '/static/images/ysws/cad/bakebuild.png',
            backgroundColor: '#C76B0F',
            imageFit: 'contain',
            url: 'https://bakebuild.hackclub.com',

        }),
        ysws({
            title: 'FuseRing',
            tags: ['cad'],
            description: 'Design a keyring, then get your keyring and a clip for your backpack.',
            image: '/static/images/ysws/cad/fusering.svg',
            backgroundColor: '#FFA35E',
            imageFit: 'contain',
            url: 'https://fusering.hackclub.com/',

        }),
        ysws({
            title: 'Enclosure',
            tags: ['cad', 'hardware'],
            description: 'Make enclosures for your devices or hardware and get them printed.',
            image: '/static/images/ysws/cad/enclosure.png',
            backgroundColor: '#341C10',
            imageFit: 'contain',
            url: 'https://enclosure.hackclub.com',

        }),
        ysws({
            title: 'Squeak',
            tags: ['cad', 'hardware'],
            description: 'Design your own mouse case and get parts to build your own mouse.',
            image: '/static/images/ysws/cad/squeak.png',
            backgroundColor: '#0e305b',
            imageFit: 'contain',
            url: 'https://blueprint.hackclub.com/starter-projects/squeak',

        }),
        ysws({
            title: 'Construct',
            tags: ['cad'],
            description: 'As a group, spend 50 hours making CAD projects and get a 3D printer for your club.',
            image: '/static/images/ysws/cad/construct.png',
            backgroundColor: '#b64e07',
            imageFit: 'contain',
            url: 'https://construct.hackclub.com/dashboard/clubs',

        }),

        ysws({
            title: 'Sprig',
            tags: ['games'],
            description: 'Build a JavaScript game and play it on your own console.',
            image: '/static/images/ysws/sprig.png',
            backgroundColor: '#000',
            imageFit: 'contain',
            url: 'https://sprig.hackclub.com',

        }),
        ysws({
            title: 'Vibes',
            tags: ['web'],
            description: 'Build a website with good vibes and throw a club pizza party.',
            image: '/static/images/ysws/vibes.png',
            backgroundColor: '#ffdd58',
            imageFit: 'contain',
            url: 'https://vibes.hackclub.com',

        }),
        ysws({
            title: 'HackCraft',
            tags: ['games'],
            description: 'Make a Minecraft mod, get Minecraft or another game.',
            image: '/static/images/ysws/hackcraft.png',
            backgroundColor: '#30AE1F',
            imageFit: 'contain',
            url: 'https://hackcraft.hackclub.com/',

        }),
        ysws({
            title: 'Carnival',
            tags: ['web'],
            description: 'Build an extension, plugin, or widget and get prizes.',
            image: '/static/images/ysws/carnival.jpg',
            backgroundColor: '#f9dfbd',
            imageFit: 'cover',
            url: 'https://carnival.hackclub.com/',

        }),
        ysws({
            title: 'TrailIt',
            tags: ['web'],
            description: 'Build a web app, produce a trailer, and get production equipment.',
            image: '/static/images/ysws/trailit.png',
            backgroundColor: '#17171D',
            imageFit: 'contain',
            url: 'https://trailit.hackclub.com',

        }),

        ysws({
            title: 'Forge',
            tags: ['hardware'],
            description: 'Design and build hardware projects, and get them funded.',
            image: '/static/images/ysws/catalog/forge-landing.png',
            backgroundColor: '#1f2d3d',
            imageFit: 'cover',
            url: 'https://forge.hackclub.com/',

        }),
        ysws({
            title: 'Shipyard',
            tags: ['web'],
            description: 'Ship 7 weeks of computing and coding challenges and earn prizes from the shop.',
            image: '/static/images/ysws/catalog/shipyard-ship.png',
            backgroundColor: '#80d7ff',
            imageFit: 'contain',
            url: 'https://shipyard.hackclub.com/',

        }),
        ysws({
            title: 'Boot',
            tags: ['hardware'],
            description: 'Make your own OS and get hardware to run it.',
            image: '/static/images/ysws/catalog/boot-hero.png',
            backgroundColor: '#000',
            imageFit: 'cover',
            url: 'https://boot.hackclub.com/',

        }),
        ysws({
            title: 'Remixed',
            tags: ['music'],
            description: 'Ship something music related and get stuff to help you make music.',
            image: '/static/images/ysws/catalog/remixed-og.png',
            backgroundColor: '#8f70ff',
            imageFit: 'cover',
            url: 'https://remixed.hackclub.com/?ref=ysws-catalog',

        }),
        ysws({
            title: 'RaspAPI',
            tags: ['web', 'hardware'],
            description: 'Build a public API and get a Raspberry Pi Zero 2W to host it on.',
            image: '/static/images/ysws/catalog/raspapi-pi.png',
            backgroundColor: '#e7f8ef',
            imageFit: 'contain',
            url: 'https://raspapi.hackclub.com/',

        }),
        ysws({
            title: 'Resolution',
            tags: ['global'],
            description: 'Set goals, ship every week, and earn prizes for following through.',
            image: '/static/images/ysws/catalog/resolution-hero.png',
            backgroundColor: '#121217',
            imageFit: 'cover',
            url: 'https://resolution.hackclub.com/ref/ysws-catalog',

        }),
        ysws({
            title: 'Fix Hack Club',
            tags: ['web'],
            description: 'Contribute to Hack Club repositories and get a grant of your choice.',
            image: '/static/images/events/fix-hack-club.png',
            imageFit: 'cover',
            url: 'https://fix.hackclub.com/',

        }),
        ysws({
            title: 'Lumen',
            tags: ['games'],
            description: 'Make a Minecraft shader pack, get Minecraft and GPUs.',
            image: '/static/images/ysws/catalog/lumen.png',
            imageFit: 'cover',
            url: 'https://lumen.hackcraft.hackclub.com/',

        }),
        ysws({
            title: 'iplace',
            tags: ['web'],
            description: 'Join a collaborative canvas of websites and get hosting and domain credits.',
            image: '/static/images/ysws/catalog/iplace-hero.png',
            backgroundColor: '#efe7d7',
            imageFit: 'cover',
            url: 'https://iplace.hackclub.com/?utm_source=ysws-catalog',

        }),
        ysws({
            title: 'Hacklet v2',
            tags: ['web'],
            description: 'Build a bookmarklet and get food for your club.',
            image: '/static/images/ysws/catalog/hacklet.png',
            backgroundColor: '#000',
            imageFit: 'cover',
            url: 'https://hacklet.hackclub.com',

        }),
        ysws({
            title: 'Syscall x Terminal Craft',
            tags: ['hardware'],
            description: 'Build a real systems project in Zig or C, build a terminal program, or do both.',
            image: '/static/images/ysws/catalog/syscall-hero.png',
            backgroundColor: '#050805',
            imageFit: 'cover',
            url: 'https://syscall.hackclub.com',

        }),
        ysws({
            title: 'Storyboard',
            tags: ['games'],
            description: 'Make a themed visual novel and earn prizes.',
            image: '/static/images/ysws/catalog/storyboard-logo.webp',
            backgroundColor: '#ffeef6',
            imageFit: 'contain',
            url: 'https://storyboard.hackclub.com/',

        }),
        ysws({
            title: 'Rework',
            tags: ['cad', 'hardware'],
            description: 'CAD a 3D printer mod and get funding plus Hack Club filament to build it.',
            image: '/static/images/ysws/cad/rework.png',
            backgroundColor: '#000',
            imageFit: 'contain',
            url: 'https://rework.hackclub.com',

        }),

    ];

    const list = document.getElementById('events-list');
    const searchForm = document.getElementById('events-search-form');
    const searchInput = document.getElementById('search-input');
    const filterTags = document.querySelectorAll('.filter-tag');

    let activeFilter = 'all';
    let searchQuery = '';

    function renderEvents() {
        list.innerHTML = '';
        let visible = 0;

        toolboxEvents.forEach(event => {
            const matchesFilter = activeFilter === 'all' || event.tags.includes(activeFilter);
            const matchesSearch = !searchQuery ||
                event.title.toLowerCase().includes(searchQuery) ||
                event.description.toLowerCase().includes(searchQuery);

            const show = matchesFilter && matchesSearch;

            if (show) {
                const card = document.createElement('div');
                card.className = 'event-card';
                card.dataset.tags = event.tags.join(',');

                const style = event.backgroundColor ? `style="background-color: ${event.backgroundColor};"` : '';
                const imageClass = event.imageFit === 'contain' ? 'contain' : 'cover';

                card.innerHTML = `
                    <div class="event-image-container" ${style}>
                        <img src="${event.image}" alt="${event.title}" class="${imageClass}" loading="lazy">
                        ${event.logo ? `<img src="${event.logo}" alt="${event.title} logo" class="event-logo">` : ''}
                        <div class="event-type">${event.type}</div>
                    </div>
                    <div class="event-content">
                        <h3 class="event-title">${event.title}</h3>
                        <p class="event-description">${event.description}</p>
                        <div class="event-details">
                            <div class="detail-item">
                                <span class="detail-label">Duration:</span>
                                <span class="detail-value">${event.duration}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Timeline:</span>
                                <span class="detail-value">${event.timeline || 'Ongoing'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Where:</span>
                                <span class="detail-value">${event.where}</span>
                            </div>
                        </div>
                        <a href="${event.url}" target="_blank" class="event-cta">${event.cta}</a>
                    </div>
                `;
                list.appendChild(card);
            }

            if (show) visible++;
        });

        let empty = document.getElementById('events-empty');
        if (visible === 0) {
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

    filterTags.forEach(tag => {
        tag.addEventListener('click', () => {
            filterTags.forEach(t => t.classList.remove('active'));
            tag.classList.add('active');
            activeFilter = tag.dataset.filter;
            renderEvents();
        });
    });

    searchInput.addEventListener('input', () => {
        searchQuery = searchInput.value.trim().toLowerCase();
        renderEvents();
    });

    searchForm.addEventListener('submit', event => event.preventDefault());

    renderEvents();
})();
