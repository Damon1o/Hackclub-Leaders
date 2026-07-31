/*
 * i18n.js — applies the active language to the dashboard chrome.
 *
 * Mirrors dark-mode.js: the choice lives in localStorage ('lang'). When the
 * visitor has never chosen, dashboard.js falls back to the club's saved
 * `settings.language` default (see applyLanguageDefault there).
 *
 * Translatable markup:
 *   <span data-i18n="nav.events">Events</span>          -> textContent
 *   <a   data-i18n-attr="title:side.team;aria-label:side.team"> -> attributes
 * The English text stays in the template as the built-in fallback.
 *
 * Loading: i18n-langs.js supplies the language list; each language's strings
 * live in static/js/i18n/<code>.js and are fetched only when that language is
 * actually selected. A visitor downloads ~30 KB of translations instead of the
 * ~370 KB of all twelve. Until the file lands, the page shows the English
 * already in the template, so nothing renders blank.
 */
(function (global) {
    'use strict';

    // Where the per-language files live, derived from this script's own URL so
    // it keeps working under any static path or CDN prefix.
    const SELF_SRC = (document.currentScript && document.currentScript.src) || '';
    const LANG_BASE = SELF_SRC.replace(/i18n\.js(\?.*)?$/, 'i18n/');

    const data = global.I18N || { LANGUAGES: [], TRANSLATIONS: {} };
    global.I18N = data;
    const LANGUAGES = data.LANGUAGES;
    const TRANSLATIONS = data.TRANSLATIONS;
    const DEFAULT_LANG = 'en';
    const STORAGE_KEY = 'lang';

    // code -> Promise, so a language is never requested twice.
    const loads = {};

    function loadLanguage(code) {
        if (!isSupported(code)) return Promise.resolve();
        // English is the text already in the markup, and it is also what
        // translate() falls back to for a missing key — never worth a request.
        if (code === DEFAULT_LANG) return Promise.resolve();
        if (TRANSLATIONS[code]) return Promise.resolve();
        if (loads[code]) return loads[code];
        loads[code] = new Promise(function (resolve) {
            const script = document.createElement('script');
            script.src = LANG_BASE + code + '.js';
            // A missing or broken language file must not wedge the page —
            // resolve either way and fall back to the template's English.
            script.onload = resolve;
            script.onerror = resolve;
            document.head.appendChild(script);
        });
        return loads[code];
    }

    function isSupported(code) {
        return LANGUAGES.some((lang) => lang.code === code);
    }

    function meta(code) {
        return LANGUAGES.find((lang) => lang.code === code) || null;
    }

    function stored() {
        try {
            return localStorage.getItem(STORAGE_KEY);
        } catch (_e) {
            return null;
        }
    }

    // Resolve one key for the active language, falling back to English, then to
    // whatever text the template already contains.
    function translate(code, key, fallback) {
        const table = TRANSLATIONS[code] || {};
        if (Object.prototype.hasOwnProperty.call(table, key)) return table[key];
        const base = TRANSLATIONS[DEFAULT_LANG] || {};
        if (Object.prototype.hasOwnProperty.call(base, key)) return base[key];
        return fallback;
    }

    function applyToElement(el, code) {
        const textKey = el.getAttribute('data-i18n');
        if (textKey) {
            el.textContent = translate(code, textKey, el.textContent);
        }
        const attrSpec = el.getAttribute('data-i18n-attr');
        if (attrSpec) {
            // "title:side.team;aria-label:side.team"
            attrSpec.split(';').forEach((pair) => {
                const [attr, key] = pair.split(':').map((s) => s && s.trim());
                if (attr && key) {
                    el.setAttribute(attr, translate(code, key, el.getAttribute(attr) || ''));
                }
            });
        }
    }

    function apply(code, root) {
        const lang = isSupported(code) ? code : DEFAULT_LANG;
        const scope = root || document;
        scope.querySelectorAll('[data-i18n], [data-i18n-attr]').forEach((el) => {
            applyToElement(el, lang);
        });
        const info = meta(lang);
        if (scope === document && document.documentElement) {
            document.documentElement.setAttribute('lang', lang);
            document.documentElement.setAttribute('dir', info ? info.dir : 'ltr');
            syncControls(lang);
        }
        // Translating rewrites textContent, which wipes out any markup other
        // code injected into these nodes (effects.js splits headings into
        // per-character spans). Let those listeners rebuild.
        document.dispatchEvent(new CustomEvent('i18n:applied', { detail: { lang: lang } }));
    }

    // Persist + apply. Call from the nav switcher and the settings save handler.
    // The strings may still be in flight, so applying is deferred until the
    // language file resolves; syncControls runs immediately to keep the
    // switcher responsive.
    function setLanguage(code) {
        const lang = isSupported(code) ? code : DEFAULT_LANG;
        try {
            localStorage.setItem(STORAGE_KEY, lang);
        } catch (_e) { /* private mode — apply in-memory only */ }
        syncControls(lang);
        loadLanguage(lang).then(function () {
            apply(lang);
            syncControls(lang);
        });
        return lang;
    }

    function current() {
        const saved = stored();
        return isSupported(saved) ? saved : DEFAULT_LANG;
    }

    // Point any <select data-lang-switcher> at the active language.
    function syncControls(code) {
        document.querySelectorAll('[data-lang-switcher]').forEach((sel) => {
            if (sel.value !== code) sel.value = code;
        });
    }

    // Fill an empty <select data-lang-switcher> with the supported languages.
    function populate(select, selected) {
        if (!select || select.options.length) return;
        LANGUAGES.forEach((lang) => {
            const opt = document.createElement('option');
            opt.value = lang.code;
            opt.textContent = lang.label;
            select.appendChild(opt);
        });
        select.value = selected;
    }

    function init() {
        const lang = current();
        document.querySelectorAll('[data-lang-switcher]').forEach((sel) => {
            populate(sel, lang);
            sel.addEventListener('change', (e) => setLanguage(e.target.value));
        });
        // English is what the templates already contain, so there is nothing
        // to fetch or repaint for it.
        if (lang === DEFAULT_LANG) {
            apply(lang);
            return;
        }
        loadLanguage(lang).then(() => apply(lang));
    }

    global.i18n = {
        apply: apply,
        setLanguage: setLanguage,
        current: current,
        languages: LANGUAGES,
        isSupported: isSupported,
        // Callers that render markup after load (dashboard.js) need the
        // strings present before they translate a fragment.
        load: loadLanguage,
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(window);
