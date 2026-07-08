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
 */
(function (global) {
    'use strict';

    const data = global.I18N || { LANGUAGES: [], TRANSLATIONS: {} };
    const LANGUAGES = data.LANGUAGES;
    const TRANSLATIONS = data.TRANSLATIONS;
    const DEFAULT_LANG = 'en';
    const STORAGE_KEY = 'lang';

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
    }

    // Persist + apply. Call from the nav switcher and the settings save handler.
    function setLanguage(code) {
        const lang = isSupported(code) ? code : DEFAULT_LANG;
        try {
            localStorage.setItem(STORAGE_KEY, lang);
        } catch (_e) { /* private mode — apply in-memory only */ }
        apply(lang);
        syncControls(lang);
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
        apply(lang);
    }

    global.i18n = {
        apply: apply,
        setLanguage: setLanguage,
        current: current,
        languages: LANGUAGES,
        isSupported: isSupported,
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(window);
