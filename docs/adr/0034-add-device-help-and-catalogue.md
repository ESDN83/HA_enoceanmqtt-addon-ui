# 0034. The Add Device page explains itself, with a catalogue of verified devices

Status: proposed (v1.8.5-beta10).

## Context

Forum post 82: a user could not add Eltako FSR14-4x actuators. The actuator
teach-in asked for an "actuator address" without saying where it comes
from, and after a teach-in that worked (the LED stopped flashing) nothing
happened: the dialog only said to use Manual Entry. The user got it working
with an AI assistant and PCT14.

Newcomers do not know which of the three ways (Teach-In, Actuator Teach-In,
Manual Entry) fits their device, where the ID is, or what an EEP is. Rocker
switches send no teach-in telegram, so Start Teach-In never detects them,
which nothing told the user.

## Decision

- **A start page under Step 1**, shown while none of the three ways is open:
  which way fits which device, where the ID is, what the profile is.
- **How-to blocks in each way**: what to press while Teach-In waits, how
  actuator teach-in works and what the address is, where the values of the
  manual form come from.
- **Illustrations are drawn SVGs per device type**, not product photos:
  photos are copyrighted and there would be one per model. Nine types cover
  the catalogue (flush actuator with dials, 62 series, DIN rail with FAM14,
  D2 module, valve, contact, rocker, handle, sensor), four more the general
  steps. They carry their own light background, so they read the same in
  both themes.
- **A device catalogue** (`data/device_catalog.json`, `GET
  /api/help/devices`) with a search: per device the way to add it, the
  profile, the steps, where the ID is, pitfalls, and the source that
  verified it. "Start with this device" opens the right way with what is
  known filled in. Only devices with a source go in; everything else falls
  back to the generic guide. AI assistants read the same file.
- **Save device** after a successful actuator teach-in opens Step 2 with
  address, sender ID, actuator type and profile filled in. Not after a GFVS
  teach-in: that is the second teach-in of an existing cover.
- Page texts in all 11 languages; catalogue entries in English.

## Consequences

- Each verified device report adds a catalogue entry (with its source) and,
  for a new device type, an illustration. CI checks that every entry has a
  source, a valid method, a profile and an existing illustration.
- Teach-in steps that are not confirmed (OPUS actuators) say so instead of
  guessing.
