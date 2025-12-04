// Register form handler
document.getElementById('register-form').addEventListener('submit', async function(e) {
    e.preventDefault();

    const username = document.getElementById('username').value;
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    const errorDiv = document.getElementById('register-error');
    const successDiv = document.getElementById('register-success');
    const errorMsg = document.getElementById('error-message');

    // Client-side validation
    if (password !== confirmPassword) {
        errorMsg.textContent = 'Passwords do not match';
        errorDiv.classList.add('show');
        return;
    }

    try {
        const response = await fetch('/api/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, email, password }),
        });

        const data = await response.json();

        if (data.success) {
            errorDiv.classList.remove('show');
            successDiv.style.display = 'block';
            setTimeout(function() {
                window.location.href = '/login.html';
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
