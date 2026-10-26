// Help for the Add Device page: a start page under Step 1, how-to blocks
// for the three ways of adding a device, and a searchable catalogue of
// devices whose setup is verified (data/device_catalog.json, ADR-0034).
// Classic script, no modules: the inline onclick handlers call these by
// bare name, so they must stay global.

let _deviceCatalog = null;
let _catalogDevice = null;   // the catalogue entry the user picked, if any
let _teachHelpLang = null;   // language the help was rendered in

function _fig(art, caption) {
    const src = getApiUrl(`/static/img/teach/${art}.svg?v=${window.APP_ASSET_V || ''}`);
    return `<figure class="teach-fig">
        <a href="${src}" target="_blank" rel="noopener"><img src="${src}" alt="${escapeHtml(caption)}" loading="lazy"></a>
        <figcaption>${escapeHtml(caption)}</figcaption>
    </figure>`;
}

function _list(items) {
    return '<ul class="small mb-0">' + items.map(i => `<li>${escapeHtml(i)}</li>`).join('') + '</ul>';
}

const _METHOD = {
    auto: { icon: 'bi-broadcast', cls: 'primary', key: 'teach_in.automatic', fallback: 'Automatic (Teach-In)' },
    actuator: { icon: 'bi-lightning', cls: 'warning', key: 'teach_in.actuator_teach_in', fallback: 'Actuator Teach-In' },
    manual: { icon: 'bi-pencil-square', cls: 'secondary', key: 'teach_in.manual', fallback: 'Manual Entry' },
};

function _methodBadge(method) {
    const m = _METHOD[method] || _METHOD.manual;
    return `<span class="badge text-bg-${m.cls}"><i class="bi ${m.icon}"></i> ${escapeHtml(t(m.key, m.fallback))}</span>`;
}

function _renderGuide() {
    const el = document.getElementById('teach-guide');
    if (!el) return;
    const col = (method, uses) => `<div class="col-md-4"><div class="teach-choice h-100">
            <div class="mb-2">${_methodBadge(method)}</div>${_list(uses)}</div></div>`;
    el.innerHTML = `
        <h5 class="mt-4"><i class="bi bi-signpost-split"></i> ${escapeHtml(t('help.start_title', 'New to EnOcean? Start here'))}</h5>
        <p class="small text-muted">${escapeHtml(t('help.start_intro', 'Every EnOcean device has a fixed ID (its address, 8 hex digits) and a profile (EEP) that says what its telegrams mean. Adding a device tells the app both. Which way to use depends on the device:'))}</p>
        <div class="row g-3">
            ${col('auto', [
                t('help.use_auto_1', 'Sensors with a LRN button: temperature, humidity, motion, contacts'),
                t('help.use_auto_2', 'Modules that answer the app: NodOn, radiator valves, pilot wire'),
                t('help.use_auto_3', 'You press a button on the device, the app reads ID and profile'),
            ])}
            ${col('actuator', [
                t('help.use_act_1', 'Eltako actuators: FSR61, FUD61, FD62, FL62, FSB61, FJ62, Series 14'),
                t('help.use_act_2', 'They do not announce themselves: the app sends them a teach-in while they are in learn mode'),
                t('help.use_act_3', 'Afterwards they obey the app like a wall switch'),
            ])}
            ${col('manual', [
                t('help.use_man_1', 'Wall switches and rocker-type window handles (they send no teach-in)'),
                t('help.use_man_2', 'ID and profile already known: label, PCT14, the old app'),
                t('help.use_man_3', 'Teach-in did not detect the device'),
            ])}
        </div>

        <h6 class="mt-4"><i class="bi bi-search"></i> ${escapeHtml(t('help.find_title', 'Find your device'))}</h6>
        <input type="search" class="form-control" id="catalog-search" oninput="renderCatalogResults()"
               placeholder="${escapeHtml(t('help.find_placeholder', 'Manufacturer, model or profile, e.g. FSR14, NodOn, A5-20-01'))}">
        <div id="catalog-results" class="mt-2"></div>
        <div id="catalog-detail" class="mt-3"></div>
        <p class="small text-muted mt-2">${escapeHtml(t('help.find_missing', 'Not listed? Use the guide below. Every device listed here was set up successfully by a user or in tests; tell us on GitHub or in the forum how yours went.'))}</p>

        <h6 class="mt-4"><i class="bi bi-upc-scan"></i> ${escapeHtml(t('help.where_id', 'Where is the ID?'))}</h6>
        <div class="teach-figs">
            ${_fig('label', t('help.fig_label', 'On the label of the device or its packaging, often next to a QR code. The label often names the profile too.'))}
            ${_fig('telegrams', t('help.fig_telegrams', 'Press a button on the device: it appears on the Dashboard as an unknown sender with its ID. Works for anything that sends.'))}
            ${_fig('din14', t('help.fig_din14', 'Eltako Series 14 on a FAM14 has no printed radio ID: PCT14 shows the ID of every channel.'))}
        </div>

        <h6 class="mt-4"><i class="bi bi-diagram-3"></i> ${escapeHtml(t('help.what_eep', 'What is the profile (EEP)?'))}</h6>
        <div class="teach-figs">
            ${_fig('eep', t('help.fig_eep', 'Three parts: RORG (telegram type), FUNC and TYPE. Enter them as hex, e.g. A5 02 05.'))}
        </div>`;
}

