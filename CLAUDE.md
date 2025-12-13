# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**FaithTracker** is a multi-tenant pastoral care management system for GKBJ church. It's a monorepo with FastAPI backend and React frontend designed for managing pastoral care across multiple campuses with complete accountability tracking.

**Tech Stack:**
- Backend: FastAPI (Python 3.11), MongoDB 7.0 (Motor async driver), APScheduler
- ASGI Server: Granian (Rust-based, faster than Uvicorn)
- JSON: msgspec (faster than orjson, lower memory)
- Frontend: React 19 + React Compiler, Vite, TanStack React Query, Shadcn/UI, Tailwind CSS
- Infrastructure: Docker (application services), Angie (host-level reverse proxy with HTTP/3, Brotli), Let's Encrypt (Certbot)

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

# Run with Granian (production-like, faster)
granian --interface asgi --host 0.0.0.0 --port 8001 --workers 2 --http auto server:app

# Run tests
./test_api.sh

# Database utilities (automatically run by install.sh and update.sh)
python create_indexes.py                # Create MongoDB indexes
python migrate.py                       # Run database migrations

# Data import utilities (manual)
python import_data.py                   # Bulk import members from CSV
python import_photos.py                 # Import member photos from directory

# Engagement status updates
python bulk_engagement_update.py        # FAST: Bulk update (10-100x faster, RECOMMENDED)
python bulk_engagement_update.py --dry-run  # Preview changes without updating
python bulk_engagement_update.py --campus-id <ID>  # Update specific campus
python recalculate_engagement.py        # SLOW: Legacy individual updates (deprecated)

# One-time migrations (safe to run multiple times)
python normalize_user_phones.py         # Normalize phone numbers to international format
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

# Run unit tests (Jest + React Testing Library)
yarn test

# Run E2E tests (Playwright)
yarn test:e2e              # Headless mode
yarn test:e2e:ui           # Interactive UI mode
yarn test:e2e:headed       # See browser
yarn test:e2e:debug        # Debug mode
```

### Testing

**Phase 1: Backend Tests (pytest)** ✅ Complete

```bash
# Run all backend tests
cd backend
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=. --cov-report=term-missing

# Run specific test file
pytest tests/test_scheduler.py -v

# Run specific test
pytest tests/test_scheduler.py::test_job_lock_acquisition -v

# Run tests in parallel (faster)
pytest tests/ -v -n auto
```

**Backend Test Coverage:**
- ✅ **Scheduler & Job Locks** (`test_scheduler.py`) - Critical for multi-worker environment
  - Job lock acquisition/release
  - Lock expiration handling
  - Concurrent lock attempts (simulates 4 workers)
  - Daily digest generation
  - Multi-campus isolation

- ✅ **Multi-Tenancy** (`test_multi_tenancy.py`) - Data isolation security
  - Campus data isolation (members, events, logs)
  - Cross-campus access prevention
  - Cannot modify/delete other campus data
  - Full_admin multi-campus access
  - Dashboard cache separation

- ✅ **Basic Functionality** (`test_basic_functionality.py`)
  - Member CRUD operations
  - Care event management
  - Engagement status tracking
  - User password hashing
  - Campus activation status

**Phase 2: Frontend Tests** ✅ Complete

**Unit Tests (Jest + React Testing Library)**

```bash
cd frontend

# Run all unit tests
yarn test

# Run with coverage
yarn test --coverage

# Run specific test file
yarn test useDebounce.test.js

# Run in watch mode
yarn test --watch
```

**Frontend Test Coverage:**
- ✅ **Custom Hooks** (`src/__tests__/hooks/`)
  - `useDebounce.test.js` - Debounce hook timing, cancellation, edge cases

- ✅ **Components** (`src/__tests__/components/`)
  - `TimelineEventCard.test.js` - Event card rendering, interactions, delete action
  - `MemberProfileHeader.test.js` - Profile header display, engagement badges, responsive

**E2E Tests (Playwright)**

```bash
cd frontend

# Install Playwright browsers (first time only)
npx playwright install

# Run all E2E tests
yarn test:e2e

# Run in UI mode (recommended for development)
yarn test:e2e:ui

# Run specific test file
yarn test:e2e auth.spec.js

# Run with visible browser
yarn test:e2e:headed

# Debug tests
yarn test:e2e:debug

