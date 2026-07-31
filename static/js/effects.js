/*
 * effects.js — the motion layer, ported from the React Bits effects to plain
 * DOM so it drops into the existing Jinja templates with no build step.
 *
 * Everything is opt-in through data attributes (space-separated, like class):
 *
 *   data-fx="split"      per-character reveal      (React Bits SplitText)
 *   data-fx="blur"       per-word blur-in          (React Bits BlurText)
 *   data-fx="shiny"      sweeping highlight        (React Bits ShinyText)
 *   data-fx="magnet"     cursor pull on hover      (React Bits Magnet)
 *   data-fx="spotlight"  cursor-follow glow        (React Bits SpotlightCard)
 *   data-fx="aurora"     animated gradient wash    (React Bits Aurora)
 *   data-fx="count"      number rolls to its value (React Bits CountUp)
 *
 * Tuning knobs, all optional: data-fx-stagger (ms between units),
 * data-fx-delay (ms before the first unit), data-fx-strength (magnet pull px).
 *
 * Two things this has to cooperate with:
 *  - i18n.js replaces textContent on [data-i18n] nodes, which would wipe out
 *    split markup. It fires `i18n:applied`; we re-split on that.
 *  - dashboard.js repaints metric tiles from state. Rather than have every
 *    caller opt in, a MutationObserver animates a counter whenever its number
 *    actually changes.
 *
 * Respects prefers-reduced-motion: text lands instantly, counters snap, and
 * the pointer-driven effects never bind.
 */
