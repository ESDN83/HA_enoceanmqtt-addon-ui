// Extracted from templates/index.html. Classic script, no modules:
// the inline onclick handlers call these by bare name, so they must stay global.

// Mapping editor state. All of it is read only by the editor functions
// below: the profile being edited, whether each editor is in YAML text
// mode, and the row counters that keep generated input names unique.
let _currentEditorProfile = null;
let _inlineTextMode = false;
let _haTextMode = false;
let _inlineRowCounter = 0;
let _haRowCounter = 0;

async function loadProfiles() {
    try {
        const response = await fetch(getApiUrl('/api/eep/tree'));
        if (!response.ok) {
            const errorText = await response.text();
            console.error('EEP tree API error:', response.status, errorText);
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        const treeResponse = await response.json();
        const tree = treeResponse.tree || treeResponse;
        const orphanedOverrides = treeResponse.orphaned_overrides || [];

        const container = document.getElementById('eep-tree');
        container.innerHTML = '';

        // Collect custom profiles and overridden profiles for separate sections
        const customProfiles = [];
        const overriddenProfiles = [];

        for (const [rorg, rorgData] of Object.entries(tree)) {
            for (const [func, funcData] of Object.entries(rorgData.funcs)) {
                for (const [type, typeData] of Object.entries(funcData.types)) {
                    if (typeData.is_custom) {
                        customProfiles.push(typeData);
                    } else if (typeData.has_mapping_override) {
                        overriddenProfiles.push(typeData);
                    }
                }
            }
        }

        // Show custom profiles section first (always expanded)
        if (customProfiles.length > 0) {
            const customSection = document.createElement('div');
            customSection.className = 'mb-3 border-start border-warning border-3 ps-2';
            customSection.innerHTML = `<strong class="text-warning"><i class="bi bi-star-fill"></i> <span data-i18n="eep.custom_profiles">Custom Profiles</span> (${customProfiles.length})</strong>`;
            customProfiles.forEach(typeData => {
                const typeDiv = document.createElement('div');
                typeDiv.className = 'ms-3 eep-item custom';
                typeDiv.style.cursor = 'pointer';
                typeDiv.dataset.search = `${typeData.eep_id} ${typeData.description} custom`.toLowerCase();
                typeDiv.innerHTML = `<i class="bi bi-file-earmark-fill text-warning"></i> ${typeData.eep_id} - ${typeData.description}`;
                typeDiv.onclick = () => showProfileDetails(typeData.eep_id);
                customSection.appendChild(typeDiv);
            });
            container.appendChild(customSection);
        }

        // Show overridden profiles section (always expanded)
        if (overriddenProfiles.length > 0) {
            const overriddenSection = document.createElement('div');
            overriddenSection.className = 'mb-3 border-start border-success border-3 ps-2';
            overriddenSection.innerHTML = `<strong class="text-success"><i class="bi bi-pencil-square"></i> <span data-i18n="eep.customized_mappings">Customized Mappings</span> (${overriddenProfiles.length})</strong>`;
            overriddenProfiles.forEach(typeData => {
                const typeDiv = document.createElement('div');
                typeDiv.className = 'ms-3 eep-item overridden';
                typeDiv.style.cursor = 'pointer';
                typeDiv.dataset.search = `${typeData.eep_id} ${typeData.description} customized mapping`.toLowerCase();
                typeDiv.innerHTML = `<i class="bi bi-file-earmark-check text-success"></i> ${typeData.eep_id} - ${typeData.description}`;
                typeDiv.onclick = () => showProfileDetails(typeData.eep_id);
                overriddenSection.appendChild(typeDiv);
            });
            container.appendChild(overriddenSection);
        }

        // Show orphaned overrides warning (mappings for profiles that no longer exist)
        if (orphanedOverrides.length > 0) {
            const orphanedSection = document.createElement('div');
            orphanedSection.className = 'mb-3 border-start border-danger border-3 ps-2';
            orphanedSection.innerHTML = `<strong class="text-danger"><i class="bi bi-exclamation-triangle-fill"></i> <span data-i18n="eep.orphaned_mappings">Orphaned Mappings</span> (${orphanedOverrides.length})</strong>
                <div class="text-danger small ms-3" data-i18n="eep.orphaned_hint">These mapping overrides reference EEP profiles that no longer exist in the current EEP.xml. Consider removing them.</div>`;
            orphanedOverrides.forEach(item => {
                const typeDiv = document.createElement('div');
                typeDiv.className = 'ms-3 eep-item orphaned';
                typeDiv.dataset.search = `${item.eep_id} orphaned`.toLowerCase();
                typeDiv.innerHTML = `<i class="bi bi-file-earmark-x text-danger"></i> ${item.eep_id} <span class="text-danger small">(${t('eep.orphaned_profile_missing', 'profile not found')})</span>`;
                orphanedSection.appendChild(typeDiv);
            });
            container.appendChild(orphanedSection);
        }

        // Standard profiles (collapsed by default)
        for (const [rorg, rorgData] of Object.entries(tree)) {
            const rorgId = `rorg-${rorg}`;
            const rorgDiv = document.createElement('div');
            rorgDiv.className = 'mb-1';

            const rorgHeader = document.createElement('div');
            rorgHeader.style.cursor = 'pointer';
            rorgHeader.innerHTML = `<strong><i class="bi bi-folder" id="icon-${rorgId}"></i> ${rorg} - ${rorgData.description}</strong>`;
            rorgHeader.onclick = () => toggleTreeNode(rorgId);
            rorgDiv.appendChild(rorgHeader);

            const rorgContent = document.createElement('div');
            rorgContent.id = rorgId;
            rorgContent.style.display = 'none'; // collapsed by default

            for (const [func, funcData] of Object.entries(rorgData.funcs)) {
                const funcId = `func-${rorg}-${func}`;
                const funcDiv = document.createElement('div');
                funcDiv.className = 'ms-3';

                const funcHeader = document.createElement('div');
                funcHeader.style.cursor = 'pointer';
                funcHeader.innerHTML = `<i class="bi bi-folder2" id="icon-${funcId}"></i> FUNC ${func}`;
                funcHeader.onclick = (e) => { e.stopPropagation(); toggleTreeNode(funcId); };
                funcDiv.appendChild(funcHeader);

                const funcContent = document.createElement('div');
                funcContent.id = funcId;
                funcContent.style.display = 'none'; // collapsed by default

                for (const [type, typeData] of Object.entries(funcData.types)) {
                    const typeDiv = document.createElement('div');
                    const itemClass = typeData.is_custom ? 'custom' : typeData.has_mapping_override ? 'overridden' : '';
                    typeDiv.className = `ms-4 eep-item ${itemClass}`;
                    typeDiv.style.cursor = 'pointer';
                    // Include RORG + FUNC + TYPE descriptions for broader search matches
                    typeDiv.dataset.search = `${rorg} ${rorgData.description} ${func} ${funcData.description || ''} ${typeData.eep_id} ${typeData.description}`.toLowerCase();
                    const icon = typeData.is_custom ? 'bi-file-earmark-fill text-warning' : typeData.has_mapping_override ? 'bi-file-earmark-check text-success' : 'bi-file-earmark';
                    typeDiv.innerHTML = `<i class="bi ${icon}"></i> ${typeData.eep_id} - ${typeData.description}`;
                    typeDiv.onclick = (e) => { e.stopPropagation(); showProfileDetails(typeData.eep_id); };
                    funcContent.appendChild(typeDiv);
                }

                funcDiv.appendChild(funcContent);
                rorgContent.appendChild(funcDiv);
            }

            rorgDiv.appendChild(rorgContent);
            container.appendChild(rorgDiv);
        }

        // Re-apply translations for dynamically created elements
        applyTranslations();

        // Re-apply search filter if query is active
        const searchQuery = document.getElementById('profile-search').value;
        if (searchQuery) filterProfiles();
    } catch (error) {
        showToast(t('profiles.load_failed', 'Failed to load profiles'), 'danger');
    }
}
function toggleTreeNode(nodeId) {
    const node = document.getElementById(nodeId);
    const icon = document.getElementById('icon-' + nodeId);
    if (node) {
        const isHidden = node.style.display === 'none';
        node.style.display = isHidden ? '' : 'none';
        if (icon) {
            icon.className = isHidden ? 'bi bi-folder2-open' : 'bi bi-folder';
        }
    }
}
async function showProfileDetails(eepId) {
    try {
        const response = await fetch(getApiUrl(`/api/eep/${eepId}`));
        const profile = await response.json();

        const container = document.getElementById('profile-details');
        let actionsHtml = '';
        if (profile.is_custom) {
            actionsHtml = `
                <div class="mt-2">
                    <button class="btn btn-sm btn-outline-primary me-2" onclick="editCustomProfile('${profile.eep_id}')">
                        <i class="bi bi-pencil"></i> ${t('profile.edit', 'Edit Profile')}
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteCustomProfile('${profile.eep_id}')">
                        <i class="bi bi-trash"></i> ${t('profile.delete', 'Delete')}
                    </button>
                </div>`;
        } else {
            actionsHtml = `
                <div class="mt-2">
                    <button class="btn btn-sm btn-outline-secondary" onclick="forkStandardProfile('${profile.eep_id}')" title="${t('profile.fork_title', 'Create a custom copy to edit fields and mapping')}">
                        <i class="bi bi-copy"></i> ${t('profile.fork', 'Fork as Custom Profile')}
                    </button>
                </div>`;
        }

        // Determine effective mapping: override > ha_mapping > none
        const effectiveMapping = profile.mapping_override || profile.ha_mapping || {};
        const hasOverride = profile.has_mapping_override === true;
        const hasMapping = Object.keys(effectiveMapping).length > 0;

        // Build HA mapping display
        let haMappingHtml = '<hr>';
        haMappingHtml += `<div class="d-flex justify-content-between align-items-center mb-2">
            <h6 class="mb-0"><i class="bi bi-house-gear"></i> ${t('mapping_editor.ha_mapping', 'HA Entity Mapping')}
                ${hasOverride ? `<span class="badge bg-info ms-2">${t('mapping_editor.customized_badge', 'Customized')}</span>` : ''}
            </h6>
            <div>
                ${hasOverride && !profile.is_custom ? `<button class="btn btn-sm btn-outline-warning me-1" onclick="resetMappingOverride('${profile.eep_id}')" title="${t('mapping_editor.reset', 'Reset')}">
                    <i class="bi bi-arrow-counterclockwise"></i> ${t('mapping_editor.reset', 'Reset')}
                </button>` : ''}
                <button class="btn btn-sm btn-outline-primary" onclick="openMappingEditor('${profile.eep_id}')">
                    <i class="bi bi-pencil"></i> ${t('mapping_editor.customize', 'Customize')}
                </button>
            </div>
        </div>`;

        if (hasMapping) {
            haMappingHtml += Object.entries(effectiveMapping).map(([shortcut, config]) => {
                const mainFields = [];
                if (config.name) mainFields.push(`${t('label.name', 'Name')}: ${config.name}`);
                if (config.device_class) mainFields.push(`${t('label.class', 'Class')}: ${config.device_class}`);
                if (config.icon) mainFields.push(`${t('label.icon', 'Icon')}: ${config.icon}`);
                if (config.unit_of_measurement) mainFields.push(`${t('label.unit', 'Unit')}: ${config.unit_of_measurement}`);

                const advancedFields = [];
                if (config.state_class) advancedFields.push(`${t('label.state', 'State')}: ${config.state_class}`);
                if (config.entity_category) advancedFields.push(`${t('label.category', 'Category')}: ${config.entity_category}`);
                if (config.expire_after) advancedFields.push(`${t('label.expire', 'Expire')}: ${config.expire_after}s`);
                if (config.force_update) advancedFields.push(t('label.force_update', 'Force Update'));
                if (config.suggested_display_precision != null) advancedFields.push(`${t('label.precision', 'Precision')}: ${config.suggested_display_precision}`);

                return `<div class="border rounded p-2 mb-2 bg-body-secondary">
                    <div class="d-flex justify-content-between">
                        <strong>${shortcut}</strong>
                        <span class="badge bg-primary">${config.component || 'sensor'}</span>
                    </div>
                    <small>${mainFields.join(' | ')}</small>
                    ${advancedFields.length ? `<br><small class="text-info">${advancedFields.join(' | ')}</small>` : ''}
                </div>`;
            }).join('');
        } else {
            haMappingHtml += `<p class="text-muted small"><i class="bi bi-info-circle"></i> ${t('mapping_editor.no_mapping', 'No HA mapping defined. Click "Customize" to create one.')}</p>`;
        }

        // Inline mapping editor (hidden by default)
        haMappingHtml += `
        <div id="inline-mapping-editor" style="display:none;" class="mt-3 border rounded p-3 bg-body-tertiary">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <h6 class="mb-0"><i class="bi bi-sliders"></i> ${t('mapping_editor.title', 'Mapping Editor')}</h6>
                <button class="btn btn-sm btn-outline-secondary" id="inline-mode-toggle" onclick="toggleInlineMappingMode()">
                    <i class="bi bi-code-slash"></i> ${t('mapping_editor.text_mode', 'Text Mode')}
                </button>
            </div>
            <div id="inline-mapping-visual">
                <p class="text-muted small mb-2">${t('mapping_editor.define_hint', 'Define how EEP fields map to Home Assistant entities. Shortcut must match a telegram field name.')}</p>
                <div id="inline-mapping-rows"></div>
                <div id="inline-mapping-empty" class="text-muted small mb-2" style="display:none;">${t('mapping_editor.no_rows', 'No mappings defined. Click "Add Row" to start.')}</div>
                <div class="d-flex gap-2 mt-2">
                    <button class="btn btn-sm btn-outline-secondary" onclick="addInlineMappingRow()">
                        <i class="bi bi-plus"></i> ${t('mapping_editor.add_row', 'Add Row')}
                    </button>
                    <button class="btn btn-sm btn-outline-secondary" onclick="prefillMappingFromFields('${profile.eep_id}')">
                        <i class="bi bi-magic"></i> ${t('mapping_editor.autofill', 'Auto-fill from Fields')}
                    </button>
                </div>
            </div>
            <div id="inline-mapping-text" style="display:none;">
                <p class="text-muted small mb-2">${t('mapping_editor.text_hint', 'Edit mapping as YAML. Any valid MQTT discovery field can be used (state_class, expire_after, etc.).')}</p>
                <textarea id="inline-mapping-yaml" class="form-control form-control-sm font-monospace" rows="14" spellcheck="false"></textarea>
            </div>
            <div class="d-flex gap-2 mt-2">
                <div class="ms-auto">
                    <button class="btn btn-sm btn-outline-secondary me-1" onclick="closeMappingEditor()">${t('mapping_editor.cancel', 'Cancel')}</button>
                    <button class="btn btn-sm btn-primary" onclick="saveMappingOverride('${profile.eep_id}')">
                        <i class="bi bi-check-lg"></i> ${t('mapping_editor.save', 'Save Mapping')}
                    </button>
                </div>
            </div>
        </div>`;

        container.innerHTML = `
            <h5>${profile.eep_id}</h5>
            <p>${profile.description}</p>
            ${profile.is_custom ? `<span class="badge bg-warning">${t('profile.custom', 'Custom Profile')}</span>` : `<span class="badge bg-secondary">${t('profile.standard', 'Standard Profile')}</span>`}
            ${actionsHtml}
            <hr>
            <h6>${t('profile.telegram_fields', 'Telegram Fields')}</h6>
            ${profile.fields.length ? profile.fields.map(f => `
                <div class="border rounded p-2 mb-2">
                    <strong>${f.shortcut || '?'}</strong> - ${f.description || t('profile.no_description', 'No description')}<br>
                    <small>${t('profile.field_offset', 'Offset')}: ${f.offset ?? '-'}, ${t('profile.field_size', 'Size')}: ${f.size ?? '-'} bits, ${t('profile.field_type', 'Type')}: ${f.type || '-'}</small>
                </div>
            `).join('') : `<p class="text-muted">${t('profile.no_fields', 'No field definitions')}</p>`}
            ${haMappingHtml}
        `;
    } catch (error) {
        showToast(t('profiles.details_failed', 'Failed to load profile details'), 'danger');
    }
}
async function openMappingEditor(eepId) {
    try {
        const resp = await fetch(getApiUrl(`/api/eep/${eepId}/mapping`));
        const data = await resp.json();
        _currentEditorProfile = data;

        // Reset text mode state when opening editor
        _resetInlineTextMode();

        const editor = document.getElementById('inline-mapping-editor');
        const container = document.getElementById('inline-mapping-rows');
        const emptyMsg = document.getElementById('inline-mapping-empty');
        container.innerHTML = '';

        const mapping = data.mapping || {};
        if (Object.keys(mapping).length > 0) {
            emptyMsg.style.display = 'none';
            for (const [shortcut, config] of Object.entries(mapping)) {
                addInlineMappingRow(shortcut, config.component || 'sensor', config.name || '', config.device_class || '', config.icon || '', config.unit_of_measurement || '', {
                    state_class: config.state_class,
                    entity_category: config.entity_category,
                    expire_after: config.expire_after,
                    force_update: config.force_update,
                    suggested_display_precision: config.suggested_display_precision,
                    value_template: config.value_template
                });
            }
        } else {
            emptyMsg.style.display = '';
        }

        editor.style.display = '';
    } catch (e) {
        showToast(t('toast.failed_load_mapping', 'Failed to load mapping'), 'danger');
    }
}
function closeMappingEditor() {
    document.getElementById('inline-mapping-editor').style.display = 'none';
    _resetInlineTextMode();
}
function _isJsYamlAvailable() {
    return typeof jsyaml !== 'undefined' && jsyaml.dump && jsyaml.load;
}
function _resetInlineTextMode() {
    _inlineTextMode = false;
    const visual = document.getElementById('inline-mapping-visual');
    const text = document.getElementById('inline-mapping-text');
    const btn = document.getElementById('inline-mode-toggle');
    if (visual) visual.style.display = '';
    if (text) text.style.display = 'none';
    if (btn) btn.innerHTML = `<i class="bi bi-code-slash"></i> ${t('mapping_editor.text_mode', 'Text Mode')}`;
}
function _resetHaTextMode() {
    _haTextMode = false;
    const visual = document.getElementById('ha-mapping-visual');
    const text = document.getElementById('ha-mapping-text');
    const btn = document.getElementById('ha-mode-toggle');
    const addBtn = document.getElementById('ha-add-row-btn');
    if (visual) visual.style.display = '';
    if (text) text.style.display = 'none';
    if (btn) btn.innerHTML = `<i class="bi bi-code-slash"></i> ${t('mapping_editor.text_mode', 'Text Mode')}`;
    if (addBtn) addBtn.style.display = '';
}
function toggleInlineMappingMode() {
    if (!_isJsYamlAvailable()) {
        showToast(t('toast.yaml_not_loaded', 'YAML library not loaded. Please reload the page.'), 'warning');
        return;
    }
    const visual = document.getElementById('inline-mapping-visual');
    const text = document.getElementById('inline-mapping-text');
    const btn = document.getElementById('inline-mode-toggle');

    if (!_inlineTextMode) {
        // Visual → Text: collect mapping and serialize to YAML
        const mapping = collectInlineMapping();
        if (mapping === undefined) {
            showToast(t('toast.fix_validation', 'Fix validation errors before switching to text mode'), 'warning');
            return;
        }
        try {
            const yamlStr = (mapping && Object.keys(mapping).length > 0) ? jsyaml.dump(mapping, { lineWidth: -1 }) : '';
            document.getElementById('inline-mapping-yaml').value = yamlStr;
        } catch (e) {
            showToast(t('toast.yaml_serialize_failed', 'Failed to serialize to YAML') + ': ' + e.message, 'danger');
            return;
        }
        visual.style.display = 'none';
        text.style.display = '';
        btn.innerHTML = `<i class="bi bi-ui-checks-grid"></i> ${t('mapping_editor.visual_mode', 'Visual Mode')}`;
        _inlineTextMode = true;
    } else {
        // Text → Visual: parse YAML and rebuild rows
        const yamlStr = document.getElementById('inline-mapping-yaml').value.trim();
        if (yamlStr) {
            try {
                const mapping = jsyaml.load(yamlStr);
                if (mapping && typeof mapping === 'object') {
                    const container = document.getElementById('inline-mapping-rows');
                    container.innerHTML = '';
                    for (const [shortcut, config] of Object.entries(mapping)) {
                        addInlineMappingRow(shortcut, config.component || 'sensor', config.name || '', config.device_class || '', config.icon || '', config.unit_of_measurement || '', {
                            state_class: config.state_class,
                            entity_category: config.entity_category,
                            expire_after: config.expire_after,
                            force_update: config.force_update,
                            suggested_display_precision: config.suggested_display_precision,
                            value_template: config.value_template
                        });
                    }
                    document.getElementById('inline-mapping-empty').style.display = 'none';
                }
            } catch (e) {
                showToast(t('toast.yaml_parse_error', 'YAML parse error') + ': ' + e.message, 'danger');
                return; // stay in text mode
            }
        } else {
            document.getElementById('inline-mapping-rows').innerHTML = '';
            document.getElementById('inline-mapping-empty').style.display = '';
        }
        visual.style.display = '';
        text.style.display = 'none';
        btn.innerHTML = `<i class="bi bi-code-slash"></i> ${t('mapping_editor.text_mode', 'Text Mode')}`;
        _inlineTextMode = false;
    }
}
function toggleHaMappingMode() {
    if (!_isJsYamlAvailable()) {
        showToast(t('toast.yaml_not_loaded', 'YAML library not loaded. Please reload the page.'), 'warning');
        return;
    }
    const visual = document.getElementById('ha-mapping-visual');
    const text = document.getElementById('ha-mapping-text');
    const btn = document.getElementById('ha-mode-toggle');
    const addBtn = document.getElementById('ha-add-row-btn');

    if (!_haTextMode) {
        // Visual → Text
        const mapping = collectHaMapping();
        if (mapping === undefined) {
            showToast(t('toast.fix_validation', 'Fix validation errors before switching to text mode'), 'warning');
            return;
        }
        try {
            const yamlStr = (mapping && Object.keys(mapping).length > 0) ? jsyaml.dump(mapping, { lineWidth: -1 }) : '';
            document.getElementById('ha-mapping-yaml').value = yamlStr;
        } catch (e) {
            showToast(t('toast.yaml_serialize_failed', 'Failed to serialize to YAML') + ': ' + e.message, 'danger');
            return;
        }
        visual.style.display = 'none';
        text.style.display = '';
        btn.innerHTML = `<i class="bi bi-ui-checks-grid"></i> ${t('mapping_editor.visual_mode', 'Visual Mode')}`;
        addBtn.style.display = 'none';
        _haTextMode = true;
    } else {
        // Text → Visual
        const yamlStr = document.getElementById('ha-mapping-yaml').value.trim();
        if (yamlStr) {
            try {
                const mapping = jsyaml.load(yamlStr);
                if (mapping && typeof mapping === 'object') {
                    const container = document.getElementById('ha-mapping-rows');
                    container.innerHTML = '';
                    for (const [shortcut, config] of Object.entries(mapping)) {
                        addHaMappingRow(shortcut, config.component || 'binary_sensor', config.name || '', config.device_class || '', config.icon || '', config.unit_of_measurement || '', {
                            state_class: config.state_class,
                            entity_category: config.entity_category,
                            expire_after: config.expire_after,
                            force_update: config.force_update,
                            suggested_display_precision: config.suggested_display_precision,
                            value_template: config.value_template
                        });
                    }
                    document.getElementById('ha-mapping-empty').style.display = 'none';
                }
            } catch (e) {
                showToast(t('toast.yaml_parse_error', 'YAML parse error') + ': ' + e.message, 'danger');
                return; // stay in text mode
            }
        } else {
            document.getElementById('ha-mapping-rows').innerHTML = '';
            document.getElementById('ha-mapping-empty').style.display = '';
        }
        visual.style.display = '';
        text.style.display = 'none';
        btn.innerHTML = `<i class="bi bi-code-slash"></i> ${t('mapping_editor.text_mode', 'Text Mode')}`;
        addBtn.style.display = '';
        _haTextMode = false;
    }
}
function getInlineMappingData() {
    /** Get mapping data from either visual or text mode (inline editor) */
    if (_inlineTextMode) {
        if (!_isJsYamlAvailable()) {
            showToast(t('toast.yaml_not_loaded', 'YAML library not loaded. Please reload the page.'), 'warning');
            return undefined;
        }
        const yamlStr = document.getElementById('inline-mapping-yaml').value.trim();
        if (!yamlStr) return {};
        try {
            const mapping = jsyaml.load(yamlStr);
            return (mapping && typeof mapping === 'object') ? mapping : {};
        } catch (e) {
            showToast(t('toast.yaml_parse_error', 'YAML parse error') + ': ' + e.message, 'danger');
            return undefined; // signal error
        }
    }
    return collectInlineMapping();
}
function getHaMappingData() {
    /** Get mapping data from either visual or text mode (HA mapping editor) */
    if (_haTextMode) {
        if (!_isJsYamlAvailable()) {
            showToast(t('toast.yaml_not_loaded', 'YAML library not loaded. Please reload the page.'), 'warning');
            return undefined;
        }
        const yamlStr = document.getElementById('ha-mapping-yaml').value.trim();
        if (!yamlStr) return null;
        try {
            const mapping = jsyaml.load(yamlStr);
            return (mapping && typeof mapping === 'object' && Object.keys(mapping).length > 0) ? mapping : null;
        } catch (e) {
            showToast(t('toast.yaml_parse_error', 'YAML parse error') + ': ' + e.message, 'danger');
            return undefined; // signal error
        }
    }
    return collectHaMapping();
}
function addInlineMappingRow(shortcut = '', component = 'sensor', name = '', deviceClass = '', icon = '', unit = '', opts = {}) {
    const container = document.getElementById('inline-mapping-rows');
    const emptyMsg = document.getElementById('inline-mapping-empty');
    if (emptyMsg) emptyMsg.style.display = 'none';

    const rowId = _inlineRowCounter++;
    const stateClass = opts.state_class || '';
    const entityCategory = opts.entity_category || '';
    const expireAfter = opts.expire_after != null ? opts.expire_after : '';
    const forceUpdate = opts.force_update || false;
    const precision = opts.suggested_display_precision != null ? opts.suggested_display_precision : '';
    const valueTemplate = opts.value_template || '';

    const row = document.createElement('div');
    row.className = 'inline-mapping-row border rounded p-2 mb-2 bg-body-secondary';
    row.innerHTML = `
        <div class="row g-2 align-items-end">
            <div class="col-6 col-xl-2">
                <label class="form-label small">${t('mapping_editor.field_shortcut', 'Shortcut')}</label>
                <input type="text" class="form-control form-control-sm" placeholder="TMP" value="${shortcut}" data-field="shortcut">
            </div>
            <div class="col-6 col-xl-2">
                <label class="form-label small">${t('mapping_editor.field_component', 'Component')}</label>
                <select class="form-select form-select-sm" data-field="component" onchange="onInlineComponentChange(this)">
                    <option value="binary_sensor" ${component === 'binary_sensor' ? 'selected' : ''}>binary_sensor</option>
                    <option value="sensor" ${component === 'sensor' ? 'selected' : ''}>sensor</option>
                    <option value="switch" ${component === 'switch' ? 'selected' : ''}>switch</option>
                    <option value="light" ${component === 'light' ? 'selected' : ''}>light</option>
                    <option value="cover" ${component === 'cover' ? 'selected' : ''}>cover</option>
                    <option value="climate" ${component === 'climate' ? 'selected' : ''}>climate</option>
                    <option value="fan" ${component === 'fan' ? 'selected' : ''}>fan</option>
                </select>
            </div>
            <div class="col-6 col-xl-2">
                <label class="form-label small">${t('mapping_editor.field_name', 'Name')}</label>
                <input type="text" class="form-control form-control-sm" placeholder="Temperature" value="${name}" data-field="name">
            </div>
            <div class="col-6 col-xl-2">
                <label class="form-label small">${t('mapping_editor.field_device_class', 'Device Class')}</label>
                <select class="form-select form-select-sm" data-field="device_class">
                    ${getDeviceClassOptions(component, deviceClass)}
                </select>
            </div>
            <div class="col-6 col-xl-2">
                <label class="form-label small">${t('mapping_editor.field_icon', 'Icon')}</label>
                <input type="text" class="form-control form-control-sm" placeholder="mdi:thermometer" value="${icon}" data-field="icon">
            </div>
            <div class="col-6 col-xl-1">
                <label class="form-label small">${t('mapping_editor.field_unit', 'Unit')}</label>
                <input type="text" class="form-control form-control-sm" placeholder="" value="${unit}" data-field="unit_of_measurement">
            </div>
            <div class="col-6 col-xl-1">
                <button type="button" class="btn btn-sm btn-outline-danger" onclick="removeInlineMappingRow(this)" title="${t('mapping_editor.field_remove', 'Remove')}">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        </div>
        <div class="mt-1">
            <a class="small text-muted text-decoration-none" data-bs-toggle="collapse" href="#inline-adv-${rowId}" role="button" aria-expanded="false">
                <i class="bi bi-chevron-right"></i> ${t('mapping_editor.advanced', 'Advanced')}
            </a>
            <div class="collapse" id="inline-adv-${rowId}">
                <div class="row g-2 mt-1">
                    <div class="col-6 col-xl-2">
                        <label class="form-label small">${t('mapping_editor.field_state_class', 'State Class')}</label>
                        <select class="form-select form-select-sm" data-field="state_class">
                            <option value="" ${!stateClass ? 'selected' : ''}>${t('mapping_editor.none', '(none)')}</option>
                            <option value="measurement" ${stateClass === 'measurement' ? 'selected' : ''}>measurement</option>
                            <option value="total" ${stateClass === 'total' ? 'selected' : ''}>total</option>
                            <option value="total_increasing" ${stateClass === 'total_increasing' ? 'selected' : ''}>total_increasing</option>
                        </select>
                    </div>
                    <div class="col-6 col-xl-2">
                        <label class="form-label small">${t('mapping_editor.field_entity_category', 'Entity Category')}</label>
                        <select class="form-select form-select-sm" data-field="entity_category">
                            <option value="" ${!entityCategory ? 'selected' : ''}>${t('mapping_editor.none', '(none)')}</option>
                            <option value="diagnostic" ${entityCategory === 'diagnostic' ? 'selected' : ''}>diagnostic</option>
                            <option value="config" ${entityCategory === 'config' ? 'selected' : ''}>config</option>
                        </select>
                    </div>
                    <div class="col-6 col-xl-2">
                        <label class="form-label small">${t('mapping_editor.field_expire_after', 'Expire After (s)')}</label>
                        <input type="number" class="form-control form-control-sm" placeholder="" value="${expireAfter}" data-field="expire_after" min="0">
                    </div>
                    <div class="col-6 col-xl-2">
                        <label class="form-label small">${t('mapping_editor.field_precision', 'Precision')}</label>
                        <input type="number" class="form-control form-control-sm" placeholder="" value="${precision}" data-field="suggested_display_precision" min="0" max="10">
                    </div>
                    <div class="col-6 col-xl-2 d-flex align-items-end">
                        <div class="form-check mb-2">
                            <input class="form-check-input" type="checkbox" data-field="force_update" ${forceUpdate ? 'checked' : ''}>
                            <label class="form-check-label small">${t('mapping_editor.field_force_update', 'Force Update')}</label>
                        </div>
                    </div>
                </div>
                <div class="row g-2 mt-1">
                    <div class="col-12 col-xl-6">
                        <label class="form-label small">${t('mapping_editor.field_value_template', 'Value Template')}</label>
                        <input type="text" class="form-control form-control-sm font-monospace" placeholder="auto-generated" value="${valueTemplate.replace(/"/g, '&quot;')}" data-field="value_template">
                    </div>
                </div>
            </div>
        </div>
    `;

    // Rotate chevron on collapse toggle
    const collapseEl = row.querySelector('.collapse');
    collapseEl.addEventListener('show.bs.collapse', () => {
        row.querySelector('.bi-chevron-right')?.classList.replace('bi-chevron-right', 'bi-chevron-down');
    });
    collapseEl.addEventListener('hide.bs.collapse', () => {
        row.querySelector('.bi-chevron-down')?.classList.replace('bi-chevron-down', 'bi-chevron-right');
    });

    container.appendChild(row);
}
function removeInlineMappingRow(btn) {
    btn.closest('.inline-mapping-row').remove();
    const container = document.getElementById('inline-mapping-rows');
    if (container.children.length === 0) {
        document.getElementById('inline-mapping-empty').style.display = '';
    }
}
function onInlineComponentChange(select) {
    const row = select.closest('.inline-mapping-row');
    const dcSelect = row.querySelector('[data-field="device_class"]');
    dcSelect.innerHTML = getDeviceClassOptions(select.value, '');
}
function collectInlineMapping() {
    const rows = document.querySelectorAll('.inline-mapping-row');
    if (rows.length === 0) return {};

    const mapping = {};
    let valid = true;
    rows.forEach(row => {
        const shortcut = (row.querySelector('[data-field="shortcut"]').value || '').trim();
        if (!shortcut) { valid = false; return; }
        const entry = { component: row.querySelector('[data-field="component"]').value };
        const name = row.querySelector('[data-field="name"]').value.trim();
        if (name) entry.name = name;
        const dc = row.querySelector('[data-field="device_class"]').value;
        if (dc) entry.device_class = dc;
        const icon = row.querySelector('[data-field="icon"]').value.trim();
        if (icon) entry.icon = icon;
        const unit = row.querySelector('[data-field="unit_of_measurement"]').value.trim();
        if (unit) entry.unit_of_measurement = unit;

        // Advanced fields
        const stateClass = row.querySelector('[data-field="state_class"]')?.value || '';
        if (stateClass) entry.state_class = stateClass;
        const entityCat = row.querySelector('[data-field="entity_category"]')?.value || '';
        if (entityCat) entry.entity_category = entityCat;
        const expireStr = row.querySelector('[data-field="expire_after"]')?.value || '';
        if (expireStr !== '') entry.expire_after = parseInt(expireStr);
        const precisionStr = row.querySelector('[data-field="suggested_display_precision"]')?.value || '';
        if (precisionStr !== '') entry.suggested_display_precision = parseInt(precisionStr);
        const forceUpdate = row.querySelector('[data-field="force_update"]')?.checked || false;
        if (forceUpdate) entry.force_update = true;
        const valTpl = row.querySelector('[data-field="value_template"]')?.value?.trim() || '';
        if (valTpl) entry.value_template = valTpl;

        mapping[shortcut] = entry;
    });
    if (!valid) return undefined;
    return mapping;
}
async function prefillMappingFromFields(eepId) {
    try {
        const resp = await fetch(getApiUrl(`/api/eep/${eepId}`));
        const profile = await resp.json();

        const container = document.getElementById('inline-mapping-rows');
        container.innerHTML = '';
        document.getElementById('inline-mapping-empty').style.display = 'none';

        if (profile.fields && profile.fields.length > 0) {
            for (const field of profile.fields) {
                const shortcut = field.shortcut || '';
                if (!shortcut) continue;
                // Guess component from field description/type
                let component = 'sensor';
                const desc = (field.description || '').toLowerCase();
                if (desc.includes('switch') || desc.includes('button') || desc.includes('rocker')) component = 'binary_sensor';
                if (desc.includes('alarm') || desc.includes('contact') || desc.includes('occupancy')) component = 'binary_sensor';
                // Guess device class
                let dc = '';
                if (desc.includes('temperature') || desc.includes('temp')) dc = 'temperature';
                else if (desc.includes('humidity')) dc = 'humidity';
                else if (desc.includes('illumina') || desc.includes('lux')) dc = 'illuminance';
                else if (desc.includes('voltage')) dc = 'voltage';
                else if (desc.includes('current') && !desc.includes('currently')) dc = 'current';
                else if (desc.includes('power') || desc.includes('watt')) dc = 'power';
                else if (desc.includes('energy')) dc = 'energy';
                else if (desc.includes('pressure')) dc = 'pressure';
                else if (desc.includes('battery')) dc = 'battery';
                else if (desc.includes('motion')) { dc = 'motion'; component = 'binary_sensor'; }
                else if (desc.includes('window')) { dc = 'window'; component = 'binary_sensor'; }
                else if (desc.includes('door')) { dc = 'door'; component = 'binary_sensor'; }
                // Guess unit
                let unit = '';
                if (dc === 'temperature') unit = '°C';
                else if (dc === 'humidity') unit = '%';
                else if (dc === 'illuminance') unit = 'lx';
                else if (dc === 'voltage') unit = 'V';
                else if (dc === 'current') unit = 'A';
                else if (dc === 'power') unit = 'W';
                else if (dc === 'energy') unit = 'kWh';
                else if (dc === 'pressure') unit = 'hPa';
                else if (dc === 'battery') unit = '%';

                addInlineMappingRow(shortcut, component, field.description || '', dc, '', unit);
            }
            showToast(t('mapping_editor.prefilled', 'Fields pre-filled from EEP profile'), 'success');
        } else {
            document.getElementById('inline-mapping-empty').style.display = '';
            showToast(t('mapping_editor.no_fields', 'No fields found in profile'), 'warning');
        }
    } catch (e) {
        showToast(t('mapping_editor.load_fields_failed', 'Failed to load profile fields'), 'danger');
    }
}
async function saveMappingOverride(eepId) {
    const mapping = getInlineMappingData();
    if (mapping === undefined) {
        showToast(t('mapping_editor.need_shortcut', 'All rows must have a shortcut name (or fix YAML errors)'), 'warning');
        return;
    }

    try {
        const resp = await fetch(getApiUrl(`/api/eep/${eepId}/mapping`), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(mapping)
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => null);
            throw new Error(err?.detail || t('mapping_editor.save_failed', 'Save failed'));
        }
        showToast(t('mapping_editor.saved', 'Mapping saved'), 'success');
        closeMappingEditor();
        showProfileDetails(eepId);
        // Refresh the profile tree to update "Customized" indicators
        loadProfiles();
    } catch (e) {
        showToast(e.message, 'danger');
    }
}
async function resetMappingOverride(eepId) {
    if (!confirm(t('mapping_editor.reset_confirm', 'Reset mapping to EEP.xml default? Your customization will be removed.'))) return;
    try {
        const resp = await fetch(getApiUrl(`/api/eep/${eepId}/mapping`), { method: 'DELETE' });
        if (!resp.ok) {
            const err = await resp.json().catch(() => null);
            throw new Error(err?.detail || t('mapping_editor.reset_failed', 'Reset failed'));
        }
        showToast(t('mapping_editor.reset_success', 'Mapping reset to default'), 'success');
        showProfileDetails(eepId);
        // Refresh the profile tree to update indicators
        loadProfiles();
    } catch (e) {
        showToast(e.message, 'danger');
    }
}
async function deleteCustomProfile(eepId) {
    if (!confirm(`${t('profile.delete_confirm', 'Delete custom profile')} ${eepId}? ${t('common.cannot_undo', 'This cannot be undone.')}`)) return;

    try {
        const response = await fetch(getApiUrl(`/api/eep/custom/${eepId}`), {method: 'DELETE'});
        if (!response.ok) {
            const errData = await response.json().catch(() => null);
            throw new Error(errData?.detail || `Server error (${response.status})`);
        }
        document.getElementById('profile-details').innerHTML = `<p class="text-muted">${t('profiles.select_hint', 'Select a profile to view details')}</p>`;
        loadProfiles();
        showToast(`${t('profile.deleted', 'Profile deleted')}: ${eepId}`, 'success');
    } catch (error) {
        showToast(error.message, 'danger');
    }
}
async function editCustomProfile(eepId) {
    try {
        const response = await fetch(getApiUrl(`/api/eep/${eepId}`));
        const profile = await response.json();

        if (!profile.is_custom) {
            showToast(t('profile.only_custom_editable', 'Only custom profiles can be edited'), 'danger');
            return;
        }

        // Reset text mode before populating
        _resetHaTextMode();

        // Populate the modal form with existing data
        const form = document.getElementById('custom-profile-form');
        form.querySelector('[name="rorg"]').value = profile.rorg;
        form.querySelector('[name="func"]').value = profile.func;
        form.querySelector('[name="type"]').value = profile.type;
        form.querySelector('[name="description"]').value = profile.description;
        form.querySelector('[name="fields"]').value = profile.fields.length
            ? JSON.stringify(profile.fields, null, 2)
            : '';

        // Populate HA mapping builder
        populateHaMapping(profile.ha_mapping || {});

        // Mark as editing (store original eep_id)
        form.dataset.editEepId = eepId;

        // Update modal title
        document.querySelector('#customProfileModal .modal-title').textContent = `Edit Custom Profile: ${eepId}`;

        // Show modal
        new bootstrap.Modal(document.getElementById('customProfileModal')).show();
    } catch (error) {
        showToast(t('profile.load_edit_failed', 'Failed to load profile for editing'), 'danger');
    }
}
async function forkStandardProfile(eepId) {
    try {
        const response = await fetch(getApiUrl(`/api/eep/${eepId}`));
        const profile = await response.json();

        // Also fetch mapping override if exists
        const mappingResp = await fetch(getApiUrl(`/api/eep/${eepId}/mapping`));
        const mappingData = await mappingResp.json();

        // Reset text mode before populating
        _resetHaTextMode();

        // Populate the modal form with standard profile data
        const form = document.getElementById('custom-profile-form');
        form.reset();
        delete form.dataset.editEepId;
        form.querySelector('[name="rorg"]').value = profile.rorg;
        form.querySelector('[name="func"]').value = profile.func;
        form.querySelector('[name="type"]').value = profile.type;
        form.querySelector('[name="description"]').value = profile.description;
        form.querySelector('[name="fields"]').value = profile.fields.length
            ? JSON.stringify(profile.fields, null, 2)
            : '';

        // Populate HA mapping from override or default
        const effectiveMapping = mappingData.mapping || {};
        populateHaMapping(effectiveMapping);

        // Update modal title
        document.querySelector('#customProfileModal .modal-title').textContent = `${t('modal.fork_title', 'Fork Standard Profile')}: ${eepId}`;

        // Show modal
        new bootstrap.Modal(document.getElementById('customProfileModal')).show();
    } catch (error) {
        showToast(t('profile.load_fork_failed', 'Failed to load profile for forking'), 'danger');
    }
}
function addHaMappingRow(shortcut = '', component = 'binary_sensor', name = '', deviceClass = '', icon = '', unit = '', opts = {}) {
    const container = document.getElementById('ha-mapping-rows');
    const emptyMsg = document.getElementById('ha-mapping-empty');
    if (emptyMsg) emptyMsg.style.display = 'none';

    const rowId = _haRowCounter++;
    const stateClass = opts.state_class || '';
    const entityCategory = opts.entity_category || '';
    const expireAfter = opts.expire_after != null ? opts.expire_after : '';
    const forceUpdate = opts.force_update || false;
    const precision = opts.suggested_display_precision != null ? opts.suggested_display_precision : '';
    const valueTemplate = opts.value_template || '';

    const row = document.createElement('div');
    row.className = 'ha-mapping-row border rounded p-2 mb-2';
    row.innerHTML = `
        <div class="row g-2 align-items-end">
            <div class="col-6 col-xl-2">
                <label class="form-label small">${t('mapping_editor.field_shortcut', 'Shortcut')}</label>
                <input type="text" class="form-control form-control-sm" placeholder="AL" value="${shortcut}"
                       data-field="shortcut">
            </div>
            <div class="col-6 col-xl-2">
                <label class="form-label small">${t('mapping_editor.field_component', 'Component')}</label>
                <select class="form-select form-select-sm" data-field="component" onchange="onComponentChange(this)">
                    <option value="binary_sensor" ${component === 'binary_sensor' ? 'selected' : ''}>binary_sensor</option>
                    <option value="sensor" ${component === 'sensor' ? 'selected' : ''}>sensor</option>
                    <option value="switch" ${component === 'switch' ? 'selected' : ''}>switch</option>
                    <option value="light" ${component === 'light' ? 'selected' : ''}>light</option>
                    <option value="cover" ${component === 'cover' ? 'selected' : ''}>cover</option>
                    <option value="climate" ${component === 'climate' ? 'selected' : ''}>climate</option>
                    <option value="fan" ${component === 'fan' ? 'selected' : ''}>fan</option>
                </select>
            </div>
            <div class="col-6 col-xl-2">
                <label class="form-label small">${t('mapping_editor.field_name', 'Name')}</label>
                <input type="text" class="form-control form-control-sm" placeholder="Alarm" value="${name}"
                       data-field="name">
            </div>
            <div class="col-6 col-xl-2">
                <label class="form-label small">${t('mapping_editor.field_device_class', 'Device Class')}</label>
                <select class="form-select form-select-sm" data-field="device_class">
                    ${getDeviceClassOptions(component, deviceClass)}
                </select>
            </div>
            <div class="col-6 col-xl-2">
                <label class="form-label small">${t('mapping_editor.field_icon', 'Icon')}</label>
                <input type="text" class="form-control form-control-sm" placeholder="mdi:alert" value="${icon}"
                       data-field="icon">
            </div>
            <div class="col-6 col-xl-1">
                <label class="form-label small">${t('mapping_editor.field_unit', 'Unit')}</label>
                <input type="text" class="form-control form-control-sm" placeholder="" value="${unit}"
                       data-field="unit_of_measurement">
            </div>
            <div class="col-6 col-xl-1">
                <button type="button" class="btn btn-sm btn-outline-danger" onclick="removeHaMappingRow(this)" title="${t('mapping_editor.field_remove', 'Remove')}">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        </div>
        <div class="mt-1">
            <a class="small text-muted text-decoration-none" data-bs-toggle="collapse" href="#ha-adv-${rowId}" role="button" aria-expanded="false">
                <i class="bi bi-chevron-right"></i> ${t('mapping_editor.advanced', 'Advanced')}
            </a>
            <div class="collapse" id="ha-adv-${rowId}">
                <div class="row g-2 mt-1">
                    <div class="col-6 col-xl-2">
                        <label class="form-label small">${t('mapping_editor.field_state_class', 'State Class')}</label>
                        <select class="form-select form-select-sm" data-field="state_class">
                            <option value="" ${!stateClass ? 'selected' : ''}>${t('mapping_editor.none', '(none)')}</option>
                            <option value="measurement" ${stateClass === 'measurement' ? 'selected' : ''}>measurement</option>
                            <option value="total" ${stateClass === 'total' ? 'selected' : ''}>total</option>
                            <option value="total_increasing" ${stateClass === 'total_increasing' ? 'selected' : ''}>total_increasing</option>
                        </select>
                    </div>
                    <div class="col-6 col-xl-2">
                        <label class="form-label small">${t('mapping_editor.field_entity_category', 'Entity Category')}</label>
                        <select class="form-select form-select-sm" data-field="entity_category">
                            <option value="" ${!entityCategory ? 'selected' : ''}>${t('mapping_editor.none', '(none)')}</option>
                            <option value="diagnostic" ${entityCategory === 'diagnostic' ? 'selected' : ''}>diagnostic</option>
                            <option value="config" ${entityCategory === 'config' ? 'selected' : ''}>config</option>
                        </select>
                    </div>
                    <div class="col-6 col-xl-2">
                        <label class="form-label small">${t('mapping_editor.field_expire_after', 'Expire After (s)')}</label>
                        <input type="number" class="form-control form-control-sm" placeholder="" value="${expireAfter}" data-field="expire_after" min="0">
                    </div>
                    <div class="col-6 col-xl-2">
                        <label class="form-label small">${t('mapping_editor.field_precision', 'Precision')}</label>
                        <input type="number" class="form-control form-control-sm" placeholder="" value="${precision}" data-field="suggested_display_precision" min="0" max="10">
                    </div>
                    <div class="col-6 col-xl-2 d-flex align-items-end">
                        <div class="form-check mb-2">
                            <input class="form-check-input" type="checkbox" data-field="force_update" ${forceUpdate ? 'checked' : ''}>
                            <label class="form-check-label small">${t('mapping_editor.field_force_update', 'Force Update')}</label>
                        </div>
                    </div>
                </div>
                <div class="row g-2 mt-1">
                    <div class="col-12 col-xl-6">
                        <label class="form-label small">${t('mapping_editor.field_value_template', 'Value Template')}</label>
                        <input type="text" class="form-control form-control-sm font-monospace" placeholder="auto-generated" value="${valueTemplate.replace(/"/g, '&quot;')}" data-field="value_template">
                    </div>
                </div>
            </div>
        </div>
    `;

    // Rotate chevron on collapse toggle
    const collapseEl = row.querySelector('.collapse');
    collapseEl.addEventListener('show.bs.collapse', () => {
        row.querySelector('.bi-chevron-right')?.classList.replace('bi-chevron-right', 'bi-chevron-down');
    });
    collapseEl.addEventListener('hide.bs.collapse', () => {
        row.querySelector('.bi-chevron-down')?.classList.replace('bi-chevron-down', 'bi-chevron-right');
    });

    container.appendChild(row);
}
function removeHaMappingRow(btn) {
    const row = btn.closest('.ha-mapping-row');
    row.remove();
    const container = document.getElementById('ha-mapping-rows');
    if (container.children.length === 0) {
        document.getElementById('ha-mapping-empty').style.display = '';
    }
}
function onComponentChange(select) {
    const row = select.closest('.ha-mapping-row');
    const dcSelect = row.querySelector('[data-field="device_class"]');
    const component = select.value;
    dcSelect.innerHTML = getDeviceClassOptions(component, '');
}
function collectHaMapping() {
    const rows = document.querySelectorAll('.ha-mapping-row');
    if (rows.length === 0) return null;

    const mapping = {};
    let valid = true;

    rows.forEach(row => {
        const shortcut = (row.querySelector('[data-field="shortcut"]').value || '').trim();
        if (!shortcut) {
            valid = false;
            return;
        }

        const entry = {
            component: row.querySelector('[data-field="component"]').value
        };

        const name = row.querySelector('[data-field="name"]').value.trim();
        if (name) entry.name = name;

        const dc = row.querySelector('[data-field="device_class"]').value;
        if (dc) entry.device_class = dc;

        const icon = row.querySelector('[data-field="icon"]').value.trim();
        if (icon) entry.icon = icon;

        const unit = row.querySelector('[data-field="unit_of_measurement"]').value.trim();
        if (unit) entry.unit_of_measurement = unit;

        // Advanced fields
        const stateClass = row.querySelector('[data-field="state_class"]')?.value || '';
        if (stateClass) entry.state_class = stateClass;
        const entityCat = row.querySelector('[data-field="entity_category"]')?.value || '';
        if (entityCat) entry.entity_category = entityCat;
        const expireStr = row.querySelector('[data-field="expire_after"]')?.value || '';
        if (expireStr !== '') entry.expire_after = parseInt(expireStr);
        const precisionStr = row.querySelector('[data-field="suggested_display_precision"]')?.value || '';
        if (precisionStr !== '') entry.suggested_display_precision = parseInt(precisionStr);
        const forceUpdate = row.querySelector('[data-field="force_update"]')?.checked || false;
        if (forceUpdate) entry.force_update = true;
        const valTpl = row.querySelector('[data-field="value_template"]')?.value?.trim() || '';
        if (valTpl) entry.value_template = valTpl;

        mapping[shortcut] = entry;
    });

    if (!valid) return undefined; // signal validation error
    return Object.keys(mapping).length > 0 ? mapping : null;
}
function populateHaMapping(haMapping) {
    const container = document.getElementById('ha-mapping-rows');
    container.innerHTML = '';

    if (!haMapping || Object.keys(haMapping).length === 0) {
        document.getElementById('ha-mapping-empty').style.display = '';
        return;
    }

    document.getElementById('ha-mapping-empty').style.display = 'none';

    for (const [shortcut, config] of Object.entries(haMapping)) {
        addHaMappingRow(
            shortcut,
            config.component || 'binary_sensor',
            config.name || '',
            config.device_class || '',
            config.icon || '',
            config.unit_of_measurement || '',
            {
                state_class: config.state_class,
                entity_category: config.entity_category,
                expire_after: config.expire_after,
                force_update: config.force_update,
                suggested_display_precision: config.suggested_display_precision,
                value_template: config.value_template
            }
        );
    }
}
async function saveCustomProfile() {
    const form = document.getElementById('custom-profile-form');
    const formData = new FormData(form);

    // Validate required fields (HTML 'required' doesn't work with onclick)
    const rorg = (formData.get('rorg') || '').trim();
    const func = (formData.get('func') || '').trim();
    const type = (formData.get('type') || '').trim();
    const description = (formData.get('description') || '').trim();

    if (!rorg || !func || !type) {
        showToast(t('toast.rorg_func_type_required', 'RORG, FUNC, and TYPE are required'), 'danger');
        return;
    }
    if (!description) {
        showToast(t('toast.description_required', 'Description is required'), 'danger');
        return;
    }

    try {
        let fields = [];
        const fieldsText = (formData.get('fields') || '').trim();
        if (fieldsText) {
            fields = JSON.parse(fieldsText);
            if (!Array.isArray(fields)) {
                showToast(t('toast.fields_json_array', 'Fields must be a JSON array'), 'danger');
                return;
            }
        }

        // Collect HA mapping from builder (visual or text mode)
        const haMapping = getHaMappingData();
        if (haMapping === undefined) {
            showToast(t('mapping_editor.ha_need_shortcut', 'HA Mapping: All rows need a Shortcut (or fix YAML errors)'), 'danger');
            return;
        }

        // Check if we're editing or creating
        const editEepId = form.dataset.editEepId;
        const url = editEepId
            ? getApiUrl(`/api/eep/custom/${editEepId}`)
            : getApiUrl('/api/eep/custom');
        const method = editEepId ? 'PUT' : 'POST';

        const payload = {
            rorg: rorg,
            func: func,
            type: type,
            description: description,
            fields: fields
        };
        if (haMapping) {
            payload.ha_mapping = haMapping;
        }

        const response = await fetch(url, {
            method: method,
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => null);
            const detail = errData?.detail || `Server error (${response.status})`;
            throw new Error(detail);
        }

        bootstrap.Modal.getInstance(document.getElementById('customProfileModal')).hide();
        form.reset();
        delete form.dataset.editEepId;
        document.querySelector('#customProfileModal .modal-title').textContent = t('modal.custom_profile_title', 'Create Custom EEP Profile');
        // Clear HA mapping rows
        document.getElementById('ha-mapping-rows').innerHTML = '';
        document.getElementById('ha-mapping-empty').style.display = '';
        loadProfiles();
        showToast(editEepId ? t('modal.profile_updated', 'Custom profile updated') : t('modal.profile_saved', 'Custom profile created'), 'success');
        // Show the profile details (use editEepId for updates, compute from form for new)
        const showEepId = editEepId || `${rorg.toUpperCase().replace('0X','')}-${func.toUpperCase().replace('0X','').padStart(2,'0')}-${type.toUpperCase().replace('0X','').padStart(2,'0')}`;
        showProfileDetails(showEepId);
    } catch (error) {
        showToast(error.message, 'danger');
    }
}
function filterProfiles() {
    const query = document.getElementById('profile-search').value.toLowerCase();
    const container = document.getElementById('eep-tree');
    const allItems = container.querySelectorAll('.eep-item');

    if (!query) {
        // Reset: show all elements, then re-collapse standard tree nodes
        container.querySelectorAll('*').forEach(el => el.style.display = '');
        container.querySelectorAll('[id^="rorg-"], [id^="func-"]').forEach(el => {
            el.style.display = 'none';
        });
        return;
    }

    // Hide everything inside the container first
    Array.from(container.children).forEach(child => child.style.display = 'none');
    allItems.forEach(item => item.style.display = 'none');
    container.querySelectorAll('[id^="rorg-"], [id^="func-"]').forEach(el => {
        el.style.display = 'none';
    });

    // Show matching items and expand their parent chain
    let matchCount = 0;
    allItems.forEach(item => {
        const text = item.dataset.search || item.textContent.toLowerCase();
        if (text.includes(query)) {
            matchCount++;
            item.style.display = '';
            // Walk up and show all ancestor nodes up to the container
            let parent = item.parentElement;
            while (parent && parent !== container) {
                parent.style.display = '';
                parent = parent.parentElement;
            }
        }
    });
}