# View test report
npx playwright show-report
```

**E2E Test Coverage:**
- ✅ **Authentication** (`e2e/auth.spec.js`)
  - Login with valid/invalid credentials
  - Logout and session clearing
  - Protected route access
  - Session persistence on reload
  - Form validation

- ✅ **Member CRUD** (`e2e/member-crud.spec.js`)
  - View members list
  - Search members
  - Create new member
  - View member details
  - Edit member information
  - Delete member
  - Filter by engagement status

- ✅ **Care Events** (`e2e/care-events.spec.js`)
  - Create birthday event
  - Create grief/loss event with auto-timeline (6 stages)
  - Create hospital visit event
  - Create financial aid event
  - Complete/ignore care events
  - Delete care events
  - Event type badges and colors

- ✅ **Dashboard** (`e2e/dashboard.spec.js`)
  - Display statistics and metrics
  - Today's tasks and birthday reminders
  - Navigate to member details
  - Complete tasks from dashboard
  - Filter tasks by status
  - Search members
  - Mobile responsive view (375x667)

**Test Environment Setup:**

Create `frontend/.env.test`:
```bash
TEST_USER_EMAIL=admin@test.com
TEST_USER_PASSWORD=testpass123
REACT_APP_BACKEND_URL=http://localhost:8001/api
```

**Legacy Integration Tests:**
`backend/test_api.sh` - Bash script with curl commands covering:
- Authentication & JWT
- Member CRUD operations
- Care events (birthdays, grief, hospital visits, financial aid)
- Grief support auto-timeline generation (6 stages)
- Dashboard statistics
- WhatsApp integration
- CSV import/export

**Test Databases:**
- Backend tests use isolated `faithtracker_test` database (auto-cleanup after each test)
- E2E tests can use development database or separate test instance

**Test Configuration Files:**
- `backend/pytest.ini` - Pytest configuration
- `frontend/playwright.config.js` - Playwright E2E configuration
- `frontend/e2e/README.md` - Detailed E2E testing guide

**Coverage Goals:**
- Backend: 80%+ (critical paths 100%)
- Frontend: 70%+ (components and hooks)
- E2E: All critical user flows

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

**Caching Patterns:**
- **In-memory cache** for static data (campuses, settings) with TTL
  - `get_from_cache(key, ttl_seconds)` - Retrieve cached value if not expired
  - `set_in_cache(key, value)` - Store value with timestamp
  - `invalidate_cache(pattern)` - Clear cache on updates (pattern-based or full clear)
- **Cached endpoints** (10-minute TTL):
  - `/api/campuses` - Campus list (invalidated on campus create/update)
  - Engagement settings (invalidated on settings update)
  - Writeoff settings (invalidated on settings update)
- **Performance impact:** 50-90% reduction in database queries for static data

**MongoDB Connection Pooling:**
- Optimized AsyncIOMotorClient configuration:
  - `maxPoolSize=50` - Maximum connections in pool
  - `minPoolSize=10` - Minimum connections to keep open
  - `maxIdleTimeMS=45000` - Close idle connections after 45s
  - Better connection reuse under load

**Image Optimization:**
- **Member photos:** 3 sizes (thumbnail/medium/large) with progressive JPEG
  - Quality: 85, LANCZOS resampling, progressive=True
  - Auto-generated on upload (100x100, 300x300, 600x600)
- **User photos:** Single 400x400 size with progressive JPEG
  - Quality: 85, optimize=True, progressive=True
- **Progressive JPEG benefits:** Faster perceived loading, better UX on slow connections

**Modular Refactoring Recommendation:**
**Status:** Keep monolithic (tactical refactoring done)
**Reasoning:**
- Current size (~6500 lines) is manageable with good organization
- Tactical optimizations applied (constants, helpers, caching)
- Monolithic simplifies deployment and debugging
- Full modular split (models/, routes/, services/) recommended only if:
  - Team grows beyond 3-4 backend developers
  - File exceeds 10,000 lines despite refactoring
  - Multiple microservices planned
  - Frequent merge conflicts occur
- **Cost/benefit:** High effort, moderate benefit at current scale

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
1. `src/pages/Dashboard.js` (~1935 lines) - Main task-oriented dashboard with TanStack Query
2. `src/pages/MemberDetail.js` (~1788 lines) - Member profile with care event timeline
3. `src/context/AuthContext.js` - Authentication state & JWT storage
4. `src/App.js` - Root component with routing and providers

**Dashboard Component Structure:**
Dashboard has been decomposed into smaller, reusable components:
- `src/components/dashboard/DashboardStats.jsx` - 4-card stats overview
- `src/components/dashboard/BirthdaySection.jsx` - Birthday task cards (today/overdue)
- `src/components/dashboard/TaskCard.jsx` - Reusable task card with avatar, contact, and complete actions
- Main `Dashboard.js` orchestrates data fetching and layout

**MemberDetail Component Structure:**
MemberDetail has been decomposed into focused components:
- `src/components/member/MemberProfileHeader.jsx` - Profile header with name, contact, engagement badge
- `src/components/member/TimelineEventCard.jsx` - Reusable care event card for timeline display
- Main `MemberDetail.js` handles data fetching, dialogs, and layout

**Component Decomposition Pattern:**
When breaking down large components (>500 lines):
1. Extract **display-only sections** into presentational components (e.g., DashboardStats)
2. Create **reusable UI patterns** as components (e.g., TaskCard)
3. Keep **data fetching and business logic** in parent component
4. Pass data via props, callbacks for actions
5. Use barrel exports (`index.js`) for clean imports

**Performance Optimizations:**
- **Debouncing:** Search inputs use 2-second debounce (MembersList.js)
  - Implemented with `use-debounce` library
  - Reduces API calls by ~80% during typing
  - Custom hook available: `src/hooks/useDebounce.js`
- **Memoization:** Expensive computations use `useMemo` (Dashboard.js)
  - `filteredMembers` - Client-side search filtering
  - `incompleteBirthdaysCount` - Repeated filter calculations
  - `incompleteTodayTasksCount` - Repeated filter calculations
  - **Impact:** Prevents unnecessary re-computation on every render

**Key Patterns:**
- Uses `@/` path alias for imports (`import { Button } from "@/components/ui/button"`)
- Shadcn/UI components in `src/components/ui/`
- Dashboard sub-components in `src/components/dashboard/`
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

**Real-Time Activity Stream (SSE):**
Live team collaboration via Server-Sent Events:
- **Backend:** `stream_activity` endpoint in `server.py` broadcasts activities
- **Frontend:** `useActivityStream.js` hook manages SSE connection
- **Component:** `LiveActivityFeed.jsx` displays real-time updates
- **Features:**
  - Auto-reconnect with exponential backoff
  - JWT auth via query parameter (EventSource doesn't support headers)
  - Activity types: complete, ignore, create_event, delete_event, etc.
  - Filters out own user's activities in real-time stream
  - Loads recent activities from REST API on mount
- **Angie config:** SSE location has compression disabled (required for streaming)

```javascript
// Frontend usage
const { isConnected, activities } = useActivityStream({
  onActivity: (activity) => toast(`${activity.user_name} completed a task`)
});
```

**View Transitions API:**
Native-like page transitions for smooth UX:
- **Hook:** `src/hooks/useViewTransition.js` - Programmatic navigation with transitions
- **Component:** `src/components/LinkWithPrefetch.jsx` - Links with auto-transitions
- **Features:**
  - Fade and slide animations between pages
  - Respects `prefers-reduced-motion`
  - Automatic fallback on unsupported browsers
  - `withViewTransition()` utility for non-navigation DOM updates

```javascript
// Programmatic navigation with transition
const { navigate, isTransitioning } = useViewTransition();
navigate('/members/123');
```

**Smart Link Prefetching:**
Data loads before user clicks for instant navigation:
- **Hook:** `src/hooks/usePrefetch.js` - TanStack Query prefetch functions
- **Component:** `LinkWithPrefetch.jsx` - Auto-prefetch on hover/focus
- **Features:**
  - Hover-to-prefetch (100ms delay before cancel)
  - Route-aware prefetching (knows data needs per route)
  - Cancels prefetch on mouse leave
  - Convenience wrappers: `MemberLink`, `DashboardLink`

```jsx
<LinkWithPrefetch to={`/members/${id}`} prefetchType="member" prefetchId={id}>
  View Member
