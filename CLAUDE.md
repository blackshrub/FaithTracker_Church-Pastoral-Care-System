# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**FaithTracker** is a multi-tenant pastoral care management system for GKBJ church. It's a monorepo with FastAPI backend and React frontend designed for managing pastoral care across multiple campuses with complete accountability tracking.

**Tech Stack:**
- Backend: FastAPI (Python 3.9+), MongoDB (Motor async driver), APScheduler
- Frontend: React 19, TanStack React Query, Shadcn/UI, Tailwind CSS
- Infrastructure: Nginx, Supervisord

## Development Commands

### Backend

```bash
# Setup
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run development server (with auto-reload)
uvicorn server:app --reload --host 0.0.0.0 --port 8001

# Run tests
./test_api.sh

# Database utilities
python create_indexes.py                # Create MongoDB indexes
python import_data.py                   # Bulk import members from CSV

# Engagement status updates
python bulk_engagement_update.py        # FAST: Bulk update (10-100x faster, RECOMMENDED)
python bulk_engagement_update.py --dry-run  # Preview changes without updating
python bulk_engagement_update.py --campus-id <ID>  # Update specific campus
python recalculate_engagement.py        # SLOW: Legacy individual updates (deprecated)
```

### Frontend

```bash
# Setup
cd frontend
yarn install

# Development server (port 3000)
yarn start

# Production build
yarn build

# Build with bundle analysis
yarn build:analyze

# Run tests
yarn test
```

### Testing

Backend has comprehensive API tests in `backend/test_api.sh` covering:
- Authentication & JWT
- Member CRUD operations
- Care events (birthdays, grief, hospital visits, financial aid)
- Grief support auto-timeline generation (6 stages)
- Dashboard statistics
- WhatsApp integration
- CSV import/export

See `backend/TESTING_GUIDE.md` for details.

## Architecture

### Backend Architecture (Monolithic)

**Critical:** The entire backend API is in a **single 6500-line file** `backend/server.py`. This is intentional for:
- Simplified deployment
- Easy code search and navigation
- No complex module imports
- Common pattern for MVPs

**Structure of `server.py`:**
1. Imports & configuration
2. Enums (EventType, UserRole, EngagementStatus, etc.)
3. **Constants** - All magic numbers extracted for easy maintenance
   - Engagement thresholds (60/90 days defaults)
   - Grief timeline stages (7, 14, 30, 90, 180, 365 days)
   - Accident followup stages (3, 7, 14 days)
   - JWT token expiration, pagination defaults, etc.
4. Pydantic models (User, Member, CareEvent, Campus, etc.)
5. Auth functions (JWT, bcrypt password hashing)
6. Utility functions (timezone handling, engagement calculation)
7. **Helper functions** - DRY patterns to reduce code duplication
   - `get_member_or_404()` - Fetch member or raise 404
   - `get_care_event_or_404()` - Fetch care event or raise 404
   - `get_campus_or_404()` - Fetch campus or raise 404
   - `log_activity()` - Activity logging with accountability
   - `generate_grief_timeline()` - Auto-generate 6-stage grief support
   - `generate_accident_followup_timeline()` - Auto-generate 3-stage followups
8. ~100 API endpoints grouped by resource (clearly marked with section headers)
9. Startup/shutdown events (scheduler, database)

**When editing `server.py`:**
- Use search to locate relevant sections (the file is large)
- **Use constants instead of magic numbers** - Check CONSTANTS section for existing values
- **Use helper functions to reduce duplication**:
  - Use `get_member_or_404()` instead of `find_one()` + manual 404 check
  - Use `get_care_event_or_404()` for care events
  - Use `log_activity()` for consistent accountability tracking
- Pydantic models are defined near the top (~lines 100-500)
- API endpoints are grouped by resource type with clear section markers
- All database operations use Motor async driver (`await db.collection.find()`)
- All queries auto-scope by `church_id` for multi-tenancy

**Encryption & Security:**
- JWT tokens for authentication
- Bcrypt for password hashing
- Fernet encryption for sensitive credentials (API sync)
- HMAC-SHA256 for webhook signature verification

### Frontend Architecture

