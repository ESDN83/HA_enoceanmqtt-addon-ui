# 0048. Add the missing channel of a two-channel module

Status: proposed (beta).

## Context

A two-channel module (D2-01-11, D2-01-12) is one device per output, with the
same address, profile and sender ID (ADR-0005). The wizard offers the second
channel right after a teach-in (#24), but a module that was entered by hand,
imported from another app or turned from a sensor into a light has only one
channel, and adding the other meant retyping everything by hand.

## Decision

- A device whose module has exactly one of its two channels configured (same
  address and profile) gets an *Add channel N* button in the device list
  (cards and table) and on the device page.
- The button creates the other channel through the existing `POST
  /api/devices`, after a confirmation: same address, profile, sender ID,
  room, manufacturer, model, role, invert and availability timeout, with the
  other `channel`. No new endpoint; the identity clash check (#63) and the
  multi-channel discovery refresh apply as for any new device.
- Not the description: on a two-channel module it names the channel's entity
  (ADR-0005), so a copy gave both switches the same name in Home Assistant.
  The new channel is named after its device name until it gets its own.
- Name: the source name plus ` CH1` or ` CH2`. A channel suffix the source
  name already has (` CH1`, `-ch2`, as the wizard used) is replaced rather
  than stacked. Names are capped at 64 characters (`maxlength` on the name
  field); a longer result has the end of the name cut so the suffix fits.
- Frontend only, no backend change.

## Consequences

- The 64-character cap is new for names typed in the form. Existing longer
  names keep working; the API does not enforce it.
