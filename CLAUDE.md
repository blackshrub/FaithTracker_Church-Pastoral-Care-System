# CLAUDE.md

## Project Overview

**FaithTracker** is a multi-tenant pastoral care management system for GKBJ church. Monorepo with Litestar backend and React frontend for managing pastoral care across multiple campuses.

**Tech Stack:**
- Backend: Litestar (Python 3.12), MongoDB 8.0 (Motor async), APScheduler, msgspec (Struct models + fast JSON)
- Cache: DragonflyDB (Redis-compatible)
- ASGI Server: Granian (Rust-based)
- Frontend: React 19 + React Compiler, Vite 8, TanStack React Query, Shadcn/UI (Radix), Tailwind CSS
- Mobile: Expo 54 + React Native 0.81, NativeWind, Expo Router
- Infrastructure: Docker, Angie (reverse proxy, HTTP/3, Brotli), Let's Encrypt
- Search: Meilisearch (typo-tolerant full-text search)

## Development Commands

### Backend
```bash
cd backend && source venv/bin/activate
uvicorn server:app --reload --host 0.0.0.0 --port 8001   # Dev
granian --interface asgi --host 0.0.0.0 --port 8001 --workers 2 --http auto server:app  # Prod
pytest tests/ -v                  # Run tests
pytest tests/ -v --cov=. -n auto  # Tests with coverage, parallel
python bulk_engagement_update.py  # Update engagement status (fast, recommended)
python bulk_engagement_update.py --dry-run  # Preview changes
```

### Frontend
```bash
cd frontend && yarn install
yarn start          # Dev server (port 3000)
yarn build          # Production build
yarn test           # Unit tests (Vitest)
yarn test:e2e       # E2E tests (Playwright)
yarn test:e2e:ui    # Interactive E2E
```

## Architecture

### Backend

The backend uses **Litestar** framework with **msgspec.Struct** models (not Pydantic). Main file is `backend/server.py` (~6000 lines) with extracted route modules:

**Structure:** `server.py` contains: imports → enums → constants → msgspec models → auth → helpers → endpoints → app config

**Route modules** (in `backend/routes/`): `auth.py`, `members.py`, `care_events.py`, `grief_support.py`, `accident_followup.py`, `financial_aid.py`, `dashboard.py`, `campus.py`

**Service modules** (in `backend/services/`): `cache.py` (DragonflyDB), `search.py` (Meilisearch), `change_stream.py` (MongoDB change streams), `member_service.py`, `care_event_service.py`, `notification_service.py`, `image_service.py`, `http_client.py`

