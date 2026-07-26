// Extracted from templates/index.html. Classic script, no modules:
// the inline onclick handlers call these by bare name, so they must stay global.

// Render the decoded payload of a telegram as a compact second line:
// prefers the human-readable *_text enum values over raw numbers and
// hides transport/meta fields. Falls back to the raw hex data.
const TELEGRAM_META_FIELDS = new Set(['sender_id', 'rssi', 'last_seen', 'raw', '_last_update', '_restored']);

async function loadStatus() {
    try {
        const response = await fetch(getApiUrl('/api/system/status'));
        const data = await response.json();

        // Update MQTT status
        const mqttBadge = document.getElementById('mqtt-status');
        const mqttConn = document.getElementById('mqtt-connection');
        const mqttCard = document.getElementById('card-mqtt');
        if (data.mqtt.connected) {
            mqttBadge.className = 'badge bg-success me-2';
            mqttBadge.innerHTML = '<i class="bi bi-wifi"></i> MQTT';
            mqttConn.className = 'badge bg-success';
            mqttConn.textContent = t('status.connected', 'Connected');
            mqttCard.classList.add('connected');
            mqttCard.classList.remove('disconnected');
        } else {
            mqttBadge.className = 'badge bg-danger me-2';
            mqttBadge.innerHTML = '<i class="bi bi-wifi-off"></i> MQTT';
            mqttConn.className = 'badge bg-danger';
            mqttConn.textContent = t('status.disconnected', 'Disconnected');
            mqttCard.classList.add('disconnected');
            mqttCard.classList.remove('connected');
        }
        document.getElementById('mqtt-host').textContent = data.mqtt.host || t('status.not_configured', 'Not configured');

        // Update EnOcean status
        const enoceanBadge = document.getElementById('enocean-status');
        const enoceanConn = document.getElementById('enocean-connection');
        const enoceanCard = document.getElementById('card-enocean');
        if (data.enocean.connected) {
            enoceanBadge.className = 'badge bg-success';
            enoceanBadge.innerHTML = '<i class="bi bi-usb-symbol"></i> EnOcean';
            enoceanConn.className = 'badge bg-success';
            enoceanConn.textContent = t('status.connected', 'Connected');
            enoceanCard.classList.add('connected');
            enoceanCard.classList.remove('disconnected');
        } else {
            enoceanBadge.className = 'badge bg-danger';
            enoceanBadge.innerHTML = '<i class="bi bi-usb-symbol"></i> EnOcean';
            enoceanConn.className = 'badge bg-danger';
            enoceanConn.textContent = t('status.disconnected', 'Disconnected');
            enoceanCard.classList.add('disconnected');
            enoceanCard.classList.remove('connected');
        }
        document.getElementById('enocean-port').textContent = data.enocean.port || t('status.not_configured', 'Not configured');

        // Update counts
        document.getElementById('device-count').textContent = data.devices.count;
        document.getElementById('profile-count').textContent = data.profiles.count;

    } catch (error) {
        console.error('Failed to load status:', error);
    }
}
async function loadRecentTelegrams() {
    try {
        const response = await fetch(getApiUrl('/api/gateway/recent-telegrams?limit=10'));
        const telegrams = await response.json();

        const container = document.getElementById('recent-activity');

        if (telegrams.length === 0) {
            container.innerHTML = `<p class="text-muted">${t('dashboard.no_telegrams', 'No telegrams received yet')}</p>`;
            return;
        }

        container.innerHTML = telegrams.map(tg => `
            <div class="border-bottom py-2">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>${tg.device_name || t('common.unknown', 'Unknown')}</strong>
                        <small class="text-muted ms-2">${tg.sender_id}</small>
                        ${tg.is_teach_in ? `<span class="badge bg-warning ms-2">${t('teach_in.teach_in_badge', 'Teach-In')}</span>` : ''}
                    </div>
                    <div>
                        <span class="badge bg-secondary">${tg.rorg}</span>
                        <small class="text-muted">${tg.dbm ? tg.dbm + ' dBm' : 'N/A'}</small>
                    </div>
                </div>
                ${formatTelegramDetails(tg)}
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load recent telegrams:', error);
    }
}
function formatTelegramDetails(tg) {
    const parts = [];
    const d = tg.decoded || {};
    for (const [key, value] of Object.entries(d)) {
        if (TELEGRAM_META_FIELDS.has(key) || key.endsWith('_text')) continue;
        const text = d[key + '_text'];
        const shown = (text !== undefined && text !== '') ? text : value;
        parts.push(`${escapeHtml(key)}: <strong>${escapeHtml(String(shown))}</strong>`);
    }
    const hex = tg.data ? `<code class="text-muted">0x${escapeHtml(tg.data)}</code>` : '';
    if (!parts.length && !hex) return '';
    return `<div class="small text-muted mt-1">${parts.join(' &middot; ')}${parts.length && hex ? ' &nbsp;' : ''}${hex}</div>`;
}
async function clearTelegrams() {
    try {
        await fetch(getApiUrl('/api/gateway/clear-telegrams'), { method: 'POST' });
        loadRecentTelegrams();
        loadUnknownDevices();
        showToast(t('toast.telegrams_cleared', 'Telegrams cleared'), 'success');
    } catch (error) {
        showToast(t('toast.telegrams_clear_failed', 'Failed to clear telegrams'), 'danger');
    }
}
async function loadUnknownDevices() {
    try {
        const response = await fetch(getApiUrl('/api/gateway/unknown-devices'));
        const devices = await response.json();

        const container = document.getElementById('unknown-devices-list');

        if (devices.length === 0) {
            container.innerHTML = `<p class="text-muted">${t('dashboard.no_unknown', 'No unknown devices detected')}</p>`;
            return;
        }

        container.innerHTML = `
            <div class="table-responsive">
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>${t('table.address', 'Address')}</th>
                            <th>${t('table.rorg', 'RORG')}</th>
                            <th>${t('table.signal', 'Signal')}</th>
                            <th>${t('table.count', 'Count')}</th>
                            <th>${t('table.last_seen', 'Last Seen')}</th>
                            <th>${t('table.action', 'Action')}</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${devices.map(d => `
                            <tr>
                                <td><code>${d.sender_id}</code></td>
                                <td><span class="badge bg-primary">${d.rorg}</span></td>
                                <td>${d.dbm ? d.dbm + ' dBm' : '<span class="text-muted">N/A</span>'}</td>
                                <td>${d.count}</td>
                                <td><small>${new Date(d.last_seen).toLocaleTimeString()}</small></td>
                                <td>
                                    <button class="btn btn-sm btn-outline-primary" onclick="addUnknownDevice('${d.sender_id}', '${d.rorg}')">
                                        <i class="bi bi-plus"></i> ${t('table.add', 'Add')}
                                    </button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch (error) {
        console.error('Failed to load unknown devices:', error);
    }
}
function addUnknownDevice(senderId, rorg) {
    // Navigate to teach-in page and pre-fill the form
    navigateTo('teach-in');
    showManualEntry();
    document.querySelector('[name="address"]').value = senderId;
    document.querySelector('[name="rorg"]').value = rorg;
}
