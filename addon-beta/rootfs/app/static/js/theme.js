// Extracted from templates/index.html. Classic script, no modules:
// the inline onclick handlers call these by bare name, so they must stay global.

function detectAndApplyTheme() {
    let dark = false;
    // Only a readable HA parent (Ingress) is authoritative; the OS
    // preference applies solely when the app runs standalone.
    let haDetected = false;

    try {
        const parentDoc = window.parent.document;
        // 1a: explicit HA theme attribute
        const haTheme = parentDoc.querySelector('html')?.getAttribute('data-theme') ||
                        parentDoc.querySelector('home-assistant')?.getAttribute('hass-theme') || '';
        if (haTheme.toLowerCase().includes('dark')) {
            dark = true;
            haDetected = true;
        }
        // 1b: HA's own background variable — the color the page really
        // paints, and the same source applyHAThemeVars() inherits from.
        // Using it keeps the theme attributes and the inherited colors
        // consistent by construction.
        if (!haDetected) {
            const haBg = getComputedStyle(parentDoc.documentElement)
                .getPropertyValue('--primary-background-color');
            const lum = colorBrightness(haBg);
            if (lum !== null) {
                dark = lum < 128;
                haDetected = true;
            }
        }
        // 1c: computed body background — but transparent means unknown
        if (!haDetected) {
            const lum = colorBrightness(getComputedStyle(parentDoc.body).backgroundColor);
            if (lum !== null) {
                dark = lum < 128;
                haDetected = true;
            }
        }

        // Try to inherit HA's CSS custom properties for exact theme matching
        applyHAThemeVars(parentDoc);
    } catch (e) {
        // Cross-origin — not in HA Ingress, fall through
    }

    // Method 2: OS preference — ONLY when not embedded in HA
    if (!haDetected && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        dark = true;
    }

    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-bs-theme', dark ? 'dark' : 'light');
}
function applyHAThemeVars(parentDoc) {
    // Map HA CSS variables to our variables for seamless theme integration
    const haRoot = parentDoc.documentElement;
    const style = getComputedStyle(haRoot);
    const mapping = {
        '--primary-color': '--primary-color',
        '--primary-background-color': '--bg-color',
        '--card-background-color': '--bg-card',
        '--sidebar-background-color': '--bg-sidebar',
        '--app-header-background-color': '--bg-navbar',
        '--primary-text-color': '--text-color',
        '--secondary-text-color': '--text-muted',
        '--divider-color': '--border-color',
    };
    const root = document.documentElement;
    for (const [haVar, ourVar] of Object.entries(mapping)) {
        const val = style.getPropertyValue(haVar).trim();
        if (val) root.style.setProperty(ourVar, val);
    }

    // Input colours must follow the SAME theme as the text we just
    // inherited. Without this they kept the values from our own
    // stylesheet, so an inherited dark text colour could end up on a
    // light field (or the reverse) — the unreadable fields in #25.
    const cardBg = style.getPropertyValue('--card-background-color').trim();
    if (cardBg) root.style.setProperty('--input-bg', cardBg);
    const divider = style.getPropertyValue('--divider-color').trim();
    if (divider) root.style.setProperty('--input-border', divider);
    // <code> badges (device addresses etc.) follow HA's secondary
    // background so they can't stay dark on a light page.
    const secBg = style.getPropertyValue('--secondary-background-color').trim();
    if (secBg) root.style.setProperty('--code-bg', secBg);
}
