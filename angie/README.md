# FaithTracker - Angie Web Server Configuration

This directory contains the Angie (nginx fork) configuration for FaithTracker. Angie runs at the **host level** as a reverse proxy, handling SSL termination, rate limiting, and security headers for the Dockerized application services.

## Why Angie?

[Angie](https://angie.software/) is a drop-in nginx replacement with additional features:
- **Built-in HTTP/3 (QUIC)** - No extra modules needed
- **Built-in Brotli compression** - Better compression than gzip
- **Active development** - Regular security updates
- **100% nginx compatible** - Existing configs work as-is

## Architecture

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    Host System                          │
                    │                                                         │
Internet ──────────►│  Angie (Port 80/443)                                   │
                    │    │                                                   │
                    │    ├── https://domain.com ────► Docker: frontend:80    │
                    │    │                                                   │
                    │    └── https://api.domain.com ► Docker: backend:8001   │
                    │                                                         │
                    │  ┌─────────────────────────────────────────────────┐   │
                    │  │              Docker Compose                      │   │
                    │  │                                                  │   │
                    │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │   │
                    │  │  │ Frontend │  │ Backend  │  │ MongoDB  │      │   │
                    │  │  │  :8080   │  │  :8001   │  │  :27017  │      │   │
                    │  │  └──────────┘  └──────────┘  └──────────┘      │   │
                    │  │                                                  │   │
                    │  └─────────────────────────────────────────────────┘   │
                    │                                                         │
                    └─────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Angie (first time only)

```bash
sudo ./angie/install.sh
```

This will:
- Add Angie repository
- Install Angie with Brotli module
- Install Certbot
- Copy configuration files
- Start Angie service

### 2. Configure Environment

Make sure your `.env` file has these settings:

```bash
DOMAIN=yourdomain.com
ACME_EMAIL=admin@yourdomain.com
```

### 3. Set Up DNS

Point your domain to the server:

| Record Type | Name | Value |
|-------------|------|-------|
| A | yourdomain.com | [server IP] |
| A | api.yourdomain.com | [server IP] |

### 4. Get SSL Certificates

```bash
sudo ./angie/setup-ssl.sh
```

This will:
- Verify DNS records
- Obtain Let's Encrypt certificates
- Generate final Angie configuration
- Reload Angie

### 5. Start Docker Services

```bash
docker compose up -d
```

### 6. Verify Deployment

```bash
./scripts/validate-deployment.sh
```

## Directory Structure

```
angie/
├── README.md                           # This file
├── angie.conf                          # Main configuration
├── conf.d/
│   ├── faithtracker.conf.template      # Site config template (uses ${DOMAIN})
│   ├── ssl.conf                        # SSL/TLS settings
│   ├── security-headers.conf           # OWASP security headers
│   └── rate-limit.conf                 # Rate limiting zones
├── snippets/
│   ├── proxy-headers.conf              # Common proxy headers
│   └── ssl-params.conf                 # SSL parameters
├── install.sh                          # Installation script
├── setup-ssl.sh                        # SSL certificate setup
└── generate-config.sh                  # Config generation from .env
```

## Configuration Files

### Main Config (`angie.conf`)

The main configuration file includes:
- Worker processes and connections
- Logging format
- Gzip compression
- **Brotli compression** (Angie built-in)
- Upstream definitions (frontend, backend)

### Site Config (`faithtracker.conf.template`)

This template uses `${DOMAIN}` placeholder. It's processed by `envsubst` to generate the final config.

Features:
- **HTTP/3 (QUIC)** on port 443/UDP
- **HTTP → HTTPS redirect**
- **Rate limiting** per endpoint type
- **CORS headers** for API
- **SSE streaming** support (no compression, no buffering)

### Security Headers (`security-headers.conf`)

Implements OWASP recommended headers:
- HSTS (1 year, preload)
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- X-XSS-Protection
- Referrer-Policy
- Permissions-Policy
- X-Robots-Tag (noindex for private app)

### Rate Limiting (`rate-limit.conf`)

Three zones for different endpoints:
- `api`: 10 req/s, burst 100 (general API)
- `auth`: 3 req/s, burst 10 (login/register)
- `frontend`: 5 req/s, burst 50 (static assets)

## Management Commands

### Using Make (Recommended)

```bash
make angie-status        # Check Angie status
make angie-reload        # Reload configuration
make angie-test          # Test configuration syntax
make angie-logs          # View Angie logs

make ssl-renew           # Force certificate renewal
```

### Direct Commands

```bash
# Check status
sudo systemctl status angie

# Reload (after config changes)
sudo systemctl reload angie

# Test configuration
sudo angie -t

# View logs
sudo journalctl -u angie -f

# View access log
sudo tail -f /var/log/angie/access.log
```

## SSL Certificate Management

### Automatic Renewal

Certbot automatically renews certificates via systemd timer:

```bash
# Check renewal timer
systemctl status certbot.timer

# Test renewal (dry-run)
sudo certbot renew --dry-run

# Force renewal
sudo certbot renew --force-renewal
```

### Certificate Location

```
/etc/letsencrypt/live/${DOMAIN}/
├── fullchain.pem   # Certificate + intermediate
├── privkey.pem     # Private key
├── chain.pem       # Intermediate certificate
└── cert.pem        # Certificate only
```

## Regenerating Configuration

If you change the domain in `.env`:

```bash
# Generate new config from template
./angie/generate-config.sh

# Or with dry-run to preview
./angie/generate-config.sh --dry-run

# Then reload Angie
sudo systemctl reload angie
```

## Troubleshooting

### Angie Won't Start

```bash
# Check configuration syntax
sudo angie -t

# Check for port conflicts
sudo netstat -tlnp | grep -E ':80|:443'

# View detailed logs
sudo journalctl -u angie -n 100
```

### SSL Certificate Issues

```bash
# Check certificate status
sudo certbot certificates

# Check certificate dates
echo | openssl s_client -servername $DOMAIN -connect $DOMAIN:443 2>/dev/null | openssl x509 -noout -dates

# Force renewal
sudo certbot renew --force-renewal
```

### 502 Bad Gateway

This usually means Docker services aren't running:

```bash
# Check Docker services
docker compose ps

# Start services
docker compose up -d

# Check backend health
curl http://127.0.0.1:8001/health
```

### Rate Limiting Issues

If legitimate requests are being rate-limited:

1. Edit `/etc/angie/conf.d/rate-limit.conf`
2. Adjust the `rate` or `burst` values
3. Reload: `sudo systemctl reload angie`

### CORS Issues

If CORS errors appear in browser:

1. Check that `DOMAIN` in `.env` matches the request origin
2. Regenerate config: `./angie/generate-config.sh`
3. Reload: `sudo systemctl reload angie`

## Migration from Traefik

This setup replaces Traefik with host-level Angie. Key differences:

| Feature | Traefik | Angie |
|---------|---------|-------|
| SSL Certificates | Built-in ACME | Certbot |
| Configuration | Docker labels | Config files |
| Rate Limiting | Middleware | nginx directives |
| HTTP/3 | Built-in | Built-in |
| Compression | Middleware | Built-in |

### Rollback to Traefik

If you need to rollback:

```bash
# Stop Angie
sudo systemctl stop angie

# Restore Traefik docker-compose
git checkout docker-compose.yml

# Start with Traefik
docker compose up -d
```

## Performance Notes

- **Brotli compression**: 15-25% smaller than gzip
- **HTTP/3 (QUIC)**: Faster on mobile/unstable connections
- **Keepalive connections**: Reduces upstream connection overhead
- **Connection pooling**: 32 connections to backend, 16 to frontend
