/* Profile page: style extraction, save, password change, forwarding emails */

document.getElementById('extract-btn').addEventListener('click', async () => {
    const samples = document.getElementById('style-samples').value.trim();
    if (samples.length < 50) {
        document.getElementById('extract-status').textContent = 'Paste more text, at least a few sentences';
        document.getElementById('extract-status').className = 'status-msg error';
        return;
    }

    const btn = document.getElementById('extract-btn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';
    document.getElementById('extract-status').textContent = '';

    try {
        const res = await fetch('/api/user/extract-style', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({samples}),
        });
        const data = await res.json();
        if (data.success && data.profile) {
            const p = data.profile;
            document.getElementById('style-tone').value = p.tone || '';
            document.getElementById('style-sentences').value = p.sentence_style || '';
            document.getElementById('style-vocab').value = (p.vocabulary || []).join(', ');
            document.getElementById('style-emphasis').value = p.emphasis || '';
            document.getElementById('style-perspective').value = p.perspective || '';
            document.getElementById('style-quirks').value = Array.isArray(p.quirks) ? p.quirks.join(', ') : (p.quirks || '');
            document.getElementById('extract-status').textContent = 'Style extracted, review and save below';
            document.getElementById('extract-status').className = 'status-msg success';
        } else {
            document.getElementById('extract-status').textContent = data.error || 'Extraction failed';
            document.getElementById('extract-status').className = 'status-msg error';
        }
    } catch {
        document.getElementById('extract-status').textContent = 'Failed to connect';
        document.getElementById('extract-status').className = 'status-msg error';
    }
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-magic"></i> Extract My Style';
});

document.getElementById('save-style-btn').addEventListener('click', async () => {
    const profile = {
        tone: document.getElementById('style-tone').value.trim(),
        sentence_style: document.getElementById('style-sentences').value.trim(),
        vocabulary: document.getElementById('style-vocab').value.split(',').map(s => s.trim()).filter(s => s),
        emphasis: document.getElementById('style-emphasis').value.trim(),
        perspective: document.getElementById('style-perspective').value.trim(),
        quirks: document.getElementById('style-quirks').value.trim(),
        rules: document.getElementById('style-rules').value.trim(),
    };

    const samples = document.getElementById('style-samples').value.trim();
    const btn = document.getElementById('save-style-btn');
    btn.disabled = true;

    try {
        const res = await fetch('/api/user/save-profile', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                style_profile: profile,
                writing_samples: samples,
                samples_preview: samples.substring(0, 200),
                user_notes: document.getElementById('user-notes').value.trim(),
            }),
        });
        const data = await res.json();
        if (data.success) {
            document.getElementById('save-status').textContent = 'Style saved!';
            document.getElementById('save-status').className = 'status-msg success';
        } else {
            document.getElementById('save-status').textContent = data.error || 'Save failed';
            document.getElementById('save-status').className = 'status-msg error';
        }
    } catch {
        document.getElementById('save-status').textContent = 'Failed to save';
        document.getElementById('save-status').className = 'status-msg error';
    }
    btn.disabled = false;
});

document.getElementById('change-pw-btn').addEventListener('click', async () => {
    const btn = document.getElementById('change-pw-btn');
    const status = document.getElementById('change-pw-status');
    const body = {
        current_password: document.getElementById('pw-current').value,
        new_password: document.getElementById('pw-new').value,
        confirm_password: document.getElementById('pw-confirm').value,
    };
    btn.disabled = true;
    status.textContent = '';
    try {
        const res = await fetch('/api/user/change-password', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (data.success) {
            status.textContent = 'Password changed!';
            status.className = 'status-msg success';
            document.getElementById('pw-current').value = '';
            document.getElementById('pw-new').value = '';
            document.getElementById('pw-confirm').value = '';
        } else {
            status.textContent = data.error || 'Failed to change password';
            status.className = 'status-msg error';
        }
    } catch {
        status.textContent = 'Failed to connect';
        status.className = 'status-msg error';
    }
    btn.disabled = false;
});

document.getElementById('fwd-add-btn').addEventListener('click', async () => {
    const input = document.getElementById('fwd-email-input');
    const email = input.value.trim().toLowerCase();
    const status = document.getElementById('fwd-status');
    if (!email || !email.includes('@')) {
        status.textContent = 'Enter a valid email address';
        status.className = 'status-msg error';
        return;
    }
    status.textContent = '';
    try {
        const res = await fetch('/api/user/forwarding-emails', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email}),
        });
        const data = await res.json();
        if (data.success) {
            addForwardingItem(data.email);
            input.value = '';
            status.textContent = 'Address added';
            status.className = 'status-msg success';
        } else {
            status.textContent = data.error || 'Failed to add';
            status.className = 'status-msg error';
        }
    } catch {
        status.textContent = 'Failed to connect';
        status.className = 'status-msg error';
    }
});

function addForwardingItem(email) {
    const li = document.createElement('li');
    li.className = 'fwd-email-item';
    li.dataset.email = email;
    li.innerHTML = '<span>' + escapeHtml(email) + '</span>'
        + '<button class="fwd-remove-btn" aria-label="Remove ' + escapeHtml(email) + '">'
        + '<i class="fas fa-times"></i></button>';
    li.querySelector('.fwd-remove-btn').addEventListener('click', () => removeForwardingItem(li, email));
    document.getElementById('fwd-email-list').appendChild(li);
}

function removeForwardingItem(li, email) {
    fetch('/api/user/forwarding-emails/' + encodeURIComponent(email), {method: 'DELETE'})
        .then(r => r.json())
        .then(data => {
            if (data.success) li.remove();
        });
}

document.querySelectorAll('.fwd-remove-btn').forEach(btn => {
    const li = btn.closest('.fwd-email-item');
    btn.addEventListener('click', () => removeForwardingItem(li, li.dataset.email));
});
