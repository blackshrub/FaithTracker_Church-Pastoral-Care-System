# Church Pastoral Care Tracking System – Development Plan

## 1) Objectives (MVP-first)
- Centralize member records with family connections (no member left behind)
- Track care events (birthday, childbirth, grief, new house, accident/illness, regular contact, prayer)
- View Upcoming/Overdue items at a glance (dashboard)
- Send reminders via WhatsApp gateway (http://dermapack.net:3001) - **VERIFIED WORKING**
- Email integration deferred (user chose WhatsApp-first approach)
- Simple role-based access (Pastoral Team, Admin) added after core works
- Apply warm, compassionate design (Primary: Sage, Secondary: Peach, Accent: Teal per design_guidelines.md)

## 2) Strategic Phases & Implementation Steps

### PHASE 1: Core Integration POC ✅ **COMPLETED**
**Status:** ✅ COMPLETED (2025-11-13)

**Goal:** Prove outbound notifications work reliably.

**Completed Work:**
- ✅ WhatsApp gateway integration verified at http://dermapack.net:3001
- ✅ Backend endpoints created: `/api/integrations/ping/whatsapp`, `/api/integrations/ping/email`
- ✅ Environment variables configured: `WHATSAPP_GATEWAY_URL`, `CHURCH_NAME` (GKBJ)
- ✅ React integration test screen built with data-testid attributes
- ✅ End-to-end WhatsApp message sent successfully to test number 6281290080025
- ✅ Response shape documented: `message_id`, `status`, `phone` format

**Key Findings:**
- WhatsApp API endpoint: `POST {gateway_url}/send/message`
- Request payload: `{"phone": "{number}@s.whatsapp.net", "message": "text"}`
- No authentication required for gateway
- Success response: `{"code": "SUCCESS", "results": {"message_id": "...", "status": "..."}}`
- Email integration explicitly deferred (WhatsApp-only mode)

**Exit Criteria Met:**
- ✅ WhatsApp test message successfully sent end-to-end
- ✅ Response shape documented with message_id and status
- ✅ Email endpoint returns clear "pending provider" message

---

### PHASE 2: Core MVP Development (Unauthenticated) 🚧 **IN PROGRESS**
**Status:** 🚧 READY TO START

**Goal:** Working slice from data → dashboard → manual reminder send.

**Backend (FastAPI + MongoDB):**
- Database Models (UUIDs, timezone-aware):
  - `Member`: id, name, phone, email, birthdate, address, family_connections (array of member IDs), notes, created_at, updated_at
  - `CareEvent`: id, member_id, event_type (birthday, childbirth, grief, new_house, accident, regular_contact, prayer), event_date, description, notes, completed, created_at, updated_at
  - `NotificationLog`: id, care_event_id, member_id, channel (whatsapp/email), phone/email, message, status (sent/failed), response_data, created_at

- API Endpoints (all `/api/*`):
  - Members: `GET /members`, `POST /members`, `GET /members/{id}`, `PUT /members/{id}`, `DELETE /members/{id}`
  - Care Events: `GET /care-events`, `POST /care-events`, `GET /care-events/{id}`, `PUT /care-events/{id}`, `DELETE /care-events/{id}`
  - Dashboard: `GET /dashboard/stats`, `GET /dashboard/upcoming`, `GET /dashboard/overdue`, `GET /dashboard/recent-activity`
  - Notifications: `POST /care-events/{id}/send-reminder` (WhatsApp only for now)

**Frontend (React + Shadcn):**
- Design System Implementation:
  - CSS custom properties for sage/peach/teal color palette (per design_guidelines.md)
  - Google Fonts: Manrope (headings), Inter (body), Cormorant Garamond (hero)
  - Dark mode toggle with system preference detection
  - Sonner toasts for all user feedback
  - data-testid on all interactive elements

- Screens/Components:
  1. **Dashboard** (`/`):
     - Stat cards: Total members, Upcoming events (7 days), Overdue follow-ups, Recent contacts
     - Upcoming events list with event type badges
     - Recent activity feed (last 10 care events)
     - Quick action: "Add Member", "Add Care Event"
  
  2. **Members List** (`/members`):
     - Table view with search/filter
     - Columns: Name, Phone, Last Contact, Upcoming Events, Actions
     - Add Member button
     - Click row → Member Detail
  
  3. **Member Detail** (`/members/{id}`):
     - Member info card with edit button
     - Family connections section
     - Care events timeline (chronological, color-coded by type)
     - "Add Care Event" button for this member
     - "Send Reminder" button for each event
  
  4. **Add/Edit Member Form** (Modal or page):
     - Name, Phone, Email, Birthdate, Address fields
     - Family connections selector (link to other members)
     - Notes textarea
  
  5. **Add/Edit Care Event Form** (Modal or page):
     - Member selector (if not from member detail)
     - Event type dropdown (with event type colors from design_guidelines.md)
     - Event date picker (Calendar component)
     - Description, Notes fields
     - "Save" and "Save & Send Reminder" buttons
  
  6. **Integration Test Panel** (`/integrations`):
     - Keep existing WhatsApp test component
     - Link from settings/admin area

- Loading/Empty/Error States:
  - Skeleton loaders for data fetching
  - Empty state illustrations for no members/events
  - Error alerts with retry buttons
  - Toast notifications for all actions

**User Stories:**
1. ✅ As a pastor, I can add a new member with phone/email/birthdate
2. ✅ As a pastor, I can link family members together (e.g., husband-wife, parent-child)
3. ✅ As a pastor, I can create a care event for a member with date/type/notes
4. ✅ As a pastor, I can see upcoming birthdays and follow-ups on the dashboard
5. ✅ As a pastor, I can manually send a WhatsApp reminder for a care event and see success/error
6. ✅ As a pastor, I can browse recent care activities
7. ✅ As a pastor, I can view a member's complete care history timeline
8. ✅ As a pastor, I can search/filter members by name or upcoming events

**Exit Criteria:**
- End-to-end flow works: add member → add care event → see in dashboard → send WhatsApp reminder
- All CRUD operations functional for members and care events
- Dashboard displays real-time stats and upcoming/overdue items
- WhatsApp reminder sending works with proper success/error handling
- UI follows design_guidelines.md (sage/peach/teal, proper spacing, Shadcn components)
- One round of automated E2E testing executed and major issues fixed
- All interactive elements have data-testid attributes

---

### PHASE 3: Authentication & Roles 📋 **NOT STARTED**
**Status:** 📋 PENDING (after Phase 2)

**Goal:** Restrict access and separate admin-only actions.

**Implementation Steps:**
- Simple JWT auth (email/password)
- User model with roles: ADMIN, PASTOR
- Protected routes on backend with role checks
- Login/Logout UI with token storage (localStorage)
- Axios interceptor for automatic token inclusion
- Admin screens:
  - User management (list, add, edit, delete users)
  - Settings (view gateway URL, church name)
  - Integration test panel access

**User Stories:**
1. As a user, I can log in with email/password and access the app
2. As an admin, I can manage users and assign roles
3. As a pastor, I can access member/care features but not admin settings
4. As a user, I remain signed in across refresh until token expires
5. As a user, I see clear feedback for invalid credentials

**Exit Criteria:**
- Protected endpoints enforce roles correctly
- Core flows remain functional under authentication
- Testing pass for auth flows and role restrictions
- Default admin account seeded in database

---

### PHASE 4: Automated Reminders & Scheduling 📋 **NOT STARTED**
**Status:** 📋 PENDING (after Phase 3)

**Goal:** Automate daily reminders and logs.

**Implementation Steps:**
- Implement APScheduler for periodic tasks
- Reminder rules:
  - Birthdays: 7, 3, 1 days before
  - Grief/Loss: Immediate follow-up, then weekly for 4 weeks
  - New House: 1 week after event
  - Accident/Illness: 3 days, 1 week, 2 weeks after
  - Regular Contact: Based on last contact date (configurable interval)
  - Prayer Requests: 1 week after request
- Message templates with church name and personalization
- NotificationLog entries for all sends
- Dashboard widgets: "Overdue Follow-ups", "Reminders sent today"
- Manual trigger button for admins

**User Stories:**
1. As a pastor, I see a list of members who need contact today
2. As an admin, I can manually trigger reminder run with a button
3. As a pastor, I can view the history of reminders per member/event
4. As a pastor, I can retry failed reminders
5. As a user, I can see which channel was used (WhatsApp)

**Exit Criteria:**
- Daily scheduled run creates sends and logs with clear success/failure
- Manual trigger works correctly
- Reminder rules configurable via admin settings
- Failed reminders can be retried
- Dashboard shows overdue and sent reminder counts

---

### PHASE 5: Enhancements & Polish 📋 **NOT STARTED**
**Status:** 📋 PENDING (after Phase 4)

**Scope:**
- Calendar view (month) with color-coded events
- Advanced search/filter with multiple criteria
- Export members and care events to CSV
- Member assignment to specific caregivers/pastors
- Tags and status for members
- Simple analytics dashboard (weekly/monthly stats)
- Performance optimization and accessibility audit
- UI/UX polish per design system

**User Stories:**
1. As a pastor, I can see a calendar of upcoming care events by type
2. As a pastor, I can filter members by tag/status to plan weekly outreach
3. As a leader, I can export care events to CSV for reporting
4. As a pastor, I can be assigned a set of members and see my list
5. As a leader, I can view weekly stats of contacts made vs pending

**Exit Criteria:**
- All features above demonstrably working
- Tests clear with no critical bugs
- UI matches design tokens throughout
- Accessibility audit passed (WCAG AA)
- Performance optimized (page load < 2s)

---

## 3) Configuration & Decisions Made

**WhatsApp Integration:**
- ✅ Gateway URL: http://dermapack.net:3001
- ✅ No authentication required
- ✅ Test phone: 6281290080025
- ✅ Church name: GKBJ
- ✅ Phone format: {number}@s.whatsapp.net

**Email Integration:**
- ⏸️ Deferred (WhatsApp-first approach)
- Status: "Pending provider configuration"

**Event Categories & Colors** (from design_guidelines.md):
- Birthday: `hsl(45, 90%, 65%)` - Warm golden yellow
- Childbirth: `hsl(330, 75%, 70%)` - Soft pink
- Grief/Loss: `hsl(240, 15%, 45%)` - Muted blue-gray
- New House: `hsl(25, 85%, 62%)` - Warm peach
- Accident/Illness: `hsl(15, 70%, 58%)` - Warm coral
- Regular Contact: `hsl(180, 42%, 45%)` - Soft teal
- Prayer Request: `hsl(260, 40%, 60%)` - Soft lavender

**Design System:**
- Primary: Sage Green `hsl(140, 32%, 45%)`
- Secondary: Warm Peach `hsl(25, 88%, 62%)`
- Accent: Soft Teal `hsl(180, 42%, 45%)`
- Fonts: Manrope (headings), Inter (body), Cormorant Garamond (hero)
- Components: Shadcn/UI from `/app/frontend/src/components/ui/`

**Timezone & Locale:**
- To be confirmed (default: UTC for now)

**Reminder Windows:**
- To be configured in Phase 4 based on event type

---

## 4) Success Criteria (Project-level)

**Phase 1 (Integration POC):** ✅ ACHIEVED
- ✅ WhatsApp sends verified end-to-end with documented response shape
- ✅ Email integration clearly marked as pending

**Phase 2 (Core MVP):** 🎯 TARGET
- Add member → log care event → dashboard visibility → manual reminder send (WhatsApp) fully functional
- All CRUD operations working smoothly
- Dashboard provides actionable insights
- UI follows design system consistently

**Phase 3 (Auth):** 🎯 TARGET
- Role-based access enforced without breaking core flows
- Secure authentication with JWT

**Phase 4 (Automation):** 🎯 TARGET
- Daily reminders and logs with retry capability
- Manual trigger works reliably

**Phase 5 (Polish):** 🎯 TARGET
- Feature-complete with calendar, analytics, export
- Performance and accessibility optimized
- Production-ready quality

**Overall Quality Standards:**
- Uses sage/peach/teal design tokens throughout
- Light/dark mode support
- Shadcn components exclusively
- data-testid on all interactive elements
- One automated test cycle per phase with fixes applied
- Responsive design (mobile, tablet, desktop)
- Accessibility WCAG AA compliant

---

## 5) Next Immediate Actions (Phase 2 Start)

**Priority 1 - Backend Setup:**
1. Create database models: Member, CareEvent, NotificationLog
2. Implement Member CRUD endpoints with family connections support
3. Implement CareEvent CRUD endpoints with event type validation
4. Create dashboard endpoints (stats, upcoming, overdue, recent activity)
5. Add notification endpoint for manual WhatsApp reminder sending

**Priority 2 - Frontend Foundation:**
1. Set up design tokens (CSS custom properties) from design_guidelines.md
2. Import Google Fonts (Manrope, Inter, Cormorant Garamond)
3. Configure Tailwind with custom colors and spacing
4. Set up dark mode toggle
5. Configure Sonner for toast notifications

**Priority 3 - Core Screens:**
1. Build Dashboard with stats cards and upcoming events list
2. Build Members List with table and search
3. Build Member Detail with timeline and family connections
4. Build Add/Edit Member form with validation
5. Build Add/Edit Care Event form with event type selector

**Priority 4 - Testing & Polish:**
1. Test end-to-end flow: add member → add event → dashboard → send reminder
2. Run automated testing agent
3. Fix critical bugs identified
4. Verify design system consistency
5. Check all data-testid attributes present

---

## 6) Technical Debt & Known Issues

**Current:**
- Backend .env file had formatting issue (fixed)
- python-dotenv warning on line 3 (non-critical, doesn't affect functionality)

**To Address in Phase 2:**
- Implement proper error handling for all API calls
- Add input validation on all forms
- Implement pagination for members and events lists
- Add loading states for all async operations

**Future Considerations:**
- Email provider selection and integration (Phase 4+)
- Reminder rule configuration UI (Phase 4)
- Advanced analytics and reporting (Phase 5)
- Multi-language support (future)
- Mobile app (future)

---

**Last Updated:** 2025-11-13
**Current Phase:** Phase 2 - Core MVP Development
**Next Milestone:** Complete member and care event management with dashboard
