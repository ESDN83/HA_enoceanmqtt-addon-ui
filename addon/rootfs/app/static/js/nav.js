// Extracted from templates/index.html. Classic script, no modules:
// the inline onclick handlers call these by bare name, so they must stay global.

// Which page is showing. Written by navigateTo, read by nobody else.
let currentPage = 'dashboard';

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    sidebar.classList.toggle('show');
    backdrop.classList.toggle('show');
}
function closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    sidebar.classList.remove('show');
    backdrop.classList.remove('show');
}
function navigateTo(page) {
    // Hide all pages
    document.querySelectorAll('.page-content').forEach(p => p.style.display = 'none');
    // Show selected page
    document.getElementById('page-' + page).style.display = 'block';
    // Update nav
    document.querySelectorAll('[data-page]').forEach(link => {
        link.classList.toggle('active', link.dataset.page === page);
    });
    currentPage = page;

    // Close sidebar on mobile after navigation
    closeSidebar();

    // Reset teach-in state when leaving the page
    if (page !== 'teach-in') {
        cancelTeachIn();
        document.getElementById('actuator-teach-in-panel').style.display = 'none';
    }

    // Clear search fields when navigating away
    if (page !== 'devices') {
        const ds = document.getElementById('device-search');
        if (ds) ds.value = '';
    }
    if (page !== 'profiles') {
        const ps = document.getElementById('profile-search');
        if (ps) ps.value = '';
    }

    // Load page-specific data
    if (page === 'devices') loadDevices();
    if (page === 'profiles') loadProfiles();
    if (page === 'settings') { loadBackups(); loadEepInfo(); loadMqttConfig(); }
    if (page === 'teach-in') resetTeachInPage();
}