</LinkWithPrefetch>
```

**Offline-First Sync Queue:**
Work without internet, sync when connected:
- **Library:** `src/lib/offlineQueue.js` - IndexedDB-backed operation queue
- **Hook:** `src/hooks/useOfflineSync.js` - React integration with TanStack Query
- **Component:** `src/components/SyncStatusIndicator.jsx` - Visual pending count
- **Features:**
  - Operations persist through page refresh and browser restart
  - Auto-sync when coming back online
  - Retry with exponential backoff (max 3 retries)
  - Visual indicator showing pending operations
  - Conflict resolution

```javascript
const { isOnline, pendingCount, queueOperation } = useOfflineSync();

// Queue operation for later sync
await queueOperation({
  type: 'COMPLETE_EVENT',
  endpoint: '/care-events/123/complete',
  method: 'POST'
});
```

**Grief Support Auto-Timeline:**
When creating a grief/loss event, the system automatically generates 6 follow-up events:
1. Mourning service (immediate)
2. 3-day check-in
3. 7-day check-in
4. 40-day check-in
5. 100-day check-in
6. 1-year memorial

**Reports & Analytics System:**
Comprehensive reporting for data-driven ministry decisions:

*Analytics Dashboard (`/analytics`):*
- **Demographics Tab:** Age distribution (bar), gender (pie), membership status (pie), categories (bar)
- **Trends Tab:** Population analysis, AI-powered insights with strategic recommendations
- **Engagement Tab:** Active/at-risk/inactive pie chart, care events by month (area)
- **Financial Tab:** Aid by type (bar), distribution summary, average calculations
- **Care Events Tab:** Event distribution by type with completion rates
- **Predictive Tab:** Member priority scoring, aid effectiveness analysis

*Reports Page (`/reports`):*
- **Monthly Management Report:** Executive summary, KPIs (care completion, engagement, reach, birthdays), ministry highlights, weekly trends, strategic insights, month comparison
- **Staff Performance Report:** Team overview, workload recommendations, top performers (gold/silver/bronze), individual metrics (tasks, contacts, active days)
- **Yearly Summary:** Annual totals, monthly trend charts, care events by type

*Backend Endpoints:*
- `GET /api/analytics/dashboard` - Comprehensive dashboard data
- `GET /api/analytics/engagement-trends` - 30-day engagement trends
- `GET /api/analytics/demographic-trends` - Population analysis with insights
- `GET /api/reports/monthly?year=YYYY&month=MM` - Monthly report JSON
- `GET /api/reports/monthly/pdf` - Downloadable PDF report
- `GET /api/reports/staff-performance` - Staff metrics
- `GET /api/reports/yearly-summary` - Annual report
- `GET /api/export/members/csv` - Members CSV export
- `GET /api/export/care-events/csv` - Care events CSV export

**API Sync with FaithFlow Enterprise:**
Full integration with external church management systems:

*Sync Methods:*
- **Polling Mode:** Pull data every 1-24 hours (configurable interval)
- **Webhook Mode:** Real-time push updates from core system
- **Daily Reconciliation:** 3 AM Asia/Jakarta automatic full sync (catches missed webhooks)

*Configuration (`SyncConfig` model):*
```python
{
  "sync_method": "polling" | "webhook",
  "api_base_url": "https://faithflow.example.com",
  "api_path_prefix": "/api",
  "api_login_endpoint": "/auth/login",
  "api_members_endpoint": "/members/",
  "api_email": "user@example.com",
  "api_password": "encrypted...",  # Fernet encrypted
  "polling_interval_hours": 6,      # 1, 3, 6, 12, or 24
  "is_enabled": true,
  "webhook_secret": "auto-generated-256-bit",
  "reconciliation_enabled": true,
  "reconciliation_time": "03:00"
}
```

*Dynamic Filter System:*
- **Filter Modes:** `include` (whitelist) or `exclude` (blacklist)
- **Operators:** `equals`, `not_equals`, `contains`, `in`, `not_in`, `greater_than`, `less_than`, `between`, `is_true`, `is_false`
- **Field Discovery:** `/sync/discover-fields` endpoint analyzes external API for available fields
- **Example:** Sync only females aged 18-35: `[{field: "gender", operator: "equals", value: "Female"}, {field: "age", operator: "between", value: [18, 35]}]`

*Security:*
- **Fernet Encryption:** API credentials encrypted before storage
- **HMAC-SHA256:** Webhook signature verification
- **Distributed Locks:** MongoDB-based locks prevent duplicate sync in multi-worker environments

*Sync Endpoints:*
- `POST /sync/config` - Save configuration
- `GET /sync/config` - Get current config
- `POST /sync/test-connection` - Test API connectivity
- `POST /sync/discover-fields` - Discover available fields
- `POST /sync/members/pull` - Manual sync trigger
- `POST /sync/webhook` - Receive webhook from core
- `GET /sync/logs` - Sync history with pagination

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
│   │   ├── dashboard/           # Dashboard-specific components
│   │   │   ├── LiveActivityFeed.jsx    # Real-time SSE activity stream
│   │   │   ├── DashboardStats.jsx      # Stats cards
│   │   │   └── TaskCard.jsx            # Reusable task card
│   │   ├── LinkWithPrefetch.jsx        # Smart links with prefetch + transitions
│   │   ├── SyncStatusIndicator.jsx     # Offline queue status
│   │   ├── Layout.js            # Main layout wrapper
│   │   ├── DesktopSidebar.js    # Desktop navigation
│   │   ├── MobileBottomNav.js   # Mobile navigation
│   │   └── ...
│   ├── hooks/                   # Custom React hooks
│   │   ├── useActivityStream.js # SSE real-time activity feed
│   │   ├── useViewTransition.js # View Transitions API wrapper
│   │   ├── usePrefetch.js       # TanStack Query prefetching
│   │   ├── useOfflineSync.js    # Offline-first mutations
│   │   └── useDebounce.js       # Input debouncing
│   ├── lib/                     # Utilities
│   │   ├── offlineQueue.js      # IndexedDB sync queue
│   │   ├── api.js               # Axios instance with auth
│   │   └── dateUtils.js         # Date formatting helpers
│   ├── context/
│   │   └── AuthContext.jsx      # Authentication state + token
│   ├── locales/
│   │   ├── en.json              # English translations
│   │   └── id.json              # Indonesian translations
│   ├── App.js                   # Root React component
│   └── i18n.js                  # i18next configuration
├── package.json                 # Uses yarn
├── tailwind.config.js           # Tailwind CSS config
└── vite.config.js               # Vite build configuration
```

