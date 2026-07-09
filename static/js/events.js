(function () {
    const toolboxEvents = [
        {
            title: 'Stardance',
            type: 'YSWS',
            tags: ['ysws', 'games', 'web', 'hardware', 'cad'],
            description: 'The largest STEM event of the summer: make anything you want and earn free prizes.',
            image: '/static/images/events/stardance/stardance-background.png',
            logo: '/static/images/events/stardance/stardance-logo.avif',
            backgroundColor: 'N/A',
            imageFit: 'cover',
            borderColor: '#EBB7FF',
            url: 'https://stardance.hackclub.com/',
            duration: 'FOREVER',
            timeline: 'Deadline: September 2026',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Stack',
            type: 'YSWS',
            tags: ['ysws', 'games'],
            description: 'Build a fun or completely unhinged project, and we\'ll send you FREE LEGO sets of your choice.',
            image: '/static/images/events/stack/stack-background.png',
            logo: '/static/images/events/stack/stack-logo.png',
            backgroundColor: 'N/A',
            imageFit: 'cover',
            borderColor: '#E03536',
            url: 'https://stack.hackclub.com/',
            duration: 'FOREVER',
            timeline: 'Deadline: N/A',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Forge',
            type: 'YSWS',
            tags: ['ysws', 'hardware'],
            description: 'Design and build hardware projects, and get them funded.',
            image: '/static/images/events/forge/forge-background.png',
            logo: '/static/images/events/forge/forge-logo.png',
            backgroundColor: 'N/A',
            imageFit: 'cover',
            borderColor: '#FF711F',
            url: 'https://forge.hackclub.com/',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Macondo',
            type: 'Hackathon',
            tags: ['hackathon', 'travel'],
            description: 'Make projects, win free prizes, and fly to Bogota, Colombia.',
            image: '/static/images/events/macondo/macondo-background.png',
            logo: '/static/images/events/macondo/macondo-logo.png',
            backgroundColor: 'N/A',
            imageFit: 'cover',
            borderColor: '#EEBC3C',
            url: 'https://macondo.hackclub.com/',
            duration: '3-day hackathon',
            timeline: 'Deadline: September 2026',
            where: 'Bogota, Colombia',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Fallout',
            type: 'Hackathon',
            tags: ['hackathon', 'hardware', 'travel'],
            description: 'Build hardware projects and visit Shenzhen, China.',
            image: '/static/images/events/fallout/fallout-logo.gif',
            logo: 'N/A',
            backgroundColor: '#38c9ff',
            imageFit: 'contain',
            borderColor: '#33ABDA',
            url: 'https://fallout.hackclub.com',
            duration: '60 hours of hardware projects',
            timeline: 'Deadline: July 1, 2026',
            where: 'Shenzhen, China',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Stasis',
            type: 'Hackathon',
            tags: ['hackathon', 'hardware', 'travel'],
            description: 'Build hardware projects and fly out to Austin, TX for a hardware hackathon.',
            image: '/static/images/events/stasis/stasis-background.png',
            logo: '/static/images/events/stasis/stasis-logo.png',
            backgroundColor: 'N/A',
            imageFit: 'cover',
            borderColor: 'N/A',
            url: 'https://stasis.hackclub.com',
            duration: 'May 15-18 hardware sprint',
            timeline: 'Deadline: May 18, 2026',
            where: 'Austin, TX',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Beest',
            type: 'Hackathon',
            tags: ['hackathon', 'travel'],
            description: 'Code projects, fly to the Netherlands, and build a mechanical animal.',
            image: '/static/images/events/beest/beest-background.webp',
            logo: '/static/images/events/beest/beest-logo.webp',
            backgroundColor: 'N/A',
            imageFit: 'cover',
            borderColor: 'N/A',
            url: 'https://beest.hackclub.com',
            duration: 'Week-long hackathon',
            timeline: 'Event: July 10-15',
            where: 'Netherlands',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Horizons',
            type: 'Hackathon',
            tags: ['hackathon', 'travel'],
            description: 'Seven hackathons run by teenagers across the globe, for teenagers everywhere.',
            image: '/static/images/events/horizons/horizons-background.png',
            logo: '/static/images/events/horizons/horizons-logo.png',
            backgroundColor: 'N/A',
            imageFit: 'cover',
            borderColor: 'N/A',
            url: 'https://horizons.hackclub.com',
            duration: '7 global hackathons',
            timeline: 'Deadline: August 14, 2026',
            where: 'Global',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Boba Drops',
            type: 'YSWS',
            tags: ['ysws', 'web'],
            description: 'Build a website using HTML and CSS, then get free boba.',
            image: 'N/A',
            logo: '/static/images/events/boba-drops/boba-drops-icon.png',
            backgroundColor: '#C76B0F',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://boba.hackclub.com',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Swirl',
            type: 'YSWS',
            tags: ['ysws', 'web'],
            description: 'Build a cooler HTML and CSS website with a unique feature, then get free ice cream.',
            image: 'N/A',
            logo: '/static/images/events/swirl/swirl-logo.svg',
            backgroundColor: '#fde09d',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://swirl.hackclub.com',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Toppings',
            type: 'YSWS',
            tags: ['ysws', 'web'],
            description: 'Add extra flavor to your website with CSS and get toppings for ice cream or boba.',
            image: 'N/A',
            logo: '/static/images/events/toppings/toppings-logo.png',
            backgroundColor: '#A7C4FF',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://toppings.hackclub.com',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Flavorless',
            type: 'YSWS',
            tags: ['ysws', 'web'],
            description: 'Build a website using only HTML and JavaScript. No CSS allowed.',
            image: 'N/A',
            logo: '/static/images/events/flavorless/flavorless-logo.png',
            backgroundColor: '#ffffff',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://flavorless.hackclub.com/?utm_source=webdev',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Waffles',
            type: 'YSWS',
            tags: ['ysws', 'web'],
            description: 'Make a website that uses JavaScript, and get free waffles.',
            image: 'N/A',
            logo: '/static/images/events/waffles/waffles-logo.jpg',
            backgroundColor: '#755000',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://waffles.hackclub.com',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Grub',
            type: 'YSWS',
            tags: ['ysws', 'web'],
            description: 'Build a website using Tailwind CSS, and get free junk food.',
            image: 'N/A',
            logo: '/static/images/events/grub/grub-logo.png',
            backgroundColor: '#c10007',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://grub.hackclub.com',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Reactive',
            type: 'YSWS',
            tags: ['ysws', 'web'],
            description: 'Make a website with React, and get a free domain to host it.',
            image: 'N/A',
            logo: '/static/images/events/reactive/reactive-logo.png',
            backgroundColor: '#112a4f',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://reactive.hackclub.dev',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Slushies',
            type: 'YSWS',
            tags: ['ysws', 'web'],
            description: 'Make a web app using Flask, and get a slushie or another food item.',
            image: 'N/A',
            logo: '/static/images/events/slushies/slushies-logo.png',
            backgroundColor: '#4E9CDB',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://slushies.hackclub.com',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Polygon',
            type: 'YSWS',
            tags: ['ysws', 'web'],
            description: 'Build a 3D website using three.js and get a grant to go watch your favourite movies!',
            image: '/static/images/events/polygon/polygon-background.png',
            logo: '/static/images/events/polygon/polygon-logo.png',
            backgroundColor: 'N/A',
            imageFit: 'cover',
            borderColor: 'N/A',
            url: 'https://polygon.hackclub.com',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'BakeBuild',
            type: 'YSWS',
            tags: ['ysws', 'cad'],
            description: 'Design a cookie cutter, then get it shipped to you with a cookie.',
            image: '/static/images/events/bakebuild/bakebuild-background.png',
            logo: 'N/A',
            backgroundColor: '#A2CAD8',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://bakebuild.hackclub.com',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'FuseRing',
            type: 'YSWS',
            tags: ['ysws', 'cad'],
            description: 'Design a keyring, then get your keyring and a clip for your backpack.',
            image: 'N/A',
            logo: '/static/images/events/fusering/fusering-logo.svg',
            backgroundColor: '#A75970',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://fusering.hackclub.com/',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Enclosure',
            type: 'YSWS',
            tags: ['ysws', 'cad', 'hardware'],
            description: 'Make enclosures for your devices or hardware and get them printed.',
            image: 'N/A',
            logo: '/static/images/events/enclosure/enclosure-logo.webp',
            backgroundColor: '#3C1E0F',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://enclosure.hackclub.com',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Blueprint',
            type: 'YSWS',
            tags: ['ysws', 'cad', 'hardware'],
            description: 'Design a macropad - get it sent from Hack Club for free!',
            image: '/static/images/events/blueprint/blueprint-background.png',
            logo: '/static/images/events/blueprint/blueprint_logo.webp',
            backgroundColor: 'N/A',
            imageFit: 'cover',
            borderColor: 'N/A',
            url: 'https://blueprint.hackclub.com/',
            duration: 'March 31st, 2026',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Construct',
            type: 'YSWS',
            tags: ['ysws', 'cad'],
            description: 'As a group, spend 50 hours making CAD projects and get a 3D printer for your club.',
            image: '/static/images/events/construct/construct-background.png',
            logo: '/static/images/events/construct/construct-logo.png',
            backgroundColor: 'N/A',
            imageFit: 'cover',
            borderColor: 'N/A',
            url: 'https://construct.hackclub.com/',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Sprig',
            type: 'YSWS',
            tags: ['ysws', 'games'],
            description: 'Build a JavaScript game and play it on your own console.',
            image: '/static/images/events/sprig/sprig-background.png',
            logo: '/static/images/events/sprig/sprig-logo.png',
            backgroundColor: 'N/A',
            imageFit: 'cover',
            borderColor: 'N/A',
            url: 'https://sprig.hackclub.com',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Vibes',
            type: 'YSWS',
            tags: ['ysws', 'web'],
            description: 'Build a website with good vibes and throw a club pizza party.',
            image: 'N/A',
            logo: 'N/A',
            backgroundColor: '#ffdd58',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://vibes.hackclub.com',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'HackCraft',
            type: 'YSWS',
            tags: ['ysws', 'games'],
            description: 'Make a Minecraft mod, get Minecraft or another game.',
            image: '/static/images/events/hackcraft/hackcraft-background.jpg',
            logo: '/static/images/events/hackcraft/hackcraft-logo.webp',
            backgroundColor: 'N/A',
            imageFit: 'cover',
            borderColor: 'N/A',
            url: 'https://hackcraft.hackclub.com/',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Carnival',
            type: 'YSWS',
            tags: ['ysws', 'web'],
            description: 'Build an extension, plugin, or widget and get prizes.',
            image: 'N/A',
            logo: '/static/images/events/carnival/carnival-logo.webp',
            backgroundColor: '#F4C552',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://carnival.hackclub.com/',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'TrailIt',
            type: 'YSWS',
            tags: ['ysws', 'web'],
            description: 'Build a web app, produce a trailer, and get production equipment.',
            image: 'N/A',
            logo: '/static/images/events/trailit/trailit-logo.webp',
            backgroundColor: '#17171D',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://trailit.hackclub.com',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Shipyard',
            type: 'YSWS',
            tags: ['ysws', 'web'],
            description: 'Ship 7 weeks of computing and coding challenges and earn prizes from the shop.',
            image: 'N/A',
            logo: 'N/A',
            backgroundColor: '#80d7ff',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://shipyard.hackclub.com/',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Boot',
            type: 'YSWS',
            tags: ['ysws', 'hardware'],
            description: 'Make your own OS and get hardware to run it.',
            image: 'N/A',
            logo: '/static/images/events/boot/boot-logo.png',
            backgroundColor: '#000',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://boot.hackclub.com/',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Remixed',
            type: 'YSWS',
            tags: ['ysws', 'music'],
            description: 'Ship something music related and get stuff to help you make music.',
            image: 'N/A',
            logo: '/static/images/events/remixed/remixed-logo.png',
            backgroundColor: '#C681FF',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://remixed.hackclub.com/',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'RaspAPI',
            type: 'YSWS',
            tags: ['ysws', 'web', 'hardware'],
            description: 'Build a public API and get a Raspberry Pi Zero 2W to host it on.',
            image: 'N/A',
            logo: 'N/A',
            backgroundColor: '#e7f8ef',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://raspapi.hackclub.com/',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Resolution',
            type: 'YSWS',
            tags: ['ysws'],
            description: 'Set goals, ship every week, and earn prizes for following through.',
            image: 'N/A',
            logo: 'N/A',
            backgroundColor: '#121217',
            imageFit: 'cover',
            borderColor: 'N/A',
            url: 'https://resolution.hackclub.com/ref/ysws-catalog',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Fix Hack Club',
            type: 'YSWS',
            tags: ['ysws', 'web'],
            description: 'Contribute to Hack Club repositories and get a grant of your choice.',
            image: '/static/images/events/fix-hack-club/fix-hack-club-background.png',
            logo: 'N/A',
            backgroundColor: 'N/A',
            imageFit: 'cover',
            borderColor: 'N/A',
            url: 'https://fix.hackclub.com/',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Lumen',
            type: 'YSWS',
            tags: ['ysws', 'games'],
            description: 'Make a Minecraft shader pack, get Minecraft and GPUs.',
            image: '/static/images/events/lumen/lumen-background.jpg',
            logo: '/static/images/events/lumen/lumen-logo.png',
            backgroundColor: 'N/A',
            imageFit: 'cover',
            borderColor: 'N/A',
            url: 'https://lumen.hackcraft.hackclub.com/',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'iplace',
            type: 'YSWS',
            tags: ['ysws', 'web'],
            description: 'Join a collaborative canvas of websites and get hosting and domain credits.',
            image: 'N/A',
            logo: 'N/A',
            backgroundColor: '#efe7d7',
            imageFit: 'cover',
            borderColor: 'N/A',
            url: 'https://iplace.hackclub.com/?utm_source=ysws-catalog',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Hacklet v2',
            type: 'YSWS',
            tags: ['ysws', 'web'],
            description: 'Build a bookmarklet and get food for your club.',
            image: 'N/A',
            logo: 'N/A',
            backgroundColor: '#000',
            imageFit: 'cover',
            borderColor: 'N/A',
            url: 'https://hacklet.hackclub.com',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Syscall x Terminal Craft',
            type: 'YSWS',
            tags: ['ysws', 'hardware'],
            description: 'Build a real systems project in Zig or C, build a terminal program, or do both.',
            image: 'N/A',
            logo: 'N/A',
            backgroundColor: '#050805',
            imageFit: 'cover',
            borderColor: 'N/A',
            url: 'https://syscall.hackclub.com',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Storyboard',
            type: 'YSWS',
            tags: ['ysws', 'games'],
            description: 'Make a themed visual novel and earn prizes.',
            image: 'N/A',
            logo: 'N/A',
            backgroundColor: '#ffeef6',
            imageFit: 'contain',
            borderColor: 'N/A',
            url: 'https://storyboard.hackclub.com/',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
        {
            title: 'Rework',
            type: 'YSWS',
            tags: ['ysws', 'cad', 'hardware'],
            description: 'CAD a 3D printer mod and get funding plus Hack Club filament to build it.',
            image: '/static/images/events/rework/rework-background.png',
            logo: '/static/images/events/rework/rework-logo.png',
            backgroundColor: 'N/A',
            imageFit: 'cover',
            borderColor: 'N/A',
            url: 'https://rework.hackclub.com',
            duration: 'FOREVER',
            timeline: 'Ongoing',
            where: 'Online',
            cta: 'Explore &rarr;',
        },
    ];

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
            ? `style="--event-image-fit: ${event.imageFit}; background-color: ${event.backgroundColor};${event.image !== 'N/A' ? ` background-image: url('${event.image}');` : ''}"`
            : `style="--event-image-fit: ${event.imageFit};${event.image !== 'N/A' ? ` background-image: url('${event.image}');` : ''}"`;

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