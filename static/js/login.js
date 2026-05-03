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
            // Redirect to the original page or home — but only if the
            // redirect param is a same-origin path. An attacker linking to
            // /login?redirect=https://evil.com would otherwise send the
            // user offsite right after they entered their password.
            const raw = new URLSearchParams(window.location.search).get('redirect') || '/';
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
