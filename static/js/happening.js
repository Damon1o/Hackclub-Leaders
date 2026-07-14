(function () {
    const strip = document.getElementById('happening-strip');
    const events = window.toolboxEvents;
    if (!strip || !events) return;

    const now = new Date();

    function deadlineOf(event) {
        const match = /^Deadline:\s*(.+)$/.exec(event.timeline || '');
        if (!match || match[1] === 'N/A') return null;
        const date = new Date(match[1]);
        return isNaN(date) ? null : date;
    }

    const upcoming = events
        .map(event => ({ event, deadline: deadlineOf(event) }))
        .filter(item => item.deadline && item.deadline >= now)
        .sort((a, b) => a.deadline - b.deadline)
        .map(item => item.event);

    const ongoing = events.filter(event => event.timeline === 'Ongoing');

    const picks = upcoming.concat(ongoing).slice(0, 3);

    picks.forEach(event => {
        const card = document.createElement('a');
        card.className = 'happening-card reveal';
        card.href = event.url;
        card.target = '_blank';
        card.rel = 'noopener noreferrer';

        const visual = document.createElement('div');
        visual.className = 'happening-card-visual';

        const artwork = event.image !== 'N/A' ? event.image
            : (event.logo !== 'N/A' ? event.logo : null);
        if (artwork) {
            const img = document.createElement('img');
            img.src = artwork;
            img.alt = event.title;
            img.loading = 'lazy';
            if (event.backgroundColor !== 'N/A') {
                img.style.backgroundColor = event.backgroundColor;
            }
            if (event.imageFit) {
                img.style.objectFit = event.imageFit;
            }
            visual.appendChild(img);
        } else if (event.backgroundColor !== 'N/A') {
            visual.style.backgroundColor = event.backgroundColor;
        }

        const date = document.createElement('span');
        date.className = 'happening-card-date';
        date.textContent = (event.timeline || 'Ongoing').replace(/^Deadline:\s*/, 'Ends ');
        visual.appendChild(date);

        const body = document.createElement('div');
        body.className = 'happening-card-body';

        const title = document.createElement('h3');
        title.className = 'happening-card-title';
        title.textContent = event.title;

        const description = document.createElement('p');
        description.className = 'happening-card-description';
        description.textContent = event.description;

        const cta = document.createElement('span');
        cta.className = 'happening-card-cta';
        cta.textContent = `Join ${event.title} →`;

        body.append(title, description, cta);
        card.append(visual, body);
        strip.appendChild(card);
    });
})();
