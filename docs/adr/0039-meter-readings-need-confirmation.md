# 0039. Implausible meter readings need a second reading

Status: proposed (v1.8.5-beta15).

## Context

Issue #51: a field log showed corrupted radio telegrams after D2-01 queries,
among them a copy of a plug's energy reply with one bit flipped in the
sender ID and one in the value. It was dropped only because the sender no
longer matched. The app checks both ESP3 CRCs, so the corruption passes the
transceiver itself. Home Assistant reads a falling `total_increasing` value
as a meter reset: one corrupted value, followed by the real one, counts the
whole meter again and spoils the energy statistics for good.

A plain "never decrease" rule is wrong too: a plug that is reset or a meter
that is replaced starts again from zero, and that must go through.

## Decision

- Energy is implausible when it is lower than the last published value or
  rose more than 4 kW times the time since then (plus 0.01 kWh). Power is
  implausible above 4000 W (a D2-01 module switches at most 16 A).
- An implausible reading is not published. It is held, and the app queries
  the module again 0.5 s later (CMD 6).
- The next reading is published if it is plausible against the last
  published value (the held one was corrupted) or against the held one (a
  real reset or a new module). Otherwise it is held in turn.
- Without a time for the last value (after a restart) only a decrease
  counts as implausible.

## Consequences

- A corrupted reading costs one extra query and never reaches Home
  Assistant.
- A real reset appears after the confirming reading, normally within a
  second, at the latest at the next poll.
- The 4 kW bound only decides what gets a second look; a real higher value
  confirms itself.
