"""Admin dashboard HTML page."""

from __future__ import annotations

from agents.common.templates import get_nav_html


def generate_admin_dashboard_page() -> str:
    nav = get_nav_html("")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin - Libertas</title>
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <link rel="stylesheet" href="/static/css/main.css?v=14">
    <style>
        .admin-hero {{
            background: #1a1a2e;
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .admin-hero h1 {{ font-size: 1.8rem; font-weight: 300; letter-spacing: 1px; margin: 0; }}
        .admin-content {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 32px 24px;
        }}
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .stat-card {{
            background: white;
            border-radius: 12px;
            padding: 20px 24px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.06);
            text-align: center;
        }}
        .stat-card .label {{
            font-size: 0.75rem;
            font-weight: 600;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}
        .stat-card .value {{
            font-size: 2rem;
            font-weight: 700;
            color: #1a1a2e;
        }}
        .stat-card .value.accent {{ color: #667eea; }}
        .section {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.06);
        }}
        .section h2 {{
            font-size: 1rem;
            color: #667eea;
            margin: 0 0 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.88rem;
        }}
        th {{
            text-align: left;
            padding: 8px 12px;
            background: #f8f9fa;
            color: #666;
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }}
        td {{
            padding: 10px 12px;
            border-top: 1px solid #f0f0f0;
            color: #333;
        }}
        tr:hover td {{ background: #fafafa; }}
        .mono {{ font-family: monospace; font-size: 0.82rem; color: #555; }}
        .auth-gate {{
            max-width: 420px;
            margin: 80px auto;
            background: white;
            border-radius: 14px;
            padding: 36px;
            box-shadow: 0 2px 20px rgba(0,0,0,0.08);
            text-align: center;
        }}
        .auth-gate i {{ font-size: 2.5rem; color: #667eea; margin-bottom: 16px; }}
        .auth-gate h2 {{ color: #1a1a2e; margin: 0 0 8px; }}
        .auth-gate p {{ color: #666; font-size: 0.9rem; margin: 0 0 20px; }}
        .auth-gate input {{
            width: 100%;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 0.95rem;
            margin-bottom: 12px;
            box-sizing: border-box;
        }}
        .auth-gate button {{
            width: 100%;
            background: #667eea;
            color: white;
            border: none;
            padding: 12px;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
        }}
        .auth-gate button:hover {{ background: #5a6fd6; }}
        .auth-error {{ color: #e74c3c; font-size: 0.85rem; margin-top: 8px; }}
        #dashboard {{ display: none; }}
        .badge {{
            display: inline-block;
            background: #f0f2ff;
            color: #667eea;
            border-radius: 4px;
            padding: 2px 7px;
            font-size: 0.78rem;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    {nav}

    <div class="admin-hero">
        <h1><i class="fas fa-chart-line"></i> Admin Dashboard</h1>
    </div>

    <div class="admin-content">

        <div id="auth-gate" class="auth-gate">
            <i class="fas fa-lock"></i>
            <h2>Admin Access</h2>
            <p>Enter the admin key to view the dashboard.</p>
            <input type="password" id="admin-key-input" placeholder="Admin key" autofocus>
            <button id="auth-btn">Unlock</button>
            <div class="auth-error" id="auth-error" style="display:none;"></div>
        </div>

        <div id="dashboard">
            <div class="stat-grid" id="stat-grid"></div>

            <div class="section">
                <h2><i class="fas fa-users"></i> Recent Users</h2>
                <table id="users-table">
                    <thead><tr>
                        <th>ID</th><th>Username</th><th>Email</th><th>Joined</th>
                    </tr></thead>
                    <tbody></tbody>
                </table>
            </div>

            <div class="section">
                <h2><i class="fas fa-route"></i> Recent Trips</h2>
                <table id="trips-table">
                    <thead><tr>
                        <th>ID</th><th>Title</th><th>Link</th><th>User</th><th>Created</th>
                    </tr></thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>

    </div>

    <script>
        let _adminKey = '';

        function fmtDate(s) {{
            if (!s) return '-';
            const d = new Date(s);
            return isNaN(d) ? s : d.toLocaleString();
        }}

        function renderStats(data) {{
            const grid = document.getElementById('stat-grid');
            const stats = [
                {{ label: 'Total Users', value: data.users_count ?? '-' }},
                {{ label: 'Total Trips', value: data.trips_count ?? '-' }},
                {{ label: 'New Users 24h', value: data.new_users_24h ?? '-', accent: true }},
                {{ label: 'New Trips 24h', value: data.new_trips_24h ?? '-', accent: true }},
                {{ label: 'Venues', value: data.venue_count ?? '-' }},
            ];
            grid.innerHTML = stats.map(s => `
                <div class="stat-card">
                    <div class="label">${{s.label}}</div>
                    <div class="value${{s.accent ? ' accent' : ''}}">${{s.value}}</div>
                </div>
            `).join('');
        }}

        function renderUsers(users) {{
            const tbody = document.querySelector('#users-table tbody');
            if (!users || !users.length) {{
                tbody.innerHTML = '<tr><td colspan="4" style="color:#999;text-align:center">No users yet</td></tr>';
                return;
            }}
            tbody.innerHTML = users.map(u => `
                <tr>
                    <td class="mono">${{u.id}}</td>
                    <td><strong>${{u.username}}</strong></td>
                    <td class="mono">${{u.email || '-'}}</td>
                    <td>${{fmtDate(u.created_at)}}</td>
                </tr>
            `).join('');
        }}

        function renderTrips(trips) {{
            const tbody = document.querySelector('#trips-table tbody');
            if (!trips || !trips.length) {{
                tbody.innerHTML = '<tr><td colspan="5" style="color:#999;text-align:center">No trips yet</td></tr>';
                return;
            }}
            tbody.innerHTML = trips.map(t => `
                <tr>
                    <td class="mono">${{t.id}}</td>
                    <td>${{t.title}}</td>
                    <td><a href="/${{t.link}}" target="_blank" class="mono">${{t.link}}</a></td>
                    <td class="mono">${{t.user_id}}</td>
                    <td>${{fmtDate(t.created_at)}}</td>
                </tr>
            `).join('');
        }}

        async function loadDashboard(key) {{
            const res = await fetch('/api/debug', {{
                headers: {{ 'X-Admin-Key': key }},
            }});
            if (res.status === 401) throw new Error('Invalid admin key');
            if (!res.ok) throw new Error('Server error');
            const data = await res.json();
            return data.data || data;
        }}

        async function unlock() {{
            const key = document.getElementById('admin-key-input').value.trim();
            const btn = document.getElementById('auth-btn');
            const errDiv = document.getElementById('auth-error');
            if (!key) return;
            btn.disabled = true;
            btn.textContent = 'Checking...';
            errDiv.style.display = 'none';
            try {{
                const data = await loadDashboard(key);
                _adminKey = key;
                document.getElementById('auth-gate').style.display = 'none';
                document.getElementById('dashboard').style.display = 'block';
                renderStats(data);
                renderUsers(data.recent_users);
                renderTrips(data.trips);
            }} catch (e) {{
                errDiv.textContent = e.message;
                errDiv.style.display = 'block';
            }}
            btn.disabled = false;
            btn.textContent = 'Unlock';
        }}

        document.getElementById('auth-btn').addEventListener('click', unlock);
        document.getElementById('admin-key-input').addEventListener('keydown', e => {{
            if (e.key === 'Enter') unlock();
        }});
    </script>
</body>
</html>"""
