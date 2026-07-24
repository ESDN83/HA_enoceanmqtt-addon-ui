# Frontend Refactor Plan: split the index.html monolith

Status: planned, not started. Execute after v1.7.0 stable ships, as its own change, beta-first.

## Why

`templates/index.html` is one file of ~4110 lines containing all HTML pages, the entire CSS (one `<style>` block), and the entire app logic (three `<script>` blocks). Every UI change, however small, means loading and searching a 4000-line file. That is slow, expensive, and error prone. The Python backend is fine (14 modular files under `core/` and `api/`, largest ~1300 lines). The problem is only the frontend.

Left as is, further UI work keeps getting harder. This plan splits the frontend into focused files so each future change touches 200 to 400 lines.

## Current state (measured)

- `addon-beta/rootfs/app/templates/index.html`: 4110 lines. 1 inline `<style>`, 3 inline `<script>`.
- `static/css/`: empty. `static/js/`: only the vendored `js-yaml.min.js`.
- 59 inline `onclick="..."` handlers in the HTML, all calling global functions.
- Static is served at `/static` (`app.mount("/static", StaticFiles(...))` in `main.py:452`). Under HA Ingress the base path is dynamic, so assets must be loaded Ingress-aware. The app already does this for js-yaml (`base + '/static/js/js-yaml.min.js'`) and i18n (`getApiUrl('/static/i18n/...')`).

## Hard constraints (do not break these)

1. Buildless. There is no npm/webpack/bundler. FastAPI serves static files directly. Keep it that way: plain `.js` files loaded with classic `<script src>`, no bundler step.
2. Functions must stay global. The 59 inline `onclick` handlers call bare function names. ES modules create scope and would break every handler. So split into classic scripts (not `type="module"`); functions remain on `window`. Do not convert to ES modules in this pass.
3. Ingress-aware loading. New `<script src>` and the CSS `<link>` must resolve under the dynamic Ingress base path. Inject them at runtime with the computed base (same mechanism as js-yaml), or make sure relative paths resolve. Test inside Ingress, not only standalone.
4. Early theme script stays inline. The small `<head>` script that sets the theme before first paint must remain inline to avoid a flash of the wrong theme. Do not externalize it. See [[theme-detection-ha-transparent-body]].
5. Load order matters. Classic scripts run in order. Put shared helpers first, feature files after, init last.
6. `{{ version }}` Jinja var stays in the template.

## Target layout

```
static/css/app.css            all CSS from the current <style> block
static/js/core.js             base path, getApiUrl, getWsUrl, escapeHtml,
                              showToast, showConfirmDialog, colorBrightness
static/js/theme.js            detectAndApplyTheme, applyHAThemeVars (main copy;
                              the anti-flash <head> snippet stays inline)
static/js/i18n.js             t(), loadTranslations, applyTranslations
static/js/nav.js              navigateTo, wizardNext/Back, page routing
static/js/dashboard.js        loadStatus, loadRecentTelegrams, formatTelegramDetails,
                              unknown devices
static/js/devices.js          loadDevices, editDevice, saveDevice, performSaveDevice,
                              resetDeviceForm, sender-id collision check
static/js/teachin.js          startTeachIn, applyTeachInData, offerSecondChannel,
                              actuator teach-in, readBaseId, suggestNextSenderOffset,
                              channel helpers
static/js/mappings.js         EEP tree, profile detail, inline mapping editor
static/js/settings.js         MQTT config, EEP.xml info/upload/download, backups
static/js/app.js              DOMContentLoaded init, wiring, intervals
templates/index.html          HTML only, plus the inline anti-flash theme script
                              and the runtime loader for the css/js above
```

Optional later: split the HTML pages into Jinja `{% include %}` partials (dashboard.html, devices.html, teachin.html, mappings.html, settings.html). Do this only after the JS/CSS split is stable.

## Execution steps (each step is shippable and testable on its own)

1. Extract CSS. Move the `<style>` contents to `static/css/app.css`. Load it Ingress-aware. Verify both themes with the harness. Ship as one beta.
2. Extract JS in slices, one file per beta, lowest-dependency first: core, then theme + i18n, then nav, then dashboard, devices, teachin, mappings, settings, and finally app.js (init). After each slice, load the new file and remove that code from the inline script. Keep functions global. Validate after each slice.
3. When the inline `<script>` blocks are empty except the anti-flash head script, delete them.
4. Optional: template partials.

Do it in `addon-beta/` first. Promote to `addon/` only after a beta confirms nothing regressed.

## Validation (do this every step, it is cheap)

Reuse the iframe harness pattern from the theme fix:
- A parent HTML with HA-like CSS vars and a transparent body, an iframe loading the template.
- Assert with `javascript_tool` returning small JSON: theme attributes, computed styles of a few surfaces, and that key global functions exist (`typeof window.saveDevice === 'function'`, etc.).
- Check the browser console for JS errors (ignore the expected API 404s in the static harness).
- Test both light HA + dark OS and dark HA + light OS.
- `python -m py_compile` is not needed (frontend only), but keep the JS-balance grep sanity check.

Avoid screenshots and full `read_page`. See [[token-cost-discipline]].

## Risks and rollback

- This is the file users touch most, mid-beta. Risk of breaking a handler if a function is missed during extraction. Mitigation: extract by whole function group, grep for every reference, validate handlers exist after each slice.
- Ingress path bugs only show inside HA, not standalone. Mitigation: one real Ingress smoke test after the CSS extract and after app.js.
- Rollback is trivial per step: each slice is one PR; revert the PR.

## Not in scope

- No behavior changes. Pure restructuring.
- No ES modules, no bundler, no framework.
- No dependency upgrades (Bootstrap stays as is).

## Effort

One focused session per major slice, roughly: CSS (small), core+theme+i18n (medium), the feature files (one each, medium), app.js wiring (medium). Spread across a few betas so each is easy to verify.
