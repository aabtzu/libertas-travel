"""Generate the user profile page HTML."""

from __future__ import annotations

import html as html_mod
from typing import Any

from agents.common.templates import get_nav_html


def _esc(text: str) -> str:
    return html_mod.escape(str(text)) if text else ""


def generate_profile_page(
    profile_data: dict[str, Any], forwarding_emails: list[str] | None = None
) -> str:
    """Build the profile page with editable writing style fields."""
    nav = get_nav_html("")

    style_profile = profile_data.get("style_profile", {})
    samples_text = _esc(
        profile_data.get("writing_samples", "") or profile_data.get("samples_preview", "")
    )

    # Pre-fill fields
    tone = _esc(style_profile.get("tone", ""))
    sentence_style = _esc(style_profile.get("sentence_style", ""))
    vocabulary = _esc(", ".join(style_profile.get("vocabulary", [])))
    emphasis = _esc(style_profile.get("emphasis", ""))
    perspective = _esc(style_profile.get("perspective", ""))
    quirks = _esc(
        ", ".join(style_profile.get("quirks", []))
        if isinstance(style_profile.get("quirks"), list)
        else style_profile.get("quirks", "")
    )
    rules = _esc(style_profile.get("rules", ""))
    user_notes = _esc(profile_data.get("user_notes", ""))
    has_profile = "true" if style_profile else "false"
    forwarding_emails = forwarding_emails or []
    forwarding_items_html = "".join(
        f'<li class="fwd-email-item" data-email="{_esc(e)}">'
        f"<span>{_esc(e)}</span>"
        f'<button class="fwd-remove-btn" aria-label="Remove {_esc(e)}">'
        f'<i class="fas fa-times"></i></button></li>'
        for e in forwarding_emails
    )
    forwarding_list_html = (
        f'<ul id="fwd-email-list">{forwarding_items_html}</ul>'
        if forwarding_emails
        else '<ul id="fwd-email-list"></ul>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Profile - Libertas</title>
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <link rel="stylesheet" href="/static/css/tokens.css?v=1">
    <link rel="stylesheet" href="/app-config.css">
    <link rel="stylesheet" href="/static/css/main.css?v=17">
    <link rel="stylesheet" href="/static/css/main-mobile-modal.css?v=2">
    <style>
        .profile-hero {{
            background: #1a1a2e;
            color: white;
            padding: 48px 40px;
            text-align: center;
        }}
        .profile-hero h1 {{ font-size: 2rem; font-weight: 300; letter-spacing: 1px; }}
        .profile-content {{
            max-width: 700px;
            margin: 0 auto;
            padding: 40px 24px;
        }}
        .profile-section {{
            background: white;
            border-radius: 14px;
            padding: 28px;
            margin-bottom: 24px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        }}
        .profile-section h2 {{
            font-size: 1.1rem;
            color: #667eea;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .field-group {{
            margin-bottom: 16px;
        }}
        .field-group label {{
            display: block;
            font-size: 0.8rem;
            font-weight: 600;
            color: #555;
            margin-bottom: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .field-group input,
        .field-group textarea {{
            width: 100%;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 10px 12px;
            font-size: 0.9rem;
            font-family: inherit;
            outline: none;
            resize: vertical;
        }}
        .field-group input:focus,
        .field-group textarea:focus {{ border-color: #667eea; }}
        .field-hint {{
            font-size: 0.75rem;
            color: #999;
            margin-top: 4px;
        }}
        .btn-primary {{
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 0.9rem;
            cursor: pointer;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }}
        .btn-primary:hover {{ background: #5a6fd6; }}
        .btn-primary:disabled {{ opacity: 0.6; cursor: wait; }}
        .btn-secondary {{
            background: white;
            color: #667eea;
            border: 1px solid #667eea;
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 0.85rem;
            cursor: pointer;
            font-weight: 600;
        }}
        .btn-secondary:hover {{ background: #f0f2ff; }}
        .profile-actions {{
            display: flex;
            gap: 12px;
            margin-top: 20px;
        }}
        .status-msg {{
            font-size: 0.85rem;
            margin-top: 8px;
        }}
        .status-msg.success {{ color: #4caf50; }}
        .status-msg.error {{ color: #e74c3c; }}
        .extract-section {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 20px;
        }}
        #fwd-email-list {{
            list-style: none;
            padding: 0;
            margin: 0 0 16px;
        }}
        .fwd-email-item {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 12px;
            border: 1px solid #e8e8f0;
            border-radius: 8px;
            margin-bottom: 6px;
            font-size: 0.9rem;
        }}
        .fwd-remove-btn {{
            background: none;
            border: none;
            color: #999;
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.85rem;
        }}
        .fwd-remove-btn:hover {{ color: #e74c3c; background: #fff0f0; }}
        .fwd-add-row {{
            display: flex;
            gap: 8px;
        }}
        .fwd-add-row input {{
            flex: 1;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 10px 12px;
            font-size: 0.9rem;
            outline: none;
        }}
        .fwd-add-row input:focus {{ border-color: #667eea; }}
    </style>
</head>
<body>
    {nav}

    <div class="profile-hero">
        <h1><i class="fas fa-user"></i> My Profile</h1>
    </div>

    <div class="profile-content">

        <!-- Writing Style -->
        <div class="profile-section">
            <h2><i class="fas fa-pen-fancy"></i> Writing Voice</h2>
            <p style="color:#666;font-size:0.9rem;margin-bottom:16px">
                Your write-ups will match this style. Extract from samples or edit directly.
            </p>

            <div class="extract-section">
                <div class="field-group">
                    <label>Writing Samples</label>
                    <textarea id="style-samples" rows="6" placeholder="Paste emails, messages, or any writing that sounds like you...">{samples_text}</textarea>
                    <div class="field-hint">The more you paste, the better the style match</div>
                </div>
                <button class="btn-secondary" id="extract-btn">
                    <i class="fas fa-magic"></i> Extract My Style
                </button>
                <span class="status-msg" id="extract-status"></span>
            </div>

            <div id="style-fields">
                <div class="field-group">
                    <label>Tone</label>
                    <input type="text" id="style-tone" value="{tone}" placeholder="e.g. casual, lowercase, direct">
                    <div class="field-hint">Overall feel, casual vs formal, warm vs matter-of-fact</div>
                </div>
                <div class="field-group">
                    <label>Sentence Style</label>
                    <input type="text" id="style-sentences" value="{sentence_style}" placeholder="e.g. short and punchy, stream-of-consciousness">
                </div>
                <div class="field-group">
                    <label>Vocabulary / Shortcuts</label>
                    <input type="text" id="style-vocab" value="{vocabulary}" placeholder='e.g. w/, go-to, solid, def'>
                    <div class="field-hint">Distinctive words or abbreviations you use</div>
                </div>
                <div class="field-group">
                    <label>What You Emphasize</label>
                    <input type="text" id="style-emphasis" value="{emphasis}" placeholder="e.g. practical tips, personal experience, food details">
                </div>
                <div class="field-group">
                    <label>Perspective</label>
                    <input type="text" id="style-perspective" value="{perspective}" placeholder="e.g. first person plural (we/us), second person (you)">
                </div>
                <div class="field-group">
                    <label>Quirks / Other Patterns</label>
                    <textarea id="style-quirks" rows="2" placeholder="e.g. uses dashes heavily, ends conversationally, no capitalization">{quirks}</textarea>
                </div>
                <div class="field-group">
                    <label>Rules</label>
                    <textarea id="style-rules" rows="3" placeholder="Strict rules the AI must follow, e.g.&#10;- never end with filler like 'worth it' or 'you earned it'&#10;- always include links when available">{rules}</textarea>
                    <div class="field-hint">These are enforced strictly, use for things the AI keeps getting wrong</div>
                </div>
            </div>

            <div class="profile-actions">
                <button class="btn-primary" id="save-style-btn">
                    <i class="fas fa-save"></i> Save Style
                </button>
                <span class="status-msg" id="save-status"></span>
            </div>
        </div>

        <!-- User Notes -->
        <div class="profile-section">
            <h2><i class="fas fa-sticky-note"></i> Notes for AI</h2>
            <div class="field-group">
                <textarea id="user-notes" rows="3" placeholder="Anything else the AI should know about your preferences, dietary restrictions, travel style, etc.">{user_notes}</textarea>
                <div class="field-hint">Free-form notes injected into write-up and recommendation context</div>
            </div>
        </div>

        <!-- Forwarding Addresses -->
        <div class="profile-section">
            <h2><i class="fas fa-envelope"></i> Forwarding Addresses</h2>
            <p style="color:#666;font-size:0.9rem;margin-bottom:12px">
                Forward booking emails to Libertas from any of these addresses.
            </p>
            {forwarding_list_html}
            <div class="fwd-add-row">
                <input type="email" id="fwd-email-input" placeholder="email@example.com">
                <button class="btn-secondary" id="fwd-add-btn">
                    <i class="fas fa-plus"></i> Add
                </button>
            </div>
            <span class="status-msg" id="fwd-status"></span>
        </div>

        <!-- Change Password -->
        <div class="profile-section">
            <h2><i class="fas fa-lock"></i> Change Password</h2>
            <div class="field-group">
                <label>Current Password</label>
                <input type="password" id="pw-current" autocomplete="current-password">
            </div>
            <div class="field-group">
                <label>New Password</label>
                <input type="password" id="pw-new" autocomplete="new-password">
            </div>
            <div class="field-group">
                <label>Confirm New Password</label>
                <input type="password" id="pw-confirm" autocomplete="new-password">
            </div>
            <div class="profile-actions">
                <button class="btn-primary" id="change-pw-btn">
                    <i class="fas fa-key"></i> Change Password
                </button>
                <span class="status-msg" id="change-pw-status"></span>
            </div>
        </div>

    </div>

    <script src="/app-config.js"></script>
    <script src="/static/js/main.js?v=7"></script>
    <script>
        const hasProfile = {has_profile};

        document.getElementById('extract-btn').addEventListener('click', async () => {{
            const samples = document.getElementById('style-samples').value.trim();
            if (samples.length < 50) {{
                document.getElementById('extract-status').textContent = 'Paste more text, at least a few sentences';
                document.getElementById('extract-status').className = 'status-msg error';
                return;
            }}

            const btn = document.getElementById('extract-btn');
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';
            document.getElementById('extract-status').textContent = '';

            try {{
                const res = await fetch('/api/user/extract-style', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{samples}}),
                }});
                const data = await res.json();
                if (data.success && data.profile) {{
                    const p = data.profile;
                    document.getElementById('style-tone').value = p.tone || '';
                    document.getElementById('style-sentences').value = p.sentence_style || '';
                    document.getElementById('style-vocab').value = (p.vocabulary || []).join(', ');
                    document.getElementById('style-emphasis').value = p.emphasis || '';
                    document.getElementById('style-perspective').value = p.perspective || '';
                    document.getElementById('style-quirks').value = Array.isArray(p.quirks) ? p.quirks.join(', ') : (p.quirks || '');
                    document.getElementById('extract-status').textContent = 'Style extracted, review and save below';
                    document.getElementById('extract-status').className = 'status-msg success';
                }} else {{
                    document.getElementById('extract-status').textContent = data.error || 'Extraction failed';
                    document.getElementById('extract-status').className = 'status-msg error';
                }}
            }} catch {{
                document.getElementById('extract-status').textContent = 'Failed to connect';
                document.getElementById('extract-status').className = 'status-msg error';
            }}
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-magic"></i> Extract My Style';
        }});

        document.getElementById('save-style-btn').addEventListener('click', async () => {{
            const profile = {{
                tone: document.getElementById('style-tone').value.trim(),
                sentence_style: document.getElementById('style-sentences').value.trim(),
                vocabulary: document.getElementById('style-vocab').value.split(',').map(s => s.trim()).filter(s => s),
                emphasis: document.getElementById('style-emphasis').value.trim(),
                perspective: document.getElementById('style-perspective').value.trim(),
                quirks: document.getElementById('style-quirks').value.trim(),
                rules: document.getElementById('style-rules').value.trim(),
            }};

            const samples = document.getElementById('style-samples').value.trim();
            const btn = document.getElementById('save-style-btn');
            btn.disabled = true;

            try {{
                // Save directly, the extract-style endpoint stores it,
                // but we also need to save edited profiles
                const res = await fetch('/api/user/save-profile', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        style_profile: profile,
                        writing_samples: samples,
                        samples_preview: samples.substring(0, 200),
                        user_notes: document.getElementById('user-notes').value.trim(),
                    }}),
                }});
                const data = await res.json();
                if (data.success) {{
                    document.getElementById('save-status').textContent = 'Style saved!';
                    document.getElementById('save-status').className = 'status-msg success';
                }} else {{
                    document.getElementById('save-status').textContent = data.error || 'Save failed';
                    document.getElementById('save-status').className = 'status-msg error';
                }}
            }} catch {{
                document.getElementById('save-status').textContent = 'Failed to save';
                document.getElementById('save-status').className = 'status-msg error';
            }}
            btn.disabled = false;
        }});

        document.getElementById('change-pw-btn').addEventListener('click', async () => {{
            const btn = document.getElementById('change-pw-btn');
            const status = document.getElementById('change-pw-status');
            const body = {{
                current_password: document.getElementById('pw-current').value,
                new_password: document.getElementById('pw-new').value,
                confirm_password: document.getElementById('pw-confirm').value,
            }};
            btn.disabled = true;
            status.textContent = '';
            try {{
                const res = await fetch('/api/user/change-password', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(body),
                }});
                const data = await res.json();
                if (data.success) {{
                    status.textContent = 'Password changed!';
                    status.className = 'status-msg success';
                    document.getElementById('pw-current').value = '';
                    document.getElementById('pw-new').value = '';
                    document.getElementById('pw-confirm').value = '';
                }} else {{
                    status.textContent = data.error || 'Failed to change password';
                    status.className = 'status-msg error';
                }}
            }} catch {{
                status.textContent = 'Failed to connect';
                status.className = 'status-msg error';
            }}
            btn.disabled = false;
        }});

        // Forwarding email add
        document.getElementById('fwd-add-btn').addEventListener('click', async () => {{
            const input = document.getElementById('fwd-email-input');
            const email = input.value.trim().toLowerCase();
            const status = document.getElementById('fwd-status');
            if (!email || !email.includes('@')) {{
                status.textContent = 'Enter a valid email address';
                status.className = 'status-msg error';
                return;
            }}
            status.textContent = '';
            try {{
                const res = await fetch('/api/user/forwarding-emails', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{email}}),
                }});
                const data = await res.json();
                if (data.success) {{
                    addForwardingItem(data.email);
                    input.value = '';
                    status.textContent = 'Address added';
                    status.className = 'status-msg success';
                }} else {{
                    status.textContent = data.error || 'Failed to add';
                    status.className = 'status-msg error';
                }}
            }} catch {{
                status.textContent = 'Failed to connect';
                status.className = 'status-msg error';
            }}
        }});

        function addForwardingItem(email) {{
            const li = document.createElement('li');
            li.className = 'fwd-email-item';
            li.dataset.email = email;
            li.innerHTML = '<span>' + escapeHtml(email) + '</span>'
                + '<button class="fwd-remove-btn" aria-label="Remove ' + escapeHtml(email) + '">'
                + '<i class="fas fa-times"></i></button>';
            li.querySelector('.fwd-remove-btn').addEventListener('click', () => removeForwardingItem(li, email));
            document.getElementById('fwd-email-list').appendChild(li);
        }}

        function removeForwardingItem(li, email) {{
            fetch('/api/user/forwarding-emails/' + encodeURIComponent(email), {{method: 'DELETE'}})
                .then(r => r.json())
                .then(data => {{
                    if (data.success) li.remove();
                }});
        }}

        document.querySelectorAll('.fwd-remove-btn').forEach(btn => {{
            const li = btn.closest('.fwd-email-item');
            btn.addEventListener('click', () => removeForwardingItem(li, li.dataset.email));
        }});

    </script>
</body>
</html>"""
