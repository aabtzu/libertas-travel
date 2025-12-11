# Feature: Email Import via Mailgun Webhook

## Summary
Allow users to forward booking confirmation emails to import trips automatically.

## Approach
Use Mailgun inbound email webhook - users get unique address like `import+TOKEN@mail.libertas-travel.com`

## Implementation Plan

### Phase 1: Mailgun Setup (Manual)
- Create Mailgun account, add domain (or subdomain like `mail.libertas-travel.com`)
- Configure MX/TXT DNS records
- Create inbound route forwarding to `https://libertas-travel.onrender.com/api/email-import`

### Phase 2: Backend
- Add `/api/email-import` POST webhook endpoint to `server.py`
- Create `agents/itinerary/email_parser.py` for parsing forwarded emails
- Add `import_token` column to users table (VARCHAR(32) UNIQUE)
- Validate Mailgun webhook signature for security

**Webhook receives:**
```python
{
    "sender": "user@gmail.com",
    "recipient": "import+TOKEN@mail.libertas-travel.com",
    "subject": "Fwd: Your Flight Confirmation",
    "body-plain": "...",
    "body-html": "...",
    "attachments": [...]
}
```

### Phase 3: User Experience
- Show unique import address in user settings/profile
- "Copy to clipboard" button
- Instructions: "Forward booking emails to this address"
- Pending/completed import notifications on My Trips page

## Security Considerations
- Webhook signature verification (Mailgun signs requests)
- Unique per-user tokens (prevent guessing)
- Rate limiting
- Content scanning for suspicious attachments

## Cost Estimate
- Mailgun free tier: 5K emails/month for 3 months
- After: ~$0.80 per 1,000 emails
- Typical usage: 10-50 emails/user/year = essentially free
