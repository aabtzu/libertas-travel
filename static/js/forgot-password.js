document.getElementById('fp-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('fp-btn');
    const errDiv = document.getElementById('fp-error');
    const errMsg = document.getElementById('fp-error-message');
    const successDiv = document.getElementById('fp-success');
    errDiv.style.display = 'none';
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sending...';

    try {
        const res = await fetch('/api/forgot-password', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: document.getElementById('fp-email').value.trim()}),
        });
        const data = await res.json();
        if (data.success) {
            document.getElementById('fp-form').style.display = 'none';
            successDiv.style.display = 'block';
        } else {
            errMsg.textContent = data.error || 'Something went wrong';
            errDiv.style.display = 'flex';
        }
    } catch {
        errMsg.textContent = 'Failed to connect';
        errDiv.style.display = 'flex';
    }
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-paper-plane"></i> Send Reset Link';
});
