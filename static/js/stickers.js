(function () {
    'use strict';

    var field = document.getElementById('stickerField');
    if (!field) return;

    var stickerList = [];
    try {
        stickerList = JSON.parse(document.getElementById('stickerData')?.textContent || '[]');
    } catch (e) {
        return;
    }
    if (!stickerList.length) return;

    var PREF_KEY = 'stickerPrefs';
    var defaultCount = parseInt(field.dataset.stickerCount, 10) || 6;
    var maxCount = Math.min(stickerList.length, 12);
    var sizeBase = [60, 100];
    var prefs = loadPrefs();

    function loadPrefs() {
        var d = { enabled: true, count: Math.min(defaultCount, maxCount), size: 1 };
        try {
            var saved = JSON.parse(localStorage.getItem(PREF_KEY) || '{}');
            if (typeof saved.enabled === 'boolean') d.enabled = saved.enabled;
            if (typeof saved.count === 'number') d.count = clamp(saved.count, 0, maxCount);
            if (typeof saved.size === 'number') d.size = clamp(saved.size, 0.5, 1.6);
        } catch (e) { /* ignore malformed prefs */ }
        return d;
    }

    function savePrefs() {
        try { localStorage.setItem(PREF_KEY, JSON.stringify(prefs)); } catch (e) { /* ignore */ }
    }

    function clamp(n, lo, hi) {
        return Math.max(lo, Math.min(hi, n));
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    function init() {
        renderStickers();
        buildControls();
    }

    function clearStickers() {
        var existing = field.querySelectorAll('.draggable-sticker');
        for (var i = 0; i < existing.length; i++) existing[i].remove();
    }

    function renderStickers() {
        clearStickers();
        if (!prefs.enabled || prefs.count < 1) return;

        var shuffled = stickerList.slice().sort(function () { return Math.random() - 0.5; });
        var chosen = shuffled.slice(0, prefs.count);
        var vw = window.innerWidth;
        var vh = window.innerHeight;
        var minS = sizeBase[0] * prefs.size;
        var maxS = sizeBase[1] * prefs.size;

        chosen.forEach(function (filename) {
            var img = document.createElement('img');
            img.src = '/static/images/Stickers/' + filename;
            img.alt = '';
            img.className = 'draggable-sticker';
            img.draggable = false;

            var size = minS + Math.random() * (maxS - minS);
            img.style.width = size + 'px';

            var left = 20 + Math.random() * (vw - size - 40);
            var top = 80 + Math.random() * (vh - size - 100);
            img.style.left = left + 'px';
            img.style.top = top + 'px';

            var angle = -12 + Math.random() * 24;
            img.style.transform = 'rotate(' + angle.toFixed(1) + 'deg)';

            img.addEventListener('pointerdown', onPointerDown);
            img.addEventListener('pointerup', onPointerUp);
            img.addEventListener('pointercancel', onPointerUp);
            img.addEventListener('lostpointercapture', onPointerUp);

            field.appendChild(img);
        });
    }

    function buildControls() {
        var wrap = document.createElement('div');
        wrap.className = 'sticker-controls';
        wrap.innerHTML =
            '<button class="sticker-controls-btn" type="button" aria-label="Sticker settings" aria-expanded="false">' +
            '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
            '<path d="M20.5 12a8.5 8.5 0 1 0-8.5 8.5c1.2 0 1.5-.8 1.5-1.7 0-1.4 1.1-2.3 2.5-2.3H18a2.5 2.5 0 0 0 2.5-2.5z"/>' +
            '<circle cx="8" cy="9.5" r="1.2"/><circle cx="15.5" cy="9" r="1.2"/><circle cx="7.5" cy="14" r="1.2"/></svg>' +
            '</button>' +
            '<div class="sticker-controls-panel" hidden>' +
            '<div class="sticker-controls-row">' +
            '<span class="sticker-controls-title">Stickers</span>' +
            '<label class="sticker-switch"><input type="checkbox" class="sc-enabled"><span class="sticker-switch-track"></span></label>' +
            '</div>' +
            '<label class="sticker-controls-field"><span>Amount</span>' +
            '<input type="range" class="sc-count" min="0" max="' + maxCount + '" step="1"></label>' +
            '<label class="sticker-controls-field"><span>Size</span>' +
            '<input type="range" class="sc-size" min="0.5" max="1.6" step="0.1"></label>' +
            '</div>';

        var btn = wrap.querySelector('.sticker-controls-btn');
        var panel = wrap.querySelector('.sticker-controls-panel');
        var enabledInput = wrap.querySelector('.sc-enabled');
        var countInput = wrap.querySelector('.sc-count');
        var sizeInput = wrap.querySelector('.sc-size');

        enabledInput.checked = prefs.enabled;
        countInput.value = prefs.count;
        sizeInput.value = prefs.size;
        setDisabled();

        btn.addEventListener('click', function () {
            var open = panel.hasAttribute('hidden');
            if (open) {
                panel.removeAttribute('hidden');
            } else {
                panel.setAttribute('hidden', '');
            }
            btn.setAttribute('aria-expanded', String(open));
        });

        enabledInput.addEventListener('change', function () {
            prefs.enabled = enabledInput.checked;
            savePrefs();
            setDisabled();
            renderStickers();
        });

        countInput.addEventListener('input', function () {
            prefs.count = clamp(parseInt(countInput.value, 10) || 0, 0, maxCount);
            savePrefs();
            renderStickers();
        });

        sizeInput.addEventListener('input', function () {
            prefs.size = clamp(parseFloat(sizeInput.value) || 1, 0.5, 1.6);
            savePrefs();
            renderStickers();
        });

        function setDisabled() {
            countInput.disabled = !prefs.enabled;
            sizeInput.disabled = !prefs.enabled;
        }

        document.body.appendChild(wrap);
    }

    function onPointerDown(e) {
        var img = e.currentTarget;
        img.setPointerCapture(e.pointerId);
        img.classList.add('is-dragging');
        img.style.zIndex = '200';

        var rect = img.getBoundingClientRect();
        img._dragStartX = e.clientX;
        img._dragStartY = e.clientY;
        img._dragOrigLeft = rect.left;
        img._dragOrigTop = rect.top;
        img._pointerId = e.pointerId;

        img.addEventListener('pointermove', onPointerMove);
        e.preventDefault();
    }

    function onPointerMove(e) {
        var img = e.currentTarget;
        if (e.pointerId !== img._pointerId) return;

        var dx = e.clientX - img._dragStartX;
        var dy = e.clientY - img._dragStartY;

        var newLeft = img._dragOrigLeft + dx;
        var newTop = img._dragOrigTop + dy;

        var elW = img.offsetWidth;
        var elH = img.offsetHeight;
        var vw = window.innerWidth;
        var vh = window.innerHeight;

        newLeft = Math.max(-elW * 0.5, Math.min(newLeft, vw - elW * 0.5));
        newTop = Math.max(0, Math.min(newTop, vh - elH * 0.5));

        img.style.left = newLeft + 'px';
        img.style.top = newTop + 'px';
    }

    function onPointerUp(e) {
        var img = e.currentTarget;
        img.classList.remove('is-dragging');
        img._pointerId = null;

        var z = 99 + Math.floor(Math.random() * 99);
        img.style.zIndex = z;
        img.removeEventListener('pointermove', onPointerMove);
    }
})();
