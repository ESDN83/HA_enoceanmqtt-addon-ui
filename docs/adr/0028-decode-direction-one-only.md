# 0028. Received telegrams are decoded with direction 1 only

Status: proposed (v1.8.5-beta1).

## Context

EEP.xml describes bidirectional profiles with two blocks: `<data
direction="1">` for what the device sends and `<data direction="2">` for what
the gateway sends back. Only A5-20-01, A5-20-04 and A5-20-06 (radiator valves)
have them. The parser merged every `<data>` block into one field list, a rule
meant for `command="n"` variants. A received A5-20-01 telegram was therefore
also read as a reply: direction 2's TMP (offset 8, the status byte) replaced the
ambient temperature (offset 16), and SP, SB, SPS and others appeared from bits
the valve uses for something else (forum post 71, reproduced from its telegram
`18 30 7A 08`: 32.47 instead of 19.14 °C).

## Decision

- `direction="2"` blocks are skipped when building a profile's fields. Those
  fields describe a telegram the gateway would send, not one it receives.
- They are not kept anywhere yet. Driving a valve needs more than the field
  list (an answer within about a second of each received telegram, a 4BS
  teach-in response, stored set values); that is a separate decision when it
  is built.
- A5-20-01 gets a default mapping for its direction 1 fields. BCAP gets no
  battery device class: the EEP text ("change battery next days") and the
  Micropelt datasheet (1 = storage OK) disagree.

## Consequences

- Of the 97 bundled profiles only the three valves change (compared field by
  field against the previous parser).
- The mapping editor's pre-fill no longer offers the reply fields for them.
