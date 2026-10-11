# 0027. Bundled profiles overlay, they are not copied

Status: proposed (v1.8.4-beta11).

## Context

Profiles that ship with the app (A5-3F-7F for Eltako shutters) were copied
into `/data/custom_eep` and compared with the bundled file on every start.
A deleted one came back after a restart (sp00ky, forum post 58), and an
edited one was silently overwritten. Once copied, the app could not tell the
user's change from its own, so a reset button would have had to guess.

## Decision

- Bundled profiles are read from the app image and never copied.
- Precedence per EEP: the user's file in `/data/custom_eep`, else the bundled
  profile unless the user removed it, else EEP.xml.
- Editing a bundled profile writes the user's file, marked with the bundled
  version it started from (`based_on_bundled`). It is never overwritten; if
  the bundled profile changes later, the UI says so.
- Deleting acts per source: the user's own profile is deleted; an edited
  bundled profile is reset (the edit is kept as `.bak`); an untouched bundled
  profile is removed and listed under "Removed bundled profiles" with a
  restore button. Removals are kept in `.hidden_bundled.yaml`, which config
  backups include.
- Existing installs: a copy equal to the bundled profile is deleted, so the
  bundled one applies; a copy that differs is kept as the user's edit.

## Consequences

- What a user deletes or edits stays that way across restarts and updates.
- Improvements to bundled profiles reach everyone who has not edited them.
- Deleting a custom profile now brings the EEP.xml profile of the same ID
  back at once; before, it was missing until the next restart.
