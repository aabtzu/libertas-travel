// Register form handler
const _inviteToken = new URLSearchParams(window.location.search).get('invite_token');

// When arriving via a collaboration invite link, fetch the site invite code
// transparently so the invitee doesn't have to know it.
async function _prefillInviteCode() {
    if (!_inviteToken) return;
    try {
        const r = await fetch(`/api/auth/collab-invite-code?token=${encodeURIComponent(_inviteToken)}`);
        const d = await r.json();
        if (d.invite_code) {
            const field = document.getElementById('invite-code');
            if (field) {
                field.value = d.invite_code;
                // Hide the field - the invitee doesn't need to see or touch it
                const group = field.closest('.form-group') || field.parentElement;
                if (group) group.style.display = 'none';
            }
        }
    } catch { /* best-effort */ }
}
_prefillInviteCode();

document.getElementById('register-form').addEventListener('submit', async function(e) {
    e.preventDefault();

    const username = document.getElementById('username').value;
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    const inviteCode = document.getElementById('invite-code').value;
    const errorDiv = document.getElementById('register-error');
    const successDiv = document.getElementById('register-success');
    const errorMsg = document.getElementById('error-message');

    if (password !== confirmPassword) {
        errorMsg.textContent = 'Passwords do not match';
        errorDiv.classList.add('show');
        return;
    }

    try {
        const response = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password, invite_code: inviteCode }),
        });

        const data = await response.json();

        if (data.success) {
            errorDiv.classList.remove('show');
            successDiv.style.display = 'block';
            // Carry invite_token to login so we redirect to the trip after login
            const loginUrl = _inviteToken
                ? `/login.html?invite_token=${encodeURIComponent(_inviteToken)}`
                : '/login.html';
            setTimeout(function() {
                window.location.href = loginUrl;
            }, 2000);
        } else {
            errorMsg.textContent = data.error || 'Registration failed';
            errorDiv.classList.add('show');
        }
    } catch (err) {
        errorMsg.textContent = 'Connection error. Please try again.';
        errorDiv.classList.add('show');
    }
});
