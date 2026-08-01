# 0010. Loading the split frontend without a build step

Status: accepted (1.8.0-beta1).

## Context

`templates/index.html` was split from 4128 lines into a stylesheet and ten JavaScript files (ADR-0006 and `docs/FRONTEND_REFACTOR_PLAN.md`). The files still have to reach the browser, and three constraints collide:

- There is no bundler and none is wanted, so every file is a plain `<link>` or `<script src>`.
- Under Home Assistant Ingress the base path is dynamic (`/api/hassio_ingress/<token>/`), so no href can be written statically into the template.
- The 59 inline `onclick` handlers call bare function names, so the files must be classic scripts that run before the handlers can fire, in dependency order.

The obvious approach, building the elements with `createElement` and appending them to `<head>`, was tried first and measured.

## Decision

Emit the `<link>` and the `<script src>` tags with `document.write`, from a small inline script in `<head>`, with the base path computed from `window.location` exactly as `getApiUrl()` and the existing js-yaml loader already do.

`app.js`, which holds the wiring, is written by a second such snippet at the **end of `<body>`**, not in `<head>` with the other nine.

## Consequences

- **`document.write` is deliberate, not legacy.** A `<link>` inserted from script is classified `renderBlockingStatus: "non-blocking"`, measured in the browser: the page may paint before the stylesheet arrives, which is a flash of unstyled content on a cold load. Written into the parser during the initial parse of `<head>` the same element measures `"blocking"`. The rule that makes `document.write` harmful, calling it after load, does not apply here.
- Parser-inserted scripts execute in document order, which gives the load order the split needs for free: shared helpers first, feature files after. Adding a file is one more entry in the array.
- `app.js` calls `detectAndApplyTheme()` immediately at the point it loads. The inline block it replaced sat at the end of the body, so loading it in `<head>` would apply the theme earlier than before. Keeping its position keeps the timing, which is what makes the split a move rather than a change. See ADR-0002 for why theme timing is delicate here.
- Functions stay global. No ES modules in this pass: module scope would break every inline handler.
- The cost is one small piece of inline JavaScript that cannot itself be moved into a file, since it is what loads the files.

## Follow-up: cache busting (1.8.0-beta6)

Splitting the file created a cache problem the monolith could not have. The template is rendered per request and always fresh, but the ten assets it pulls in are static files under `/static`, and nothing in their address changed between releases. A browser was therefore free to keep serving last version's copies alongside the new page. That is not theoretical: beta5 added a field to the device form, the template arrived with the new markup, Firefox reused its cached `devices.js` from beta4 where the function driving that field does not exist, and the field silently stayed away. Chrome revalidated and showed it, which is what made the report look like a template bug.

Every asset address now carries `?v=<add-on version>`, taken from the same `VERSION` the footer shows, so an update changes the address and the browser cannot substitute an old file. `window.APP_ASSET_V` carries the same value to the two loads that happen from JavaScript rather than from the template, the translation JSON and js-yaml.

A version query is enough here and a content hash is not needed: there is no build step to compute one, the assets only ever change together with a release, and the version is already read from `config.yaml` at runtime.

The fix only takes effect from the release that introduces it, since the page carrying the stamped addresses is the new one. Upgrading to beta6 may still need one hard reload; after that it cannot recur.
