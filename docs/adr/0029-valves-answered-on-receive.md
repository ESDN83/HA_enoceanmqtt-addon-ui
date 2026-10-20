# 0029. Radiator valves are answered on receive

Status: proposed (v1.8.5-beta2, amended in v1.8.5-beta3).

## Context

A battery or energy harvesting radiator valve (A5-20-01, e.g. Micropelt
MVA004 / SAM, Kieback&Peter MD15) transmits every few minutes and then listens
for about one second. A command sent at any other time is never received. It
pairs with a 4BS bidirectional teach-in: it sends a query and wants a response
in that same second (green flash; three red flashes when nobody answers). The
app answered neither (forum post 73, log of a real MVA004 on a USB300).

## Decision

- Formats taken from the Micropelt datasheet and checked against two
  independent implementations, FHEM `10_EnOcean.pm` (hvac.01) and embyt
  enocean-mqtt (`answer`):
  - teach-in response: the query's DB3..DB1 unchanged, DB0 = 0xF0, addressed
    to the valve;
  - answer: DB3 setpoint (% or 0..255 = 0..40 C), DB2 room temperature 0x00
    (the valve's own sensor, per the Micropelt datasheet; FHEM sends its own
    room temperature here), DB1 0x08 summer bit and 0x04 temperature setpoint,
    DB0 0x08.
- The answer goes out from the receive path in a task of its own. The read
  loop processes telegrams inline and must stay free to read the
  transceiver's acknowledgement of that answer; awaiting it there would block
  until the acknowledgement times out. Measured latency 14 to 15 ms.
- Sender: the device's Sender ID, or at teach-in the lowest gateway offset no
  configured device uses (Eltako actuators act on a sender whatever the
  destination, so it is never shared). It is stored on an already configured
  valve and pre-filled in the form for a new one.
- An unknown valve is only answered during a teach-in session, so a
  neighbour's valve is never paired. A configured valve is answered any time.
- A valve's teach-in query is not decoded as data (its DB3 gave a 128 % valve
  position). A general "LRN bit = teach-in" rule for configured devices stays
  off because some devices (Staufix) send that bit in normal data.
- Home Assistant values (setpoint %, target temperature, mode, summer mode)
  are stored in `/data/valve_setpoints.yaml` and go out with the next answer.
  Setting a setpoint or a temperature also sets the matching mode. Default
  before anything is set: temperature mode at 21 C, so pairing never closes a
  valve.
- A valve's unique_ids leave the Sender ID out: it is assigned at teach-in,
  and putting it in would replace every entity of an existing valve.

## Consequences

- Room temperature from another Home Assistant sensor (DB2) and the
  maintenance functions FHEM offers (run-in, valve open/closed) are not
  supported yet.
- A5-20-04 and A5-20-06 are not answered; they use another reply format.
- A valve configured with a Sender ID before this change (unlikely, the form
  hid the field for sensors) gets new unique_ids once.
- The simulator logs each received telegram's destination and can send a raw
  telegram from any address, so teach-in and answers are testable without a
  valve.

## Amendment (v1.8.5-beta3): the rule holds for every send on receive

The UTE teach-in response (NodOn, D2-05/D2-01) was awaited inside the read
loop and ran into exactly this: the transceiver acknowledged after 12 ms, the
loop read it only after the 300 ms wait, logged "No transceiver ack" and held
the teach-in dialog for that long. It now goes out in its own task too. A
static check of `_process_radio_telegram` (every awaited call followed into
`_send_radio_packet`) finds no other send on that path.
