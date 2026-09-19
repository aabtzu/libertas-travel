const token = new URLSearchParams(window.location.search).get('token');
if (!token) {
    document.getElementById('rp-form').style.display = 'none';
    document.getElementById('rp-invalid').style.display = 'block';
}

document.getElementById('rp-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('rp-btn');
    const errDiv = document.getElementById('rp-error');
    const errMsg = document.getElementById('rp-error-message');
    errDiv.style.display = 'none';
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';

    try {
        const res = await fetch('/api/reset-password', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                token,
                new_password: document.getElementById('rp-new').value,
                confirm_password: document.getElementById('rp-confirm').value,
            }),
        });
        const data = await res.json();
        if (data.success) {
            document.getElementById('rp-form').style.display = 'none';
            document.getElementById('rp-success').style.display = 'block';
        } else if (data.error && data.error.includes('expired')) {
            document.getElementById('rp-form').style.display = 'none';
            document.getElementById('rp-invalid').style.display = 'block';
        } else {
            errMsg.textContent = data.error || 'Something went wrong';
            errDiv.style.display = 'flex';
        }
    } catch {
        errMsg.textContent = 'Failed to connect';
        errDiv.style.display = 'flex';
    }
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-key"></i> Set New Password';
});