function _renderAutoHelp() {
    const el = document.getElementById('teach-help-auto');
    if (!el) return;
    el.innerHTML = `
        <p class="small mb-2">${escapeHtml(t('help.auto_now', 'Now trigger the teach-in on the device, within 60 seconds:'))}</p>
        <div class="teach-figs">
            ${_fig('sensor', t('help.fig_sensor', 'Sensor: press its LRN button, often under the cover.'))}
            ${_fig('contact', t('help.fig_contact', 'Contact: press the LRN button.'))}
            ${_fig('module', t('help.fig_module', 'NodOn / D2 module: pairing button as its manual describes. The app answers and fills in the sender ID.'))}
            ${_fig('valve', t('help.fig_valve', 'Radiator valve: hold its button for 5 s.'))}
        </div>
        <div class="alert alert-light small mt-2 mb-0">
            <i class="bi bi-info-circle"></i> ${escapeHtml(t('help.auto_not_rocker', 'Wall switches and rocker-type window handles send no teach-in and are not detected here: press them once, take the ID from the Dashboard and use Manual Entry. Nothing detected after 60 s: move the device next to the USB stick and try again, or use Manual Entry.'))}
        </div>`;
}

function _renderActuatorHelp() {
    const el = document.getElementById('teach-help-actuator');
    if (!el) return;
    el.innerHTML = `
        <details class="teach-details mb-3" open>
            <summary><i class="bi bi-question-circle"></i> ${escapeHtml(t('help.act_how', 'How does this work?'))}</summary>
            <div class="teach-figs mt-2">
                ${_fig('flow', t('help.fig_flow', 'The actuator stores the app\'s sender ID (gateway base ID + offset) while it is in learn mode. Use a different offset for each actuator.'))}
                ${_fig('flush', t('help.fig_flush', 'Eltako 61 series: upper dial to LRN, LED flashes, send, LED off = learned. Turn the dial back afterwards.'))}
                ${_fig('knob62', t('help.fig_knob62', 'Eltako 62 series: learn mode on, then the number of telegrams picks what is learned (FL62 3x, FJ62 4x).'))}
                ${_fig('din14', t('help.fig_din14_act', 'Series 14: one device per channel, the address of each channel comes from PCT14.'))}
            </div>
            <p class="small mt-2 mb-0"><strong>${escapeHtml(t('teach_in.actuator_address', 'Actuator Address'))}:</strong>
            ${escapeHtml(t('help.act_address', 'the ID the actuator sends its state from. Switch it by hand once: its confirmation shows the ID on the Dashboard. Series 14: the channel\'s ID from PCT14. The teach-in itself works with any address; the address is what links its state to Home Assistant.'))}</p>
        </details>`;
}

