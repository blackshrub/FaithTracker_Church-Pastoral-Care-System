# FaithTracker Pastoral Care System

**FaithTracker** is a comprehensive, multi-tenant pastoral care management system designed for churches. It enables pastoral care departments to efficiently monitor, schedule, and manage all interactions with church members across multiple campuses.

![Status](https://img.shields.io/badge/status-production--ready-brightgreen)
![Platform](https://img.shields.io/badge/platform-FastAPI%20%2B%20React-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.9+-blue)
![React](https://img.shields.io/badge/react-19-61DAFB)

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Deployment](#deployment)
  - [Docker Deployment (Recommended)](#docker-deployment-recommended)
  - [Manual Installation](#manual-installation)
- [Domain & DNS Configuration](#domain--dns-configuration)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

FaithTracker solves the complex challenge of managing pastoral care across multiple church campuses:

- **Multi-Tenant Architecture**: Complete data isolation between campuses with role-based access control
- **Task-Oriented Dashboards**: Intelligent task categorization (Today, Overdue, Upcoming)
- **Comprehensive Event Tracking**: Birthdays, grief support, financial aid, hospital visits, and more
- **Smart Scheduling**: Flexible recurring schedules with timezone-aware notifications
- **Member Engagement Monitoring**: Track and visualize member participation over time
- **Bilingual Interface**: Full English and Indonesian (Bahasa Indonesia) support
- **Complete Accountability**: Track WHO did WHAT on WHICH member (13 action types logged)
- **Enterprise API Sync**: Bi-directional sync with external systems (polling + webhooks)

---

## Key Features

### Multi-Tenant & Role-Based Access
- **Full Administrator**: Access all campuses, switch views dynamically
- **Campus Administrator**: Manage a single campus with full control
- **Pastor Role**: Regular pastoral care staff with task management

### Member Management
- Complete CRUD operations for church members
- Photo upload with automatic optimization (thumbnail/medium/large)
- Family grouping and relationship tracking
- Engagement status monitoring (Active, At Risk, Disconnected)
- Bulk import from CSV with field mapping

### Care Event System
| Event Type | Description |
|------------|-------------|
| Birthday | Automated tracking with age calculation |
| Grief & Loss | Multi-stage support (mourning, 7-day, 40-day, 100-day, 1-year) |
| Financial Aid | Recurring schedules (weekly, monthly, quarterly) with amount tracking |
| Accident/Illness | Hospital visits with 3-14 day follow-up timeline |
| Life Events | New house, childbirth celebrations |
| Regular Contact | Scheduled check-ins with at-risk members |

### Smart Task Management
- Automatic task generation from events
- Priority-based sorting (overdue > today > upcoming)
- One-click task completion with optimistic UI
- "Ignore" functionality with history tracking
- Configurable writeoff thresholds per event type

### Analytics & Reporting
- Member engagement trends over time
- Event type distribution charts
- Campus-level statistics
- Demographic breakdowns (age, gender, membership status)
- Financial aid tracking with totals

### Global Search
- Lightning-fast live search (300ms debounce)
- Search members by name or phone
- Member photos and engagement badges in results
- Visible on all pages (mobile + desktop)

### Activity Log & Accountability
- Complete audit trail of all staff actions
- 13 action types tracked (complete, ignore, create, delete, etc.)
- Filter by staff member, action type, date range
- Export to CSV for reporting
- Timezone-aware timestamps (Asia/Jakarta)

### API Sync (Enterprise Integration)
- **Dual Sync Methods**:
  - Polling: Auto-sync every 1-24 hours (configurable)
  - Webhooks: Real-time updates with HMAC-SHA256 security
- Dynamic filter system (include/exclude by gender, age, status)
- Daily reconciliation at 3 AM for data integrity
- One-click enable/disable

### Security & Performance
- Rate limiting on authentication endpoints (5 req/min for login)
- Health check endpoints (`/health`, `/ready`) for monitoring
- JWT authentication with bcrypt password hashing
- GZIP compression for responses
- Security headers (HSTS, X-Frame-Options, CSP)
- MongoDB connection pooling optimization

### User Experience
- Loading skeletons for smooth perceived performance
- Mobile-first responsive design
- Progressive JPEG images for faster loading
- TanStack React Query for smart caching

---

## Tech Stack

### Backend
| Technology | Purpose |
|------------|---------|
| FastAPI | Python web framework (async) |
| MongoDB | Database with Motor async driver |
| APScheduler | Background job scheduling |
| JWT + bcrypt | Authentication |
| Pillow | Image processing & optimization |
| slowapi | Rate limiting |

### Frontend
| Technology | Purpose |
|------------|---------|
| React 19 | UI framework |
| TanStack React Query | Server state management |
| Shadcn/UI | Component library |
| Tailwind CSS | Styling |
| react-i18next | Internationalization |
| Recharts | Data visualization |

### Infrastructure
| Technology | Purpose |
|------------|---------|
| Docker + Docker Compose | Container orchestration (recommended) |
| Traefik v3 | Reverse proxy with automatic SSL (Docker) |
| Nginx | Reverse proxy (manual installation) |
| Let's Encrypt | Free SSL certificates |
| Supervisord | Process management (manual installation) |

---

## Deployment

FaithTracker uses a **subdomain architecture**:
- **Frontend**: `https://yourdomain.com`
- **API**: `https://api.yourdomain.com`

Choose your deployment method:

### Docker Deployment (Recommended)

Docker deployment is the easiest way to get FaithTracker running with automatic SSL certificates.

#### Prerequisites
- A Linux server (Ubuntu 20.04+, Debian 11+, or any Docker-compatible OS)
- Docker and Docker Compose installed
- A domain name pointing to your server
- Ports 80 and 443 open

#### Step 1: Install Docker (if not installed)

```bash
# Install Docker
curl -fsSL https://get.docker.com | bash

# Start Docker
sudo systemctl enable docker
sudo systemctl start docker

# Verify installation
docker --version
docker compose version
```

#### Step 2: Clone the Repository

```bash
git clone https://github.com/tesarfrr/FaithTracker_Church-Pastoral-Care-System.git
cd FaithTracker_Church-Pastoral-Care-System
```

#### Step 3: Run the Docker Installer

```bash
sudo bash docker-install.sh
```

The wizard will prompt you for:
| Setting | Example | Description |
|---------|---------|-------------|
| Domain | `faithtracker.mychurch.org` | Your main domain |
| Email | `admin@mychurch.org` | For SSL certificate notifications |
| Admin Email | `pastor@mychurch.org` | Login credentials |
| Admin Password | `SecurePass123` | Minimum 8 characters |
| Church Name | `My Church` | Displayed in the app |

#### Step 4: Wait for Deployment

The installer will:
1. Generate secure MongoDB password and JWT secrets
2. Build Docker containers (~5-10 minutes first time)
3. Start all services (Traefik, MongoDB, Backend, Frontend)
4. Automatically obtain SSL certificates from Let's Encrypt

#### Step 5: Access Your Application

Once complete, access:
- **Frontend**: `https://yourdomain.com`
- **API**: `https://api.yourdomain.com`
- **API Docs**: `https://api.yourdomain.com/docs`

> **Note**: SSL certificates may take 1-2 minutes to be issued. If you see certificate errors, wait and refresh.

#### Docker Management Commands

```bash
# View running containers
docker compose ps

# View logs (all services)
docker compose logs -f

# View logs (specific service)
docker compose logs -f backend
docker compose logs -f frontend

# Restart all services
docker compose restart

# Stop all services
docker compose down

# Rebuild and restart (after code changes)
docker compose build --no-cache
docker compose up -d

# View resource usage
docker stats
```

#### Updating FaithTracker (Docker)

```bash
cd /path/to/FaithTracker_Church-Pastoral-Care-System

# Pull latest changes
git pull origin main

# Rebuild and restart
docker compose build --no-cache
docker compose up -d
```

---

### Manual Installation

For servers without Docker, or if you prefer traditional deployment with Nginx.

#### Prerequisites
- Ubuntu 20.04+ or Debian 11+
- Python 3.9+
- Node.js 18+ with Yarn
- MongoDB 4.4+
- Nginx
- Certbot (for SSL)

#### One-Command Installation

```bash
wget https://raw.githubusercontent.com/tesarfrr/FaithTracker_Church-Pastoral-Care-System/main/install.sh -O install.sh && chmod +x install.sh && sudo ./install.sh
```

The installer will:
1. Check system prerequisites
2. Install dependencies (Python, Node.js, MongoDB, Nginx)
3. Configure environment variables interactively
4. Set up systemd services
5. Configure dual-domain Nginx (main + api subdomain)
6. Obtain SSL certificates for both domains
7. Run verification tests

#### Manual Setup (Development)

```bash
# Clone repository
git clone https://github.com/tesarfrr/FaithTracker_Church-Pastoral-Care-System.git
cd FaithTracker_Church-Pastoral-Care-System

# Backend setup
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit with your configuration
uvicorn server:app --reload --host 0.0.0.0 --port 8001

# Frontend setup (new terminal)
cd frontend
yarn install
cp .env.example .env  # Edit REACT_APP_BACKEND_URL
yarn start  # Development
yarn build  # Production
```

#### Environment Variables

**Backend (.env)**:
```bash
MONGO_URL=mongodb://localhost:27017/faithtracker
JWT_SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-fernet-key-here
ALLOWED_ORIGINS=https://yourdomain.com
FRONTEND_URL=https://yourdomain.com
```

**Frontend (.env)**:
```bash
REACT_APP_BACKEND_URL=https://api.yourdomain.com
```

---

## Domain & DNS Configuration

FaithTracker requires **two DNS records** pointing to your server:

### Required DNS Records

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | `@` (or `yourdomain.com`) | `YOUR_SERVER_IP` | 300 |
| A | `api` | `YOUR_SERVER_IP` | 300 |

### Step-by-Step DNS Setup

#### 1. Find Your Server's IP Address

```bash
# On your server
curl -4 ifconfig.me
```

#### 2. Configure DNS at Your Registrar

**Example for Cloudflare:**
1. Log in to Cloudflare Dashboard
2. Select your domain
3. Go to **DNS** → **Records**
4. Add records:
   - **Type**: A, **Name**: `@`, **IPv4**: `YOUR_SERVER_IP`, **Proxy**: DNS only (gray cloud)
   - **Type**: A, **Name**: `api`, **IPv4**: `YOUR_SERVER_IP`, **Proxy**: DNS only (gray cloud)

**Example for Namecheap:**
1. Log in to Namecheap
2. Go to **Domain List** → **Manage** → **Advanced DNS**
3. Add records:
   - **Type**: A Record, **Host**: `@`, **Value**: `YOUR_SERVER_IP`
   - **Type**: A Record, **Host**: `api`, **Value**: `YOUR_SERVER_IP`

**Example for GoDaddy:**
1. Log in to GoDaddy
2. Go to **My Products** → **DNS**
3. Add records:
   - **Type**: A, **Name**: `@`, **Value**: `YOUR_SERVER_IP`
   - **Type**: A, **Name**: `api`, **Value**: `YOUR_SERVER_IP`

#### 3. Verify DNS Propagation

```bash
# Check main domain
dig yourdomain.com +short

# Check API subdomain
dig api.yourdomain.com +short

# Both should return your server IP
```

Or use online tools:
- [whatsmydns.net](https://www.whatsmydns.net/)
- [dnschecker.org](https://dnschecker.org/)

> **Note**: DNS propagation can take 5 minutes to 48 hours. Most changes propagate within 15-30 minutes.

#### 4. Verify from Your Server

```bash
# Test that your server can be reached
curl -I http://yourdomain.com
curl -I http://api.yourdomain.com
```

### SSL Certificate Details

**Docker (Traefik)**:
- Certificates are automatically obtained and renewed
- Stored in Docker volume `faithtracker_traefik-letsencrypt`
- Renewal happens automatically before expiry

**Manual (Certbot)**:
- Certificates stored in `/etc/letsencrypt/live/`
- Auto-renewal via systemd timer
- Check renewal: `sudo certbot renew --dry-run`

### Troubleshooting DNS/SSL

| Issue | Solution |
|-------|----------|
| SSL certificate error | Wait 1-2 minutes for Let's Encrypt to issue certificate |
| DNS not resolving | Wait for propagation (up to 48 hours), verify DNS records |
| "Connection refused" | Check firewall: `sudo ufw allow 80,443/tcp` |
| Traefik not getting cert | Ensure DNS is propagated, check Traefik logs: `docker compose logs traefik` |
| Certbot failed | Verify DNS A records point to server, ensure ports 80/443 are open |

---

## API Documentation

### Base URL
```
https://api.yourdomain.com
```

The API uses subdomain routing. All endpoints are accessed directly at `api.yourdomain.com/*` (no `/api` prefix).

### Authentication
All endpoints (except `/auth/login` and health checks) require JWT Bearer token:
```
Authorization: Bearer <token>
```

### Health Endpoints (No Auth Required)
```bash
GET /health   # Liveness probe
GET /ready    # Readiness probe (checks DB)
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/login` | POST | Authenticate user |
| `/auth/register` | POST | Create user (admin only) |
| `/members` | GET | List members (paginated) |
| `/members` | POST | Create member |
| `/members/{id}` | GET | Get member details |
| `/care-events` | GET | List care events |
| `/care-events` | POST | Create care event |
| `/dashboard/reminders` | GET | Get dashboard data |
| `/activity-logs` | GET | Get activity logs |

### Example: Login
```bash
curl -X POST https://api.yourdomain.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@church.org", "password": "secret"}'
```

Response:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": "user-uuid",
    "email": "admin@church.org",
    "name": "Admin User",
    "role": "full_admin"
  }
}
```

### Example: Create Member
```bash
curl -X POST https://api.yourdomain.com/members \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "phone": "+6281234567890",
    "birth_date": "1990-01-15",
    "gender": "male"
  }'
```

For complete API documentation, see [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) or the interactive Swagger UI.

### OpenAPI / Swagger
- **Swagger UI**: `https://api.yourdomain.com/docs`
- **ReDoc**: `https://api.yourdomain.com/redoc`
- **OpenAPI JSON**: `https://api.yourdomain.com/openapi.json`

---

## Testing

### Backend Tests (pytest)
```bash
cd backend
pytest tests/ -v                    # Run all tests
pytest tests/ -v --cov=. --cov-report=term-missing  # With coverage
pytest tests/ -v -n auto            # Parallel execution
```

**Test Coverage**:
- Scheduler & job locks
- Multi-tenancy data isolation
- Member CRUD operations
- Care event management
- Authentication

### Frontend Tests

**Unit Tests (Jest)**:
```bash
cd frontend
yarn test                # Run all tests
yarn test --coverage     # With coverage
yarn test --watch        # Watch mode
```

**E2E Tests (Playwright)**:
```bash
yarn test:e2e            # Headless
yarn test:e2e:ui         # Interactive UI
yarn test:e2e:headed     # Visible browser
```

**E2E Test Coverage**:
- Authentication flow
- Member CRUD operations
- Care event creation/completion
- Dashboard interactions

---

## Project Structure

```
faithtracker/
├── backend/
│   ├── server.py              # Main API (monolithic ~6500 lines)
│   ├── scheduler.py           # Background jobs
│   ├── Dockerfile             # Backend container
│   ├── requirements.txt       # Python dependencies
│   ├── tests/                 # pytest tests
│   └── uploads/               # User-uploaded files
├── frontend/
│   ├── src/
│   │   ├── pages/             # Page components
│   │   ├── components/        # Reusable components
│   │   │   ├── ui/            # Shadcn/UI components
│   │   │   ├── dashboard/     # Dashboard components
│   │   │   ├── skeletons/     # Loading skeletons
│   │   │   └── member/        # Member components
│   │   ├── context/           # React contexts
│   │   ├── locales/           # i18n translations
│   │   └── lib/               # Utilities
│   ├── Dockerfile             # Frontend container (multi-stage)
│   ├── nginx.conf             # Static file serving config
│   ├── e2e/                   # Playwright tests
│   └── package.json
├── docker/
│   └── mongo-init.js          # MongoDB initialization
├── nginx/                     # Nginx templates (manual install)
├── docker-compose.yml         # Docker orchestration with Traefik
├── docker-install.sh          # Docker deployment wizard
├── install.sh                 # Manual installation script
├── update.sh                  # Update script
├── .env.example               # Environment template
├── docs/                      # Documentation
├── CLAUDE.md                  # AI assistant instructions
└── README.md                  # This file
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [CLAUDE.md](./CLAUDE.md) | Development guidelines for AI assistants |
| [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) | REST API quick reference |
| [docs/FEATURES.md](./docs/FEATURES.md) | Detailed feature documentation |
| [docs/API.md](./docs/API.md) | Complete API endpoint reference |
| [docs/DEPLOYMENT_DEBIAN.md](./docs/DEPLOYMENT_DEBIAN.md) | Production deployment guide |
| [docs/STRUCTURE.md](./docs/STRUCTURE.md) | Codebase architecture |
| [CHANGELOG.md](./CHANGELOG.md) | Version history |

---

## Multi-Language Support

FaithTracker supports:
- **English (en)**: Complete translation
- **Bahasa Indonesia (id)**: Complete translation

Translation files are in `/frontend/src/locales/`. To add a new language:
1. Copy `en.json` to `[language-code].json`
2. Translate all strings
3. Update `i18n.js` to include the new language

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/AmazingFeature`
3. Commit changes: `git commit -m 'feat: add amazing feature'`
4. Push to branch: `git push origin feature/AmazingFeature`
5. Open a Pull Request

### Commit Message Format
```
<type>: <description>

Types: feat, fix, docs, style, refactor, test, chore
```

### Development Guidelines
- Follow existing code style
- Add tests for new features
- Update documentation as needed
- Use the TodoWrite tool for task tracking

---

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- Built for **GKBJ Church** pastoral care department
- Powered by **FastAPI** and **React**
- UI components by **Shadcn/UI**
- Icons by **Lucide React**

---

**Made with care for pastoral excellence**