**State Management:**
- **Global auth state:** `src/context/AuthContext.js` (JWT token, user info)
- **Server state:** TanStack React Query in `Dashboard.js` and `MemberDetail.js`
- **Local UI state:** `useState` hooks for modals, forms, etc.

**Most Critical Files:**
1. `src/pages/Dashboard.js` (~3500 lines) - Main task-oriented dashboard with TanStack Query
2. `src/pages/MemberDetail.js` (~2900 lines) - Member profile with care event timeline
3. `src/context/AuthContext.js` - Authentication state & JWT storage
4. `src/App.js` - Root component with routing and providers

**Key Patterns:**
- Uses `@/` path alias for imports (`import { Button } from "@/components/ui/button"`)
- Shadcn/UI components in `src/components/ui/`
- All pages responsive with mobile-first design
- Bilingual support (English/Indonesian) via `react-i18next`

**Translation Files:**
- `src/locales/en.json` - English translations
- `src/locales/id.json` - Indonesian translations
- Use `const { t } = useTranslation()` in components
- Access translations with `t('key.path')`

### Database Schema (MongoDB)

**Collections:**
- `users` - User accounts with roles (full_admin, campus_admin, pastor)
- `campuses` - Church campuses/locations
- `members` - Church members (indexed on `church_id`, `member_id`)
- `care_events` - Pastoral care events (indexed on `church_id`, `member_id`, `event_date`)
- `financial_aid_schedules` - Recurring financial aid tracking
- `family_groups` - Family grouping for members
- `notification_logs` - WhatsApp/email delivery logs
- `activity_logs` - Complete audit trail of staff actions
- `api_sync_configs` - FaithFlow Enterprise API sync settings
- `api_sync_history` - Sync execution history

**Multi-Tenancy:**
All queries automatically filter by `church_id` to ensure data isolation between campuses.

### Key Features

**Grief Support Auto-Timeline:**
When creating a grief/loss event, the system automatically generates 6 follow-up events:
1. Mourning service (immediate)
2. 3-day check-in
3. 7-day check-in
4. 40-day check-in
5. 100-day check-in
6. 1-year memorial

**API Sync with FaithFlow Enterprise:**
Two sync methods:
- Polling: Pull data every 1-24 hours (configurable)
- Webhooks: Real-time updates with HMAC-SHA256 security
- Dynamic filter system (include/exclude by gender, age, status)
- Daily reconciliation at 3 AM Asia/Jakarta time

**Activity Logging:**
Every action is logged with WHO did WHAT on WHICH member:
- 13 action types tracked (complete, ignore, create, delete, etc.)
- Timezone-aware timestamps (Asia/Jakarta)
- Full audit trail for accountability

## Design Guidelines

**Color Restrictions:**
- NEVER use dark/saturated gradient combinations (purple/pink, blue-500 to purple-600)
- NEVER let gradients cover more than 20% of viewport
- NEVER apply gradients to text-heavy areas or small UI elements (<100px)

**Primary Colors:**
- Teal Primary: `hsl(174, 94%, 39%)` - #14b8a6 (calm, trustworthy)
- Amber Secondary: `hsl(38, 92%, 50%)` - #f59e0b (warm, welcoming)

**Semantic Colors:**
- Success: Green (completed tasks)
- Warning: Amber (attention needed)
- Destructive: Red (errors, critical issues)

**Mobile-First:**
All components must be responsive. Design for mobile first, then enhance for larger screens.

## File Organization

### Backend
```
backend/
├── server.py                    # MONOLITHIC - entire API (~6500 lines)
├── scheduler.py                 # APScheduler background jobs
├── requirements.txt             # Python dependencies
├── test_api.sh                  # Comprehensive API test suite
├── TESTING_GUIDE.md            # Testing documentation
├── uploads/                     # User-uploaded files (member photos)
├── jemaat/                      # Member photo archive
└── *.py                         # Utility scripts (import, indexes, etc.)
```