### Mobile (Expo/React Native)
```
mobile/
├── app/                         # Expo Router file-based routing
│   ├── _layout.tsx             # Root layout with providers
│   ├── index.tsx               # Entry point with auth redirect
│   ├── (auth)/                 # Auth screens (login)
│   └── (tabs)/                 # Main app tabs (authenticated)
├── components/                  # Reusable components
├── services/                    # API and mock services
├── stores/                      # Zustand state management
├── hooks/                       # Custom React hooks
├── lib/                         # Utilities (i18n, storage, etc.)
├── constants/                   # Theme, API endpoints, etc.
├── types/                       # TypeScript types
├── tailwind.config.js          # NativeWind Tailwind config
├── babel.config.js             # Babel configuration
└── app.json                    # Expo configuration
```

### Angie (Host-level Web Server)
```
angie/
├── README.md                   # Setup documentation
├── angie.conf                  # Main Angie configuration
├── conf.d/
│   ├── faithtracker.conf.template  # Site config (uses ${DOMAIN})
│   ├── ssl.conf                # SSL/TLS settings
│   ├── security-headers.conf   # OWASP security headers
│   └── rate-limit.conf         # Rate limiting zones
├── snippets/
│   ├── proxy-headers.conf      # Common proxy headers
│   └── ssl-params.conf         # SSL parameters
├── install.sh                  # Installation script (Debian/Ubuntu)
├── setup-ssl.sh                # Certbot SSL setup
└── generate-config.sh          # Generate config from .env
```

