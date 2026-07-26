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
            showToast(t('settings.mqtt_saved_restarting', 'MQTT settings saved — app is restarting...'), 'success');
        } else {
            showToast(t('settings.mqtt_saved', 'MQTT settings saved — restart the app to apply'), 'success');
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
                showToast(t('settings.mqtt_reset_done', 'MQTT settings reset to defaults — restart the app to apply'), 'success');
                loadMqttConfig();
            } catch (error) {
                showToast(t('settings.mqtt_save_failed', 'Failed to save MQTT settings') + ': ' + error.message, 'danger');
            }
        }
    );
}
