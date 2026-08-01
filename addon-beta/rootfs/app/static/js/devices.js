// Extracted from templates/index.html. Classic script, no modules:
// the inline onclick handlers call these by bare name, so they must stay global.

async function loadDevices() {
    try {
        const response = await fetch(getApiUrl('/api/devices'));
        const devices = await response.json();

        const container = document.getElementById('device-list');
        container.innerHTML = '';

        if (devices.length === 0) {
            container.innerHTML = `<div class="col-12"><p class="text-muted">${t('devices.empty', 'Add your first device')} <a href="#" onclick="navigateTo('teach-in')">${t('nav.add_device', 'Add Device')}</a></p></div>`;
            return;
        }

        devices.forEach(device => {
            const card = document.createElement('div');
            // device-col is the stable hook for filterDevices; the col-* classes are
            // layout only and may change. Two-up once the sidebar appears at md,
            // three-up only at xl where there is room for it.
            card.className = 'device-col col-12 col-md-6 col-xl-4 mb-3';
            // Build searchable text from device properties only (not button text)
            const searchText = [device.name, device.address, `${device.rorg}-${device.func}-${device.type}`,
                device.actuator_type, device.room, device.description, device.sender_id
            ].filter(Boolean).join(' ').toLowerCase();
            card.dataset.search = searchText;
            // The name is user text, so it never goes into an onclick
            // attribute. An apostrophe ("Volet d'entrée") used to end the JS
            // string and kill the whole handler, which left the device with no
            // way to be edited or deleted at all (#36). Handlers are attached
            // below and take the name from the closure. See ADR-0009.
            card.innerHTML = `
                <div class="card device-card" style="cursor: pointer;">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <h5 class="card-title mb-1">${escapeHtml(device.name)}</h5>
                            <!-- Not a btn-group: that pulls adjacent buttons together with a
                                 negative margin so their outlines share an edge, which reads as
                                 the pencil and the bin overlapping. A flex row with a gap keeps
                                 them visibly separate. -->
                            <div class="d-flex gap-1 device-actions">
                                <button class="btn btn-sm btn-outline-primary" data-action="edit" title="Edit">
                                    <i class="bi bi-pencil"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-danger" data-action="delete" title="Delete">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </div>
                        </div>
                        <p class="card-text mb-1">
                            <code class="text-muted">${escapeHtml(device.address)}</code>
                        </p>
                        <p class="card-text mb-1">
                            <span class="badge bg-primary">${escapeHtml(device.rorg)}-${escapeHtml(device.func)}-${escapeHtml(device.type)}</span>
                            ${device.actuator_type ? `<span class="badge bg-warning text-dark ms-1"><i class="bi bi-lightning"></i> ${escapeHtml(device.actuator_type)}</span>` : ''}
                            ${device.room ? `<span class="badge bg-secondary ms-1">${escapeHtml(device.room)}</span>` : ''}
                        </p>
                        ${device.description ? `<p class="card-text mb-0"><small class="text-muted">${escapeHtml(device.description)}</small></p>` : ''}
                        ${device.sender_id ? `<p class="card-text mb-0"><small class="text-muted"><i class="bi bi-arrow-left-right"></i> Sender: ${escapeHtml(device.sender_id)}</small></p>` : ''}
                    </div>
                </div>
            `;
            card.querySelector('.device-card').addEventListener('click', () => showDeviceDetail(device.name));
            card.querySelector('.device-actions').addEventListener('click', e => e.stopPropagation());
            card.querySelector('[data-action="edit"]').addEventListener('click', () => editDevice(device.name));
            card.querySelector('[data-action="delete"]').addEventListener('click', () => deleteDevice(device.name));
            container.appendChild(card);
        });

        // Re-apply search filter if query is active
        const searchQuery = document.getElementById('device-search').value;
        if (searchQuery) filterDevices();
    } catch (error) {
        showToast(t('devices.load_failed', 'Failed to load devices'), 'danger');
    }
}
function updateDerivedSenderId() {
    const baseId = document.getElementById('gateway-base-id').value;
    const offset = parseInt(document.getElementById('sender-offset').value) || 1;
    const output = document.getElementById('derived-sender-id');
    if (baseId && baseId.startsWith('0x')) {
        const base = parseInt(baseId, 16);
        const sender = base + offset;
        output.value = '0x' + sender.toString(16).toUpperCase().padStart(8, '0');
    }
}
// Full reset of the device wizard form. MUST clear the edit state too:
// a canceled edit used to leave the previous device's name (locked
// read-only) and sender ID in the form, so the next manual entry
// silently inherited them (#29, #30).
function resetDeviceForm() {
    const note = document.getElementById('multichannel-note');
    if (note) note.style.display = 'none';
    const form = document.getElementById('device-form');
    if (!form) return;
    form.reset();
    delete form.dataset.editMode;
    // The identity snapshot belongs to the edit that is being abandoned. Left
    // behind it would make the next entry compare against a stranger, which is
    // the same class of bug as the name and sender ID that used to survive a
    // canceled edit (#29, #30).
    delete form.dataset.identityBefore;
    const nameField = form.querySelector('[name="name"]');
    if (nameField) nameField.readOnly = false;
    form.querySelectorAll('.field-detected').forEach(el => {
        el.classList.remove('field-detected');
        el.removeAttribute('title');
    });
    const roleField = form.querySelector('[name="actuator_type"]');
    if (roleField) {
        roleField.value = '';
        toggleSenderIdField(roleField);   // hides sender + invert groups
    }
    const channelGroup = document.getElementById('channel-group');
    if (channelGroup) channelGroup.style.display = 'none';
    // form.reset() restores the markup default (1440), so only the visibility
    // of the interval field has to follow the now-unticked checkbox.
    toggleAvailabilityField();
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.textContent = t('teach_in.add_device', 'Add Device');
    const heading = document.querySelector('#step-2 h4');
    if (heading) heading.textContent = t('teach_in.step2', 'Step 2: Configure Device');
}
// The interval only means anything once the watchdog is switched on, so it
// stays hidden until then (#37). Deliberately not tied to the device role: an
// actuator is a poor candidate, since it only transmits when it is switched,
// but a D2-01 module does report unsolicited on every physical toggle, so
// hiding the option for actuators would take a legitimate case away.
function toggleAvailabilityField() {
    const cb = document.getElementById('availability-watch');
    const group = document.getElementById('availability-timeout-group');
    const field = document.getElementById('availability-timeout');
    if (!cb || !group || !field) return;
    // Greyed out rather than hidden. The first person to use this asked where
    // the time was entered, because a field that only appears after ticking a
    // box cannot be found by anyone who does not already know it is there.
    // Disabled keeps it visible and explains itself, and a disabled input is
    // left out of FormData anyway, which is harmless here because saveDevice
    // reads the value from the element and decides by the checkbox.
    field.disabled = !cb.checked;
    group.classList.toggle('opacity-50', !cb.checked);
}
// Channel picker only makes sense for multi-channel D2-01 modules.
function toggleChannelField(rorg, func) {
    const group = document.getElementById('channel-group');
    if (!group) return;
    const r = String(rorg || '').toUpperCase().replace('0X', '');
    const f = String(func || '').toUpperCase().padStart(2, '0');
    group.style.display = (r === 'D2' && f === '01') ? '' : 'none';
}
// 2-channel EEPs — one physical module, two independently switchable
// outputs (matches _multichannel_eeps in the backend).
function isTwoChannelEep(rorg, func, type) {
    const r = String(rorg || '').toUpperCase().replace('0X', '');
    const f = String(func || '').toUpperCase().padStart(2, '0');
    const ty = String(type || '').toUpperCase().padStart(2, '0');
    return r === 'D2' && f === '01' && (ty === '11' || ty === '12');
}
function toggleSenderIdField(select) {
    const senderGroup = document.getElementById('sender-id-group');
    if (senderGroup) {
        senderGroup.style.display = select.value ? '' : 'none';
        // Clear sender_id when switching back to sensor
        if (!select.value) {
            const input = senderGroup.querySelector('input[name="sender_id"]');
            if (input) input.value = '';
        }
    }
    // Invert applies to covers (Open/Close direction) and to switches
    // (ON/OFF meaning of Eltako status reports — which rocker side
    // means ON depends on how the actuator was taught in).
    const invertGroup = document.getElementById('invert-group');
    if (invertGroup) {
        const showInvert = select.value === 'cover' || select.value === 'switch';
        invertGroup.style.display = showInvert ? '' : 'none';
        if (!showInvert) {
            const cb = invertGroup.querySelector('input[name="invert"]');
            if (cb) cb.checked = false;
        }
        const label = invertGroup.querySelector('.form-check-label');
        if (label) {
            label.textContent = select.value === 'switch'
                ? t('teach_in.invert_label_switch', 'Invert reported state (ON/OFF swapped)')
                : t('teach_in.invert_label', 'Reverse direction (Open/Close inverted)');
        }
    }
}
// The fields that say WHICH physical module this entry is. Changing one does
// not reconfigure anything over the air: the module keeps whatever it was
// taught, and the entry simply stops describing it (#35).
const IDENTITY_FIELDS = [
    ['address', 'device.field_address', 'Address'],
    ['rorg', 'device.field_rorg', 'RORG'],
    ['func', 'device.field_func', 'FUNC'],
    ['type', 'device.field_type', 'TYPE'],
    ['sender_id', 'device.field_sender_id', 'Sender ID'],
];

