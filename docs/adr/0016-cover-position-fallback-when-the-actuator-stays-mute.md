# 0016. A commanded travel falls back to its target when the actuator reports nothing

Status: accepted (v1.8.2-beta3), amended by the FSB61NP field log
(v1.8.2-beta4, see "Amendment" below). Extends ADR-0015.

## Context

ADR-0015 tracks the position of an Eltako shutter purely from what the actuator
reports, and argues explicitly against writing the commanded target into the
state: the actuator answers a travel with the time it actually ran, that report
is measured against the position the shutter had *before* the command, and an
optimistic echo would make the same move count twice.

That holds for an actuator that answers. The first field reports on #40 produced
one of each:

- an **FJ62/12-36V DC** reports after a commanded travel. Four moves at a travel
  time of 40 s came back with exactly the commanded runtimes and the position
  followed.
- an **FSB61NP** looks like it does not. Commands work, the shutter moves, and
  the position never leaves the end stops.

Eltako's "Inhalte der Eltako-Funktelegramme" has one shared confirmation section
for FSB61NP-230V, FSB71, FJ62/12-36V DC and FJ62NP-230V, and it is silent on
exactly this case:

> Wenn der Aktor vor Ablauf von RV gestoppt wird, wird nur die tatsächlich
> gefahrene Zeit mit Angabe der Richtung in einem ORG7 Telegramm mit derselben
> ID geschickt! Das ist zugleich auch die Info, dass der Motor jetzt steht.

The runtime report is documented for a run that was **stopped before RV
expired**. A commanded travel carries its own runtime, and "die
Laufzeiteinstellung am Gerät wird ignoriert", so for one reading nothing was
stopped early and nothing is reported. Both readings fit the sentence, and the
field has produced an actuator for each.

Without a report the failure was worse than a stale position: the F6 start
telegram (`0x01`/`0x02`) was the last thing to arrive, so the entity also stayed
on *opening* or *closing* forever.

## Decision

**Report first, commanded target second.** Every A5-3F-7F travel is remembered
with the position it was measured against, and settled by whichever comes first:

- **A travel report wins**, always, and is measured against the remembered
  baseline rather than against whatever is currently published. That is what
  keeps the fallback from ever being counted twice: the report does not see the
  fallback's value.
- **An end position wins** the same way. It is absolute, so it answers the
  command outright.
- **Otherwise the commanded target becomes the position**, once the commanded
  runtime plus a three second grace has passed with nothing heard.

A **stop cancels the fallback but keeps the baseline**: the travel will not
reach what it was sent to, so the target is not the answer, while the report the
actuator sends for a stop is still measured against the position it started
from.

**No per-device option.** Nothing in a telegram says which of the two families
an actuator belongs to, and asking the user to know is asking them to read the
same ambiguous sentence. The timeout distinguishes them at runtime, per command,
and needs no configuration.

## Consequences

- On a mute actuator the position is only as good as the configured travel time,
  because nothing measures the run. On a reporting one nothing changes at all.
- A lost report is indistinguishable from a mute actuator, so a dropped report
  now writes the commanded target instead of freezing the position. For a
  command that did run, that is the better of the two failures.
- The position settles three seconds after the run on a mute actuator, rather
  than at the moment the report would have arrived.
- ADR-0015's refusal of an optimistic echo stands where an actuator reports. The
  fallback is not an echo: it never runs while a report is coming.

## Verification

The fake transceiver in the devcontainer models both readings of the sentence
above (`fake-tcm.sh shutter <device> mode=fj62|fsb61`), so the add-on can be
held against either without hardware. At travel time 10:

- `fsb61`: 100 % to 60 % sent `CLOSE 4.0s`, the model moved to 60 % and stayed
  silent, and the add-on settled on 60 % after the grace instead of holding 100 %
  and *closing*.
- `fj62`: 60 % to 20 % and 20 % to 80 % were answered with `0028020A` and
  `003C010A`, the position followed the reports and the fallback did not fire.
- A stop three seconds into a full close was reported as `001D020A`, landing on
  51 % against the model's 51.4 %, with no fallback afterwards.

## Amendment (v1.8.2-beta4): an FSB61NP does not stay mute, it claims an end position

The fallback above was built on the assumption that a mute actuator says
nothing at all. The log from the real FSB61NP says otherwise (#40). Commanded
from fully open to 75 % at a travel time of 40 s, it ran the 10 s it was given
and then sent **`0x50`, "lower end position"**, with the shutter a quarter of
the way down:

```
17:34:54  Sending A5-3F-7F CLOSE for 10.0s   (data 0064020a)
17:34:54  RX F6 02   -> travel down started
17:35:04  RX F6 50   -> "lower end position"
```

Eltako describes that telegram for a command that finds the shutter already at
an end: "wird bei einem Fahrkommando trotzdem das Relais eingeschaltet ... und
nach Ablauf der RV abgeschaltet. (0x70 oder 0x50 wird gesendet)". This actuator
sends it at the end of *every* commanded run. It means "the relay is off
again", not "an end stop was reached", and taking it literally drove the
position to 0 % and the entity to *closed* on every partial move: worse than
the freeze the fallback was written for.

**So an end position is absolute only when no partial travel is in flight.**
While one is, `0x70`/`0x50` settles that travel with its commanded target
instead. The two cannot be told apart from the telegram, and of the two
possible errors, a position off by the tracking error beats a position that
jumps to an end the shutter is visibly not at, and that corrects itself at the
next full travel anyway. A full travel is unaffected: there the end position
and the target say the same thing.

The published state follows the position it produced, so a cover cannot be
*closed* at 75 % any more.

The simulator grew a third model for this: `fj62` reports the run time,
`fsb61` claims the end position, `mute` says nothing. Only the first two have
been seen in the field; `mute` keeps the timeout fallback under test.

Verified at travel time 10, each against the model's own physical position:
`fsb61` 100 % to 75 % landed on 75 % (*motor stopped*, not 0 %), `fj62` 75 % to
25 % on 25 % from its report, `mute` 25 % to 60 % on 60 % from the fallback, and
a stop three seconds into a full close on 31 % against the model's 31.5 %.

## Sources

- Eltako, "Inhalte der Eltako-Funktelegramme", section *Bestätigungs-Telegramme
  bidirektionaler Aktoren*, FSB61NP-230V / FSB71 / FJ62/12-36V DC / FJ62NP-230V,
  and the command sections *FSB14, FSB61, FSB71* and *FJ62/12-36V DC,
  FJ62NP-230V*.
- Issue #40, both field reports.
