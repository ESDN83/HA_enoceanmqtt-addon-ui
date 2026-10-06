# 0021. The page reloads itself after an update

Status: proposed (v1.8.4-beta6).

## Context

Two testers in a row ran a new beta with the previous version's scripts:
the new API answered, the old JavaScript drew the page. One got
"[object Object]" on save and no press-duration field (forum post 41), the
other the old migration table without the keep-IDs option (post 47). Script
URLs already carry `?v=<version>` (ADR-0010), so a fresh page load cannot mix
versions. The likely cause is a page that stayed open in Home Assistant across
the update, and possibly a cached copy of the page itself.

## Decision

- The page knows its own version (`APP_ASSET_V`). `loadStatus`, which already
  polls `/api/system/status` every 10 s, compares it with the server's.
- On a mismatch a banner offers a reload, and the next page switch reloads by
  itself. A page switch is the safe moment: no form is half filled in. An
  automatic reload at any other time could throw away a device being edited.
- The reload happens once per version (sessionStorage). If the mismatch is
  still there afterwards, the page itself is cached; the banner then asks for
  Ctrl+F5 instead of reloading in a loop.
- `/` is served with `Cache-Control: no-store`.

## Consequences

- Testers no longer need to be told to reload after an update.
- A browser without sessionStorage reloads at most once per page switch until
  the versions match, which a plain reload fixes.
