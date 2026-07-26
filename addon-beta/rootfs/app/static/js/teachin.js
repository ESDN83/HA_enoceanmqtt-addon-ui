// Extracted from templates/index.html. Classic script, no modules:
// the inline onclick handlers call these by bare name, so they must stay global.

// Teach-in state. It lives here with its only readers: the websocket and
// its timeout belong to startTeachIn/cancelTeachIn, the busy flag to
// testActuator.
let teachInSocket = null;
let teachInTimer = null;
let _testActuatorBusy = false;

function showActuatorTeachIn() {
    // Cancel any running automatic teach-in first
    cancelTeachIn();
    document.getElementById('actuator-teach-in-panel').style.display = 'block';
    readBaseId();
}
function hideActuatorTeachIn() {
    document.getElementById('actuator-teach-in-panel').style.display = 'none';
}
async function readBaseId() {
    const input = document.getElementById('gateway-base-id');
    input.value = 'Reading...';
    try {
        const resp = await fetch(getApiUrl('/api/gateway/read-base-id'), { method: 'POST' });
        const data = await resp.json();
        if (resp.ok && data.base_id) {
            input.value = data.base_id;
            await suggestNextSenderOffset();
            updateDerivedSenderId();
        } else {
            input.value = 'Error: ' + (data.detail || 'unknown');
        }
    } catch (e) {
        input.value = 'Error: ' + e.message;
    }
}
async function suggestNextSenderOffset() {
    const offsetField = document.getElementById('sender-offset');
    const baseIdRaw = document.getElementById('gateway-base-id')?.value || '';
    if (!offsetField || !baseIdRaw.startsWith('0x')) return;

    const base = parseInt(baseIdRaw, 16);
    const used = new Set();
    try {
        const resp = await fetch(getApiUrl('/api/devices'));
        if (!resp.ok) return;
        const devices = await resp.json();
        (Array.isArray(devices) ? devices : Object.values(devices || {})).forEach(dev => {
            const sid = dev && dev.sender_id;
            if (!sid) return;
            const val = parseInt(String(sid).replace(/^0x/i, ''), 16);
            if (!isNaN(val)) {
                const off = val - base;
                if (off >= 1 && off <= 127) used.add(off);
            }
        });
    } catch (e) {
        return;  // best effort — keep whatever is in the field
    }

    for (let off = 1; off <= 127; off++) {
        if (!used.has(off)) {
            offsetField.value = off;
            return;
        }
    }
}
async function sendActuatorTeachIn() {
    const address = document.getElementById('actuator-address').value.trim();
    const offset = parseInt(document.getElementById('sender-offset').value) || 1;
    const actuatorType = document.getElementById('actuator-type-teach-in').value;
    const resultDiv = document.getElementById('actuator-teach-in-result');

    if (!address) {
        resultDiv.innerHTML = '<div class="alert alert-danger">Enter the actuator address</div>';
        resultDiv.style.display = 'block';
        return;
    }

    const proto = actuatorType === 'light' ? 'A5-38-08 (Central Command)' : 'F6 (Rocker)';
    resultDiv.innerHTML = `<div class="alert alert-info"><i class="bi bi-hourglass-split"></i> ${t('teach_in.sending', 'Sending')} ${proto} teach-in...</div>`;
    resultDiv.style.display = 'block';

    try {
        const resp = await fetch(getApiUrl('/api/gateway/teach-in-actuator'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ destination: address, sender_offset: offset, actuator_type: actuatorType })
        });
        const data = await resp.json();

        if (resp.ok) {
            resultDiv.innerHTML = `<div class="alert alert-success">
                <i class="bi bi-check-circle"></i> <strong>${t('teach_in.teach_in_sent', 'Teach-in sent!')}</strong> (${data.teach_type || proto})<br>
                ${t('teach_in.sender_id', 'Sender ID')}: <code>${data.sender_id}</code> → ${t('teach_in.destination', 'Destination')}: <code>${data.destination}</code><br>
                <small class="text-muted">${data.message}</small><br><br>
                <strong>${t('teach_in.next_step', 'Next')}:</strong> ${t('teach_in.next_step_desc', 'Use "Manual Entry" to add this device with sender ID')} <code>${data.sender_id}</code>
                ${t('teach_in.and_actuator_type', 'and actuator type')} <code>${actuatorType}</code>
            </div>`;
        } else {
            resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-x-circle"></i> ${data.detail || t('common.unknown_error', 'Unknown error')}</div>`;
        }
    } catch (e) {
        resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-x-circle"></i> ${e.message}</div>`;
    }
}
async function sendRepeatTeachIn() {
    const address = document.getElementById('actuator-address').value.trim();
    const offset = parseInt(document.getElementById('sender-offset').value) || 1;
    const actuatorType = document.getElementById('actuator-type-teach-in').value;
    const resultDiv = document.getElementById('actuator-teach-in-result');
    const btn = document.getElementById('btn-repeat-teach-in');

    if (!address) {
        resultDiv.innerHTML = '<div class="alert alert-danger">Enter the actuator address</div>';
        resultDiv.style.display = 'block';
        return;
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-arrow-repeat spin"></i> Sending... (30s)';
    const proto = actuatorType === 'light' ? 'A5-38-08' : 'F6 Rocker';
    resultDiv.innerHTML = `<div class="alert alert-warning">
        <i class="bi bi-broadcast"></i> <strong>Sending ${proto} teach-in repeatedly for 30 seconds...</strong><br>
        Put the actuator in learn mode NOW! (Place it next to the USB300)
    </div>`;
    resultDiv.style.display = 'block';

    try {
        const resp = await fetch(getApiUrl('/api/gateway/teach-in-repeat'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                destination: address, sender_offset: offset,
                actuator_type: actuatorType,
                duration_seconds: 30, interval_seconds: 5
            })
        });
        const data = await resp.json();

        if (resp.ok) {
            resultDiv.innerHTML = `<div class="alert alert-success">
                <i class="bi bi-check-circle"></i> <strong>${data.rounds_sent} teach-in rounds sent!</strong> (${data.teach_type})<br>
                Sender ID: <code>${data.sender_id}</code><br>
                <small>${data.message}</small>
            </div>`;
        } else {
            resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-x-circle"></i> ${data.detail || 'Error'}</div>`;
        }
    } catch (e) {
        resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-x-circle"></i> ${e.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-arrow-repeat"></i> Repeat Teach-In (30s)';
    }
}
async function testActuator(deviceName, command) {
    // Debounce: prevent double-send from rapid clicks
    if (_testActuatorBusy) return;
    _testActuatorBusy = true;
    setTimeout(() => { _testActuatorBusy = false; }, 1500);

    const resultSpan = document.getElementById('test-actuator-result');
    resultSpan.innerHTML = '<span class="text-info"><i class="bi bi-hourglass-split"></i> Sending...</span>';

    try {
        const resp = await fetch(getApiUrl('/api/gateway/test-actuator'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_name: deviceName, command: command })
        });
        const data = await resp.json();

        if (resp.ok) {
            resultSpan.innerHTML = `<span class="text-success"><i class="bi bi-check-circle"></i> ${command} sent to ${deviceName}</span>`;
        } else {
            resultSpan.innerHTML = `<span class="text-danger"><i class="bi bi-x-circle"></i> ${data.detail || 'Error'}</span>`;
        }
    } catch (e) {
        resultSpan.innerHTML = `<span class="text-danger"><i class="bi bi-x-circle"></i> ${e.message}</span>`;
    }

    // Clear result after 5 seconds
    setTimeout(() => { resultSpan.innerHTML = ''; }, 5000);
}
function startTeachIn() {
    // Cancel any previous session first — otherwise a second start
    // orphans the old setInterval (its handle is overwritten and can no
    // longer be cleared). The orphan keeps firing every second once
    // `remaining` goes negative, spamming the timeout toast unstoppably.
    cancelTeachIn();

    // Start from a clean form. Previously the role dropdown kept
    // whatever was picked in an earlier session, so devices were
    // silently registered as the wrong type (#23).
    resetTeachInForm();

    // Auto-close actuator panel if open
    document.getElementById('actuator-teach-in-panel').style.display = 'none';

    const status = document.getElementById('teach-in-status');
    status.style.display = 'block';

    // Start 60-second countdown
    let remaining = 60;
    const countdownEl = document.getElementById('teach-in-countdown');
    countdownEl.textContent = `(${remaining}s)`;
    const timer = setInterval(() => {
        remaining--;
        countdownEl.textContent = `(${remaining}s)`;
        if (remaining <= 0) {
            // Stop THIS interval no matter what the shared handle points
            // at, so it can never keep firing.
            clearInterval(timer);
            if (teachInTimer === timer) teachInTimer = null;
            cancelTeachIn();
            showToast(t('teach_in.timeout', 'Teach-in timed out — no device detected'), 'warning');
        }
    }, 1000);
    teachInTimer = timer;

    // Connect to WebSocket
    teachInSocket = new WebSocket(getWsUrl('/api/gateway/teach-in'));

    teachInSocket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if (data.type !== 'teach_in') return;

        applyTeachInData(data.data);

        // A UTE teach-in carries the NUMBER of channels (DB5), never a
        // channel index — so a 2-channel module cannot tell us "this
        // pairing is for output 2", and waiting for a follow-up
        // telegram would be pointless (#24). One teach-in binds the
        // whole module; the individual outputs are addressed by the
        // channel (IO) field in the commands. Tell the user that.
        const channels = parseInt(data.data.channels || 1, 10) || 1;
        finalizeTeachIn(channels);
    };

    teachInSocket.onerror = function() {
        cancelTeachIn();
        status.style.display = 'block';
        status.querySelector('.alert').className = 'alert alert-danger';
        status.querySelector('.alert').innerHTML = '<i class="bi bi-x-circle"></i> Connection failed. EnOcean gateway may not be connected.';
    };
}
function resetTeachInForm() { resetDeviceForm(); }