### Frontend
```
frontend/
├── src/
│   ├── pages/                   # Top-level page components
│   │   ├── Dashboard.js         # Main dashboard (TanStack Query)
│   │   ├── MemberDetail.js      # Member profile (TanStack Query)
│   │   ├── Settings.js          # User/campus/API sync settings
│   │   ├── ActivityLog.js       # Staff accountability log
│   │   └── ...
│   ├── components/
│   │   ├── ui/                  # Shadcn/UI components (button, card, etc.)
│   │   ├── Layout.js            # Main layout wrapper
│   │   ├── DesktopSidebar.js    # Desktop navigation
│   │   ├── MobileBottomNav.js   # Mobile navigation
│   │   └── ...
│   ├── context/
│   │   └── AuthContext.js       # Authentication state
│   ├── locales/
│   │   ├── en.json              # English translations
│   │   └── id.json              # Indonesian translations
│   ├── App.js                   # Root React component
│   └── i18n.js                  # i18next configuration
├── package.json                 # Uses yarn
├── tailwind.config.js           # Tailwind CSS config
└── craco.config.js              # Create React App overrides
```

## Common Tasks

### Adding a New API Endpoint

1. Open `backend/server.py`
2. Find the relevant section (e.g., member endpoints around line 2000+)
3. Add Pydantic model if needed (near top of file)
4. Add endpoint with proper auth: `@api_router.post("/your-endpoint")`
5. Use `user = Depends(get_current_user)` for authentication
6. Always filter by `user["church_id"]` for multi-tenancy
7. Test with curl or `test_api.sh`

### Adding a New React Component

1. Create component in `src/components/` or `src/pages/`
2. Use Shadcn/UI components from `@/components/ui/`
3. Import translations: `const { t } = useTranslation()`
4. Use Tailwind CSS for styling
5. Ensure responsive design (mobile-first)
6. Add translations to both `en.json` and `id.json`

### Adding a New Translation

1. Edit `frontend/src/locales/en.json` - add English text
2. Edit `frontend/src/locales/id.json` - add Indonesian text
3. Use in component: `t('your.key.path')`
4. Translation files use nested objects for organization

### Modifying TanStack Query Data Fetching

**Dashboard.js and MemberDetail.js use TanStack React Query:**
- `useQuery` for data fetching with automatic caching
- `useMutation` for updates with optimistic UI
- `queryClient.invalidateQueries()` to refresh data after mutations

**Pattern:**
```jsx
const { data, isLoading, error } = useQuery({
  queryKey: ['members'],
  queryFn: async () => {
    const res = await axios.get('/api/members');
    return res.data;
  }
});

const mutation = useMutation({
  mutationFn: async (data) => {
    return axios.post('/api/members', data);
  },
  onSuccess: () => {
    queryClient.invalidateQueries(['members']);
  }
});
```

## Environment Variables

### Backend (.env)
```
MONGODB_URI=mongodb://localhost:27017/faithtracker
JWT_SECRET=your-secret-key
ENCRYPTION_KEY=base64-encoded-fernet-key
WHATSAPP_API_URL=https://api.whatsapp.com/send (optional)
WHATSAPP_API_TOKEN=your-token (optional)
```

### Frontend (.env)
```
REACT_APP_BACKEND_URL=http://localhost:8001/api
```

## Timezone Handling

**Critical:** All datetime operations use `Asia/Jakarta` timezone (UTC+7).

```python
from zoneinfo import ZoneInfo
JAKARTA_TZ = ZoneInfo("Asia/Jakarta")

# When creating datetime objects
now = datetime.now(JAKARTA_TZ)
```

Daily jobs (reconciliation, reminders) run at 3 AM Jakarta time.

## Multi-Tenancy

**Every database query must filter by `church_id`** to ensure data isolation:

```python
members = await db.members.find({
    "church_id": user["church_id"]
}).to_list(None)
```

**User Roles:**
- `full_admin`: Can access all campuses, switch views dynamically
- `campus_admin`: Manage single campus with full control
- `pastor`: Regular pastoral care staff with task management

## Code Management & Version Control

### Git Commit Strategy - MANDATORY

**CRITICAL**: You MUST commit changes after every meaningful modification. This enables easy rollback and change tracking.

**Commit Frequency Rules:**
1. **Immediately after file changes** - Commit after creating, editing, or deleting files
2. **One logical change per commit** - Each commit should represent a single, coherent change
3. **Before major refactors** - Commit working state before starting large refactorings
4. **After completing features** - Commit when a feature or fix is complete
5. **After successful tests** - Commit after verifying changes work correctly

