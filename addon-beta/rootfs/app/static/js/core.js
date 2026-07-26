// Extracted from templates/index.html. Classic script, no modules:
// the inline onclick handlers call these by bare name, so they must stay global.

function getApiUrl(path) {
    // Get base path from current URL (for HA Ingress)
    // pathname could be "/" or "/api/hassio_ingress/<token>/" etc
    let basePath = window.location.pathname;

    // Remove trailing slash
    basePath = basePath.replace(/\/$/, '');

    // If we're at root or basePath already contains /api/, don't prepend
    if (basePath === '' || basePath === '/') {
        return path;
    }

    // For HA Ingress: basePath will be like /api/hassio_ingress/abc123
    return basePath + path;
}
function getWsUrl(path) {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const basePath = window.location.pathname.replace(/\/$/, '');
    return `${wsProtocol}//${window.location.host}${basePath}${path}`;
}
function colorBrightness(str) {
    if (!str) return null;
    str = String(str).trim();
    let r, g, b, a = 1;
    let m = str.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
    if (m) {
        let h = m[1];
        if (h.length === 3) h = h.split('').map(c => c + c).join('');
        r = parseInt(h.slice(0, 2), 16); g = parseInt(h.slice(2, 4), 16); b = parseInt(h.slice(4, 6), 16);
    } else {
        m = str.match(/rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)(?:[,\s/]+([\d.]+))?/i);
        if (!m) return null;
        r = +m[1]; g = +m[2]; b = +m[3];
        if (m[4] !== undefined) a = parseFloat(m[4]);
    }
    if (a === 0) return null;
    return (r + g + b) / 3;
}
// The pending action lives here, next to its only two users, so the
// confirmation modal is one unit rather than a variable in one file and
// its readers in another.
let _pendingConfirmAction = null;

function showConfirmDialog(title, body, btnLabel, btnClass, action) {
    document.getElementById('confirmModalTitle').textContent = title;
    document.getElementById('confirmModalBody').innerHTML = body;
    const btn = document.getElementById('confirmModalAction');
    btn.textContent = btnLabel;
    btn.className = 'btn ' + btnClass;
    _pendingConfirmAction = action;
    new bootstrap.Modal(document.getElementById('confirmModal')).show();
}
async function executeConfirmedAction() {
    bootstrap.Modal.getInstance(document.getElementById('confirmModal')).hide();
    if (_pendingConfirmAction) {
        await _pendingConfirmAction();
        _pendingConfirmAction = null;
    }
}
function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
}
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    container.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}
