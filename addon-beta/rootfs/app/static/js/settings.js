// Extracted from templates/index.html. Classic script, no modules:
// the inline onclick handlers call these by bare name, so they must stay global.

// === MQTT Settings (Web UI editor for /data/options.json mqtt block) ===
const MQTT_CFG_FIELDS = ['host', 'port', 'username', 'password', 'discovery_prefix', 'prefix', 'client_id'];

async function exportConfig() {
    try {
        const response = await fetch(getApiUrl('/api/system/export'), {method: 'POST'});
        if (!response.ok) throw new Error(t('settings.export_failed', 'Export failed'));
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const disposition = response.headers.get('Content-Disposition');
        a.download = disposition ? disposition.split('filename=')[1] : 'enocean_config.zip';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast(t('export.success', 'Config exported successfully'), 'success');
    } catch (error) {
        showToast(t('export.failed', 'Export failed') + ': ' + error.message, 'danger');
    }
}
async function importConfig(input) {
    if (!input.files.length) return;

    const formData = new FormData();
    formData.append('file', input.files[0]);

    try {
        const response = await fetch(getApiUrl('/api/system/import'), {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        showToast(`${t('settings.import_success', 'Import successful')}: ${result.details.devices ? 'devices, ' : ''}${result.details.mappings ? 'mappings, ' : ''}${result.details.custom_profiles} custom profiles`, 'success');
        loadStatus();
    } catch (error) {
        showToast(t('settings.import_failed', 'Import failed'), 'danger');
    }
}
async function restartServices() {
    if (!confirm(t('settings.restart_confirm', 'Restart EnOcean and MQTT services?'))) return;

    try {
        await fetch(getApiUrl('/api/system/restart'), {method: 'POST'});
        showToast(t('settings.restarting', 'Services restarting...'), 'info');
        setTimeout(loadStatus, 3000);
    } catch (error) {
        showToast(t('settings.restart_failed', 'Restart failed'), 'danger');
    }
}
async function loadBackups() {
    try {
        const response = await fetch(getApiUrl('/api/system/backups'));
        const backups = await response.json();
        renderBackupList(backups);
    } catch (error) {
        document.getElementById('backup-list').innerHTML =
            `<p class="text-danger">${t('backup.load_failed', 'Failed to load backups')}</p>`;
    }
}
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}
function renderBackupList(backups) {
    const container = document.getElementById('backup-list');

    if (backups.length === 0) {
        container.innerHTML = `<p class="text-muted">${t('backup.no_backups', 'No backups yet. Click "Create Backup" to save your current configuration.')}</p>`;
        return;
    }

    container.innerHTML = `
        <div class="table-responsive">
            <table class="table table-sm table-hover mb-0">
                <thead>
                    <tr>
                        <th>${t('backup.filename', 'Filename')}</th>
                        <th>${t('backup.created', 'Created')}</th>
                        <th>${t('backup.size', 'Size')}</th>
                        <th>${t('backup.devices', 'Devices')}</th>
                        <th>${t('backup.version', 'Version')}</th>
                        <th class="text-end">${t('backup.actions', 'Actions')}</th>
                    </tr>
                </thead>
                <tbody>
                    ${backups.map(b => `
                        <tr>
                            <td><code class="small">${b.filename}</code></td>
                            <td><small>${new Date(b.created_at).toLocaleString()}</small></td>
                            <td><small>${formatFileSize(b.size)}</small></td>
                            <td><small>${b.devices}</small></td>
                            <td><small>${b.version}</small></td>
                            <td class="text-end text-nowrap">
                                <button class="btn btn-sm btn-outline-primary me-1" onclick="downloadBackup('${b.filename}')" title="${t('backup.download', 'Download')}">
                                    <i class="bi bi-download"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-warning me-1" onclick="confirmRestoreBackup('${b.filename}')" title="${t('backup.restore', 'Restore')}">
                                    <i class="bi bi-arrow-counterclockwise"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-danger" onclick="confirmDeleteBackup('${b.filename}')" title="${t('backup.delete', 'Delete')}">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}
async function createBackup() {
    try {
        showToast(t('backup.creating', 'Creating backup...'), 'info');
        const response = await fetch(getApiUrl('/api/system/backup'), {method: 'POST'});
        if (!response.ok) throw new Error(t('backup.failed', 'Backup failed'));
        const result = await response.json();
        showToast(`${t('backup.created_success', 'Backup created')}: ${result.filename}`, 'success');
        loadBackups();
    } catch (error) {
        showToast(t('backup.failed', 'Backup failed') + ': ' + error.message, 'danger');
    }
}
function downloadBackup(filename) {
    const a = document.createElement('a');
    a.href = getApiUrl(`/api/system/backup/download/${filename}`);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}
function confirmRestoreBackup(filename) {
    showConfirmDialog(
        t('backup.restore_title', 'Restore Backup'),
        `<p>${t('backup.restore_confirm', 'Are you sure you want to restore from:')}</p>
         <p><strong><code>${filename}</code></strong></p>
         <p class="text-warning mb-0"><i class="bi bi-exclamation-triangle"></i>
         ${t('backup.restore_warning', 'This will overwrite your current devices, mappings, and custom profiles.')}</p>`,
        t('backup.restore', 'Restore'),
        'btn-warning',
        async () => {
            try {
                showToast(t('backup.restoring', 'Restoring backup...'), 'info');
                const response = await fetch(getApiUrl(`/api/system/backup/restore/${filename}`), {method: 'POST'});
                if (!response.ok) {
                    const err = await response.json().catch(() => null);
                    throw new Error(err?.detail || t('backup.restore_failed', 'Restore failed'));
                }
                const result = await response.json();
                showToast(`${t('backup.restored', 'Backup restored')}: ${result.details.devices ? t('nav.devices', 'devices') + ', ' : ''}${result.details.mappings ? t('nav.mappings', 'mappings') + ', ' : ''}${result.details.custom_profiles} ${t('backup.custom_profiles', 'custom profiles')}`, 'success');
                loadStatus();
                loadDevices();
                loadProfiles();
            } catch (error) {
                showToast(t('backup.restore_failed', 'Restore failed') + ': ' + error.message, 'danger');
            }
        }
    );
}
function confirmDeleteBackup(filename) {
    showConfirmDialog(
        t('backup.delete_title', 'Delete Backup'),
        `<p>${t('backup.delete_confirm', 'Are you sure you want to delete:')}</p>
         <p><strong><code>${filename}</code></strong></p>
         <p class="text-danger mb-0"><i class="bi bi-exclamation-triangle"></i>
         ${t('backup.delete_warning', 'This cannot be undone.')}</p>`,
        t('backup.delete', 'Delete'),
        'btn-danger',
        async () => {
            try {
                const response = await fetch(getApiUrl(`/api/system/backup/${filename}`), {method: 'DELETE'});
                if (!response.ok) throw new Error(t('backup.delete_failed', 'Delete failed'));
                showToast(t('backup.deleted', 'Backup deleted'), 'success');
                loadBackups();
            } catch (error) {
                showToast(t('backup.delete_failed', 'Delete failed') + ': ' + error.message, 'danger');
            }
        }
    );
}
async function loadEepInfo() {
    try {
        const response = await fetch(getApiUrl('/api/system/eep-info'));
        const data = await response.json();

        const sourceLabels = {
            user: t('settings.eep_source_user', 'Custom (uploaded)'),
            bundled: t('settings.eep_source_bundled', 'Bundled (default)'),
            minimal: t('settings.eep_source_minimal', 'Minimal (fallback)')
        };

        document.getElementById('eep-source').textContent = sourceLabels[data.source] || data.source;

        const fileSize = data.source === 'user' ? data.user_file_size : data.bundled_file_size;
        document.getElementById('eep-file-size').textContent = fileSize > 0 ? formatFileSize(fileSize) : '-';
        document.getElementById('eep-profile-count').textContent = data.profile_count;

        document.getElementById('eep-delete-btn').style.display = data.user_file_exists ? '' : 'none';
    } catch (error) {
        console.error('Failed to load EEP info:', error);
    }
}
async function uploadEep(input) {
    if (!input.files.length) return;

    const formData = new FormData();
    formData.append('file', input.files[0]);

    try {
        const response = await fetch(getApiUrl('/api/system/upload-eep'), {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            showToast(t('settings.eep_upload_failed', 'EEP.xml upload failed') + ': ' + (error.detail || ''), 'danger');
            return;
        }

        showToast(t('settings.eep_upload_success', 'EEP.xml uploaded successfully'), 'success');
        loadEepInfo();
        loadStatus();
        loadProfiles(); // Refresh tree to detect orphaned mappings
    } catch (error) {
        showToast(t('settings.eep_upload_failed', 'EEP.xml upload failed'), 'danger');
    }

    input.value = '';
}
async function deleteEep() {
    if (!confirm(t('settings.eep_delete_confirm', 'Delete custom EEP.xml and revert to bundled version?'))) return;

    try {
        const response = await fetch(getApiUrl('/api/system/delete-eep'), {
            method: 'DELETE'
        });

        if (!response.ok) {
            showToast(t('settings.eep_delete_failed', 'Failed to delete custom EEP.xml'), 'danger');
            return;
        }

        showToast(t('settings.eep_delete_success', 'Custom EEP.xml deleted, reverted to bundled'), 'success');
        loadEepInfo();
        loadStatus();
        loadProfiles(); // Refresh tree to detect orphaned mappings
    } catch (error) {
        showToast(t('settings.eep_delete_failed', 'Failed to delete custom EEP.xml'), 'danger');
    }
}
async function downloadEep() {
    try {
        const response = await fetch(getApiUrl('/api/system/download-eep'));
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'EEP.xml';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (error) {
        showToast(t('settings.eep_download_failed', 'EEP.xml download failed') + ': ' + error.message, 'danger');
    }
}
function mqttCfgInput(key) {
    return document.getElementById('mqtt-cfg-' + key.replace(/_/g, '-'));
}
async function loadMqttConfig() {
    try {
        const response = await fetch(getApiUrl('/api/system/mqtt-config'));
        if (!response.ok) return;
        const data = await response.json();
        for (const key of MQTT_CFG_FIELDS) {
            const el = mqttCfgInput(key);
            if (el) el.value = data.mqtt[key] ?? '';
        }
    } catch (error) {
        console.error('loadMqttConfig failed', error);
    }
}
async function saveMqttConfig(restart) {
    const mqtt = {};
    for (const key of MQTT_CFG_FIELDS) {
        const el = mqttCfgInput(key);
        if (el) mqtt[key] = el.value;
    }
    try {
        const response = await fetch(getApiUrl('/api/system/mqtt-config'), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({mqtt: mqtt, restart: !!restart})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'HTTP ' + response.status);
        if (data.restarting) {
            showToast(t('settings.mqtt_saved_restarting', 'MQTT settings saved, the app is restarting...'), 'success');
        } else {
            showToast(t('settings.mqtt_saved', 'MQTT settings saved. Restart the app to apply'), 'success');
        }
        loadMqttConfig();
    } catch (error) {
        showToast(t('settings.mqtt_save_failed', 'Failed to save MQTT settings') + ': ' + error.message, 'danger');
    }
}
function resetMqttConfig() {
    showConfirmDialog(
        t('settings.mqtt_reset_confirm_title', 'Reset MQTT settings?'),
        t('settings.mqtt_reset_confirm', 'This restores all MQTT options to their defaults (auto-discovery via Home Assistant broker). The app must be restarted to apply.'),
        t('settings.mqtt_reset', 'Reset to Defaults'),
        'btn-danger',
        async () => {
            try {
                const response = await fetch(getApiUrl('/api/system/mqtt-config'), {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({reset: true})
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.detail || 'HTTP ' + response.status);
                showToast(t('settings.mqtt_reset_done', 'MQTT settings reset to defaults. Restart the app to apply'), 'success');
                loadMqttConfig();
            } catch (error) {
                showToast(t('settings.mqtt_save_failed', 'Failed to save MQTT settings') + ': ' + error.message, 'danger');
            }
        }
    );
}

// === Import from another EnOcean add-on (ADR-0020) ===
// The server only reads and checks the old list; every chosen device is then
// created through the normal POST /api/devices, one by one.
let legacyCandidates = [];

async function loadLegacySources() {
    const hint = document.getElementById('legacy-sources-hint');
    try {
        const r = await fetch(getApiUrl('/api/system/legacy-import/sources'));
        const s = await r.json();
        document.getElementById('legacy-btn-christophehd').disabled = !s.christophehd.available;
        document.getElementById('legacy-btn-slim').disabled = !s.slim.available;
        const notes = [];
        if (s.slim.installed && !s.slim.available) notes.push(t('legacy.slim_stopped', 'Slim is installed but not running. Start it to read its devices.'));
        if (!s.christophehd.available && !s.slim.installed) notes.push(t('legacy.none_found', 'No old app found. You can still upload an enoceanmqtt.devices or Slim devices.json file.'));
        hint.textContent = notes.join(' ');
    } catch (e) {
        hint.textContent = '';
    }
}

async function legacyPreview(source) {
    const fd = new FormData();
    fd.append('source', source);
    await legacyRunPreview(fd);
}

async function legacyPreviewFile(input) {
    if (!input.files.length) return;
    const fd = new FormData();
    fd.append('file', input.files[0]);
    input.value = '';
    await legacyRunPreview(fd);
}

async function legacyRunPreview(fd) {
    const box = document.getElementById('legacy-preview');
    box.innerHTML = '<div class="spinner-border spinner-border-sm"></div>';
    try {
        const r = await fetch(getApiUrl('/api/system/legacy-import/preview'), {method: 'POST', body: fd});
        const res = await r.json();
        if (!r.ok) throw new Error(res.detail || r.statusText);
        legacyCandidates = res.devices;
        renderLegacyPreview(res);
    } catch (e) {
        box.innerHTML = '';
        showToast(t('legacy.read_failed', 'Could not read the device list') + ': ' + e.message, 'danger');
    }
}

const LEGACY_SKIP_REASONS = {
    ignored: ['legacy.skip_ignored', 'marked ignore'],
    no_address: ['legacy.skip_no_address', 'no valid address'],
    no_eep: ['legacy.skip_no_eep', 'no EEP'],
    model_only: ['legacy.skip_model', 'defined by model only, add it by hand with its EEP'],
};

function renderLegacyPreview(res) {
    const box = document.getElementById('legacy-preview');
    const rows = legacyCandidates.map((c, i) => {
        const status = c.exists
            ? `<span class="badge bg-secondary">${t('legacy.exists', 'already configured')}</span>`
            : (c.eep_known ? '' : `<span class="badge bg-warning text-dark">${t('legacy.unknown_eep', 'EEP not in database')}</span>`);
        return `<tr>
            <td><input type="checkbox" class="form-check-input legacy-pick" data-i="${i}" ${c.exists || !c.eep_known ? '' : 'checked'}></td>
            <td><input type="text" class="form-control form-control-sm legacy-name" data-i="${i}" value="${escapeHtml(c.name)}"></td>
            <td><code>${escapeHtml(c.address)}</code></td>
            <td>${escapeHtml(c.eep)}</td>
            <td>${c.sender_id ? `<code>${escapeHtml(c.sender_id)}</code>` : ''}</td>
            <td>${status}</td>
        </tr>`;
    }).join('');
    const skipped = (res.skipped || []).map(s => {
        const [key, fb] = LEGACY_SKIP_REASONS[s.reason] || ['', s.reason];
        return `<li>${escapeHtml(s.name)}${s.address ? ` (<code>${escapeHtml(s.address)}</code>)` : ''}: ${key ? t(key, fb) : escapeHtml(fb)}</li>`;
    }).join('');
    const fmt = res.format === 'slim' ? 'EnOcean MQTT Slim' : 'ChristopheHD enocean-mqtt';
    box.innerHTML = `
        <div class="small mb-2"><strong>${fmt}</strong>: ${legacyCandidates.length} ${t('legacy.found', 'devices found')}</div>
        ${legacyCandidates.length ? `<div class="table-responsive"><table class="table table-sm align-middle">
            <thead><tr><th></th><th>${t('legacy.col_name', 'Name')}</th><th>${t('legacy.col_address', 'Address')}</th><th>EEP</th><th>${t('legacy.col_sender', 'Sender ID')}</th><th></th></tr></thead>
            <tbody>${rows}</tbody></table></div>` : ''}
        ${skipped ? `<div class="small text-muted">${t('legacy.skipped', 'Not imported')}:<ul class="mb-2">${skipped}</ul></div>` : ''}
        <div class="small text-muted mb-2">${t('legacy.check_actuators', 'Actuators (lights, switches, covers) may need their type and sender ID checked afterwards.')}</div>
        ${legacyCandidates.length ? `<button class="btn btn-primary" onclick="legacyImportSelected()"><i class="bi bi-plus-circle"></i> ${t('legacy.import_selected', 'Add selected devices')}</button>` : ''}`;
}

async function legacyImportSelected() {
    const picks = [...document.querySelectorAll('.legacy-pick:checked')].map(el => +el.dataset.i);
    if (!picks.length) return;
    let ok = 0;
    const failed = [];
    for (const i of picks) {
        const c = legacyCandidates[i];
        const name = document.querySelector(`.legacy-name[data-i="${i}"]`).value.trim();
        try {
            const r = await fetch(getApiUrl('/api/devices'), {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    name, address: c.address, rorg: c.rorg, func: c.func, type: c.type,
                    sender_id: c.sender_id || '', manufacturer: c.manufacturer || '',
                }),
            });
            if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
            ok++;
        } catch (e) {
            failed.push(`${name}: ${e.message}`);
        }
    }
    document.getElementById('legacy-preview').innerHTML = failed.length
        ? `<div class="alert alert-warning small mb-0">${failed.map(escapeHtml).join('<br>')}</div>` : '';
    showToast(`${ok} ${t('legacy.added', 'devices added')}${failed.length ? `, ${failed.length} ${t('legacy.failed', 'failed')}` : ''}`,
        failed.length ? 'warning' : 'success');
    if (typeof loadDevices === 'function') loadDevices();
}

const LEGACY_HELP_STEPS = [
    ['legacy.help_1', 'Make a full Home Assistant backup. This tool comes without warranty.'],
    ['legacy.help_2', 'Leave the old app running for now. Slim is read over the network; ChristopheHD is read from /config/enoceanmqtt.devices. You can also upload the file.'],
    ['legacy.help_3', 'Step 1: read the list, check the names, add the selected devices. Devices that already exist are not ticked.'],
    ['legacy.help_4', 'Stop the old app and turn off "Start on boot". Only one app can use the transceiver.'],
    ['legacy.help_5', 'Step 2: find the old entities and remove the ones you no longer need. Only devices that exist in this app are offered, and the Home Assistant device itself is not deleted.'],
    ['legacy.help_6', 'Rename the new entities to the old entity IDs (Settings, Entities). Automations and dashboards then keep working. The history of the old entities is not carried over.'],
    ['legacy.help_7', 'Check actuators (light, switch, cover): their type and sender ID may need setting.'],
];

function showLegacyHelp() {
    document.getElementById('legacyHelpSteps').innerHTML =
        LEGACY_HELP_STEPS.map(([k, fb]) => `<li class="mb-2">${escapeHtml(t(k, fb))}</li>`).join('');
    new bootstrap.Modal(document.getElementById('legacyHelpModal')).show();
}

let legacyOld = [];

async function legacyFindOld() {
    const box = document.getElementById('legacy-old');
    box.innerHTML = '<div class="spinner-border spinner-border-sm"></div>';
    try {
        const r = await fetch(getApiUrl('/api/system/legacy-import/old-entities'), {method: 'POST'});
        const res = await r.json();
        if (!r.ok) throw new Error(res.detail || r.statusText);
        legacyOld = res.entities;
        renderLegacyOld(res);
    } catch (e) {
        box.innerHTML = '';
        showToast(t('legacy.find_failed', 'Could not search for old entities') + ': ' + e.message, 'danger');
    }
}

function renderLegacyOld(res) {
    const box = document.getElementById('legacy-old');
    if (!legacyOld.length) {
        box.innerHTML = `<div class="small text-muted">${t('legacy.old_none', 'No old entities found for the devices configured here.')}</div>`;
        return;
    }
    const rows = legacyOld.map((o, i) => `<tr>
        <td><input type="checkbox" class="form-check-input legacy-old-pick" data-i="${i}" checked></td>
        <td>${escapeHtml(o.device)}</td>
        <td>${escapeHtml(o.name)}</td>
        <td><code>${escapeHtml(o.address)}</code></td>
        <td>${o.source === 'slim' ? 'Slim' : 'ChristopheHD'}</td>
        <td class="small text-muted"><code>${escapeHtml(o.unique_id)}</code></td>
    </tr>`).join('');
    box.innerHTML = `
        ${res.slim_running ? `<div class="alert alert-warning small py-2">${t('legacy.slim_still_running', 'Slim is still running. Stop it first, otherwise it publishes these entities again.')}</div>` : ''}
        <div class="small mb-2">${legacyOld.length} ${t('legacy.old_found', 'old entities found')}</div>
        <div class="table-responsive"><table class="table table-sm align-middle">
            <thead><tr><th></th><th>${t('legacy.col_device', 'Device')}</th><th>${t('legacy.col_entity', 'Entity')}</th><th>${t('legacy.col_address', 'Address')}</th><th>${t('legacy.col_source', 'From')}</th><th>Unique ID</th></tr></thead>
            <tbody>${rows}</tbody></table></div>
        <button class="btn btn-danger" onclick="legacyRemoveOld()" ${res.slim_running ? 'disabled' : ''}>
            <i class="bi bi-trash"></i> ${t('legacy.remove_selected', 'Remove selected old entities')}</button>`;
}

function legacyRemoveOld() {
    const topics = [...document.querySelectorAll('.legacy-old-pick:checked')].map(el => legacyOld[+el.dataset.i].topic);
    if (!topics.length) return;
    showConfirmDialog(
        t('legacy.remove_title', 'Remove old entities?'),
        escapeHtml(t('legacy.remove_body', 'Home Assistant removes {n} old entities. Automations that still use their entity IDs stop working until you rename the new entities. The devices and the new entities stay.').replace('{n}', topics.length)),
        t('legacy.remove_selected', 'Remove selected old entities'), 'btn-danger',
        async () => {
            try {
                const r = await fetch(getApiUrl('/api/system/legacy-import/old-entities/remove'), {
                    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({topics}),
                });
                const res = await r.json();
                if (!r.ok) throw new Error(res.detail || r.statusText);
                showToast(`${res.removed.length} ${t('legacy.removed', 'old entities removed')}`, 'success');
                await legacyFindOld();
            } catch (e) {
                showToast(t('legacy.remove_failed', 'Removing failed') + ': ' + e.message, 'danger');
            }
        });
}
