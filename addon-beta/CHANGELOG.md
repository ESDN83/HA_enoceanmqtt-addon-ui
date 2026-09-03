# Changelog

## [1.8.1] - 2026-09-03 (beta channel)

Same build as stable 1.8.1, which promotes beta1 and beta2. See the stable
changelog for the full list, including the note on covers keeping their current
direction across the update.

Since beta2, two fixes for warnings Home Assistant 2026.10 logs: a cover state
without a position rendered as `None` instead of nothing, and the gateway
diagnostics payload could go out without the command queue's counters.

**Tip: export your configuration first.** Settings > Import / Export > "Export
All" writes a zip with your devices, profiles and mappings.

## [1.8.1-beta2] - 2026-08-31 (beta channel)

Field feedback on beta1 from the reporter of #39. Stop works on his FJ62, the
rest of this is what he found next.

### Bug Fixes

- **Open and close were swapped on F6 covers.** Up is the top half of the
  rocker and down the bottom one, the way Eltako wires a directional
  pushbutton. It was the other way round, so close opened the shutter (#39).

  **Your covers keep running exactly as they do today.** The update ticks
  **Reverse direction** for every cover that already exists, which reproduces
  the old telegrams, and it says so in the log. Nothing moves differently after
  the update. If your shutter has been running the wrong way round, untick that
  box once and it is correct from then on. Covers added after the update need
  no box ticked at all.
- **"Reverse direction" now works on an F6 cover.** It only ever reached
  D2-05 covers, so ticking it on an Eltako changed nothing (#39).
- **The stop button in the add-on's own interface works.** The test buttons
  had their own copy of the rocker semantics and still sent a bare release.
  They now send through the same path as a command from Home Assistant, which
  also gives them the transmit pacing and the queue (#39).

See ADR-0014.

## [1.8.1-beta1] - 2026-08-30 (beta channel)

### Bug Fixes

- **Stop works on an Eltako shutter.** The stop command sent a bare rocker
  release, which no real rocker ever sends and the actuator ignored. It is now
  a short tap of the last direction, which is what Eltako documents as
  "interrupts the movement immediately". A stop while nothing is moving starts
  a run, exactly as the same tap on a wall switch does (#39).

### New

- **An Eltako shutter now reports its state by itself.** End position, start of
  a run and the time it actually ran are read from the actuator's own
  telegrams, whatever EEP the device is configured with, so a cover shows
  open, closed, opening and closing instead of nothing (#39).
- **Position for Eltako shutters.** Set **Travel time (s)** on a cover and the
  reported run times become a position, synchronised every time the shutter
  reaches an end position. Read-only for now. 0 keeps the old behaviour.
- **A5-3F-7F decodes as an Eltako shutter profile**, shipped as a bundled
  custom profile: travel time, direction and the pushbutton block flag, with
  the raw data bytes kept alongside.
- The teach-in dialog and the docs now explain the Eltako 62 series, where the
  number of teach-in telegrams picks the sender type: 3 for a universal
  pushbutton, 4 for a directional pushbutton, 5 and 6 for central up and down.

See ADR-0014 for the reasoning and the Eltako sources.

## [1.8.0] - 2026-08-25 (beta channel)

Same build as stable 1.8.0, which promotes beta14. See the stable changelog for
the full list and the three behaviour changes worth reading before you update.

**Tip: export your configuration first.** Settings > Import / Export > "Export All" writes a zip with your devices, profiles and mappings. Home Assistant's own backup before an update covers the same data, because the add-on keeps everything in `/data`, and it can be restored for this add-on alone without a full restore. The export is simply independent of all that, and it imports into any installation.

## [1.8.0-beta14] - 2026-08-23 (beta channel)

### Bug Fixes
- **A switching light actuator now reports its state to Home Assistant.** Reported on the community forum for an Eltako FL62NP: teach-in worked, switching worked, the add-on showed the switching status under the device, and the Home Assistant entity stayed on Unknown.

  The status confirmation these actuators send is a plain rocker telegram, and the add-on only recognised it in one exact configuration: device role "Actuator: Switch", with an F6 profile, confirmed on rocker B. Anyone who picked "Actuator: Light / Dimmer" for a light actuator, or taught the module in under A5-38-08 as several Eltako tables suggest, or has a module that confirms on rocker A, got no state at all. The confirmation is now read from the telegram itself, whatever the configured profile and whichever of the two roles is set.

- **A light actuator on an F6 profile can be switched from the "Light" role.** It used to be sent A5-38-08 dimmer commands, which a relay ignores, so the entity did nothing. It now sends the same rocker press the switch role sends. The brightness slider is gone from those entities, since a relay cannot dim.

- **The device page showed the wrong MQTT topics.** They were written as `enocean/<device>/state`, while the default prefix is `enoceanmqtt` and it is configurable on top of that. Anyone who went looking for their state topic was sent to one that does not exist. The page now shows the configured prefix.

- **An actuator entity is no longer Unknown after a Home Assistant restart.** The rocker release that follows every press carries no state, and publishing it deleted the state from the retained topic. The last known state is repeated instead.

## [1.8.0-beta13] - 2026-08-20 (beta channel)

### Bug Fixes
- **"Last telegram received" flooded the Home Assistant log too** (#38). The same defect as the duration sensor in beta10, at the entity next to it, and it survived that fix because it is quieter: one warning per publish instead of a warning and an error. Measured on a production install, 722 of them.

  While no telegram had been received the entity was fed the word `unknown`, and a sensor declared as a timestamp cannot parse that. Home Assistant rejected every one of those messages, so the entity stayed on Unknown by way of a rejection rather than by intent. It now sends the value the MQTT integration itself uses for "no value", which clears the state without validating it: the same Unknown in the interface, no log line behind it. "Transceiver base ID" used the same shortcut and was changed with it, although nothing rejected it there.

- **"Last telegram received" is no longer empty after every restart.** The telegram buffer only lives in memory, so a restart wiped it and the entity claimed nothing had ever been received, on an installation where the radio had been working for weeks. It now falls back to the newest timestamp in the device state cache, which does survive the restart. After a restart the entity shows when a telegram last actually arrived instead of nothing, and the Unknown state is left for the case it describes: an installation that has genuinely never received one.

## [1.8.0-beta12] - 2026-08-19 (beta channel)

### Changes
- **Installing or updating the add-on no longer fails when Home Assistant's wheel mirror is slow.** An update aborted mid-build while downloading a 133 kB file from `wheels.home-assistant.io` at 1.5 kB/s. Nothing was wrong with the add-on, and retrying sometimes helped, but the mirror stalls for minutes at a time and no amount of patience got the build through: it failed at a two minute limit and again at five.

  The add-on now installs its dependencies from PyPI, where the identical files arrive in a fraction of a second, and falls back to the Home Assistant mirror only for the rare architecture where PyPI has no ready-made package. A build that could not finish at all now takes under a minute.

## [1.8.0-beta10] - 2026-08-19 (beta channel)

### Bug Fixes
- **The gateway's "Last queue busy time" flooded the Home Assistant log** (#38). Reported from a production install: 1336 messages in 22 hours, one warning plus one error per minute. Until the first command had been sent the value was empty, and Home Assistant rejects that for a sensor declared as a duration with statistics. It now starts at 0 instead, which is the same statement in a form the sensor accepts: no burst yet, so the last burst took no measurable time. The messages stopped once a command had run and started again after every restart, which is why it looked harmless at first.

  Only that one entity was affected. The others carry no numeric declaration and were never a problem.

## [1.8.0-beta9] - 2026-08-09 (beta channel)

### Bug Fixes
- **"Last telegram received" stayed on Unknown** (#38). Reported straight from a production install. The add-on stamped its telegram buffer with a local time and no time zone, and Home Assistant silently discards a timestamp without one: the value never even arrived, the entity was never updated. Every timestamp the add-on emits now carries its time zone. The telegram monitor in the web UI was not affected, it reads the same value through the browser's own date parser, which accepts either form.
- **"Last telegram received" was up to a minute behind.** It was only refreshed by the once-a-minute availability pass. It now updates on every received telegram, throttled, so a busy installation cannot turn it into MQTT traffic.

## [1.8.0-beta8] - 2026-08-09 (beta channel)

### New Features
- **A new "Gateway Diagnostics" option adds a device for the add-on itself** (#38). Off by default and switched on in the add-on configuration, with a description there explaining when it is worth having. Nobody gets these entities without asking for them, and switching the option back off removes them again.

  Once on, an "EnOcean Gateway" device appears with seven entities. Four describe the gateway:

  - **Transceiver connected**, whether the USB or TCP gateway is actually talking to the add-on.
  - **Transceiver base ID**.
  - **Devices configured**.
  - **Last telegram received**, the time anything was last heard on the radio.

  Three describe the send queue, which is the part an automation can act on:

  - **Command queue busy**, on while anything is queued or on the air. This is the one to wait for, it goes off exactly when the last telegram has left.
  - **Commands pending**, how many are waiting.
  - **Last queue busy time**, how long the previous burst took, written once when the queue falls idle.

  They arrive switched on, since ticking the option was already the decision. Individual ones can be disabled in Home Assistant as usual. The busy entity also carries the dropped and timed-out counters as attributes.

  **How to use it.** Home Assistant considers a script finished once it has published its MQTT commands, which says nothing about whether the add-on has actually sent them, so chaining two scripts used to mean guessing a delay. Wait for the queue instead:

  ```yaml
  actions:
    - action: script.close_covers
    - delay: "00:00:01"
    - wait_template: >
        {{ is_state('binary_sensor.enocean_gateway_command_queue_busy', 'off') }}
      timeout: "00:02:00"
      continue_on_timeout: true
    - action: script.lights_off
  ```

  The entity id used above is the one the add-on ships with. **You can rename these entities freely**, in Home Assistant under the entity's settings, and put them wherever you like. Renaming, moving to an area or hiding them changes nothing about how they work, because the add-on identifies its entities internally and never by their id. Just remember to use your own id in the automation if you rename the busy one.

  The one second delay is not the guess it looks like. A script returns the moment its last MQTT message is published, which can be a few milliseconds before the add-on has reported itself busy. Without that pause the wait would look at a queue that is still idle and pass straight through. Everything after it is exact: the wait ends when the last telegram has left, whether that takes two seconds or twenty.

  Always give the wait a `timeout`, so a broken transceiver cannot stall the automation forever.

  Worth knowing: **none of this is needed to keep commands from being lost.** Nothing has been lost since beta7, commands only take their turn. These entities are for automations whose next step depends on the physical result, and for looking at how long a scene actually takes on the radio.

### Bug Fixes
- **Every telegram is logged again.** beta7 wrote its `TX EnOcean` line only for single telegrams, so the simulated button presses used for Eltako switches and blinds went out unlogged. In a debug log 40 of 43 telegrams were missing and could only be reconstructed by counting acknowledgements. The line is back for both halves of a press, in the same format as before.
- **Blinds now report whether the command went out.** The blind path was the only one that stayed silent about its outcome. Since blinds have no state feedback, that log line is the only evidence there is. NodOn blind commands were also reported as sent without checking, same as the others before beta7.

## [1.8.0-beta7] - 2026-08-08 (beta channel)

### Bug Fixes
- **Commands sent in quick succession were silently lost** (#38). Reported from the field on eleven Eltako F4SR14 relays and three dimmers: Home Assistant showed every device in the commanded state, but not all of them had physically switched. Spacing the commands 300 ms apart worked, anything faster did not. Three things went wrong at once.

  The add-on started every incoming command immediately, side by side. A scene therefore wrote a dozen telegrams into the transceiver at the same moment, and the transceiver has one radio and a small queue: what does not fit is dropped. The add-on then never looked at the transceiver's answer, which says exactly that, and reported the command as sent regardless. And because it counted as sent, the state was echoed to Home Assistant, so a relay that had heard nothing still showed as switched.

  Commands now go through a queue and are sent one at a time, with a pause between telegrams that the transceiver can keep up with. The answer is evaluated, and a command the transceiver did not accept no longer produces a state in Home Assistant, it produces a line in the log. A whole scene of 14 devices takes about one and a half seconds; before it was faster only because part of it was thrown away.

  No configuration needed, and no reason to keep delays in your scripts.
- **Blinds keep their exact button timing.** An Eltako blind actuator reads how long a button was held: briefly means run the full way, longer means move only while held. The simulated press and its release are now inseparable, so no other command can slip between them and turn a close command into a nudge of a few centimetres. If the timing is ever stretched anyway, the log says so.
- **One stuck command can no longer block all the others.** Every command has a deadline of two seconds, after which it is abandoned and the queue carries on. A transceiver that stops accepting data is recognised within half a second and reconnected instead of quietly holding up everything behind it. The release of a button press is exempt: it is always sent, otherwise a blind would keep running.

### Changes
- **The log now names lost commands.** A full or backlogged command queue, a telegram the transceiver refused, and a command that ran into its deadline each produce their own message. `/health` additionally reports how many commands are waiting, were dropped or timed out.

## [1.8.0-beta6] - 2026-08-01 (beta channel)

### Bug Fixes
- **A device whose name contains a slash could still not be opened, renamed or deleted** (#36). Carries the 1.7.3 fix. New names with `/` were already rejected, but devices that already had one stayed out of reach and failed with "Not Found", because the name is part of the web address of the request and a slash inside it splits that address. Those devices are reachable again.

  **Please rename them.** The slash also breaks commands: Home Assistant's command topic for such a device does not match what the add-on listens to, so a switch or blind with a slash in its name never receives anything. Renaming it fixes that.
- **The availability watchdog started its clock at every restart** (#37). Found in the field on an A5-30-03 that reports once a day. The device had been silent for 47 hours, the add-on was restarted, and it was reported unavailable exactly one full interval later instead of straight away. Restarting therefore cleared a genuinely dead device and cost up to a full interval of detection time each time. The clock now runs from the device's own last telegram, which survives a restart in the state cache. Only a device nothing has ever been heard from is counted from the start of the add-on. There is a two minute settling window after a start, so no verdict is formed before the connection is up and the cached states are back.
- **The browser could keep the previous version's web UI.** The add-on's stylesheet, scripts and translations were requested without a version, so after an update a browser was free to serve its cached copies of the old ones next to the new page. Firefox did exactly that and a new field went missing. Every asset now carries the add-on version in its address, so an update always loads the matching files. This takes effect from this version on: on the update to beta6 one hard reload may still be needed, after that no longer.

### Changes
- **The interval field in the device form is always visible.** It used to appear only when the box was ticked, which left the setting looking incomplete. It is shown greyed out instead and becomes editable when the box is ticked.

## [1.8.0-beta5] - 2026-07-30 (beta channel)

### New Features
- **A device can now be reported as unavailable when it goes silent** (#37). Off by default and switched on per device, because devices differ: a window contact may report twice a day, a temperature sensor every few minutes, and a switch actuator only ever transmits when it is switched. Tick the box in the device form and give the time within which a sign of life is expected. Leave generous room: a device that normally reports every 8 hours needs well over 8 hours, or it is marked unavailable during its normal quiet periods.

  The clock runs from the later of the device's last telegram and the add-on's own start. That way a device that really has been silent for weeks is marked shortly after a restart instead of looking freshly reported (the state cache republishes its last value on every start, which used to hide exactly this), while a device is never blamed for the add-on having been switched off: after a restart everything gets one full interval to check in first.

### Bug Fixes
- **Entities stayed "online" when the add-on died unexpectedly.** Every entity watched only its own device topic. The gateway's Last Will, which the broker publishes on an unexpected disconnect, sat on a topic nothing referenced, so a crash left every device looking alive while nothing was listening to the radio. A clean stop was fine, but a clean stop is not the case that matters. Entities now depend on the device and the gateway together.

## [1.8.0-beta4] - 2026-07-30 (beta channel)

Carries the 1.7.2 hotfix. Details in the stable changelog; the short version:

### Bug Fixes
- **A device could become impossible to edit or delete** (#36). The device name was written straight into the buttons' `onclick` code and into the API address. A name containing an apostrophe ("Volet d'entrée") killed the Edit and Delete buttons outright, and a name containing `/` or `#` produced an address that never reached the add-on. Names are kept out of the markup now and encoded in every request.
- **A failed delete reported success** (#36). The delete button never checked the answer, so a failed delete still showed "Device deleted" while the device stayed in the list. Failures now name the reason.
- **Deleted and renamed devices left ghosts behind** (#36). Their last state stayed in the cache under the old name and was republished as a retained message on every start, so a new device given that name later inherited it. Delete and rename clear the old name completely, a rename carries the state over, and leftovers from earlier versions are cleaned up once at the next start.
- **The state cache could lose a change**. It was only written after a telegram arrived, so a delete made shortly before stopping the add-on came back on the next start.

### Changes
- **Device names are checked when saved**. `/`, `+` and `#` are rejected with an explanation; they are not valid in an MQTT topic. Apostrophes, quotes and accented characters are fine.

## [1.8.0-beta3] - 2026-07-26 (beta channel)

### Bug Fixes
- **The layout became unusable in a window of medium width, and stacked in two steps instead of one.** One cause behind all of it: the sidebar appears at 768 pixels and takes about 250 pixels from the content, and every grid on every page chose exactly that width to switch from one column to three or four. Content lost a quarter of its room and was divided at the same moment, so a device card shrank to 142 pixels, the mapping editor's fields were squeezed into a 261-pixel pane, and the dashboard tiles looked stacked, then side by side, then stacked again. Every grid now reaches its dense layout one step later, past the sidebar. Measured: a device card is 225 pixels instead of 142 at that width, the mapping editor pane 503 instead of 327, and the dashboard goes two tiles per row and then four, never back, with the tiles never getting narrower on the way.

## [1.8.0-beta2] - 2026-07-26 (beta channel)

### Bug Fixes
- **After restoring a backup, devices stayed invisible in Home Assistant until each one was opened and saved.** Import and restore rewrote the device list and reloaded it, but never announced the result: no discovery config and no state was published, so Home Assistant kept knowing only the devices it had seen before. Both paths now re-announce everything, the same way a restart does. Verified on a restore: 39 discovery configs and 11 states published without touching a single device.
- **Two helpers in the API never ran at all.** They reached back into the application with `from main import ...`, but the add-on starts as `python3 main.py`, so the running module is `__main__` and that import quietly built a second, empty copy, every call returned without doing anything, while still logging success. Both take their handle from the application state now. This is what kept the restore fix above from working on the first attempt, and it also disabled the state echo after a test command from the add-on's own interface.
- **The edit and delete icons in the device list touched each other, and slid out of the card on a narrow window.** They sat in a Bootstrap button group, which pulls adjacent buttons together with a negative margin so their outlines share an edge. Separately, a flex item refuses by default to shrink below its own content, so the device name pushed the buttons past the card edge well before the layout stacked, the longer the name, the earlier. The buttons are spaced apart, the name may shrink and wrap, and the buttons may not shrink. Checked at 1280, 560 and 375 pixels with a 47-character name: the buttons stay 17 pixels inside the card at every width and the page never scrolls sideways.

## [1.8.0-beta1] - 2026-07-26 (beta channel)

Mostly an internal restructuring of the web interface: it lived in one 4128-line file and is now split by topic, so future UI work stays affordable. That part changes nothing you can see, and **if anything in the interface behaves differently than it did in 1.7.0, that is a bug in this build, please report it.** Two small visible improvements ride along, listed below.

### New Features
- **A warning before changing a device's identity** (#35). Address, RORG, FUNC, TYPE and Sender ID say *which* physical module an entry describes. Editing one does not reconfigure anything over the air, so the entry quietly stops matching the module that was taught in. Saving such an edit now asks first and lists exactly what is about to change, old value next to new. Renaming is folded into the same dialog, so changing a name and an address at once asks once instead of twice.

### Fixed
- **A dimmer's entity kept showing the old brightness after a command.** Switching or dimming a light from Home Assistant sent the telegram, but nothing was published to the state topic, so the entity waited for the actuator's own status report, and if that report was lost on the way, the stale value stayed forever. The lamp obeyed while Home Assistant still read 18%. The commanded state is now published immediately, the way it already worked for switch actuators (ADR-0008); a real status report from the actuator still overwrites it. The same was missing when switching a lamp from the add-on's own test button, which drives the actuator directly, that publishes a state now too.
- **Five interface strings were never translated in any language**, because their keys existed in no language file: the whole rename confirmation dialog, and the "Reverse direction" label for covers. On a German interface the switch role showed German and the cover role English in the same field. Both languages now carry the keys.

### Changed
- **The web interface is no longer one file.** `templates/index.html` went from 4128 lines to 808: the stylesheet is now `static/css/app.css` and the code sits in ten files by topic (core, theme, i18n, nav, dashboard, devices, teachin, mappings, settings, app). Nothing was rewritten, the code was moved. There is still no build step. Everything is loaded Ingress-aware and render-blocking, so the first paint is styled, and `app.js` deliberately loads at the end of the page, where the old inline code sat, so the theme is applied at exactly the same moment as before.

## [1.7.1] - 2026-07-26 (beta channel)

Same fixes as stable 1.7.1: every command was transmitted twice (overlapping MQTT subscriptions), the debug log flooded with one line per discarded byte, and a duplicated "Connected to MQTT broker" line. See the stable changelog for detail.

## [1.7.0] - 2026-07-26 (beta channel)

Promoted to stable. The beta channel now serves exactly the same code as the stable add-on, so both are on 1.7.0 and the next beta starts from here. Nothing changed since beta9.

**If you enabled "Invert reported state" on an Eltako switch actuator during beta5 to beta7, turn it off.** The default was corrected in beta8, so the workaround now inverts a correct value.

The full 1.7.0 release notes are in the stable add-on's changelog; the beta entries below are the development history.

## [1.7.0-beta9] - 2026-07-25 (beta channel)

### Bug Fixes
- **D2-01 modules now report their state back to Home Assistant** (#34 follow-up). A D2-01 actuator answers with a status telegram carrying the channel (`IO`) and the output value (`OV`), but that was decoded and then never mapped to the entity state. The switch only ever showed the result of commands sent from Home Assistant, so switching at the module itself, or from another sender, was invisible. The status is now applied to the device whose channel matches `IO`, and only to that one, so on a two-channel module each output keeps its own state instead of inheriting its neighbour's.
- **A D2-01 module configured as a light was always reported off**. The light path reads `SW` and `EDIM`, which only exist in an Eltako A5-38-08 telegram. For a D2-01 those fields are missing, so the state came out as off on every report. The light path is now limited to the telegrams it was written for, and D2-01 lights take their state and brightness from `OV`.

## [1.7.0-beta8] - 2026-07-25 (beta channel)

> **If you enabled "Invert reported state" on an Eltako switch actuator in beta5 to beta7, please turn it off after this update.** The default was wrong and is now corrected, so the workaround is no longer needed.

### Bug Fixes
- **Switch actuators show a real toggle again, not two buttons** (community forum). A switch entity was published as optimistic, which makes Home Assistant treat it as `assumed_state` and render two buttons (on/off) instead of a single toggle. The entity is no longer optimistic, so it shows as a proper switch. To keep the immediate reaction that optimistic gave, the add-on now echoes the commanded state to the state topic right after sending, so the toggle also works for actuators that do not report their state. A status confirmation from the actuator overwrites that echo with the real value.
- **"Invert reported state" was hidden when editing a switch**. The option only appeared while the role dropdown was being changed; opening an existing switch device for editing showed it for covers only, so the setting could not be reviewed or turned off afterwards. The edit form now applies the same field rules as the role dropdown. This matters for the default change above: it is how you switch the old workaround back off.
- **Channel naming survived only until the next restart** (#34 follow-up). beta7 fixed the naming in the create and edit path, but the add-on's startup republish still had its own older copy of the rule: it published each channel entity under its device name and the shared module under one channel's description. Every add-on restart therefore silently renamed the channels back (for example both showing "Kueche"). Discovery naming now lives in one place that both paths call, so a restart keeps what was configured.
- **Eltako status feedback was inverted by default** (community forum). An Eltako actuator confirms its state with the opposite rocker code to the one we send as a command: it reports ON as `0x70` (BO) and OFF as `0x50` (BI), while the command for ON is `0x50`. The status sync used the command convention, so an FSR61 reported ON as OFF and users had to enable "Invert reported state" to compensate. The default now follows the Eltako confirmation convention. The invert option stays for actuators taught in the other way round.

## [1.7.0-beta7] - 2026-07-24 (beta channel)

### Bug Fixes
- **Editing a channel device no longer corrupts naming or leaves stale entities** (#34): On a 2-channel module (D2-01-11/12), editing one channel renamed *both* channel entities to the same name, and identity edits (address, Sender ID, EEP, channel) left the old Home Assistant entities behind as orphans that piled up. Root cause was in the edit/save path, now fixed in three places: it (1) keeps the `channel` field (it was silently dropped, so channel edits reverted on reopen), (2) rebuilds discovery *with* the channel, so a channel-1 entity is no longer recomputed under the channel-0 `unique_id`, and (3) retracts any entity whose `unique_id` changes instead of orphaning it (empty-payload removal, the same way delete already worked). Deleting one channel now keeps the shared diagnostic sensors (RSSI, Last Seen) the remaining channel still needs.
- **Two channels of a module now really show distinct names** (#34, #24): The distinct-naming intended in beta5 wasn't reaching Home Assistant: both channels share one HA device (same address) and were published without a per-entity name, so both inherited the same device name (the last one written). Now a shared-address module gets a stable module label as its HA device name (manufacturer + EEP, e.g. "NodOn D2-01-12") and each channel entity carries its own configured name, distinct at creation and after every edit. create, update and delete re-publish all channels of the module together so the naming stays consistent when a channel is added, edited, or removed. Recorded as ADR-0007 and verified on a real Home Assistant (Supervisor + Mosquitto) with a D2-01-12 channel pair.

### New Features
- **Devices can be renamed** (#24): The device name (the primary identifier and MQTT topic base) is now editable when editing a device, not just at creation. Renaming re-homes the device's MQTT topics and object_id and cleans up the old ones; the Home Assistant entity itself is preserved because its `unique_id` doesn't depend on the name. A confirmation dialog warns before a rename. This also lets a mis-named channel (e.g. an asymmetric "-ch2") be fixed after the fact instead of deleting and re-adding it.

## [1.7.0-beta6] - 2026-07-24 (beta channel)

### Bug Fixes
- **Dark/light theme, the actual root cause** (#25): The remaining dark islands on a light page (mapping editor, EEP.xml info table, `code` address badges, even the native number spinner in Actuator Teach-In) all came from one wrong assumption in theme detection. Home Assistant's `<body>` usually has **no background of its own**, so reading its computed background returned `rgba(0,0,0,0)` (transparent): which the previous check parsed as pitch black and concluded "Home Assistant is dark". A light HA was therefore rendered dark, and every surface styled by Bootstrap's `data-bs-theme`/`color-scheme` went dark on the light page. Detection now reads HA's own `--primary-background-color` variable (the color HA actually paints, and the same source the app already inherits its colors from) and treats a transparent result as "unknown", so the theme attributes and the inherited colors are consistent by construction. `code` badges also follow HA's secondary background. Verified in an embedded-iframe harness with a transparent parent body in both directions (light HA + dark OS → all light, contrast 15+; dark HA + light OS → all dark, readable).

## [1.7.0-beta5] - 2026-07-24 (beta channel)

### Bug Fixes
- **Manual entry no longer inherits a canceled edit** (#29, #30): Canceling an edit left the previous device's name (locked read-only) and Sender ID in the wizard form; the next manual entry silently inherited them. Starting a manual entry (and a teach-in) now fully resets the form, including the edit state.
- **Sender-ID collision warning** (#29): Saving a new Eltako-style (non-D2) actuator whose Sender ID is already used by another device now asks for confirmation, since broadcast-driven actuators each need their own Sender ID. D2 channel devices are exempt, sharing one Sender ID is correct there.

### New Features
- **"Add channel 2 now?" prompt** (#24): After saving channel 1 of a 2-channel module (D2-01-11/12), the wizard actively offers to create the channel-2 device with everything pre-filled (same address, EEP, sender; channel 2; name suggestion). Replaces the easy-to-miss passive hint.
- **Distinct entity names for channel devices** (#24): When several devices share one module address, each entity now carries its own configured device name in Home Assistant instead of both showing the identical module label.
- **Eltako switch status sync (FSR61)** (community forum): F6-driven switch actuators with status reporting (e.g. FSR61) now update their HA switch state from the actuator's confirmation telegrams, no MQTT YAML workaround needed. Since which rocker side means ON depends on how the actuator was taught in, the device's new "Invert reported state" option (shown for the switch role) flips it if needed.
- **Channel picker in manual entry**: The channel field now also appears when a D2-01 EEP is typed in manually, not only after a teach-in.

## [1.7.0-beta4] - 2026-07-24 (beta channel)

### Bug Fixes
- **Dark/light theme finally consistent** (#25, #23): The remaining dark panels on a light page (Mapping Editor, the EEP.xml info table on the Settings page, alerts, modals) were caused by contradictory theme detection: when Home Assistant's theme was light but the *operating system* preferred dark, the OS won, so the app inherited light colors from HA while Bootstrap rendered its components dark. Now, when the app runs inside Home Assistant, **only** the HA theme decides; the OS preference applies only when the app is opened standalone. Verified with an embedded-page test in both directions (light HA + dark OS → all light; dark HA + light OS → all dark, read-only fields readable).

## [1.7.0-beta3] - 2026-07-23 (beta channel)

### Bug Fixes
- **Unreadable form fields, properly this time** (#25): beta1 only fixed the dark theme, which missed the actual cause and in one case made it worse. Input fields were styled only under `[data-theme="dark"]`, while the text colour could come from somewhere else entirely (Bootstrap's own `data-bs-theme`, or the Home Assistant colours the app copies in at runtime): so a field's background and its text could come from two different themes. That's why fields looked dark on a light page, and grey-on-grey in Device Search, Edit Device, Actuator Teach-In, Settings, the mapping editor and "Step 2: Configure Device". Fields are now bound to the *same* variables as the page in every theme, and the inherited Home Assistant colours also drive the field background/border, so the two can no longer disagree.
- **Second channel never received any state** (#24): Devices were indexed one-per-address, so with one device per output (same module address) only the first ever got the decoded telegram; the second channel's entity stayed empty. All devices sharing an address now receive the state.

## [1.7.0-beta2] - 2026-07-23 (beta channel)

### Changed
- **Dropped the speculative teach-in delay for multi-channel modules**: beta1 kept the teach-in open ~2 s waiting for a channel-selection telegram. Verified against the spec and the reported telegrams: a UTE teach-in carries only the *number* of channels (DB5), never a channel index, and the observed payload was byte-identical for both channels. So no such telegram exists and the wait only slowed the wizard down. The wizard now shows a clear note instead: one teach-in covers the whole module, add one device per channel with the same address.

## [1.7.0-beta1] - 2026-07-23 (beta channel)

Fixes reported by @vincent-lvh for the NodOn SIN-2-2-01 (EEP D2-01-12). Please test!

### Bug Fixes
- **D2-01 actuators did nothing when commanded** (#23): The command handler branched on the *role* (light/switch/cover) before looking at the EEP, so a D2-01 module registered as a "light" was driven with Eltako A5-38-08 dimmer telegrams and never reacted. The EEP is now checked first: every `D2-01-xx` device gets a proper addressed "Actuator Set Output" (VLD) telegram. A light role sends its brightness (0–100) as the output value, a switch role sends 0/100.
- **Teach-in reused the previous device's role** (#23): The role dropdown kept whatever was selected last, and UTE devices were always pre-set to "cover", so NodOn relays were silently registered as blinds. The form is now reset at the start of every teach-in and the role is derived from the EEP (D2-05 → cover, D2-01 → switch, A5-38 → light).
- **Every actuator got the same Sender ID** (#23): The sender offset always started at 1, although each actuator needs its own. The next unused offset is now suggested automatically from the configured devices.
- **Channel 2 could never be taught in** (#24): A teach-in always ended up on channel 1. The cause is not a missed telegram: a UTE teach-in only carries the *number* of channels, never a channel index, so a module cannot signal "this pairing is for output 2". One teach-in binds the whole module and the outputs are addressed by the channel field in the commands, which is what the new channel setting does. After teaching in a 2-channel module the wizard now says so explicitly.
- **Unreadable dark-on-dark form fields** (#25): Read-only and disabled inputs (Gateway Base ID, Sender ID, Edit Device fields) kept Bootstrap's own low-contrast colours. They now use the same contrast as normal inputs, in both dark-theme modes.

### New Features
- **Channel selection for 2-channel modules** (#24): Devices have a `channel` setting (shown for D2-01). Add one device per channel using the same address; commands target the selected output and each channel gets its own Home Assistant entity.
- **Detected fields are marked** (#23): Values that came from the teach-in telegram are highlighted, so it is obvious what was detected and what was typed by hand.

## [1.6.2-beta1] - 2026-07-22 (beta channel)

> ⚠️ **Action needed after updating.** The Serial Port is now a device selector, and Home Assistant can't save it empty, after updating, open Configuration and **select a serial device** (TCP users: pick any device, TCP takes priority), then Save, or the add-on won't start.

Matches stable release 1.6.2 (serial device selector + `udev`).

## [1.5.2-beta1] - 2026-07-14 (beta channel)

### Fixed
- **Saving the configuration with a TCP transceiver failed** with "Device '' does not exist" when Serial Port was left empty: the Supervisor validated the empty string against the tty device list. `serial_port` is now a plain optional text field.

### Documentation
- Getting Started corrected: TCP transceivers are configured in the separate **TCP Port** field (`tcp:HOST:PORT`), not in Serial Port; `tcp_port` added to the options table.

## [1.5.1-beta1] - 2026-07-14 (beta channel)

### Changed
- **Terminology: "add-on" is now "app"** across the Web UI (EN/DE), documentation, and repository metadata, following Home Assistant's rename of add-ons to Apps in HA 2026.2. No functional changes.

## [1.5.0-beta4] - 2026-07-10 (beta channel)

### Bug Fixes
- **Broken unit strings in the new EEP profiles**: The 62 profiles ported in beta1 carried a text-encoding artifact: `°C` was stored as `Â°C` and `m³` as `mÂ³`, so HA showed garbled units for all new temperature profiles and the gas meter. All 38 occurrences fixed.

This beta matches stable release 1.5.0.

## [1.5.0-beta3] - 2026-07-10 (beta channel)

### Improvements
- **Recent Telegrams show decoded payload**: Each entry on the dashboard now has a second line with the decoded telegram fields (human-readable enum texts preferred, e.g. `R1: Button BI · EB: pressed`, or `TMP: 21.5`) plus the raw hex data. Previously only device, sender ID, RORG and signal strength were shown, so you couldn't see what a telegram actually meant.

## [1.5.0-beta2] - 2026-07-10 (beta channel)

### New Features
- **MQTT Settings in the Web UI**: New card on the Settings page to view and edit all MQTT options (host, port, username, password, discovery prefix, topic prefix, client ID) with **Save**, **Save & Restart Add-on** (via Supervisor API), and **Reset to Defaults** buttons. Reset restores auto-discovery via Home Assistant's broker. Previously there was no way to get the original values back once edited in the add-on Configuration tab. Reads/writes the same `/data/options.json` the Configuration tab uses, so both stay in sync (atomic write with `.bak` backup; password never echoed back). Idea from @arno0392's fork, adapted.
- **Download EEP.xml**: New download button next to the upload on the Settings page. Exports the currently active profile database (user-uploaded or bundled), so you can inspect/edit it before re-uploading.

## [1.5.0-beta1] - 2026-07-10 (beta channel)

### New Features
- **EEP profile library: 9 → 71 profiles**: 62 new default HA mappings, contributed by [@arno0392](https://github.com/arno0392)'s fork (thank you!): full A5-02 temperature family (01–30), A5-04-02/03 temp+humidity, A5-06-01 light, A5-07-02/03 occupancy, A5-08-01/02/03 combo sensors, A5-09-02/04/05 air quality (CO₂/VOC), A5-10-01/06 HVAC panels, A5-12-01/02/03 meters (electricity/gas/water with `state_class: total_increasing`), A5-14-01/05/09/0A vibration/window/illuminance, A5-30-01/02 digital inputs, D2-01 electronic switch family (01–0E, 11 two-channel dimmer, 12 two-channel switch), D2-05-01 blinds, F6-03-01/02 four-rocker switches, F6-10-00 window handle. Existing profiles (incl. the F6-02-01/02 per-button binary sensors) are unchanged.
- **Multi-channel state merge (D2-01-11/12)**: Two-channel devices report only the changed channel per telegram (`IO` field selects the channel). The add-on now caches both channels per device and publishes a merged payload (`OV` = channel 0, `OV_CH1` = channel 1), so one channel update no longer wipes the other in HA. Also from @arno0392's fork; channel-1 payload handling is still being field-confirmed, feedback welcome.

## [1.4.0-beta4] - 2026-07-04 (test branch, unreleased)

### Bug Fixes
- **Teach-in timeout no longer spams an unstoppable popup**: Starting teach-in again (or leaving it running) could orphan the 60 s countdown's `setInterval`: its handle was overwritten and could no longer be cleared, so once the counter went negative it fired the "Teach-in timed out, no device detected" toast every second with no way to stop it. `startTeachIn()` now cancels any prior session first, and the countdown clears its own interval on timeout.
- **Web UI showed a stale version**: the displayed version was hard-coded in `main.py` (and `api/system.py`), so it drifted from `config.yaml` (UI still said `1.4.0-beta1`). The version is now read from `config.yaml` at runtime via `app_version.py` (a single source of truth, copied into the image by the Dockerfile), so the UI/API can no longer disagree with the store version.

## [1.4.0-beta3] - 2026-07-04 (test branch, unreleased)

### Bug Fixes (issue #2, needs field testing)
- **D2-01 switches (e.g. NodOn relay / boiler contact) now use the correct command**: Switch actuators with EEP `D2-01-xx` were driven with F6 rocker *broadcasts*, which they ignore (they are VLD/RORG D2 devices): and worse, the broadcast (`Dest=FFFFFFFF`) also moved unrelated D2-05 blinds. They now receive a proper addressed `Actuator Set Output` VLD command (`010064` = ON, `010000` = OFF). Fixes both the boiler not switching and the phantom shutter movement reported in #2. Verified against the EnOcean EEP D2-01 profile (python-enocean).

### New Features (issue #2)
- **Reverse direction (invert) option for covers**: Covers can now be flagged **Invert** in the device form. For reverse-wired/mounted shutters this swaps Open/Close and the position mapping on both the command side (`send_d2_05_command`) and the HA position feedback (MQTT discovery `position_template`), so 100 % = open stays correct without rewiring the motor. Per-device, defaults off; the option appears in the Add/Edit device form when the Cover role is selected.

## [1.4.0-beta2] - 2026-07-03 (test branch, unreleased)

### Bug Fixes (D2-05-00, issue #2, needs field testing)
- **Stop command now uses the correct telegram length**: Per EEP D2-05-00, the `Stop` command (CMD 2) is a **single data byte** (`CHN|CMD`), not the 4-byte `Go to Position and Angle` layout. The beta1 build sent 4 bytes (`7F7F0002`), which the actuator rejected, so Stop physically did nothing (confirmed in @EricGIRARD35's logs). Now sends the correct 1-byte `02`. Verified against the EnOcean EEP spec and the python-enocean reference profile.

### New Features (D2-05-00, issue #2, needs field testing)
- **UTE (bidirectional) teach-in for NodOn D2-05-00 covers**: NodOn shutter modules put into bidirectional learn mode emit a UTE teach-in **query** (RORG `0xD4`). The beta1 build ignored these (`RORG mismatch: got 0xD4 … skipping decode`), so pairing never completed and the module stayed unresponsive to commands. The add-on now, while a teach-in session is open, answers a UTE query with a proper UTE teach-in **response** (`DB6=0x91` "accepted", EEP fields echoed) addressed back to the module, binding the gateway Sender ID `base_id + offset`. Telegram bytes verified against the python-enocean `UTETeachInPacket` reference. The teach-in wizard now pre-fills the bound Sender ID and pre-selects the Cover role so the new device is configured with the exact Sender ID the module was told to bind (the mismatch that otherwise breaks control).

### New Features (needs field testing)
- **D2-05-00 Blind Actuators (NodOn/EnOcean VLD)**: Covers configured with EEP `D2-05-xx` now send proper structured VLD (RORG D2) command telegrams instead of simulated F6 rocker presses. This makes **Stop** work and adds a real **Position** slider (0–100 %) in Home Assistant. `Go to Position and Angle` (CMD 1) and `Stop` (CMD 2) are used; HA positions are inverted to the EnOcean convention (0 % = open). Eltako/RPS covers keep the existing F6 rocker-simulation path, the command handler branches on the configured EEP. (#2)

## [1.3.0] - 2026-07-03

### New Features
- **External MQTT Broker Support**: New `mqtt.host`, `mqtt.port`, `mqtt.username`, and `mqtt.password` add-on options. Leave `host` empty to keep the previous behaviour (auto-connect to Home Assistant's Mosquitto broker); set it to connect to a standalone external broker instead (e.g. a Mosquitto container on UNRAID/Synology). The MQTT service dependency was relaxed from `need` to `want` so the add-on also starts on systems with no HA MQTT broker add-on installed. (#3)

### Bug Fixes
- **F6-02-02 / F6-02-01 Button Binary Sensors**: Rocker switches (e.g. Eltako FT55, EEP F6-02-02) now create one momentary `binary_sensor` per button (AI/AO/BI/BO) via MQTT Discovery, ON while the button is held and OFF on release. Previously F6-02-02 had no mapping at all, so only the `RSSI` and `last_seen` diagnostic entities were created. F6-02-01 keeps its existing Rocker A/B text sensors and Energy Bow for backwards compatibility and gains the same four button sensors. (#1)

## [1.2.5] - 2026-04-17

### Improvements
- **Debounced State Persistence**: `last_states.yaml` is no longer written on every single `publish_state()` call. Updates mark the cache dirty and a single background task flushes the full YAML every 10s (and always on shutdown via a cancelled-task fallback). Eliminates SD/flash write amplification for installations with chatty sensors.
- **Startup Hardening**: If the EnOcean gateway is unreachable at addon start, the lifespan no longer crashes the whole app. Instead a background task retries `connect()` with backoff (5s → 60s) until the gateway comes up, so the Web UI stays available for reconfiguration and the supervisor doesn't restart in a loop.
- **Typed Transceiver Errors**: `_send_command()` now raises `NotConnectedError` / `CommandTimeoutError` / `TransportLostError` instead of returning `None` for every failure mode. `read_base_id()` catches each and logs a distinct reason: "Base ID read skipped" vs "timed out" vs "transport lost", so log output tells you *why*, not just *that* it failed.

### Cleanup
- **Removed Dead `/api/gateway/send` Endpoint**: Had placeholder command bytes that didn't match real EEP encodings and wasn't called from anywhere in the frontend. The working command paths are `/api/gateway/test-actuator` and the MQTT command bridge.

## [1.2.4] - 2026-04-17

### Bug Fixes
- **False-Positive Teach-In for Non-Standard Devices**: A5 teach-in detection checks the LRN bit (bit 3 of data[3]). Some non-standard devices (e.g. Eltako Staufix boiler sensor) send regular data telegrams with LRN=0, which were mis-flagged as teach-ins on every received packet. Now only applies teach-in detection to senders that are NOT already configured, an already-known device cannot logically send a new teach-in.

## [1.2.3] - 2026-04-17

### Bug Fixes
- **Reconnect Base-ID Deadlock**: After a TCP reconnect, the base-ID re-read used to run synchronously inside `_read_loop` via `_wait_and_reconnect`. But `_send_command()` depends on `_read_loop` to deliver the response packet, so awaiting it from inside `_read_loop` deadlocked until the 3s command timeout ("Timeout waiting for response to command 0x08 / Invalid base ID response: None" in the logs). The base-ID refresh now runs as an independent task so the read loop resumes immediately and the response round-trip completes.

## [1.2.2] - 2026-04-17

### Bug Fixes
- **TCP Silent Disconnect Fix**: The read loop no longer silently loops when the TCP peer closes the connection. Previously, when an ESP32 gateway (or any TCP peer) sent a clean FIN, `recv()` returned empty bytes which the code treated as a read timeout, leaving the addon in a zombie state with no log output and no reconnect. `_serial_read()` now raises `ConnectionResetError` in that case so the read loop can trigger a reconnect.
- **TCP Keepalive**: Enabled `SO_KEEPALIVE` on TCP connections with `TCP_KEEPIDLE=30s`, `TCP_KEEPINTVL=10s`, `TCP_KEEPCNT=3`. Half-open connections (ESP32 crash, WiFi drop, router reboot, anything without a clean FIN) are now detected in ~60s instead of the OS default of ~2 hours.
- **Automatic Reconnect**: On transport loss (`ConnectionError`, `SerialException`, `OSError`), the read loop now closes the dead transport and retries the connect with exponential backoff (1s → 2s → … → 30s max). Previously the task died and `/health` kept reporting `enocean_connected: true`.
- **Non-blocking Writes**: `send_telegram()` and `_send_command()` now write via `run_in_executor`. A full send buffer on a half-dead socket no longer freezes the entire FastAPI event loop (UI + MQTT).
- **Command Race Condition**: `_send_command()` is now serialized via an `asyncio.Lock` so concurrent callers cannot clobber each other's `_response_future` slot and mis-route responses.

## [1.2.1] - 2026-03-27

### New Features
- **TCP Port Configuration**: New `tcp_port` config option for connecting to remote EnOcean devices via TCP (e.g., `tcp:192.168.1.118:8638` for SLZB-MR5U USB-Passthrough or similar USB-over-IP devices). TCP takes priority over serial when both are configured.

### Bug Fixes
- **TCP Read Fix**: Fixed TCP socket read in serial handler. The `_serial_read()` method now correctly reads from TCP sockets (previously only serial devices were read, causing TCP connections to receive no data).

## [1.2.0] - 2026-03-10

### New Features
- **Advanced Mapping Fields**: state_class, entity_category, expire_after, force_update, suggested_display_precision, and value_template support in mapping editor
- **Visual & Text Mode Editor**: Toggle between visual form and YAML text editor for mapping overrides (inline and modal)
- **Fork Standard Profiles**: Create custom copies of standard EEP profiles to edit Telegram Fields and HA mappings together
- **YAML-Based Config**: All configuration files migrated from JSON to YAML (devices, mapping overrides) with automatic migration of existing JSON files
- **YAML Export/Import**: Full configuration export/import as YAML files
- **Pass-Through Fields**: Support for pass-through field mappings in the mapping editor

### Improvements
- **Profile Tree Sections**: Dedicated sections for Custom Profiles and Customized Mappings at the top of the EEP tree
- **Orphaned Override Warnings**: Visual warning for mapping overrides that reference non-existent EEP profiles
- **Enhanced Mapping Display**: Profile detail view now shows advanced mapping fields (state_class, expire_after, etc.)
- **Tree Auto-Refresh**: Profile tree refreshes automatically after saving or resetting mapping overrides
- **Text Mode State Reset**: Proper cleanup of text/visual mode state when opening/closing editors

### Bug Fixes
- **HA Ingress Compatibility**: Fixed js-yaml library loading through HA Ingress proxy (dynamic path resolution instead of absolute `/static/` path)
- **Text Mode 400 Error**: Fixed form submission when clicking Text Mode button in Custom Profile modal (missing `type="button"`)
- **Backup Restore**: Custom profiles (custom_eep/) now properly reloaded after restore (EEP manager re-initialization)
- **Version Display**: Fixed version shown in UI sidebar (was stuck at 1.1.0)
- **jsyaml Error Handling**: Added availability checks and try-catch around YAML serialization calls

## [1.1.0] - 2026-03-08

### New Features
- **Multi-Language UI (i18n)**: Auto-detects browser language, supports 11 languages: English, German, Chinese, Hindi, Spanish, French, Arabic, Bengali, Portuguese, Russian, Japanese
- **EEP.xml Upload**: Upload custom EEP.xml via Settings page, with validation, reload, and delete-to-revert
- **EEP.xml in Backups**: Custom EEP.xml is included in export/import ZIP backups
- **HA Entity Mapping Overrides**: Customize HA entity mappings per EEP profile directly from the profile detail view, with inline editor, auto-fill from EEP.xml fields, and save/reset functionality

### Improvements
- **Dark Mode Fixes**: Sidebar uses correct grey (#2b3035) instead of blue, removed `bg-light` from profile cards
- **Consistent dashes**: all feature descriptions use the same separator

### Bug Fixes
- **Mapping Overrides in Backups**: `mapping_overrides.json` is now included in backup export/import

## [1.0.0] - 2026-03-07

First stable release of **EnOcean MQTT UI**, a complete All-in-One Home Assistant Add-on for EnOcean devices.

### Core Features
- **Modern Web UI**: Bootstrap 5 single-page application with responsive design, sidebar navigation, and mobile hamburger menu
- **Visual Device Wizard**: Add devices via teach-in or manual entry, no YAML editing needed
- **96+ EEP Profiles**: Bundled EEP.xml from [ChristopheHD's enocean library](https://github.com/ChristopheHD/enocean) with F6 (RPS), D5 (1BS), A5 (4BS), D2 (VLD), and D1 (MSC) RORGs
- **Custom EEP Profile Editor**: Create custom profiles with field definitions (enum, value, command types) and built-in HA Entity Mapping builder
- **Home Assistant MQTT Discovery**: Automatic entity creation with per-device availability, LWT, and HA birth message support
- **Live Telegram Monitor**: Real-time ESP3 telegram decoding with signal strength display
- **Unknown Device Detection**: Auto-detect unconfigured EnOcean devices with quick-add buttons

### Actuator Control
- **Eltako dimmer/switch/blind control**: Send F6 rocker telegrams to Eltako FD62NPN, FSR61, FSB61 and similar actuators
- **Actuator teach-in**: Send teach-in telegrams with configurable sender offset (1-127) per device
- **A5-38-08 Central Command Dimming**: Brightness control for Eltako dimmers via HA light entities
- **Test buttons**: ON/OFF/Open/Close/Stop directly from device detail view

### Backup & Settings
- **Local Backup System**: Create, list, download, restore, and delete local backup ZIPs from the Settings page
- **Import/Export**: Download or upload configuration as ZIP files
- **Confirmation popups**: Restore and delete actions require explicit confirmation
- **Device state caching**: Persist sensor states across restarts (essential for infrequent senders like Kessel Staufix)

### UI Polish
- **Dark mode**: Automatically detects HA dark theme (Ingress) or OS `prefers-color-scheme`. All components adapt.
- **Device & profile search**: Filter devices by name/address, search EEP profiles with auto-expanding tree nodes
- **Teach-in countdown timer**: 60-second visual countdown with cancel button
- **Custom Profile highlight**: Yellow button and highlighting for custom profiles

### Architecture
- **ChristopheHD MQTT compatibility**: Uses `enoceanmqtt` prefix, compatible topic patterns and discovery UIDs
- **O(1) device lookup**: Hash map for address-to-device resolution on every telegram
- **Correct value scaling**: XML child element parsing for range/scale values (not attributes)
- **Configurable logging**: Log level properly applied to all loggers including uvicorn
- **Repository metadata**: `repository.json` for "Add to Home Assistant" button

### Credits
- [ChristopheHD](https://github.com/ChristopheHD/enocean): EEP.xml profile database and MQTT compatibility patterns
- EnOcean Alliance for the EEP specification
- Home Assistant community
