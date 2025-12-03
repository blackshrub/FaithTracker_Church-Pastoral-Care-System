# Deployment Guide

This guide covers deploying FaithTracker to production environments.

## Prerequisites

- Docker & Docker Compose v2.0+
- Domain name with DNS configured
- SSL certificates (auto-provisioned via Let's Encrypt)
- At least 4GB RAM, 2 CPU cores

## Quick Start (Docker)

### 1. Clone and Configure

```bash
git clone https://github.com/your-org/FaithTracker.git
cd FaithTracker

# Copy environment template
cp .env.example .env
```

### 2. Configure Environment Variables

Edit `.env` with your production values:

```bash
# Required
DOMAIN=faithtracker.yourdomain.com
ACME_EMAIL=admin@yourdomain.com
JWT_SECRET=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
MONGO_ROOT_PASSWORD=$(openssl rand -hex 16)

# Optional
WHATSAPP_GATEWAY_URL=http://your-whatsapp-gateway:3001
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=secure-initial-password
```

### 3. Create Required Files

```bash
# Create Let's Encrypt storage
mkdir -p letsencrypt
touch letsencrypt/acme.json
chmod 600 letsencrypt/acme.json

# Create MongoDB init script (optional)
mkdir -p docker
cat > docker/mongo-init.js << 'EOF'
// Custom MongoDB initialization if needed
EOF
```

### 4. Deploy

```bash
# Build and start all services
docker compose up -d --build

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### 5. Verify Deployment

```bash
# Check health endpoints
curl https://api.yourdomain.com/health
curl https://yourdomain.com/health

# Check SSL certificate
openssl s_client -connect yourdomain.com:443 -servername yourdomain.com
```

## Architecture Overview

```
                    ┌─────────────┐
                    │   Traefik   │
                    │  (Reverse   │
                    │   Proxy)    │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │  Frontend   │ │   Backend   │ │  Dashboard  │
    │   (Nginx)   │ │  (Granian)  │ │  (Traefik)  │
    └─────────────┘ └──────┬──────┘ └─────────────┘
                           │
                    ┌──────▼──────┐
                    │   MongoDB   │
                    │   (7.0)     │
                    └─────────────┘
```

## Resource Requirements

| Service   | CPU Limit | Memory Limit | Notes                    |
|-----------|-----------|--------------|--------------------------|
| MongoDB   | 2 cores   | 2 GB         | Adjust based on data size|
| Backend   | 2 cores   | 1 GB         | Handles API + scheduler  |
| Frontend  | 1 core    | 256 MB       | Static files only        |
| Traefik   | 0.5 core  | 128 MB       | Reverse proxy            |

## Updating

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker compose down
docker compose up -d --build

# Run migrations (if needed)
docker compose exec backend python migrate.py
```

## Backup & Restore

### Backup MongoDB

```bash
# Create backup
docker compose exec mongo mongodump \
  --username admin \
  --password $MONGO_ROOT_PASSWORD \
  --authenticationDatabase admin \
  --db faithtracker \
  --out /backup

# Copy backup to host
docker cp faithtracker-mongo:/backup ./backup-$(date +%Y%m%d)
```

### Restore MongoDB

```bash
# Copy backup to container
docker cp ./backup faithtracker-mongo:/restore

# Restore
docker compose exec mongo mongorestore \
  --username admin \
  --password $MONGO_ROOT_PASSWORD \
  --authenticationDatabase admin \
  --db faithtracker \
  /restore/faithtracker
```

## Troubleshooting

### Services won't start

```bash
# Check logs
docker compose logs backend
docker compose logs mongo

# Verify environment
docker compose config

# Check disk space
df -h
```

### SSL certificate issues

```bash
# Check acme.json permissions
ls -la letsencrypt/acme.json  # Should be 600

# View Traefik logs
docker compose logs traefik | grep -i cert

# Force certificate renewal
rm letsencrypt/acme.json
touch letsencrypt/acme.json
chmod 600 letsencrypt/acme.json
docker compose restart traefik
```

### Database connection issues

```bash
# Test MongoDB connection
docker compose exec mongo mongosh \
  --username admin \
  --password $MONGO_ROOT_PASSWORD \
  --authenticationDatabase admin

# Check network
docker network inspect faithtracker-network
```

### High memory usage

```bash
# Check container stats
docker stats

# Adjust limits in docker-compose.yml under deploy.resources
```

## Security Checklist

- [ ] Change default passwords
- [ ] Enable firewall (allow only 80, 443)
- [ ] Configure backup schedule
- [ ] Set up monitoring/alerting
- [ ] Review Traefik dashboard access
- [ ] Enable rate limiting
- [ ] Configure CORS properly

## Monitoring

### Health Checks

- Backend: `https://api.yourdomain.com/health`
- Frontend: `https://yourdomain.com/health`
- MongoDB: `docker compose exec mongo mongosh --eval "db.adminCommand('ping')"`

### Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend

# Last 100 lines
docker compose logs --tail=100 backend
```

## Manual Deployment (Without Docker)

See [CLAUDE.md](CLAUDE.md) for manual setup instructions including:
- Python virtual environment setup
- MongoDB installation
- Nginx configuration
- Systemd service files
