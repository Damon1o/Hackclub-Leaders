// Club Map — renders every active Hack Club from the official directory
// (same API the hackclub.github.io/map site uses).
(async function () {
    const el = document.getElementById('clubMap');
    if (!el || typeof L === 'undefined') return;

    const countLabel = document.getElementById('mapClubCount');
    const errorPanel = document.getElementById('mapError');

    const map = L.map(el, {
        center: [25, 8],
        zoom: 2,
        minZoom: 2,
        worldCopyJump: true,
        maxBounds: [[-90, -180], [90, 180]],
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    const renderer = L.canvas({ padding: 0.4 });

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function safeUrl(value) {
        try {
            const url = new URL(String(value));
            return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : '';
        } catch (error) {
            return '';
        }
    }

    try {
        const response = await fetch('https://clubapi.hackclub.com/clubs/map');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const clubs = await response.json();

        let plotted = 0;
        clubs.forEach((club) => {
            const fields = club.fields || {};
            if (fields.club_status !== 'Active') return;
            const lat = Number(fields.venue_lat_fuzz);
            const lng = Number(fields.venue_lng_fuzz);
            if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
            if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return;

            const marker = L.circleMarker([lat, lng], {
                renderer,
                radius: 5,
                weight: 1.5,
                color: '#ffffff',
                fillColor: '#ec3750',
                fillOpacity: 0.9,
            });
            const website = safeUrl(fields.club_website);
            marker.bindPopup(`
                <strong>${escapeHtml(fields.club_name || 'Hack Club')}</strong>
                ${website ? `<br><a href="${website}" target="_blank" rel="noopener noreferrer">View website</a>` : ''}
            `);
            marker.addTo(map);
            plotted += 1;
        });
        if (countLabel) {
            countLabel.textContent = `${plotted.toLocaleString()} active clubs around the world.`;
        }
    } catch (error) {
        if (countLabel) countLabel.textContent = '';
        if (errorPanel) errorPanel.hidden = false;
        el.hidden = true;
    }
})();
