# Frontend Refactor Plan: split the index.html monolith

Status: in progress since 2026-07-26, on the 1.8.0 beta line. Measurements below were taken against `addon-beta` at 1.7.0-beta9, which is also what stable 1.7.0 ships. Run it as its own change, beta-first, and do not mix it with functional work.

## Why

`templates/index.html` is one file of ~4110 lines containing all HTML pages, the entire CSS (one `<style>` block), and the entire app logic (three `<script>` blocks). Every UI change, however small, means loading and searching a 4000-line file. That is slow, expensive, and error prone. The Python backend is fine (14 modular files under `core/` and `api/`, largest ~1300 lines). The problem is only the frontend.

Left as is, further UI work keeps getting harder. This plan splits the frontend into focused files so each future change touches 200 to 400 lines.

## Current state (measured 2026-07-25)

- `addon-beta/rootfs/app/templates/index.html`: 4128 lines.
- One inline `<style>`: 319 lines of CSS.
- Three inline `<script>` blocks: 43, 9 and 3034 lines, so 3086 lines of JS holding 102 top-level functions. Nearly everything is in that third block.
- 66 inline event handlers in the HTML, of which 59 are `onclick`, the rest `onchange` / `onsubmit` / `oninput`. All call bare global function names.
- One external `<script src>`: Bootstrap 5.3.2 from a CDN. Out of scope here, but note it is the only remote dependency.
- `static/css/`: empty (`.gitkeep`). `static/js/`: only the vendored `js-yaml.min.js`.
- Static is served at `/static` (`app.mount("/static", StaticFiles(...))`, `main.py:466`). Under HA Ingress the base path is dynamic, so assets must be loaded Ingress-aware. The app already does this for js-yaml (`base + '/static/js/js-yaml.min.js'`, around line 1088) and i18n (`getApiUrl('/static/i18n/...')`).

## Hard constraints (do not break these)

1. Buildless. There is no npm/webpack/bundler. FastAPI serves static files directly. Keep it that way: plain `.js` files loaded with classic `<script src>`, no bundler step.
2. Functions must stay global. The 59 inline `onclick` handlers call bare function names. ES modules create scope and would break every handler. So split into classic scripts (not `type="module"`); functions remain on `window`. Do not convert to ES modules in this pass.
3. Ingress-aware loading. New `<script src>` and the CSS `<link>` must resolve under the dynamic Ingress base path. Inject them at runtime with the computed base (same mechanism as js-yaml), or make sure relative paths resolve. Test inside Ingress, not only standalone.
4. Early theme script stays inline. The small `<head>` script that sets the theme before first paint must remain inline to avoid a flash of the wrong theme. Do not externalize it. See [[theme-detection-ha-transparent-body]].
5. Load order matters. Classic scripts run in order. Put shared helpers first, feature files after, init last.
6. `{{ version }}` Jinja var stays in the template.
7. Move each rule to exactly one place. Two bugs in beta7 and beta8 came from the same rule existing in two copies that drifted apart: discovery naming lived in both the edit path and the startup republish, and the "invert" field visibility lived in both the role dropdown and the edit form. Splitting a 3000-line file is precisely when a function gets copied instead of moved. After each slice, grep for the old name and confirm there is one definition, not two.

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

## Move the code, do not retype it

Retyping the bodies through a model context is what would make this expensive,
so do not. Move whole functions by line range with a throwaway script, and have
it prove the move: the extracted lines plus the remaining lines must reproduce
the original block line for line, or it writes nothing. The same round-trip
check applies to the CSS extract, where the only permitted edit is removing the
template's eight-space indent.

Listing the top-level functions with their sizes is enough to plan a slice
without opening the file. Measured: 2804 of the 3035 lines in that block sit
inside top-level functions. The remaining ~230 lines are globals,
`DOMContentLoaded` wiring and intervals; no line-range move handles those, so
move them by hand into `app.js` in the last slice.

Nothing automated should add the `<script src>` loader. Do that once, by hand,
Ingress aware, when the first file is created.

The helper scripts used for this live on the maintainer's machine and are
deliberately not in the repo, so treat the method above as the contract, not any
particular script.

## Execution steps (each step is shippable and testable on its own)

1. Extract CSS. Move the `<style>` contents to `static/css/app.css`. Load it Ingress-aware. Verify both themes with the harness. Ship as one beta.
2. Extract JS in slices, one file per beta, lowest-dependency first: core, then theme + i18n, then nav, then dashboard, devices, teachin, mappings, settings, and finally app.js (init). After each slice, load the new file and remove that code from the inline script. Keep functions global. Validate after each slice.
3. When the inline `<script>` blocks are empty except the anti-flash head script, delete them.
4. Optional: template partials.

Do it in `addon-beta/` first. Promote to `addon/` only after a beta confirms nothing regressed.

`addon/` and `addon-beta/` were byte-identical when the split started (both the 1.7.0 template). Do not try to keep the two in sync during the split. Finish the split in beta, then promote by copying the whole result over.

## Validation (do this every step, it is cheap)

Deploy the changed files into the running devcontainer add-on and restart it, which takes seconds. Syntax-check the remaining inline JS with `node --check` before copying: an unbalanced brace produces a page that serves fine and does nothing. After deploying, load the UI through Ingress and confirm the page still serves and the console is clean. Reading `main.py`'s served page with curl only proves it is served, not that it runs, so open it once per slice.

A cheap guard against a lost function, run after each slice:

```js
['saveDevice','editDevice','navigateTo','startTeachIn','loadDevices']
  .filter(f => typeof window[f] !== 'function')
```

Also reuse the iframe harness pattern from the theme fix:
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

Retyping 3000 lines through a model context is what makes this expensive, so do
not: use `extract.py`. With the script the cost per slice is dominated by the
template edit, the loader wiring and the validation, not by the code volume.

Rough order, one slice at a time: CSS (small), core plus theme plus i18n
(medium, this is also where the loader gets built), then one feature file per
slice (each medium), then `app.js` with the leftover ~230 lines of wiring
(medium, and the fiddliest, since it is the part the script will not move).

Budget it as several sessions rather than one. The limit is not cleverness, it
is that each slice needs a real Ingress check before the next one starts, and
rushing that is how an inline handler silently loses its function.
