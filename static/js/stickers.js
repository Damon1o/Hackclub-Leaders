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

    var count = parseInt(field.dataset.stickerCount, 10) || 6;
    var sizeRange = [60, 100];

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        renderStickers();
        return;
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', renderStickers);
    } else {
        renderStickers();
    }

    function renderStickers() {
        var shuffled = stickerList.slice().sort(function () { return Math.random() - 0.5; });
        var chosen = shuffled.slice(0, count);
        var vw = window.innerWidth;
        var vh = window.innerHeight;

        chosen.forEach(function (filename) {
            var img = document.createElement('img');
            img.src = '/static/images/Stickers/' + filename;
            img.alt = '';
            img.className = 'draggable-sticker';
            img.draggable = false;

            var size = sizeRange[0] + Math.random() * (sizeRange[1] - sizeRange[0]);
            img.style.width = size + 'px';
            img.style.height = size + 'px';

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