## Mobile App Styling Guidelines

**Use NativeWind as the Primary Styling System**

The mobile app uses a unified styling approach:
- NativeWind (Tailwind CSS for React Native) for all styling
- Unified `tailwind.config.js` design tokens (colors, spacing, typography)
- Gluestack UI for specific interactive components only

**Gluestack UI Components (use sparingly):**
- ✅ Buttons (`Button`, `ButtonText`, `ButtonIcon`)
- ✅ Modals / Sheets
- ✅ Form elements (inputs, selects, checkboxes)
- ✅ Toast / Alert notifications
- ✅ Select / Dropdown menus

**React Native + NativeWind for:**
- ✅ Animated headers
- ✅ PremiumMotion transitions
- ✅ Shared Axis transitions
- ✅ Cards
- ✅ Lists (`FlashList` or `FlatList`)
- ✅ Collapsible screens
- ✅ All other UI elements

**Important:**
- Always wrap app with `GluestackUIProvider` in root layout
- Use `SafeAreaProvider` for safe area handling
- Use `GestureHandlerRootView` for gesture support
- Mock data mode (`USE_MOCK_DATA`) uses in-memory storage for Expo Go

## Backend Utility Scripts

### Automated (Run by install.sh/update.sh)

**`create_indexes.py`** - Creates MongoDB indexes for performance
- Automatically run during installation and updates
- Creates indexes on all collections including job_locks (for scheduler)
- Safe to run multiple times (idempotent)
- Run manually: `python create_indexes.py`