function _renderManualHelp() {
    const el = document.getElementById('teach-help-manual');
    if (!el) return;
    el.innerHTML = `
        <details class="teach-details mb-3">
            <summary><i class="bi bi-question-circle"></i> ${escapeHtml(t('help.man_how', 'Where do I find these values?'))}</summary>
            <div class="teach-figs mt-2">
                ${_fig('label', t('help.fig_label', 'On the label of the device or its packaging, often next to a QR code. The label often names the profile too.'))}
                ${_fig('telegrams', t('help.fig_telegrams', 'Press a button on the device: it appears on the Dashboard as an unknown sender with its ID. Works for anything that sends.'))}
                ${_fig('eep', t('help.fig_eep', 'Three parts: RORG (telegram type), FUNC and TYPE. Enter them as hex, e.g. A5 02 05.'))}
            </div>
            ${_list([
                t('help.man_address', 'Address: the device ID, e.g. 0x05834FA4.'),
                t('help.man_eep', 'RORG, FUNC, TYPE: the profile from the label, the datasheet or the device list in Step 1. The RORG in the telegram list narrows it down.'),
                t('help.man_type', 'Actuator type: only for devices the app switches (light, switch, cover). Sensors and wall switches have none.'),
                t('help.man_sender', 'Sender ID: only for actuators. The gateway base ID plus a free offset, the one the actuator was taught. Actuator Teach-In shows it.'),
            ])}
        </details>`;
}

async function _loadCatalog() {
    if (_deviceCatalog) return _deviceCatalog;
    try {
        const resp = await fetch(getApiUrl('/api/help/devices'));
        _deviceCatalog = resp.ok ? ((await resp.json()).devices || []) : [];
    } catch (e) {
        _deviceCatalog = [];
    }
    return _deviceCatalog;
}

function renderCatalogResults() {
    const out = document.getElementById('catalog-results');
    if (!out) return;
    const q = (document.getElementById('catalog-search')?.value || '').trim().toLowerCase();
    const list = _deviceCatalog || [];
    const hits = q ? list.filter(d => [d.name, d.manufacturer, d.category, d.eep, ...(d.models || [])]
                                .join(' ').toLowerCase().includes(q)) : list;
    if (!hits.length) {
        out.innerHTML = `<div class="small text-muted">${escapeHtml(t('help.find_none', 'No match. Use the guide below.'))}</div>`;
        return;
    }
    out.innerHTML = '<div class="catalog-list">' + hits.map(d => `
        <button type="button" class="catalog-item${_catalogDevice && _catalogDevice.id === d.id ? ' active' : ''}" onclick="showCatalogDevice('${d.id}')">
            <img src="${getApiUrl(`/static/img/teach/${d.art}.svg?v=${window.APP_ASSET_V || ''}`)}" alt="" loading="lazy">
            <span><strong>${escapeHtml(d.name)}</strong><br>
            <small class="text-muted">${escapeHtml((d.models || []).join(', '))} · ${escapeHtml(d.eep)}</small></span>
        </button>`).join('') + '</div>';
}

