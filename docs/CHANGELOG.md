# Changelog

All notable changes to FaithTracker will be documented in this file.

## [2.1.0] - 2025-12-02

### ⚡ Major Performance Optimizations

#### Backend Performance
- **Granian ASGI Server** - Replaced Uvicorn with Rust-based Granian (10-15% faster)
  - 2 workers with HTTP auto-negotiation
  - Supports HTTP/1.1 and HTTP/2 (H2C upgrade)
- **orjson Serialization** - 2-5x faster JSON encoding/decoding
  - Custom `CustomORJSONResponse` for MongoDB datetime handling
  - Set as default response class for all endpoints
- **Brotli Compression** - 15-25% smaller responses than gzip
  - Configured via Angie (built-in support)
  - Minimum response size: 256 bytes
- **HTTP/3 (QUIC) Support** - Lower latency for mobile users
  - UDP port 443 exposed
  - Automatic protocol negotiation
- **Query Optimization** - `list_users` endpoint uses `$lookup` (eliminates N+1)
- **Security Fix** - `hashed_password` excluded from user queries

#### Frontend Performance
- **React Compiler** - Automatic memoization (no manual optimization needed)
  - Configured via `babel-plugin-react-compiler`
  - Target: React 19
- **Route Loaders** - Parallel data prefetching during navigation
  - New file: `frontend/src/lib/routeLoaders.js`
  - Primes TanStack Query cache before component renders
- **PWA Service Worker** - Offline-capable with Workbox
  - Caches static assets (JS, CSS, HTML)
  - Does NOT cache API responses (ensures data freshness)
- **Code Splitting** - Optimized vendor chunks
  - Separate chunks: react, router, ui, charts, query, utils, i18n
  - Lazy-loaded charts (not in initial bundle)

### 🔧 Technical Changes

#### Dependencies Added
- `granian==1.7.6` - Rust ASGI server
- `orjson==3.10.18` - Fast JSON library
- `babel-plugin-react-compiler` - React Compiler
- `vite-plugin-pwa` - PWA support
- `eslint-plugin-react-compiler` - Linting for React Compiler

#### Infrastructure
- **docker-compose.yml**:
  - HTTP/3 enabled: `--entrypoints.websecure.http3`
  - UDP port 443 exposed for QUIC
  - Brotli compression middleware for backend and frontend
- **backend/Dockerfile**:
  - Changed from Uvicorn to Granian CMD
- **frontend/vite.config.js**:
  - React Compiler plugin
  - PWA plugin with Workbox
  - Optimized manual chunks

#### Files Modified
- `backend/server.py` - Added CustomORJSONResponse, orjson imports
- `backend/requirements.txt` - Added granian, orjson
- `backend/Dockerfile` - Granian CMD
- `docker-compose.yml` - HTTP/3, Brotli compression
- `frontend/vite.config.js` - React Compiler, PWA
- `frontend/src/App.jsx` - Route loaders, createBrowserRouter
- `frontend/src/lib/routeLoaders.js` - New file for data prefetching
- `frontend/package.json` - New dependencies

### 🐛 Bug Fixes
- Fixed Analytics page "data.reduce is not a function" error
  - Root cause: orjson couldn't serialize MongoDB datetime objects
  - Fix: CustomORJSONResponse with `orjson_default` handler
- Fixed route loader query key conflicts
  - Changed prefetch keys to unique names (e.g., `member-prefetch`)
  - Prevents cache pollution between loader and component

---

## [2.0.0] - 2025-11-20

### 🎉 Major Features Added

#### Global Search System
- **Live search** across members and care events
- Visible on ALL pages (mobile + desktop navigation)
- 300ms debounce for smooth performance
- Displays member photos and engagement badges
- Click results to navigate to member detail
- API endpoint: `GET /api/search?q={query}`

#### Complete Accountability System
- **Activity logging** for all user actions (13 action types)
- Track WHO performed WHAT on WHICH member
- New Activity Log page with:
  - Filter by staff member, action type, date range
  - Summary cards (total activities, active staff, tasks completed)
  - Export to CSV functionality
  - Timezone-aware timestamps (Asia/Jakarta)
- Timeline displays:
  - "Created by: [Staff Name]"
  - "Completed by: [Staff Name] on [Date]"
  - "Ignored by: [Staff Name] on [Date]"
- Activity tracking for:
  - Create/complete/ignore care events
  - Grief support follow-ups (complete/ignore)
  - Accident/illness follow-ups (complete/ignore)
  - Financial aid (distribute/stop/clear)
  - Contact at-risk/disconnected members
  - Send WhatsApp reminders