**Commit Message Format:**
```bash
# Pattern: <type>: <concise description>

# Examples:
git commit -m "feat: add custom backend port configuration to install.sh"
git commit -m "fix: correct CORS origins to use domain from wizard"
git commit -m "refactor: extract auth functions into utils/security.py"
git commit -m "docs: update CLAUDE.md with git commit best practices"
git commit -m "test: add unit tests for authentication endpoints"
git commit -m "chore: update dependencies in requirements.txt"
git commit -m "perf: add database indexes for member queries"
```

**Commit Type Prefixes:**
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code restructuring (no behavior change)
- `docs:` - Documentation changes
- `test:` - Adding or updating tests
- `chore:` - Maintenance (dependencies, config, etc.)
- `perf:` - Performance improvements
- `style:` - Code style changes (formatting, whitespace)

**Granularity Examples:**

✅ **GOOD** (Granular, easy to rollback):
```bash
git commit -m "feat: add backend port configuration to install wizard"
git commit -m "feat: add SSL/HTTPS setup wizard to install.sh"
git commit -m "fix: update systemd service to use custom port"
git commit -m "fix: update nginx config to proxy to custom backend port"
```

❌ **BAD** (Too large, hard to rollback):
```bash
git commit -m "update install.sh with all wizard improvements"
```

**Git Workflow:**
```bash
# 1. Check status
git status

# 2. Add specific files (preferred) or all changes
git add backend/server.py backend/config.py
# OR for all changes
git add .

# 3. Commit with descriptive message
git commit -m "feat: add rate limiting to authentication endpoints"

# 4. NEVER push unless user explicitly requests
# git push  # DON'T DO THIS AUTOMATICALLY

# 5. To undo last commit (if needed):
git reset --soft HEAD~1  # Keeps changes in staging
git reset --hard HEAD~1  # DANGER: Discards changes
```

**When to Commit:**
- ✅ After creating new files ([backend/init_db.py](backend/init_db.py), [backend/migrate.py](backend/migrate.py))
- ✅ After editing existing files ([install.sh](install.sh), [CLAUDE.md](CLAUDE.md))
- ✅ After configuration changes ([backend/.env](backend/.env), [frontend/.env](frontend/.env))
- ✅ After completing a logical unit of work
- ✅ Before switching to a different task
- ❌ Never commit `.env` files with real secrets (use `.env.example`)
- ❌ Never commit `node_modules/`, `venv/`, `__pycache__/`

**Rollback Strategy:**
```bash
# View commit history
git log --oneline -10

# Rollback to specific commit
git revert <commit-hash>  # Safe: creates new commit

# Undo last commit but keep changes
git reset --soft HEAD~1

# View changes in a commit
git show <commit-hash>

# Compare commits
git diff <commit1> <commit2>
```

**Best Practices:**
1. Commit early, commit often
2. Write clear, descriptive commit messages
3. Keep commits small and focused
4. Never commit broken code to main
5. Test before committing
6. Use git status frequently
7. Review changes before committing (`git diff`)

## Performance Considerations

### Database Query Optimizations

**Aggregation Pipelines:**
- Dashboard endpoints use MongoDB aggregation pipelines instead of multiple queries
- `$facet` operator combines multiple aggregations in single pipeline (dashboard stats)
- `$lookup` operator joins collections server-side instead of N+1 queries (upcoming events, recent activity, grief support)
- Financial aid totals calculated server-side using `$group` and `$sum`

**Field Projections:**
- Member list endpoints fetch only required fields (11 fields instead of 20+)
- 50-70% reduction in data transfer for list views
- Applies to: members list, at-risk members, grief stages, accident followups, financial aid

**Bulk Operations:**
- `bulk_engagement_update.py` uses aggregation pipeline for 10-100x faster updates
- Single `$merge` operation instead of individual document updates
- Recommended over legacy `recalculate_engagement.py`

### Caching & Infrastructure

- MongoDB indexes created by `create_indexes.py` on frequently queried fields
- TanStack Query caches API responses to reduce network requests
- Photos served directly from filesystem via `/api/uploads/` endpoint
- Dashboard uses pagination and filtering to handle large datasets
- Engagement status is recalculated periodically (not on every request)

## API Documentation

FastAPI auto-generates interactive API docs:
- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

For detailed endpoint documentation, see `API_DOCUMENTATION.md`.