function showCatalogDevice(id) {
    const d = (_deviceCatalog || []).find(x => x.id === id);
    const out = document.getElementById('catalog-detail');
    if (!d || !out) return;
    _catalogDevice = d;
    renderCatalogResults();
    const m = _METHOD[d.method] || _METHOD.manual;
    out.innerHTML = `<div class="card catalog-detail"><div class="card-body">
        <div class="d-flex justify-content-between flex-wrap gap-2 mb-2">
            <h5 class="mb-0">${escapeHtml(d.name)}</h5>${_methodBadge(d.method)}
        </div>
        <div class="small text-muted mb-3">${escapeHtml(d.category)} · ${escapeHtml((d.models || []).join(', '))} ·
            ${escapeHtml(t('help.profile', 'Profile'))} <code>${escapeHtml(d.eep)}</code></div>
        <div class="row g-3">
            <div class="col-md-5">${_fig(d.art, d.category)}</div>
            <div class="col-md-7">
                <h6>${escapeHtml(t('help.how_to', 'How to add it'))}</h6>
                <ol class="small">${d.teach.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ol>
                <h6>${escapeHtml(t('help.where_id', 'Where is the ID?'))}</h6>
                <p class="small">${escapeHtml(d.id_where)}</p>
                ${d.notes && d.notes.length ? `<h6>${escapeHtml(t('help.notes', 'Good to know'))}</h6>${_list(d.notes)}` : ''}
                <p class="small text-muted mt-2 mb-2">${escapeHtml(t('help.source', 'Verified by'))}: ${escapeHtml(d.source)}</p>
                <button class="btn btn-${m.cls}" onclick="useCatalogDevice()"><i class="bi ${m.icon}"></i>
                    ${escapeHtml(t('help.use_this', 'Start with this device'))}</button>
            </div>
        </div></div></div>`;
    out.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Open the right way of adding the picked device, with what is known filled in.
function useCatalogDevice() {
    const d = _catalogDevice;
    if (!d) return;
    if (d.method === 'auto') {
        startTeachIn();
    } else if (d.method === 'actuator') {
        showActuatorTeachIn();
        const sel = document.getElementById('actuator-type-teach-in');
        if (sel && d.actuator_type) { sel.value = d.actuator_type; toggleGfvsOptions(sel); }
        document.getElementById('actuator-teach-in-panel').scrollIntoView({ behavior: 'smooth' });
    } else {
        showManualEntry();
        prefillDeviceForm({ eep: d.eep, actuator_type: d.actuator_type, manufacturer: d.manufacturer,
                            description: (d.models || [])[0] || '' });
    }
}

// Fill the Step 2 form; only fields given are touched.
function prefillDeviceForm(v) {
    const form = document.getElementById('device-form');
    if (!form) return;
    const set = (name, value) => {
        const el = form.querySelector(`[name="${name}"]`);
        if (!el || value === undefined || value === null) return;
        if (el.type === 'checkbox') el.checked = !!value; else el.value = value;
    };
    if (v.eep) {
        const [rorg, func, type] = v.eep.split('-');
        set('rorg', rorg); set('func', func); set('type', type);
        onEepFieldInput();
    }
    set('address', v.address);
    set('sender_id', v.sender_id);
    if (v.manufacturer && !/^Any\b/.test(v.manufacturer)) set('manufacturer', v.manufacturer);
    set('description', v.description);
    if (v.actuator_type !== undefined) {
        set('actuator_type', v.actuator_type);
        const role = form.querySelector('[name="actuator_type"]');
        if (role) toggleSenderIdField(role);
    }
}

// The guide is the page's starting point: it shows while no way of adding
// a device is open.
function syncTeachGuide() {
    const guide = document.getElementById('teach-guide');
    if (!guide) return;
    const busy = ['actuator-teach-in-panel', 'teach-in-status']
        .some(id => document.getElementById(id)?.style.display === 'block');
    guide.style.display = busy ? 'none' : '';
}

async function initTeachHelp() {
    if (_teachHelpLang !== currentLang) {
        _teachHelpLang = currentLang;
        _renderGuide();
        _renderAutoHelp();
        _renderActuatorHelp();
        _renderManualHelp();
        await _loadCatalog();
        renderCatalogResults();
        if (_catalogDevice) showCatalogDevice(_catalogDevice.id);
    }
    syncTeachGuide();
}