#### Hybrid Follow-up System (NEW)
- **Scheduled follow-ups** - System-generated follow-up stages (6 for grief, 3 for accident)
- **Additional visits** - Staff can log unscheduled visits anytime
- **Features:**
  - Log additional visits directly in grief/accident tabs
  - Inline expandable form (date, type, notes)
  - Visual distinction (pink/blue for scheduled, grey for additional)
  - All visits count toward member engagement
  - Complete activity logging
  - Delete individual additional visits
- **Benefits:**
  - Accountability: Required follow-ups tracked
  - Flexibility: Unlimited additional visits
  - Reality: Captures all pastoral interactions
  - Context: All visits grouped under parent event
- **API Endpoint:** `POST /api/care-events/{parent_id}/additional-visit`


#### Member Data Sync (FaithFlow Enterprise Integration)
- **Two sync methods:**
  - **Polling**: Automatic sync every 1-24 hours (configurable)
  - **Webhooks**: Real-time updates with HMAC-SHA256 signature verification
- **Dynamic filter system:**
  - Field discovery from core API (analyzes sample data)
  - Custom filter rules with 10 operators (equals, contains, between, etc.)
  - Include/Exclude modes
  - Unlimited filter rules
  - Smart dropdowns for distinct values
- **Features:**
  - Pagination support (fetches ALL members, not just first page)
  - Smart archival (members not matching filters archived automatically)
  - Photo sync from base64
  - Age calculation from date_of_birth
  - Phone number normalization
  - Daily reconciliation at 3 AM (configurable)
  - One-click enable/disable
  - Sync history with detailed statistics
- **API Endpoints:**
  - `POST /api/sync/config` - Save configuration
  - `GET /api/sync/config` - Get configuration
  - `POST /api/sync/test-connection` - Validate credentials
  - `POST /api/sync/discover-fields` - Analyze core API structure
  - `POST /api/sync/members/pull` - Manual sync
  - `POST /api/sync/webhook` - Webhook receiver
  - `POST /api/sync/regenerate-secret` - Rotate webhook secret
  - `GET /api/sync/logs` - Sync history

#### User Management Features
- **Edit users** in Admin Dashboard
- **Phone number column** in users table
- **Profile photo upload** (Settings → Profile tab)
- Upload user photos (400x400px, auto-resized)
- Photos displayed in:
  - Navigation (mobile + desktop)
  - Activity Log
  - Search results
  - Member timelines
- API endpoints:
  - `PUT /api/users/{id}` - Update user
  - `POST /api/users/{id}/photo` - Upload photo
  - `GET /api/user-photos/{filename}` - Serve photos

### 🐛 Bug Fixes

#### Enum Consistency
- Fixed "inactive" → "disconnected" enum across 7 locations (server.py, import_data.py, scheduler.py)
- Fixed "hospital_visit" → "accident_illness" enum (2 locations)
- Updated engagement threshold to 90 days consistently

#### Phone Number Normalization
- Added `normalize_phone_number()` function
- Converts local format (081xxx) to international (+6281xxx)
- Applied to:
  - User registration and updates
  - Member creation and updates
  - WhatsApp message sending
- Migration script: `normalize_user_phones.py`
- Migrated 2 existing users to normalized format

#### UI/UX Improvements
- **Grief stages renamed**: "First Follow-up" through "Sixth Follow-up" (was "1 Week After", etc.)
- **Ignored stages**: Now show disabled grey button instead of overlapping badge
- **Completed stages**: Show disabled green button
- **One-time events**: Auto-complete on creation (Regular Contact, Childbirth, New House, Financial Aid one-time)
- **Data separation**: Grief/Accident tabs show only parent events, Timeline tab shows all entries
- **Activity Log mobile access**: Added to "More" menu

#### Performance Optimizations
- **40+ database indexes** created across 9 collections
- **Optimistic UI updates**: Tasks disappear instantly when marked complete
- **Compound indexes** for dashboard queries
- Performance improvements:
  - Dashboard load: 10-50x faster
  - Member lookup: 100x faster
  - Task filtering: 20x faster
  - Activity log queries: 50x faster
- Migration script: `create_performance_indexes.py`

#### CareEvent Model Updates
- Added `created_by_user_id` and `created_by_user_name`
- Added `completed_by_user_id` and `completed_by_user_name`
- Added `ignored_by` and `ignored_by_name`
- Added `reminder_sent_by_user_id` and `reminder_sent_by_user_name`
- Added `grief_stage_id` and `accident_stage_id` for linking timeline entries
- Phone field now optional (handles members without phones)

#### Activity Log Fixes
- Date filtering now uses datetime objects (was comparing with ISO strings)
- Optional fields have proper defaults (`= None`)
- Timezone-aware display (Asia/Jakarta format)
- Shows user photos when available

