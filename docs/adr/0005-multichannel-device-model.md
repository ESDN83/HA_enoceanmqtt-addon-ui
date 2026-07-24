# 0005. Multi-channel actuator model

Status: accepted (v1.7.0-beta1 to beta5).

## Context

A two-channel module such as the NodOn SIN-2-2-01 (EEP D2-01-12) has one radio address and two independently switchable outputs. A UTE teach-in only reports the number of channels (DB5), never a channel index, and the observed teach-in payload is byte-identical for both channels. So the module cannot tell us "this pairing is for output 2"; one teach-in binds the whole module.

## Decision

- One teach-in binds the module. Each output is a separate device sharing the same address and sender ID; the target output is selected by the channel (IO) field in the addressed D2-01 command.
- A device has a `channel` field. The channel is part of the discovery `unique_id` so both channels get distinct HA entities on the same HA device.
- When several devices share one address, each entity uses its own configured device name (not the shared module name) so the channels are distinguishable.
- Incoming state is published to every device on the address, so both channels receive updates. The backend merges channel state (`OV`, `OV_CH1`) for D2-01-11/12.
- The wizard offers to add the second channel right after saving the first, pre-filled. Sharing one sender ID across channels is correct here; the sender-ID collision warning therefore applies only to non-D2 (broadcast) actuators.

## Consequences

- No follow-up teach-in telegram is expected or waited for. An earlier "wait for the channel telegram" idea was removed as wrong.
- Address lookup returns a list of devices, not one.
