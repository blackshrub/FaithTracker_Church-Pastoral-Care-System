# FaithTracker Pastoral Care System

A modern pastoral care management system for churches. Track birthdays, hospital visits, grief support, financial aid, and more - all from one real-time dashboard.

![Status](https://img.shields.io/badge/status-production--ready-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

## Quick Start

### Prerequisites

- Linux server with Docker installed
- Domain name pointing to your server (A records for `domain.com` and `api.domain.com`)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/tesarfrr/FaithTracker_Church-Pastoral-Care-System.git
cd FaithTracker_Church-Pastoral-Care-System

# 2. Copy and configure environment
cp .env.example .env
nano .env  # Edit with your domain, email, passwords

# 3. Start services
make up

# 4. Check status
make health
```

Your app will be live at:
- **Web App**: `https://yourdomain.com`
- **API Docs**: `https://api.yourdomain.com/docs`

## Common Commands

```bash
make help              # Show all commands
make up                # Start all services
make down              # Stop all services
make restart           # Restart all services
make logs              # View all logs
make status            # Show service status

# Building
make build             # Build with cache (fast, for code changes)
make rebuild           # Build without cache (for dependency changes)

# Individual services
make restart-backend   # Restart backend only
make logs-backend      # View backend logs

# Database
make backup            # Backup MongoDB
make shell-db          # Open MongoDB shell
make clear-cache       # Clear dashboard cache

# Deployment
make deploy            # Full: backup → rebuild → restart → health check
make quick-deploy      # Fast: build (cached) → restart
```

## Updating

```bash
git pull origin main
make rebuild           # Use rebuild if dependencies changed
make up
```

## Features

| Feature | Description |
|---------|-------------|
| **Birthday Tracking** | Automatic reminders with age calculation |
| **Grief Support** | 6-stage follow-up timeline (7 days → 1 year) |
| **Hospital Visits** | Track hospital stays with follow-ups |
| **Financial Aid** | One-time and recurring aid scheduling |
| **Live Activity Feed** | Real-time team updates via SSE |
| **Offline Support** | Works without internet, syncs when online |
| **Multi-Campus** | Data isolation with role-based access |
| **Reports & Analytics** | PDF reports, CSV exports, trend analysis |

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Backend** | FastAPI, MongoDB 7.0, Granian (Rust ASGI) |
| **Frontend** | React 19, Vite, TanStack Query, Tailwind |
| **Infrastructure** | Docker, Angie (nginx fork), HTTP/3, Let's Encrypt |

## Project Structure

```
FaithTracker/
├── backend/           # FastAPI backend
├── frontend/          # React frontend
├── mobile/            # React Native app (Expo)
├── docker/            # Docker configs
├── docs/              # Documentation
├── scripts/           # Utility scripts
├── docker-compose.yml
├── Makefile           # Docker commands
└── CLAUDE.md          # AI assistant guide
```

## Documentation

See the `docs/` folder for detailed documentation:

- [API Documentation](docs/API_DOCUMENTATION.md)
- [Features](docs/FEATURES.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Webhook Integration](docs/WEBHOOK_INTEGRATION.md)
- [Security](docs/SECURITY.md)
- [Contributing](docs/CONTRIBUTING.md)
- [Changelog](docs/CHANGELOG.md)

## Troubleshooting

### Check service health
```bash
make health
```

### View logs
```bash
make logs           # All services
make logs-backend   # Backend only
```

### SSL certificate issues
Wait 1-2 minutes after first start. Let's Encrypt needs time to issue certificates.

### Clear stale cache
```bash
make clear-cache
```

## License

MIT License - Use freely for your church!

---

**Built with love for churches worldwide**