// Pick a sensible role from the EEP instead of always guessing "cover".
// A NodOn SIN-2-2-01 (D2-01-12) is a relay, not a blind — defaulting
// every UTE device to cover silently mis-registered them (#23).
function roleFromEep(rorg, func) {
    const r = String(rorg || '').toUpperCase().replace('0X', '');
    const f = String(func || '').toUpperCase().padStart(2, '0');
    if (r === 'D2' && f === '05') return 'cover';   // blinds
    if (r === 'D2' && f === '01') return 'switch';  // relays / dimmers
    if (r === 'A5' && f === '38') return 'light';   // Eltako dimmers
    return '';                                      // sensor
}
function offerSecondChannel(saved) {
    showConfirmDialog(
        t('teach_in.second_channel_title', 'Add channel 2 now?'),
        t('teach_in.second_channel_body', 'This module has two outputs. Add a second device for channel 2 with the same address and sender ID? Everything will be pre-filled — you only confirm the name.'),
        t('teach_in.second_channel_btn', 'Add channel 2'),
        'btn-primary',
        () => {
            resetDeviceForm();
            // Back to the configure step
            const steps = document.querySelectorAll('.wizard-step');
            steps.forEach(s => s.classList.remove('active'));
            steps[1]?.classList.add('active');
            const form = document.getElementById('device-form');
            const set = (name, value) => {
                const el = form.querySelector(`[name="${name}"]`);
                if (el) el.value = value ?? '';
            };
            set('name', (saved.name || '') + '-ch2');
            set('address', saved.address);
            set('rorg', saved.rorg);
            set('func', saved.func);
            set('type', saved.type);
            set('description', saved.description || '');
            set('room', saved.room || '');
            set('manufacturer', saved.manufacturer || '');
            const roleField = form.querySelector('[name="actuator_type"]');
            if (roleField) {
                roleField.value = saved.actuator_type || 'switch';
                toggleSenderIdField(roleField);
            }
            // Same sender ID on purpose: D2 commands are addressed and
            // the module is bound to exactly this controller ID.
            set('sender_id', saved.sender_id || '');
            toggleChannelField(saved.rorg, saved.func);
            set('channel', '1');
        }
    );
}
function applyTeachInData(d) {
    const set = (name, value, detected) => {
        const el = document.querySelector(`[name="${name}"]`);
        if (!el) return;
        el.value = value ?? '';
        markDetected(el, detected && value != null && value !== '');
    };

    set('address', d.sender_id, true);
    set('rorg', d.rorg, true);
    set('func', d.func, true);
    set('type', d.type, true);

    toggleChannelField(d.rorg, d.func);

    // Channel: 2-channel modules report which output to drive.
    const chField = document.querySelector('[name="channel"]');
    if (chField) {
        const ch = (d.channel !== undefined && d.channel !== null) ? d.channel : 0;
        chField.value = ch;
        markDetected(chField, d.channel !== undefined && d.channel !== null);
    }

    // Role derived from the EEP (not carried over from a previous run).
    const roleField = document.querySelector('[name="actuator_type"]');
    if (roleField) {
        const role = roleFromEep(d.rorg, d.func);
        roleField.value = role;
        toggleSenderIdField(roleField);
        markDetected(roleField, !!role);
    }

    // UTE binds a specific Sender ID — the device must use exactly it.
    if (d.teach_method === 'UTE' && d.response_sender) {
        const senderField = document.querySelector('[name="sender_id"]');
        if (senderField) {
            senderField.value = d.response_sender;
            markDetected(senderField, true);
        }
    }
}
function finalizeTeachIn(channels) {
    cancelTeachIn();
    wizardNext();
    showToast(t('teach_in.detected', 'Device detected!'), 'success');

    // Multi-channel module: one teach-in covers the whole module, so
    // point out that each output needs its own device entry.
    if ((parseInt(channels, 10) || 1) >= 2) {
        const banner = document.getElementById('multichannel-note');
        if (banner) banner.style.display = '';
    }
}
function cancelTeachIn() {
    if (teachInTimer) {
        clearInterval(teachInTimer);
        teachInTimer = null;
    }
    if (teachInSocket) {
        teachInSocket.close();
        teachInSocket = null;
    }
    document.getElementById('teach-in-status').style.display = 'none';
}
function resetTeachInPage() {
    cancelTeachIn();
    document.getElementById('actuator-teach-in-panel').style.display = 'none';
    // Reset wizard to step 1
    document.querySelectorAll('.wizard-step').forEach((step, i) => {
        step.classList.toggle('active', i === 0);
    });
}