**`migrate.py`** - Database schema migrations
- Automatically run during updates
- Handles schema changes between versions
- Run manually: `python migrate.py`

**`init_db.py`** - Initialize database
- Automatically run during installation only
- Creates admin user and default campus
- Usage: `python init_db.py --admin-email EMAIL --admin-password PASS --church-name NAME`

### Manual Data Import

**`import_data.py`** - Bulk import members from CSV
- Import hundreds/thousands of members at once
- CSV format: name, phone, email, family_group_name, notes
- Usage: `python import_data.py --campus-id ID --file members.csv`
- See script for CSV template

**`import_photos.py`** - Import member photos
- Bulk import photos matched by member phone number
- Photos named like: 6281234567890.jpg
- Usage: `python import_photos.py --directory /path/to/photos --campus-id ID`

### Performance & Maintenance

**`bulk_engagement_update.py`** ⭐ RECOMMENDED
- Fast bulk update of member engagement status (10-100x faster)
- Uses MongoDB aggregation pipeline
- Usage:
  ```bash
  python bulk_engagement_update.py                 # Update all
  python bulk_engagement_update.py --dry-run       # Preview only
  python bulk_engagement_update.py --campus-id ID  # Specific campus
  ```

**`recalculate_engagement.py`** (Deprecated)
- Legacy individual updates - much slower
- Only use if bulk_engagement_update fails
- Usage: `python recalculate_engagement.py`

### One-Time Migrations

**`normalize_user_phones.py`**
- Converts phone numbers to international format (+62...)
- Safe to run multiple times
- Usage: `python normalize_user_phones.py`

### Testing

**`test_api.sh`**
- Comprehensive API testing script
- Tests all 40+ endpoints
- Usage: `cd backend && ./test_api.sh`

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

### Backend Performance Optimizations

**Granian ASGI Server:**
- Rust-based ASGI server (10-15% faster than Uvicorn)
- Configured with 2 workers and HTTP auto-negotiation
- Supports HTTP/1.1 and HTTP/2 (H2C upgrade)
- Production command: `granian --interface asgi --host 0.0.0.0 --port 8001 --workers 2 --http auto server:app`

**msgspec Fast JSON Serialization:**
- Faster than orjson with ~30-50% lower memory usage
- Custom `CustomMsgspecResponse` class handles MongoDB/BSON type serialization
- Uses reusable encoder instance for efficiency (`_msgspec_encoder`)
- Used as default response class for all FastAPI endpoints
- Handles `datetime`, `date`, `ObjectId`, `Decimal128`, and other types automatically

**Response Compression (Angie):**
- Brotli compression built-in (15-25% smaller than gzip)
- Gzip fallback for older clients
- Minimum response size: 256 bytes
- Applied to both frontend and backend responses
- Configured in `/angie/angie.conf`

**HTTP/3 (QUIC) Support:**
- Enabled in Angie (built-in support) for lower latency
- UDP port 443 exposed for QUIC protocol
- Automatic protocol negotiation (HTTP/1.1, HTTP/2, HTTP/3)
- Benefits mobile users with unstable connections

### Frontend Performance Optimizations

**React Compiler:**
- Automatic memoization of components and hooks
- No manual `useMemo`, `useCallback`, or `React.memo` needed
- Configured via `babel-plugin-react-compiler` in Vite
- Target: React 19

**Data Fetching (TanStack Query only):**
- All data fetching happens in components via `useQuery`
- No React Router loaders (removed - auth context not available in loaders)
- Cache settings: `staleTime: 30s-5min`, `gcTime: 5-10min` for fast navigation
- Automatic refetch on window focus ensures data freshness

**PWA Service Worker:**
- Caches static assets (JS, CSS, HTML) for offline use
- Does NOT cache API responses (ensures data freshness)
- Uses Workbox via `vite-plugin-pwa`
- Auto-updates on new deployments

**Code Splitting:**
- Vendor chunks: react, router, ui, charts, query, utils, i18n
- Lazy-loaded pages via `React.lazy()`
- Charts loaded on demand (not in initial bundle)

## API Documentation

FastAPI auto-generates interactive API docs:
- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

For detailed endpoint documentation, see `API_DOCUMENTATION.md`.

