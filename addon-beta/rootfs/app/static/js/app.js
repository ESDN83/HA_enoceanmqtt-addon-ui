// Extracted from templates/index.html. Classic script, no modules:
// the inline onclick handlers call these by bare name, so they must stay global.
//
// This file is the wiring, and it is loaded at the END of <body>, not in
// <head> with the others. That is where the inline block sat, and
// detectAndApplyTheme() runs immediately on load, so moving it earlier would
// change when the theme is first applied. Same position, same timing.

// Listen for OS theme changes (standalone mode)
if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', detectAndApplyTheme);
}

// Apply theme immediately (before DOMContentLoaded to prevent flash)
detectAndApplyTheme();

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    // Re-check theme after full load (HA Ingress may set theme late)
    setTimeout(detectAndApplyTheme, 500);

    // Navigation
    document.querySelectorAll('[data-page]').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            navigateTo(this.dataset.page);
        });
    });

    // Load initial data
    initI18n().then(() => {
        loadStatus();
        loadRecentTelegrams();
        loadUnknownDevices();
    });
    setInterval(loadStatus, 10000); // Refresh every 10 seconds
    setInterval(loadRecentTelegrams, 5000); // Refresh telegrams every 5 seconds
    setInterval(loadUnknownDevices, 15000); // Refresh unknown devices every 15 seconds

    // Device form
    document.getElementById('device-form').addEventListener('submit', saveDevice);

    // Search handlers
    document.getElementById('device-search')?.addEventListener('input', filterDevices);
    document.getElementById('profile-search')?.addEventListener('input', filterProfiles);

    // Reset custom profile modal when closed
    document.getElementById('customProfileModal')?.addEventListener('hidden.bs.modal', function() {
        const form = document.getElementById('custom-profile-form');
        form.reset();
        delete form.dataset.editEepId;
        document.querySelector('#customProfileModal .modal-title').textContent = t('modal.custom_profile_title', 'Create Custom EEP Profile');
        // Clear HA mapping builder
        document.getElementById('ha-mapping-rows').innerHTML = '';
        document.getElementById('ha-mapping-empty').style.display = '';
        // Reset text mode when modal closes
        _resetHaTextMode();
    });
});

// Update derived sender ID when offset changes
document.getElementById('sender-offset')?.addEventListener('input', updateDerivedSenderId);

// === EEP.xml Upload Management ===
