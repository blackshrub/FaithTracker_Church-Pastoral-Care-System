# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.x.x   | :white_check_mark: |
| 1.x.x   | :x:                |

## Reporting a Vulnerability

We take the security of FaithTracker seriously. If you believe you have found a security vulnerability, please report it to us responsibly.

### How to Report

1. **Do NOT** create a public GitHub issue for security vulnerabilities
2. Email your findings to: security@faithtracker.church (or contact the repository maintainers directly)
3. Include as much detail as possible:
   - Type of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- We will acknowledge receipt within 48 hours
- We will provide a detailed response within 7 days
- We will work with you to understand and validate the issue
- We will keep you informed about our progress
- We will credit you in our release notes (unless you prefer anonymity)

## Security Measures

FaithTracker implements the following security measures:

### Authentication & Authorization

- **JWT-based authentication** with secure token handling
- **Bcrypt password hashing** (cost factor: 12)
- **Role-based access control** (full_admin, campus_admin, pastor)
- **Rate limiting** on login endpoints (5 attempts/minute)
- **Session timeout** after 24 hours of inactivity

### Data Protection

- **Multi-tenancy isolation** - All queries filter by `church_id`
- **Fernet encryption** for sensitive API credentials
- **No plaintext passwords** stored in the database
- **Input validation** using Pydantic models

### API Security

- **CORS** configured for specific origins only
- **Security headers** (OWASP recommended):
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
  - `X-XSS-Protection: 1; mode=block`
  - `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`
  - `Strict-Transport-Security` (HSTS) in production
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: geolocation=(), microphone=(), camera=()`

### File Upload Security

- **File type validation** - Only allowed MIME types accepted
- **File size limits** - 10 MB for images, 5 MB for CSV imports
- **Image processing** - Files are re-processed (not stored as-is)

### Infrastructure

- **HTTPS only** in production (via Angie/Let's Encrypt)
- **HTTP to HTTPS redirect**
- **MongoDB authentication** required
- **Environment variables** for sensitive configuration
- **No secrets in code** - All credentials via environment

### Webhook Security

- **HMAC-SHA256 signature verification** for webhook payloads
- **Replay attack prevention** through timestamp validation

## Security Best Practices for Operators

### Environment Configuration

1. **Change default secrets**:
   ```bash
   JWT_SECRET=<generate-strong-random-string>
   ENCRYPTION_KEY=<generate-base64-fernet-key>
   ```

2. **Use strong database passwords**:
   ```bash
   MONGO_ROOT_PASSWORD=<strong-random-password>
   ```

3. **Restrict CORS origins**:
   ```bash
   ALLOWED_ORIGINS=https://your-domain.com
   ```

### Server Hardening

1. Keep Docker and all dependencies updated
2. Use firewall rules to restrict access
3. Enable MongoDB authentication
4. Regular security updates for host OS
5. Monitor access logs for suspicious activity

### Backup Security

1. Encrypt database backups
2. Store backups in a secure, separate location
3. Test backup restoration regularly
4. Implement backup rotation policy

## Vulnerability Disclosure Timeline

- **Day 0**: Vulnerability reported
- **Day 1-2**: Acknowledgment sent
- **Day 3-7**: Initial assessment and response
- **Day 8-30**: Fix development (for critical: 7 days)
- **Day 31-45**: Testing and deployment
- **Day 46+**: Public disclosure (coordinated with reporter)

## Security Contact

For security-related inquiries, contact the repository maintainers through GitHub or the provided security email.

---

*Last updated: November 2024*