#### Cascade Delete Logic
- Delete parent grief/accident event → Deletes all:
  - Child follow-up stages
  - Timeline entries created from stages
  - Related activity logs
- Delete child timeline entry → Resets stage to pending
- Undo action → Deletes timeline entries and activity logs

#### Sync Improvements
- Save configuration auto-triggers sync if enabled
- Test connection shows accurate total member count (not just first 100)
- Webhook endpoint uses direct member endpoint (fast)
- Webhook handles test/ping events
- Webhook signature verification with HMAC-SHA256
- Church ID matching (stores core_church_id for webhook routing)
- Age calculation from date_of_birth during sync

### 📝 Breaking Changes

#### Member Model
- `email` field removed from Member model (email only for Users/staff)
- `phone` field now Optional (was required)

#### Grief/Accident Behavior
- Completing/ignoring stages NO LONGER creates duplicate parent events
- Timeline entries created have `grief_stage_id` or `accident_stage_id`
- Tabs filter out timeline entries (only show actual stages)

### 🔧 Technical Improvements

#### Backend
- Split responsibilities:
  - `server.py`: Main API endpoints
  - `scheduler.py`: Background jobs (reminders, reconciliation)
  - `normalize_user_phones.py`: Phone migration script
  - `create_performance_indexes.py`: Index creation
- Added imports: `secrets`, `hmac`, `hashlib`, `Request`
- Improved error handling with detailed messages
- Webhook delivery logging

#### Frontend
- New components:
  - `SearchBar.js` - Global search component
  - `FilterRuleBuilder.js` - Dynamic sync filter builder
- New pages:
  - `ActivityLog.js` - Staff accountability tracking
- Updated components:
  - `Layout.js` - Added SearchBar to header
  - `DesktopSidebar.js` - Added Activity Log to menu
  - `MobileBottomNav.js` - Added Activity Log to More menu
  - `Settings.js` - New Profile and API Sync tabs
  - `AdminDashboard.js` - Edit users, phone column
  - `MemberDetail.js` - Actor display, improved stage UI
  - `Dashboard.js` - Optimistic updates
- 50+ translation keys added (English + Indonesian)

#### Database Collections
- `activity_logs` - User action tracking
- `sync_configs` - API sync configuration
- `sync_logs` - Sync operation history
- `webhook_logs` - Webhook delivery tracking
- Added indexes to all collections

### 📚 Documentation Updates
- Core system integration requirements document
- Webhook integration guide with signature examples
- Updated API documentation with sync endpoints
- Installation script improvements

### 🔒 Security
- Webhook HMAC-SHA256 signature verification
- Auto-generated 32-byte webhook secrets
- Credential masking in UI (password shows ********)
- Admin-only access to sync configuration
- Activity audit trail for all operations

### ⚡ Performance
- 40+ database indexes
- Optimistic UI updates (instant feedback)
- Lazy evaluation for filters
- Pagination for all member sync operations
- Direct member endpoint for webhooks (no list iteration)

### 🎨 UI/UX
- Dynamic button labels ("Save & Sync Now" vs "Save Configuration")
- Collapsible filter section (checkbox to show/hide)
- Active Sync Configuration card (one-click disable)
- Enable/Disable button changes dynamically
- Clear explanations for include/exclude modes
- Timezone-aware timestamps throughout
- Visual feedback for sync status
- Progress indicators for long operations



### 🔒 Security Enhancements

**Credential Encryption:**
- Fernet symmetric encryption for API sync credentials
- Auto-generate encryption key with warning if not set
- Encrypt passwords before database storage
- Decrypt only when needed for API calls
- ENCRYPTION_KEY environment variable support

**Custom Confirmation Dialogs:**
- Replaced all 24 native confirm() dialogs with custom ConfirmDialog component
- No suppression risk (browser "Prevent this page from creating dialogs")
- Better UX with descriptive titles and messages
- Consistent styling across application
- Proper error handling and callbacks

### 📝 Production Polish

**Code Quality:**
- File headers added to all main components
- Debug console.log statements commented out
- Product branding: "FaithTracker Pastoral Care System"
- Version 2.0.0 in package.json
- MIT License added

**Dashboard Performance:**
- Fixed stats calculation to use stored engagement_status
- 100x faster stat queries (no recalculation loop)
- Accurate real-time member counts


---

## [1.0.0] - Initial Release

- Multi-tenant pastoral care management
- Task-oriented dashboard
- Care event tracking (birthdays, grief, financial aid, etc.)
- Member management with photos
- Family grouping
- Analytics and reporting
- CSV import/export
- WhatsApp integration
- Bilingual support (English/Indonesian)
- Mobile-first responsive design
