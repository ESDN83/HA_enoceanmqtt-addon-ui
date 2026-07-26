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
            card.className = 'col-md-4 mb-3';
            // Build searchable text from device properties only (not button text)
            const searchText = [device.name, device.address, `${device.rorg}-${device.func}-${device.type}`,
                device.actuator_type, device.room, device.description, device.sender_id
            ].filter(Boolean).join(' ').toLowerCase();
            card.dataset.search = searchText;
            card.innerHTML = `
                <div class="card device-card" style="cursor: pointer;" onclick="showDeviceDetail('${device.name}')">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <h5 class="card-title mb-1">${device.name}</h5>
                            <div class="btn-group btn-group-sm" onclick="event.stopPropagation()">
                                <button class="btn btn-outline-primary" onclick="editDevice('${device.name}')" title="Edit">
                                    <i class="bi bi-pencil"></i>
                                </button>
                                <button class="btn btn-outline-danger" onclick="deleteDevice('${device.name}')" title="Delete">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </div>
                        </div>
                        <p class="card-text mb-1">
                            <code class="text-muted">${device.address}</code>
                        </p>
                        <p class="card-text mb-1">
                            <span class="badge bg-primary">${device.rorg}-${device.func}-${device.type}</span>
                            ${device.actuator_type ? `<span class="badge bg-warning text-dark ms-1"><i class="bi bi-lightning"></i> ${device.actuator_type}</span>` : ''}
                            ${device.room ? `<span class="badge bg-secondary ms-1">${device.room}</span>` : ''}
                        </p>
                        ${device.description ? `<p class="card-text mb-0"><small class="text-muted">${device.description}</small></p>` : ''}
                        ${device.sender_id ? `<p class="card-text mb-0"><small class="text-muted"><i class="bi bi-arrow-left-right"></i> Sender: ${device.sender_id}</small></p>` : ''}
                    </div>
                </div>
            `;
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
function resetDeviceForm() {
    const note = document.getElementById('multichannel-note');
    if (note) note.style.display = 'none';
    const form = document.getElementById('device-form');
    if (!form) return;
    form.reset();
    delete form.dataset.editMode;
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
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.textContent = t('teach_in.add_device', 'Add Device');
    const heading = document.querySelector('#step-2 h4');
    if (heading) heading.textContent = t('teach_in.step2', 'Step 2: Configure Device');
}
function toggleChannelField(rorg, func) {
    const group = document.getElementById('channel-group');
    if (!group) return;
    const r = String(rorg || '').toUpperCase().replace('0X', '');
    const f = String(func || '').toUpperCase().padStart(2, '0');
    group.style.display = (r === 'D2' && f === '01') ? '' : 'none';
}
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
async function saveDevice(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    const device = Object.fromEntries(formData);
    // Checkboxes are absent from FormData when unchecked; send an
    // explicit boolean so unchecking "invert" is persisted too.
    const invertCb = form.querySelector('input[name="invert"]');
    device.invert = !!(invertCb && invertCb.checked);
    const editMode = form.dataset.editMode;

    // Rename warning: the device name is the primary key and the MQTT
    // topic base, so renaming re-homes its topics/object_id. The HA
    // entity itself is preserved (its unique_id is name-independent).
    if (editMode && device.name && device.name !== editMode) {
        showConfirmDialog(
            t('device.rename_title', 'Rename device?'),
            t('device.rename_body', 'This changes the device\'s MQTT topics and entity object_id') +
                ' ("' + escapeHtml(editMode) + '" → "' + escapeHtml(device.name) + '"). ' +
                t('device.rename_hint', 'The Home Assistant entity is kept; only its topics change. Rename?'),
            t('device.rename_btn', 'Rename'),
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
            response = await fetch(getApiUrl(`/api/devices/${editMode}`), {
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
        const response = await fetch(getApiUrl(`/api/devices/${name}`));
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

        // Channel (2-channel D2-01 modules)
        const chField = document.querySelector('[name="channel"]');
        if (chField) chField.value = String(device.channel || 0);
        toggleChannelField(device.rorg, device.func);

        // Mark as edit mode
        const form = document.getElementById('device-form');
        form.dataset.editMode = name;

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
        const response = await fetch(getApiUrl(`/api/devices/${name}`));
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
                    <button class="btn btn-outline-primary btn-sm ms-2" onclick="editDevice('${device.name}')">
                        <i class="bi bi-pencil"></i> ${t('device.edit', 'Edit Device')}
                    </button>
                </div>

                <div class="card mb-3">
                    <div class="card-header">
                        <h5 class="mb-0"><i class="bi bi-cpu"></i> ${device.name}</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-6">
                                <table class="table table-sm">
                                    <tr><th>${t('device.address', 'Address')}</th><td><code>${device.address}</code></td></tr>
                                    <tr><th>${t('device.eep_profile', 'EEP Profile')}</th><td><span class="badge bg-primary">${device.rorg}-${device.func}-${device.type}</span></td></tr>
                                    ${device.description ? `<tr><th>${t('device.description', 'Description')}</th><td>${device.description}</td></tr>` : ''}
                                    ${device.room ? `<tr><th>${t('device.room', 'Room')}</th><td>${device.room}</td></tr>` : ''}
                                    ${device.sender_id ? `<tr><th>${t('device.sender_id', 'Sender ID')}</th><td><code>${device.sender_id}</code></td></tr>` : ''}
                                    ${device.actuator_type ? `<tr><th>${t('device.device_role', 'Device Role')}</th><td><span class="badge bg-warning text-dark">${device.actuator_type}</span></td></tr>` : ''}
                                    ${device.manufacturer ? `<tr><th>${t('device.manufacturer', 'Manufacturer')}</th><td>${device.manufacturer}</td></tr>` : ''}
                                </table>
                            </div>
                            <div class="col-md-6">
                                <h6>${t('device.mqtt_topics', 'MQTT Topics')}</h6>
                                <small class="text-muted">
                                    <code>enocean/${device.name}/state</code><br>
                                    ${device.sender_id ? `<code>enocean/${device.name}/set</code>` : ''}
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
                                <button class="btn btn-success" onclick="testActuator('${device.name}', 'OPEN')">
                                    <i class="bi bi-arrow-up"></i> ${t('device.open', 'Open')}
                                </button>
                                <button class="btn btn-secondary" onclick="testActuator('${device.name}', 'STOP')">
                                    <i class="bi bi-stop-fill"></i> ${t('device.stop', 'Stop')}
                                </button>
                                <button class="btn btn-danger" onclick="testActuator('${device.name}', 'CLOSE')">
                                    <i class="bi bi-arrow-down"></i> ${t('device.close', 'Close')}
                                </button>
                            ` : `
                                <button class="btn btn-success" onclick="testActuator('${device.name}', 'ON')">
                                    <i class="bi bi-power"></i> ${t('device.test_on', 'Test ON')}
                                </button>
                                <button class="btn btn-danger" onclick="testActuator('${device.name}', 'OFF')">
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
    } catch (error) {
        showToast(t('device.details_failed', 'Failed to load device details'), 'danger');
    }
}
async function deleteDevice(name) {
    if (!confirm(`${t('devices.delete_confirm', 'Delete device')} "${name}"?`)) return;

    try {
        await fetch(getApiUrl(`/api/devices/${name}`), {method: 'DELETE'});
        loadDevices();
        showToast(t('devices.deleted', 'Device deleted'), 'success');
    } catch (error) {
        showToast(t('devices.delete_failed', 'Failed to delete device'), 'danger');
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
    const cards = document.querySelectorAll('#device-list > .col-md-4');

    cards.forEach(card => {
        const text = card.dataset.search || card.textContent.toLowerCase();
        card.style.display = text.includes(query) ? '' : 'none';
    });
}