**When editing backend code:**
- Use constants instead of magic numbers — check `constants.py`
- Use helpers: `get_member_or_404()`, `get_care_event_or_404()`, `log_activity()`
- All DB queries must filter by `church_id` for multi-tenancy
- All DB operations use Motor async: `await db.collection.find()`
- Use `msgspec.Struct` for models (not Pydantic)
- Litestar decorators: `@get`, `@post`, `@put`, `@delete` (not FastAPI's `@app.get`)

**Caching:** DragonflyDB via `CacheService` in `services/cache.py`. Dashboard: 10min TTL, Settings: 1hr TTL. Graceful in-memory fallback.

**Real-time:** SSE via DragonflyDB pub/sub + MongoDB change streams. Endpoint: `stream_activity`. Frontend hook: `useActivityStream.js`.

### Frontend

**Critical files:**
- `src/pages/Dashboard.jsx` — Main dashboard with TanStack Query
- `src/pages/MemberDetail.jsx` — Member profile with care event timeline
- `src/context/AuthContext.jsx` — JWT auth state
- `src/App.jsx` — Root with routing

**Patterns:**
- `@/` path alias for imports
- Shadcn/UI components in `src/components/ui/`
- Bilingual: `react-i18next` — translations in `src/locales/{en,id}.json`
- Custom hooks: `useActivityStream`, `useViewTransition`, `usePrefetch`, `useOfflineSync`, `useDebounce`, `useOptimisticMutation`
- Optimistic mutations: `useCompleteEventOptimistic()`, `useIgnoreEventOptimistic()`, `useUpdateMemberOptimistic()`, `useCreateEventOptimistic()`

**Performance:** React Compiler (auto-memoization), code splitting (lazy pages), prefetch on hover, PWA (static asset caching, no API caching), View Transitions API

### Database (MongoDB)

**Collections:** `users`, `campuses`, `members`, `care_events`, `financial_aid_schedules`, `family_groups`, `notification_logs`, `activity_logs`, `pastoral_notes`, `api_sync_configs`, `api_sync_history`, `dashboard_cache`, `job_locks`

**Multi-tenancy:** Every query filters by `church_id`. Roles: `full_admin` (all campuses), `campus_admin` (one campus), `pastor` (task management).

**Timezone:** All datetimes use `Asia/Jakarta` (UTC+7). Use `JAKARTA_TZ = ZoneInfo("Asia/Jakarta")`.

## Design Guidelines

**Colors:**
- Primary: Teal `#14b8a6` — Secondary: Amber `#f59e0b`
- Success: Green, Warning: Amber, Destructive: Red
- NEVER use dark/saturated gradient combos or gradients on >20% viewport

**Mobile-first.** All components must be responsive.

## Common Tasks

### Adding a New API Endpoint
1. Find relevant section in `server.py` or create in `routes/`
2. Add msgspec Struct model if needed
3. Use `@post("/your-endpoint")` with auth guard
4. Filter by `user["church_id"]` for multi-tenancy
5. Use `log_activity()` for accountability

### Adding a New React Component
1. Create in `src/components/` or `src/pages/`
2. Use Shadcn/UI + Tailwind CSS
3. Add translations to both `en.json` and `id.json`
4. Use `const { t } = useTranslation()` for i18n

### Adding Translations
Edit `src/locales/en.json` and `src/locales/id.json`. Use: `t('your.key.path')`

## Key Features

- **Grief Auto-Timeline:** Creates 6 follow-up events (immediate → 1-year memorial)
- **Accident Follow-up:** Auto-generates 3-stage follow-up (3, 7, 14 days)
- **SSE Activity Stream:** Real-time team collaboration via DragonflyDB pub/sub + MongoDB change streams
- **Offline-First Sync:** IndexedDB queue, auto-sync on reconnect (`useOfflineSync`)
- **Smart Prefetching:** Hover-to-prefetch with TanStack Query + Speculation Rules API
- **View Transitions:** Native-like page transitions with `useViewTransition`
- **Reports:** Monthly/yearly PDF reports, staff performance, analytics dashboard
- **API Sync:** External system integration (polling/webhook/daily reconciliation)
- **Meilisearch:** Typo-tolerant full-text search across members and care events

## Environment Variables

### Backend (.env)
```
MONGODB_URI=mongodb://localhost:27017/faithtracker
JWT_SECRET=your-secret-key
ENCRYPTION_KEY=base64-encoded-fernet-key
DRAGONFLY_URL=redis://dragonfly:6379/0
MEILI_URL=http://meilisearch:7700
MEILI_MASTER_KEY=your-search-key
```

### Frontend (.env)
```
VITE_BACKEND_URL=https://api.yourdomain.com
```

## Infrastructure

**Docker services:** DragonflyDB, MongoDB 8.0, Meilisearch, Backend (Granian)
**Frontend:** Static build served by host-level Angie
**Secrets:** Docker secrets in `./secrets/` (mongo_password, jwt_secret, encryption_key)
**Data:** Bind mounts in `./data/` (mongo, dragonfly, meilisearch, uploads)
**Migration:** Copy entire project folder + `data/` + `secrets/` → `make setup` on new server

## Git Commit Strategy

Commit after every meaningful change. Format: `<type>: <description>`

Types: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`, `perf:`, `style:`

Never push unless explicitly requested. Never commit `.env` files with real secrets.

## Testing

- **Backend:** pytest + pytest-asyncio. Isolated `faithtracker_test` DB.
- **Frontend unit:** Vitest + React Testing Library
- **Frontend E2E:** Playwright (auth, CRUD, care events, dashboard, reports, analytics)
- **CI/CD:** GitHub Actions (lint, test, build, security scan, Trivy)
- **Dependabot:** Auto-updates for pip, npm, docker, GitHub Actions (weekly)

## Mobile App

Expo 54 + React Native, NativeWind for styling, Gluestack UI for interactive components only (buttons, modals, forms). Everything else: NativeWind. Mock data mode for Expo Go development.
