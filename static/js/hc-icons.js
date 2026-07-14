/**
 * Hack Club Icons Helper
 * Fetches and caches SVGs from https://icons.hackclub.com/api/icons/:color/:glyph
 */

(function() {
    'use strict';

    const ICON_API = 'https://icons.hackclub.com/api/icons';
    const CACHE = new Map();
    const DEFAULT_COLOR = 'currentColor';

    // Common color mappings for Hack Club theme
    const THEME_COLORS = {
        hackclubGreen: 'hackclub-green',
        hackclubRed: 'hackclub-red',
        hackclubBlue: 'hackclub-blue',
        hackclubYellow: 'hackclub-yellow',
        hackclubPurple: 'hackclub-purple',
        hackclubOrange: 'hackclub-orange',
        black: 'black',
        white: 'white',
        currentColor: 'currentColor'
    };

    async function fetchIcon(glyph, color = DEFAULT_COLOR) {
        const cacheKey = `${glyph}:${color}`;
        if (CACHE.has(cacheKey)) return CACHE.get(cacheKey);

        const colorParam = THEME_COLORS[color] || color;
        const url = `${ICON_API}/${colorParam}/${glyph}`;

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`Failed to fetch icon: ${glyph}`);
            const svgText = await response.text();
            CACHE.set(cacheKey, svgText);
            return svgText;
        } catch (error) {
            console.warn(`[hc-icons] Could not load icon "${glyph}":`, error);
            return null;
        }
    }

    function createIconElement(glyph, options = {}) {
        const {
            color = DEFAULT_COLOR,
            size = 24,
            className = '',
            ariaLabel = '',
            title = '',
            ...attrs
        } = options;

        const wrapper = document.createElement('span');
        wrapper.className = `hc-icon ${className}`;
        wrapper.style.display = 'inline-flex';
        wrapper.style.width = `${size}px`;
        wrapper.style.height = `${size}px`;
        wrapper.style.flexShrink = '0';

        if (ariaLabel) wrapper.setAttribute('aria-label', ariaLabel);
        if (title) wrapper.setAttribute('title', title);

        // Apply color via CSS custom property for currentColor support
        if (color !== DEFAULT_COLOR) {
            wrapper.style.color = THEME_COLORS[color] || color;
        }

        Object.entries(attrs).forEach(([key, value]) => {
            wrapper.setAttribute(key, value);
        });

        // Load icon asynchronously
        fetchIcon(glyph, color).then(svg => {
            if (svg) {
                wrapper.innerHTML = svg;
                const svgEl = wrapper.querySelector('svg');
                if (svgEl) {
                    svgEl.removeAttribute('width');
                    svgEl.removeAttribute('height');
                    svgEl.style.width = '100%';
                    svgEl.style.height = '100%';
                    // Ensure fill uses currentColor
                    if (color === DEFAULT_COLOR || color === 'currentColor') {
                        svgEl.style.fill = 'currentColor';
                    }
                }
            } else {
                // Fallback: show a generic icon or nothing
                wrapper.innerHTML = '<svg viewBox="0 0 24 24" style="width:100%;height:100%"><rect width="24" height="24" fill="none"/></svg>';
            }
        });

        return wrapper;
    }

    // Expose globally
    window.hcIcons = {
        fetchIcon,
        createIconElement,
        THEME_COLORS
    };

    // Auto-replace elements with data-hc-icon attribute
    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('[data-hc-icon]').forEach(el => {
            const glyph = el.getAttribute('data-hc-icon');
            const color = el.getAttribute('data-hc-color') || DEFAULT_COLOR;
            const size = parseInt(el.getAttribute('data-hc-size') || '24', 10);
            const label = el.getAttribute('data-hc-label') || '';
            
            const iconEl = createIconElement(glyph, { color, size, ariaLabel: label });
            el.replaceWith(iconEl);
        });
    });
})();