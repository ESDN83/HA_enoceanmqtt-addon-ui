# 0015. An Eltako shutter is driven to a position by time, after a second teach-in

Status: accepted (v1.8.2-beta1), amended by the first field report
(v1.8.2-beta2, see "Amendment" below). Extends ADR-0014, follows the routing
rule of ADR-0003.

## Context

Since 1.8.1 an Eltako shutter (FSB, FJ62) is driven with rocker taps and
reports its own state, and with a travel time set it also reports a position.
That position was read-only: a rocker tap carries a direction and nothing else,
so there was no way to send the shutter to 40 %. Two reports asked for the
missing half within a day of each other (#40, and the community forum: four
FJ62NP running, no percentage entity).

Eltako's own documentation covers the path, EEP A5-3F-7F ("Inhalte der
Eltako-Funktelegramme", section *FJ62/12-36V DC, FJ62NP-230V*):

- **Teach-in**: `00 00 00 28` unlocks the learn mode, `FF F8 0D 80` teaches the
  gateway in as GFVS. The actuator switches its confirmation telegrams on by
  itself and locks the learn mode afterwards.
- **Travel command**: `DB3+DB2` runtime, `DB1` `0x00` stop / `0x01` up /
  `0x02` down, `DB0` bit3 data, bit2 block for pushbuttons (kept at 0), bit1
  time base (0 = seconds in DB2, 1 = 100 ms over DB3+DB2). The actuator's own
  runtime setting is ignored whenever a time is sent.

openHAB's `A5_3F_7F_EltakoFSB` encodes the same bytes and served as the second
implementation to check against, as it did for the receive side in ADR-0014.

## Decision

- **A position is a runtime.** `|target - current| / 100 * travel_time`, sent
  in 100 ms steps. Whole seconds would move a 30 s shutter in steps of 3 %.
  Open and close send the full travel time, which reaches the end from any
  position and lands on an end position, where the position resynchronises.
- **The position is not echoed.** The actuator answers a travel with the time
  it actually ran, and ADR-0014 measures that report against the position the
  shutter had *before* the command. Writing the target in first would make the
  report count the same move twice. openHAB tracks an FSB from the same
  reports for the same reason.
- **The command path is opt-in per device, not derived from the EEP.** GFVS is
  a *second* teach-in, separate from the directional pushbutton, and nothing in
  a telegram says whether an actuator has it. The EEP field says which profile
  the device's reports are decoded with, which is not the same question, so
  ADR-0003's "route by EEP" is answered here by a flag that is more specific
  than the EEP: `position_control`, ticked by whoever did the teach-in. With it
  off, every cover behaves exactly as in 1.8.1.
- **With it on, all four commands travel by time**, stop included (`DB1 =
  0x00`). Mixing paths would leave the add-on guessing which teach-in an
  actuator still holds; one flag, one protocol, and the flag is a checkbox away
  from being reverted.
- **`set_position_topic` appears in the discovery only with the flag and a
  travel time.** A slider that cannot move the shutter is worse than no slider.
- **Such a cover stops being `optimistic`.** Every cover entity was marked
  optimistic, from the days when an Eltako shutter reported nothing. With the
  flag on it has both a target and real feedback, and leaving it optimistic
  makes Home Assistant keep its own idea of the position while the add-on
  measures the next move against the reported one: on the test bench the two
  drifted apart within two commands. It also renders the entity as
  `assumed_state`, which hides whether the actuator reports at all, the one
  thing this beta is meant to find out.
- ~~**The GFVS teach-in is sent four times by default.**~~ Reversed by the
  field report, see the amendment. Eltako names no repeat count for GFVS, and
  one telegram is easy to miss: the reporter of #40 needed four rounds of the
  *pushbutton* teach-in before an FJ62 took it. The assumption that repeats
  cost nothing once the actuator has locked its learn mode was wrong. The
  dialog carries the count and warns that the lock has to be released by hand
  (4 short taps and one long one on an already learned pushbutton) before
  anything else can be taught.

## Consequences

- An unknown position with a percentage command assumes the end furthest from
  the target. The run is then at most one full travel, and a shutter that stood
  somewhere else reaches its end position and reports it, which synchronises
  every command after that one.
- The position is only as good as the configured travel time, and a shutter
  moved by a wall switch stays tracked exactly as in ADR-0014: through the
  actuator's own reports.
- If a field test shows that an FJ62 stays silent after a *commanded* travel
  (it reports one it was tapped into), the position would freeze at its last
  value and the echo this ADR argues against would have to come back, with the
  matching report suppressed. openHAB relying on those reports says it does not.

## Amendment (v1.8.2-beta2), from the first field report on an FJ62/12-36V DC

Three things came back from #40, and two of them are corrections.

- **The GFVS teach-in is sent once.** Four rounds locked the actuator so hard
  that a factory reset no longer reached it; about an hour disconnected from
  power brought it back. "Repeats cost nothing" was an assumption, and it was
  wrong: the actuator locks its learn mode the moment it has stored the sender,
  so every further round arrives at a locked actuator. The default is 1, the
  count stays adjustable up to 10 for an actuator that really does miss the
  first telegram. *Repeat Teach-In (30s)*, which would fire a sequence every
  two seconds for half a minute, is hidden for this option, and
  `/api/gateway/teach-in-repeat` refuses `cover_gfvs` outright rather than
  leaving the hazard one API call away.
- **A travel report is accepted on either time base.** The report was only read
  when DB0 was `0x0A`, on the reasoning that a *command* uses the seconds base
  and the strict match therefore also rejects a foreign gateway's command. That
  reasoning does not hold, because this add-on's own commands use `0x0A` too,
  and it cost every report that came back on the seconds base. Only bit3 (data
  telegram) and a direction in DB1 are required now; bit1 decides whether
  DB3+DB2 is read as 100 ms or as seconds.
- **The assumed position is written down before the command.** The report is
  relative and needs a previous position to be measured against. When the
  position was unknown, the command assumed an end but kept the assumption to
  itself, so the report that followed had nothing to measure against and was
  discarded: the slider only ever moved when an end stop was hit, which is
  exactly what the field report describes. The assumed *pre-command* position
  is now published before the telegram goes out. It is not the target, so the
  argument against an optimistic echo above still stands.

Confirmed by the same report and left alone: the actuator does send its travel
report after a *commanded* travel, not only after a pushbutton one, so the
fallback the Consequences section held in reserve is not needed. Still open,
and the reason the travel report is now logged at info level next to the
command that caused it: whether an FJ62 honours the 100 ms time base for a
partial run, or runs its full travel regardless.

## Sources

- Eltako, "Inhalte der Eltako-Funktelegramme", section *FJ62/12-36V DC,
  FJ62NP-230V*.
- openHAB `A5_3F_7F_EltakoFSB`, second implementation of the same bytes.
- Issue #40, and the forum report of four FJ62NP without a position entity.
