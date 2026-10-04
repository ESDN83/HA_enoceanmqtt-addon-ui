# 0019. A rocker cover's press time is a device setting

Status: proposed (v1.8.4-beta1), awaiting a field test on a Flextron ALADIN
300630.

## Context

A cover driven as a directional pushbutton (F6) is commanded by the time
between press and release. Since ADR-0012 the add-on sends a 100 ms tap,
because Eltako reads a short press as "run the full way" and a long one as
"move only while held".

A forum user with two Flextron ALADIN 300630 shutter receivers reported that
they barely move. Flextron documents the opposite convention: a short press
adjusts the slats (one step), a press longer than about 2 s starts continuous
travel, and a short press during travel stops. The user worked around it by
switching the receivers to single-button mode, where each tap cycles
up/stop/down/stop, which loses the explicit Open and Close.

The add-on had no way to send a long press. The transmit slot (ADR-0012)
holds the radio for the whole pair, and both the slot timeout (1 s) and the
command deadline (2 s) are shorter than a 2 s press.

## Decision

- New per-device field `press_time` (ms), cover only, 0 by default, at most
  5000. 0 keeps the 100 ms tap. It applies to Open and Close on the rocker
  path; Stop stays a tap, which stops a running shutter under both
  conventions.
- A press longer than the 250 ms short-press limit is sent as press and
  release in **separate** transmit slots, with the hold in between outside
  the slot. Other devices are not blocked for seconds, and a long press that
  ends a few milliseconds late still is a long press. The release is retried
  up to three times if the slot is busy, so it is not lost.
- The command queue grants a command its device's press time on top of the
  normal deadline, so a long press is not reported as timed out.

## Consequences

- Eltako users see no change: the field is empty and the tap path is the
  same code as before.
- The threshold for Flextron (about 2 s) comes from Flextron's ALADIN
  documentation as quoted in search results; the 300630 manual itself could
  not be fetched from the development environment. The hint suggests 2500 ms
  and the value is adjustable, so a different threshold needs no new release.
- A cover with a long press occupies one queue worker for its press time.
  With two workers a scene of several such covers runs one press time per
  pair of covers, not all at once.