// Collect every change that deserves a warning before saving an edit: the
// rename (which re-homes the MQTT topics) and any identity field. One list,
// because two stacked Bootstrap modals do not work, and because the user
// wants to see everything they are about to change at once.
function collectRiskyChanges(device, editMode, form) {
    const changes = [];
    if (!editMode) return changes;
    if (device.name && device.name !== editMode) {
        changes.push({ label: t('device.field_name', 'Name'), from: editMode, to: device.name });
    }
    let before;
    try {
        before = JSON.parse(form.dataset.identityBefore || 'null');
    } catch (err) {
        before = null;
    }
    if (!before) return changes;   // opened without a snapshot: warn on the rename only
    for (const [key, i18nKey, fallback] of IDENTITY_FIELDS) {
        const from = String(before[key] ?? '');
        const to = String(device[key] ?? '');
        if (from !== to) changes.push({ label: t(i18nKey, fallback), from, to, identity: true });
    }
    return changes;
}

async function saveDevice(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    const device = Object.fromEntries(formData);
    // Checkboxes are absent from FormData when unchecked; send an
    // explicit boolean so unchecking "invert" is persisted too.
    const invertCb = form.querySelector('input[name="invert"]');
    device.invert = !!(invertCb && invertCb.checked);
    // The watchdog is one number on the wire: minutes, 0 meaning never. The
    // checkbox only decides whether the number is sent at all, so unticking it
    // has to reach the backend as 0 rather than as a missing field (#37).
    const watchCb = form.querySelector('input[name="availability_watch"]');
    const timeoutField = form.querySelector('input[name="availability_timeout"]');
    device.availability_timeout = (watchCb && watchCb.checked)
        ? Math.max(1, parseInt(timeoutField && timeoutField.value, 10) || 1)
        : 0;
    delete device.availability_watch;
    const editMode = form.dataset.editMode;

    // Warn before a rename (the device name is the primary key and the MQTT
    // topic base, so renaming re-homes its topics/object_id; the HA entity
    // survives because its unique_id is name-independent) and before any
    // identity change (#35).
    const changes = collectRiskyChanges(device, editMode, form);
    if (changes.length) {
        const identity = changes.some(c => c.identity);
        const list = '<ul class="mb-2">' + changes.map(c =>
            '<li>' + escapeHtml(c.label) + ': <code>' + escapeHtml(c.from || '—') +
            '</code> → <code>' + escapeHtml(c.to || '—') + '</code></li>').join('') + '</ul>';
        showConfirmDialog(
            identity
                ? t('device.identity_title', 'Change device identity?')
                : t('device.rename_title', 'Rename device?'),
            list + (identity
                ? t('device.identity_body', 'These fields identify the physical module. Changing them does not reconfigure the device over the air — it keeps whatever it was taught in with. The entry will only match again after you teach the module in anew, and existing Home Assistant entities are replaced.')
                : t('device.rename_body', 'This changes the device\'s MQTT topics and entity object_id') + ' ' +
                  t('device.rename_hint', 'The Home Assistant entity is kept; only its topics change. Rename?')),
            identity ? t('device.identity_btn', 'Change anyway') : t('device.rename_btn', 'Rename'),
            'btn-warning',
            () => performSaveDevice(device, editMode, form)
        );
        return;
    }

    // Sender-ID collision check for broadcast-driven (non-D2) actuators:
    // Eltako devices each need their OWN sender ID, otherwise they react
    // to each other's commands (#29). D2 channel devices intentionally
    // share one sender (addressed commands), so they are exempt.
    const isD2 = String(device.rorg || '').toUpperCase().replace('0X', '') === 'D2';
    if (!editMode && device.actuator_type && device.sender_id && !isD2) {
        try {
            const resp = await fetch(getApiUrl('/api/devices'));
            if (resp.ok) {
                const all = await resp.json();
                const list = Array.isArray(all) ? all : Object.values(all || {});
                const clash = list.find(d => d.sender_id && device.sender_id &&
                    d.sender_id.toLowerCase() === device.sender_id.toLowerCase() &&
                    d.name !== device.name);
                if (clash) {
                    showConfirmDialog(
                        t('device.sender_clash_title', 'Sender ID already in use'),
                        t('device.sender_clash_body', 'This Sender ID is already used by') + ' "' + escapeHtml(clash.name) + '". ' +
                        t('device.sender_clash_hint', 'Eltako-style actuators each need their own Sender ID — otherwise both react to the same commands. Save anyway?'),
                        t('device.sender_clash_btn', 'Save anyway'),
                        'btn-warning',
                        () => performSaveDevice(device, editMode, form)
                    );
                    return;
                }
            }
        } catch (err) { /* best effort — fall through to save */ }
    }

    await performSaveDevice(device, editMode, form);
}
async function performSaveDevice(device, editMode, form) {
    try {
        let response;
        if (editMode) {
            // Update existing device
            response = await fetch(getApiUrl(`/api/devices/${encodeURIComponent(editMode)}`), {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(device)
            });
        } else {
            // Create new device
            response = await fetch(getApiUrl('/api/devices'), {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(device)
            });
        }

        if (!response.ok) {
            let errorMsg = t('device.save_failed', 'Failed to save device');
            try {
                const error = await response.json();
                errorMsg = error.detail || errorMsg;
            } catch (parseError) {
                errorMsg = `Server error: ${response.status} ${response.statusText}`;
            }
            throw new Error(errorMsg);
        }

        // Clear edit mode and reset form state
        delete form.dataset.editMode;
        document.querySelector('[name="name"]').readOnly = false;
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) submitBtn.textContent = t('teach_in.add_device', 'Add Device');
        const heading = document.querySelector('#step-2 h4');
        if (heading) heading.textContent = t('teach_in.step2', 'Step 2: Configure Device');

        if (editMode) {
            // After editing, go back to devices page
            showToast(t('device.updated', 'Device updated successfully'), 'success');
            navigateTo('devices');
        } else {
            // After adding new device, show success screen
            wizardNext();
            showToast(t('device.saved', 'Device saved successfully'), 'success');
            // 2-channel module and this was channel 1? Offer channel 2
            // right away with everything pre-filled (#24).
            if (isTwoChannelEep(device.rorg, device.func, device.type)
                    && parseInt(device.channel || 0, 10) === 0) {
                offerSecondChannel(device);
            }
        }
        loadDevices();
    } catch (error) {
        showToast(error.message, 'danger');
    }
}
async function editDevice(name) {
    try {
        // encodeURIComponent, or a name containing '/' or '#' produces a URL
        // that never reaches this route and the device becomes uneditable (#36).
        const response = await fetch(getApiUrl(`/api/devices/${encodeURIComponent(name)}`));
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
        const device = await response.json();

        // Navigate to teach-in page
        navigateTo('teach-in');

        // Go directly to step-2 (form) regardless of current wizard state
        document.querySelectorAll('.wizard-step').forEach((step, index) => {
            step.classList.toggle('active', index === 1);
        });

        // Fill in form fields
        document.querySelector('[name="name"]').value = device.name;
        document.querySelector('[name="address"]').value = device.address;
        document.querySelector('[name="rorg"]').value = device.rorg;
        document.querySelector('[name="func"]').value = device.func;
        document.querySelector('[name="type"]').value = device.type;
        document.querySelector('[name="description"]').value = device.description || '';
        document.querySelector('[name="room"]').value = device.room || '';
        document.querySelector('[name="actuator_type"]').value = device.actuator_type || '';
        document.querySelector('[name="manufacturer"]').value = device.manufacturer || '';
        // Reuse the role dropdown's own rules for which extra fields
        // are visible. This block used to carry its own copy that only
        // showed "invert" for covers, so editing a switch never
        // offered "Invert reported state".
        toggleSenderIdField(document.querySelector('[name="actuator_type"]'));
        // Fill the values after the toggle, which clears what it hides.
        document.querySelector('[name="sender_id"]').value = device.sender_id || '';
        const invertCb = document.querySelector('[name="invert"]');
        if (invertCb) invertCb.checked = !!device.invert;

        // Availability watchdog: a stored 0 means off, anything else is the
        // number of minutes (#37).
        const watchTimeout = parseInt(device.availability_timeout, 10) || 0;
        const watchCb = document.getElementById('availability-watch');
        const timeoutField = document.getElementById('availability-timeout');
        if (watchCb) watchCb.checked = watchTimeout > 0;
        if (timeoutField && watchTimeout > 0) timeoutField.value = watchTimeout;
        toggleAvailabilityField();

        // Channel (2-channel D2-01 modules)
        const chField = document.querySelector('[name="channel"]');
        if (chField) chField.value = String(device.channel || 0);
        toggleChannelField(device.rorg, device.func);

        // Mark as edit mode
        const form = document.getElementById('device-form');
        form.dataset.editMode = name;
        // Snapshot the identity fields as they were loaded, so saveDevice can
        // tell what the user actually changed and warn about it (#35).
        form.dataset.identityBefore = JSON.stringify({
            address: device.address ?? '',
            rorg: device.rorg ?? '',
            func: device.func ?? '',
            type: device.type ?? '',
            sender_id: device.sender_id ?? '',
        });

        // Change button text. The name is editable in edit mode too
        // (rename is supported); saveDevice warns before an actual
        // rename since it changes the MQTT topics.
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) submitBtn.textContent = t('device.save', 'Save Device');
        document.querySelector('[name="name"]').readOnly = false;

        // Update heading
        const heading = document.querySelector('#step-2 h4');
        if (heading) heading.textContent = t('device.edit', 'Edit Device');

    } catch (error) {
        showToast(t('device.load_failed', 'Failed to load device'), 'danger');
    }
}
async function showDeviceDetail(name) {
    try {
        const response = await fetch(getApiUrl(`/api/devices/${encodeURIComponent(name)}`));
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
        const device = await response.json();

        // Fetch recent telegrams for this device
        let telegrams = [];
        try {
            const tRes = await fetch(getApiUrl(`/api/gateway/recent-telegrams?limit=100`));
            const allTelegrams = await tRes.json();
            telegrams = allTelegrams.filter(t =>
                t.device_name === name || t.sender_id === device.address
            ).slice(0, 20);
        } catch (e) { /* ignore */ }

        // Build detail view in the devices page
        const container = document.getElementById('device-list');
        container.innerHTML = `
            <div class="col-12">
                <div class="mb-3">
                    <button class="btn btn-outline-secondary btn-sm" onclick="loadDevices()">
                        <i class="bi bi-arrow-left"></i> ${t('device.back', 'Back to Devices')}
                    </button>
                    <button class="btn btn-outline-primary btn-sm ms-2" data-action="edit">
                        <i class="bi bi-pencil"></i> ${t('device.edit', 'Edit Device')}
                    </button>
                </div>

                <div class="card mb-3">
                    <div class="card-header">
                        <h5 class="mb-0"><i class="bi bi-cpu"></i> ${escapeHtml(device.name)}</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-6">
                                <table class="table table-sm">
                                    <tr><th>${t('device.address', 'Address')}</th><td><code>${escapeHtml(device.address)}</code></td></tr>
                                    <tr><th>${t('device.eep_profile', 'EEP Profile')}</th><td><span class="badge bg-primary">${escapeHtml(device.rorg)}-${escapeHtml(device.func)}-${escapeHtml(device.type)}</span></td></tr>
                                    ${device.description ? `<tr><th>${t('device.description', 'Description')}</th><td>${escapeHtml(device.description)}</td></tr>` : ''}
                                    ${device.room ? `<tr><th>${t('device.room', 'Room')}</th><td>${escapeHtml(device.room)}</td></tr>` : ''}
                                    ${device.sender_id ? `<tr><th>${t('device.sender_id', 'Sender ID')}</th><td><code>${escapeHtml(device.sender_id)}</code></td></tr>` : ''}
                                    ${device.actuator_type ? `<tr><th>${t('device.device_role', 'Device Role')}</th><td><span class="badge bg-warning text-dark">${escapeHtml(device.actuator_type)}</span></td></tr>` : ''}
                                    ${device.manufacturer ? `<tr><th>${t('device.manufacturer', 'Manufacturer')}</th><td>${escapeHtml(device.manufacturer)}</td></tr>` : ''}
                                </table>
                            </div>
                            <div class="col-md-6">
                                <h6>${t('device.mqtt_topics', 'MQTT Topics')}</h6>
                                <small class="text-muted">
                                    <code>enocean/${escapeHtml(device.name)}/state</code><br>
                                    ${device.sender_id ? `<code>enocean/${escapeHtml(device.name)}/set</code>` : ''}
                                </small>
                            </div>
                        </div>
                    </div>
                </div>

                ${device.actuator_type ? `
                <div class="card mb-3">
                    <div class="card-header bg-warning bg-opacity-25">
                        <h6 class="mb-0"><i class="bi bi-lightning"></i> ${t('device.actuator_test', 'Actuator Test')}</h6>
                    </div>
                    <div class="card-body">
                        <p class="small text-muted mb-2">${t('device.actuator_hint', 'Send F6 rocker commands directly to test if teach-in was successful.')}</p>
                        <div class="d-flex gap-2 align-items-center flex-wrap">
                            ${device.actuator_type === 'cover' ? `
                                <button class="btn btn-success" data-test-command="OPEN">
                                    <i class="bi bi-arrow-up"></i> ${t('device.open', 'Open')}
                                </button>
                                <button class="btn btn-secondary" data-test-command="STOP">
                                    <i class="bi bi-stop-fill"></i> ${t('device.stop', 'Stop')}
                                </button>
                                <button class="btn btn-danger" data-test-command="CLOSE">
                                    <i class="bi bi-arrow-down"></i> ${t('device.close', 'Close')}
                                </button>
                            ` : `
                                <button class="btn btn-success" data-test-command="ON">
                                    <i class="bi bi-power"></i> ${t('device.test_on', 'Test ON')}
                                </button>
                                <button class="btn btn-danger" data-test-command="OFF">
                                    <i class="bi bi-power"></i> ${t('device.test_off', 'Test OFF')}
                                </button>
                            `}
                            <span id="test-actuator-result" class="small"></span>
                        </div>
                    </div>
                </div>
                ` : ''}

                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <span><i class="bi bi-clock-history"></i> ${t('device.recent_telegrams', 'Recent Telegrams for')} ${device.name}</span>
                        <small class="text-muted">${telegrams.length} ${t('device.telegrams_count', 'telegram(s)')}</small>
                    </div>
                    <div class="card-body" style="max-height: 400px; overflow-y: auto;">
                        ${telegrams.length === 0
                            ? `<p class="text-muted">${t('device.no_telegrams', 'No telegrams received from this device yet')}</p>`
                            : `<div class="table-responsive"><table class="table table-sm">
                                <thead><tr><th>${t('telegram.time', 'Time')}</th><th>${t('telegram.rorg', 'RORG')}</th><th>${t('telegram.data', 'Data')}</th><th>${t('telegram.dbm', 'dBm')}</th><th>${t('telegram.teach_in', 'Teach-In')}</th></tr></thead>
                                <tbody>
                                    ${telegrams.map(tg => `
                                        <tr>
                                            <td><small>${new Date(tg.timestamp).toLocaleTimeString()}</small></td>
                                            <td><span class="badge bg-secondary">${tg.rorg}</span></td>
                                            <td><code>${tg.data || '-'}</code></td>
                                            <td>${tg.dbm ? tg.dbm + ' dBm' : '<span class="text-muted">N/A</span>'}</td>
                                            <td>${tg.is_teach_in ? '<span class="badge bg-warning">Yes</span>' : '-'}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table></div>`
                        }
                    </div>
                </div>
            </div>
        `;
        // Same reason as the device cards: the name stays out of the markup and
        // is carried by the closure instead (#36).
        container.querySelector('[data-action="edit"]').addEventListener('click', () => editDevice(device.name));
        container.querySelectorAll('[data-test-command]').forEach(btn =>
            btn.addEventListener('click', () => testActuator(device.name, btn.dataset.testCommand)));
    } catch (error) {
        showToast(t('device.details_failed', 'Failed to load device details'), 'danger');
    }
}
async function deleteDevice(name) {
    if (!confirm(`${t('devices.delete_confirm', 'Delete device')} "${name}"?`)) return;

    try {
        // The response was never checked, so a failed delete still reported
        // success while the device stayed in the list. That is what made #36
        // look unfixable from the UI.
        const response = await fetch(getApiUrl(`/api/devices/${encodeURIComponent(name)}`), {method: 'DELETE'});
        if (!response.ok) {
            let detail = `${response.status} ${response.statusText}`;
            try { detail = (await response.json()).detail || detail; } catch (e) { /* keep status */ }
            throw new Error(detail);
        }
        loadDevices();
        showToast(t('devices.deleted', 'Device deleted'), 'success');
    } catch (error) {
        showToast(`${t('devices.delete_failed', 'Failed to delete device')}: ${error.message}`, 'danger');
    }
}
function getDeviceClassOptions(component, selected) {
    const classes = {
        'binary_sensor': ['', 'battery', 'cold', 'door', 'garage_door', 'gas', 'heat', 'moisture', 'motion', 'moving', 'occupancy', 'opening', 'plug', 'power', 'problem', 'safety', 'smoke', 'sound', 'vibration', 'window'],
        'sensor': ['', 'battery', 'current', 'energy', 'humidity', 'illuminance', 'power', 'pressure', 'signal_strength', 'temperature', 'timestamp', 'voltage'],
        'cover': ['', 'awning', 'blind', 'curtain', 'garage', 'gate', 'shade', 'shutter', 'window'],
        'switch': ['', 'outlet', 'switch'],
        'light': [''],
        'climate': [''],
        'fan': ['']
    };
    const options = classes[component] || [''];
    return options.map(c =>
        `<option value="${c}" ${c === selected ? 'selected' : ''}>${c || '(none)'}</option>`
    ).join('');
}
function filterDevices() {
    const query = document.getElementById('device-search').value.toLowerCase();
    const cards = document.querySelectorAll('#device-list > .device-col');

    cards.forEach(card => {
        const text = card.dataset.search || card.textContent.toLowerCase();
        card.style.display = text.includes(query) ? '' : 'none';
    });
}
