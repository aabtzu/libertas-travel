let _adminKey = '';

function fmtDate(s) {
    if (!s) return '-';
    const d = new Date(s);
    return isNaN(d) ? s : d.toLocaleString();
}

function renderStats(data) {
    const grid = document.getElementById('stat-grid');
    const stats = [
        { label: 'Total Users', value: data.users_count ?? '-' },
        { label: 'Total Trips', value: data.trips_count ?? '-' },
        { label: 'New Users 24h', value: data.new_users_24h ?? '-', accent: true },
        { label: 'New Trips 24h', value: data.new_trips_24h ?? '-', accent: true },
        { label: 'Venues', value: data.venue_count ?? '-' },
    ];
    grid.innerHTML = stats.map(s => `
        <div class="stat-card">
            <div class="label">${s.label}</div>
            <div class="value${s.accent ? ' accent' : ''}">${s.value}</div>
        </div>
    `).join('');
}

function renderUsers(users) {
    const tbody = document.querySelector('#users-table tbody');
    if (!users || !users.length) {
        tbody.innerHTML = '<tr><td colspan="4" style="color:#999;text-align:center">No users yet</td></tr>';
        return;
    }
    tbody.innerHTML = users.map(u => `
        <tr>
            <td class="mono">${u.id}</td>
            <td><strong>${u.username}</strong></td>
            <td class="mono">${u.email || '-'}</td>
            <td>${fmtDate(u.created_at)}</td>
        </tr>
    `).join('');
}

function renderTrips(trips) {
    const tbody = document.querySelector('#trips-table tbody');
    if (!trips || !trips.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="color:#999;text-align:center">No trips yet</td></tr>';
        return;
    }
    tbody.innerHTML = trips.map(t => `
        <tr>
            <td class="mono">${t.id}</td>
            <td>${t.title}</td>
            <td><a href="/${t.link}" target="_blank" class="mono">${t.link}</a></td>
            <td class="mono">${t.user_id}</td>
            <td>${fmtDate(t.created_at)}</td>
        </tr>
    `).join('');
}

async function loadDashboard(key) {
    const res = await fetch('/api/debug', {
        headers: { 'X-Admin-Key': key },
    });
    if (res.status === 401) throw new Error('Invalid admin key');
    if (!res.ok) throw new Error('Server error');
    const data = await res.json();
    return data.data || data;
}

async function unlock() {
    const key = document.getElementById('admin-key-input').value.trim();
    const btn = document.getElementById('auth-btn');
    const errDiv = document.getElementById('auth-error');
    if (!key) return;
    btn.disabled = true;
    btn.textContent = 'Checking...';
    errDiv.style.display = 'none';
    try {
        const data = await loadDashboard(key);
        _adminKey = key;
        document.getElementById('auth-gate').style.display = 'none';
        document.getElementById('dashboard').style.display = 'block';
        renderStats(data);
        renderUsers(data.recent_users);
        renderTrips(data.trips);
    } catch (e) {
        errDiv.textContent = e.message;
        errDiv.style.display = 'block';
    }
    btn.disabled = false;
    btn.textContent = 'Unlock';
}

document.getElementById('auth-btn').addEventListener('click', unlock);
document.getElementById('admin-key-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') unlock();
});
