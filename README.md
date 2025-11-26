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
- [Quick Start](#quick-start)
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
| Nginx | Reverse proxy |
| Supervisord | Process management |
| Debian 12 / Ubuntu | Operating system |

---

## Quick Start

### One-Command Installation

```bash
wget https://raw.githubusercontent.com/tesarfrr/FaithTracker_Church-Pastoral-Care-System/main/install.sh -O install.sh && chmod +x install.sh && sudo ./install.sh
```

The installer will:
1. Check system prerequisites
2. Install dependencies (Python, Node.js, MongoDB, Nginx)
3. Configure environment variables interactively
4. Set up systemd services
5. Configure Nginx reverse proxy
6. Run verification tests

### Manual Installation

#### Prerequisites
- Python 3.9+
- Node.js 18+ with Yarn
- MongoDB 4.4+
- Nginx

#### Setup

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

### Environment Variables

**Backend (.env)**:
```bash
MONGODB_URI=mongodb://localhost:27017/faithtracker
JWT_SECRET=your-secret-key-here
ENCRYPTION_KEY=your-fernet-key-here
WHATSAPP_API_URL=https://api.whatsapp.com  # Optional
```

**Frontend (.env)**:
```bash
REACT_APP_BACKEND_URL=http://localhost:8001/api
```

---

## API Documentation

### Base URL
```
{BACKEND_URL}/api
```

### Authentication
All endpoints (except `/auth/login`) require JWT Bearer token:
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
curl -X POST ${API}/auth/login \
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
curl -X POST ${API}/members \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "phone": "+6281234567890",
    "birth_date": "1990-01-15",
    "gender": "male"
  }'
```

For complete API documentation, see [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) or the interactive Swagger UI at `/docs`.

### OpenAPI / Swagger
- **Swagger UI**: `{BACKEND_URL}/docs`
- **ReDoc**: `{BACKEND_URL}/redoc`
- **OpenAPI JSON**: `{BACKEND_URL}/openapi.json`

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
│   ├── e2e/                   # Playwright tests
│   └── package.json
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
