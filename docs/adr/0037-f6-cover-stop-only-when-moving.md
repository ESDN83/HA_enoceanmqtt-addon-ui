# 0037. A rocker-taught shutter is not sent Stop when it reported standing still

Status: proposed (v1.8.5-beta13, stop pending in beta14). Amends ADR-0014.

## Context

ADR-0014 sends Stop as a tap of the last direction, because Eltako shutter
actuators taught as a directional pushbutton have no stop command: a tap
while running stops, the same tap while standing starts a run. Issue #49
(two OPUS 561.164 = FSB61NP, debug log of 22 commands) reproduced it four
times: each time the actuator had sent its travel report 2-3 s before, so
the app knew the shutter stood still, and Stop started it again.

## Decision

- Per rocker-taught cover, the actuator's own reports are tracked: travel
  started (`F6 01` / `02`) means moving; an end position (`70` / `50`) or a
  travel report (A5, run time) means stopped.
- Every command sent clears it, before it is sent: the actuator answers
  about 200 ms later, possibly before the send returns.
- Stop is not sent only when the last report since the last command says
  stopped. Without such a report Stop is sent as before: stopping a moving
  shutter matters more than an occasional restart.
- A sent Stop is pending until a report answers it (travel report, end
  position, travel started) or OPEN/CLOSE is sent. While pending, and for at
  most 2 s, further Stops are not sent: the actuator takes a second tap as
  a new run (beta13 field test: a double tap restarted the shutter 4 of 4
  times, and a Stop queued just before the travel report went out just
  after it). Travel reports came 0.2-0.4 s after a Stop; after 2 s without
  one, the Stop is taken as lost and is sent again.
- Covers with position control (A5-3F-7F) are unchanged: their Stop is a
  real stop command.

## Consequences

- A shutter whose actuator does not send confirmation telegrams behaves as
  before (no reports, Stop always sent).
- A shutter moved by a wall switch after the last report is still treated
  as moving or stopped from the reports: its own travel reports keep the
  state current.
