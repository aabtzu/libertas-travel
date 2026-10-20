// Show error if Google OAuth callback redirected back with ?error=
(function () {
    const _GOOGLE_ERRORS = {
        google_denied: 'Google sign-in was cancelled.',
        google_state: 'Sign-in session expired. Please try again.',
        google_token: 'Could not complete Google sign-in. Please try again.',
        google_userinfo: 'Could not retrieve your Google account info. Please try again.',
        google_no_email: 'Your Google account does not have a verified email address.',
        google_db: 'Account setup failed. Please try again.',
    };
    const err = new URLSearchParams(window.location.search).get('error');
    if (err && _GOOGLE_ERRORS[err]) {
        const errorDiv = document.getElementById('login-error');
        document.getElementById('error-message').textContent = _GOOGLE_ERRORS[err];
        if (errorDiv) errorDiv.classList.add('show');
        history.replaceState(null, '', location.pathname);
    }
}());

// Login form handler
document.getElementById('login-form').addEventListener('submit', async function(e) {
    e.preventDefault();

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('login-error');
    const errorMsg = document.getElementById('error-message');

    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password }),
        });

        const data = await response.json();

        if (data.success) {
            // Trigger browser password save prompt using PasswordCredential API
            if (window.PasswordCredential) {
                try {
                    const cred = new PasswordCredential({
                        id: username,
                        password: password,
                        name: username
                    });
                    await navigator.credentials.store(cred);
                } catch (credErr) {
                    // Ignore credential storage errors - login still succeeded
                    console.log('Password credential storage skipped:', credErr);
                }
            }
            // If an invite token was carried from the register page, accept it
            const params = new URLSearchParams(window.location.search);
            const inviteToken = params.get('invite_token');
            if (inviteToken) {
                window.location.href = `/api/trips/invite/accept?token=${encodeURIComponent(inviteToken)}`;
                return;
            }
            // Redirect to the original page or home, but only if the
            // redirect param is a same-origin path. An attacker linking to
            // /login?redirect=https://evil.com would otherwise send the
            // user offsite right after they entered their password.
            const raw = params.get('redirect') || '/';
            const safe = raw.startsWith('/') && !raw.startsWith('//') ? raw : '/';
            window.location.href = safe;
        } else {
            errorMsg.textContent = data.error || 'Invalid username or password';
            errorDiv.classList.add('show');
        }
    } catch (err) {
        errorMsg.textContent = 'Connection error. Please try again.';
        errorDiv.classList.add('show');
    }
});
