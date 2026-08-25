// Extracted from templates/index.html. Classic script, no modules:
// the inline onclick handlers call these by bare name, so they must stay global.

// The selected language and the loaded strings live with their only
// readers, so the translation system is one unit.
let currentLang = 'en';
let i18nStrings = {};

async function initI18n() {
    const lang = (navigator.language || 'en').split('-')[0];
    const supported = ['en','de','zh','hi','es','fr','ar','bn','pt','ru','ja'];
    currentLang = supported.includes(lang) ? lang : 'en';
    try {
        // Version-stamped for the same reason as the scripts: without it a
        // browser keeps last version's translations and new keys never show.
        const resp = await fetch(getApiUrl(`/static/i18n/${currentLang}.json?v=${window.APP_ASSET_V || ''}`));
        if (resp.ok) {
            i18nStrings = await resp.json();
        }
    } catch (e) {
        console.warn('Failed to load translations, using defaults');
    }
    applyTranslations();
}
function t(key, fallback) {
    return i18nStrings[key] || fallback || key;
}
function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.dataset.i18n;
        const val = i18nStrings[key];
        if (val) el.textContent = val;
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.dataset.i18nPlaceholder;
        const val = i18nStrings[key];
        if (val) el.placeholder = val;
    });
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        const key = el.dataset.i18nTitle;
        const val = i18nStrings[key];
        if (val) el.title = val;
    });
}