(function (global) {
    'use strict';

    const reduced =
        global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const supportsObserver = 'IntersectionObserver' in global;

    function fxList(el) {
        return (el.getAttribute('data-fx') || '').trim().split(/\s+/);
    }

    function num(el, attr, fallback) {
        const value = parseFloat(el.getAttribute(attr));
        return Number.isFinite(value) ? value : fallback;
    }

    // ── Reveal-on-scroll plumbing ────────────────────────────────────────────
    // One shared observer; each element says what to do via its own callback.

    const pending = new WeakMap();
    const observer = supportsObserver
        ? new IntersectionObserver(
              (entries) => {
                  entries.forEach((entry) => {
                      if (!entry.isIntersecting) return;
                      observer.unobserve(entry.target);
                      const run = pending.get(entry.target);
                      pending.delete(entry.target);
                      if (run) run();
                  });
              },
              { threshold: 0.2, rootMargin: '0px 0px -8% 0px' }
          )
        : null;

    // Run once, on the next painted frame — but never later than the timeout.
    // requestAnimationFrame is paused in a background tab, and these callbacks
    // are what make text visible; a frame that never arrives must not leave
    // content stuck at opacity 0.
    function nextPaint(run) {
        let done = false;
        const once = () => {
            if (done) return;
            done = true;
            run();
        };
        requestAnimationFrame(() => requestAnimationFrame(once));
        setTimeout(once, 120);
    }

    function whenVisible(el, run) {
        if (!observer) {
            run();
            return;
        }
        pending.set(el, run);
        observer.observe(el);
    }

    // ── SplitText / BlurText ─────────────────────────────────────────────────

    // Remember the plain text so a re-split after a language change starts
    // from the translated string rather than from our own span soup.
    const originalText = new WeakMap();

    function splitInto(el, mode) {
        // Splitting rebuilds the element from its text, so anything with child
        // elements (a nested <span class="marker-swipe">, an icon) would lose
        // them. Those nodes get the plain rise instead.
        if (el.children.length) return null;
        const text = originalText.has(el) ? originalText.get(el) : el.textContent;
        originalText.set(el, text);
        if (!text.trim()) return null;

        // Screen readers get the sentence; the per-unit spans are decorative.
        el.setAttribute('aria-label', text.trim());
        el.textContent = '';

        // Words are always the outer unit. Per-character spans are inline-block,
        // which would otherwise let a line break land in the middle of a word;
        // keeping them inside a word wrapper preserves normal line breaking.
        const words = text.split(/(\s+)/);
        const spans = [];
        words.forEach((word) => {
            if (!word) return;
            if (/^\s+$/.test(word)) {
                el.appendChild(document.createTextNode(word));
                return;
            }
            if (mode === 'blur') {
                const span = document.createElement('span');
                span.className = 'fx-unit fx-unit-blur';
                span.setAttribute('aria-hidden', 'true');
                span.textContent = word;
                el.appendChild(span);
                spans.push(span);
                return;
            }
            const wrapper = document.createElement('span');
            wrapper.className = 'fx-word';
            wrapper.setAttribute('aria-hidden', 'true');
            Array.from(word).forEach((char) => {
                const span = document.createElement('span');
                span.className = 'fx-unit fx-unit-char';
                span.textContent = char;
                wrapper.appendChild(span);
                spans.push(span);
            });
            el.appendChild(wrapper);
        });
        return spans;
    }

    function applyTextEffect(el, mode) {
        if (reduced) {
            el.classList.add('fx-text', 'is-shown');
            return;
        }
        const spans = splitInto(el, mode);
        if (!spans) {
            applyRise(el);
            return;
        }

        const stagger = num(el, 'data-fx-stagger', mode === 'blur' ? 70 : 22);
        const delay = num(el, 'data-fx-delay', 0);
        spans.forEach((span, i) => {
            span.style.transitionDelay = delay + i * stagger + 'ms';
        });

        el.classList.add('fx-text');
        whenVisible(el, () => {
            // Let the browser paint the "before" state first, so the reveal
            // actually transitions rather than snapping.
            nextPaint(() => el.classList.add('is-shown'));
        });
    }

    // ── Rise ─────────────────────────────────────────────────────────────────
    // The safe reveal: moves the element itself, never touches its markup, so
    // it works on anything — cards, headings with nested spans, whole sections.

    function applyRise(el) {
        if (reduced) {
            el.classList.add('fx-rise', 'is-shown');
            return;
        }
        el.classList.add('fx-rise');
        el.style.transitionDelay = num(el, 'data-fx-delay', 0) + 'ms';
        whenVisible(el, () => {
            nextPaint(() => el.classList.add('is-shown'));
        });
    }

    // ── Magnet ───────────────────────────────────────────────────────────────

    function applyMagnet(el) {
        if (reduced) return;
        const strength = num(el, 'data-fx-strength', 8);
        el.classList.add('fx-magnet');

        el.addEventListener('pointermove', (event) => {
            if (event.pointerType === 'touch') return;
            const box = el.getBoundingClientRect();
            const dx = (event.clientX - (box.left + box.width / 2)) / (box.width / 2);
            const dy = (event.clientY - (box.top + box.height / 2)) / (box.height / 2);
            el.style.transform = `translate(${dx * strength}px, ${dy * strength}px)`;
        });
        const release = () => {
            el.style.transform = '';
        };
        el.addEventListener('pointerleave', release);
        el.addEventListener('blur', release);
    }

    // ── Spotlight ────────────────────────────────────────────────────────────

    function applySpotlight(el) {
        if (reduced) return;
        el.classList.add('fx-spotlight');
        el.addEventListener('pointermove', (event) => {
            const box = el.getBoundingClientRect();
            el.style.setProperty('--fx-x', event.clientX - box.left + 'px');
            el.style.setProperty('--fx-y', event.clientY - box.top + 'px');
        });
    }

    // ── CountUp ──────────────────────────────────────────────────────────────

    // Elements we are mid-animation on, so the MutationObserver ignores the
    // intermediate values we write ourselves.
    const animating = new WeakSet();
    const shownValue = new WeakMap();

    function parseNumber(text) {
        const match = String(text).replace(/,/g, '').match(/-?\d+(\.\d+)?/);
        return match ? parseFloat(match[0]) : null;
    }

    function countTo(el, from, to) {
        const template = String(el.textContent);
        const decimals = (String(to).split('.')[1] || '').length;
        // Keep any prefix/suffix the label carries ("$1,200", "12 ships").
        const render = (value) =>
            template.replace(
                /-?[\d,]+(\.\d+)?/,
                value.toLocaleString(undefined, {
                    minimumFractionDigits: decimals,
                    maximumFractionDigits: decimals,
                })
            );

        const duration = Math.min(1100, 380 + Math.abs(to - from) * 12);
        const start = performance.now();
        animating.add(el);

        function frame(now) {
            const t = Math.min(1, (now - start) / duration);
            // easeOutExpo — fast out of the gate, settles gently on the value.
            const eased = t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
            el.textContent = render(from + (to - from) * eased);
            if (t < 1) {
                requestAnimationFrame(frame);
                return;
            }
            el.textContent = render(to);
            shownValue.set(el, to);
            animating.delete(el);
        }
        requestAnimationFrame(frame);
    }

    function applyCount(el) {
        const target = parseNumber(el.textContent);
        if (target === null) return;
        if (reduced) {
            shownValue.set(el, target);
            return;
        }
        shownValue.set(el, target);
        // Don't blank the number up front: requestAnimationFrame is paused in
        // a background tab, so a page loaded there would sit showing "0" —
        // a wrong figure, which is worse than no animation. Reset and animate
        // in the same frame instead.
        whenVisible(el, () => countTo(el, 0, target));
    }

    // Metric tiles are repainted from state; roll from the old number to the
    // new one instead of snapping, and ignore our own in-flight writes.
    function watchCounters(root) {
        if (reduced || !('MutationObserver' in global)) return;
        const watcher = new MutationObserver((records) => {
            records.forEach((record) => {
                const el = record.target.nodeType === 1 ? record.target : record.target.parentNode;
                if (!el || !el.matches || !el.matches(COUNT_SELECTOR)) return;
                if (animating.has(el)) return;
                const next = parseNumber(el.textContent);
                const prev = shownValue.get(el);
                if (next === null || next === prev) return;
                if (prev === undefined) {
                    shownValue.set(el, next);
                    return;
                }
                countTo(el, prev, next);
            });
        });
        root.querySelectorAll(COUNT_SELECTOR).forEach((el) => {
            watcher.observe(el, { childList: true, characterData: true, subtree: true });
        });
    }

    // ── Wiring ───────────────────────────────────────────────────────────────

    // Metric tiles opt in by convention so the thirteen dashboard templates
    // don't each need an attribute.
    const COUNT_SELECTOR = '[data-fx~="count"], .metric-tile > strong';
    const SPOTLIGHT_SELECTOR = '.metric-tile';

    const HANDLERS = {
        split: (el) => applyTextEffect(el, 'split'),
        blur: (el) => applyTextEffect(el, 'blur'),
        rise: applyRise,
        magnet: applyMagnet,
        spotlight: applySpotlight,
        // shiny and aurora are pure CSS; the class is all they need.
        shiny: (el) => el.classList.add('fx-shiny'),
        aurora: (el) => el.classList.add('fx-aurora'),
    };

    const wired = new WeakSet();

    function enhance(root) {
        const scope = root || document;
        scope.querySelectorAll('[data-fx]').forEach((el) => {
            if (wired.has(el)) return;
            wired.add(el);
            fxList(el).forEach((name) => {
                const handler = HANDLERS[name];
                if (handler) handler(el);
            });
        });
        scope.querySelectorAll(COUNT_SELECTOR).forEach((el) => {
            if (wired.has(el)) return;
            wired.add(el);
            applyCount(el);
        });
        scope.querySelectorAll(SPOTLIGHT_SELECTOR).forEach((el) => {
            if (wired.has(el)) return;
            wired.add(el);
            applySpotlight(el);
        });
    }

    function init() {
        enhance(document);
        watchCounters(document);
    }

    // i18n rewrites textContent, which destroys split markup — rebuild it.
    document.addEventListener('i18n:applied', () => {
        document.querySelectorAll('[data-fx]').forEach((el) => {
            const modes = fxList(el);
            const mode = modes.includes('blur') ? 'blur' : modes.includes('split') ? 'split' : null;
            if (!mode || reduced) return;
            el.classList.remove('is-shown');
            originalText.delete(el);
            applyTextEffect(el, mode);
            nextPaint(() => el.classList.add('is-shown'));
        });
    });

    global.fx = { enhance: enhance };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(window);
