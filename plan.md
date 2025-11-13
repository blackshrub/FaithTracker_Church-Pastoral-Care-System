# Church Pastoral Care Tracking System – Development Plan

## 1) Objectives (MVP-first)
- Centralize member records with family connections (no member left behind)
- Track care events (birthday, childbirth, grief, new house, accident/illness, regular contact, prayer)
- View Upcoming/Overdue items at a glance (dashboard)
- Send reminders via WhatsApp gateway (http://dermapack.net:3001) and Email
- Simple role-based access (Pastoral Team, Admin) added after core works
- Apply warm, compassionate design (Primary: Sage, Secondary: Peach, Accent: Teal per design_guidelines.md)

## 2) Strategic Phases & Implementation Steps

PHASE 1: Core Integration POC (Required before app build)
- Goal: Prove outbound notifications work reliably.
- Steps:
  - Request Integration Playbooks: WhatsApp gateway (provided endpoint/docs), Email (await provider choice: SMTP/SendGrid/etc.)
  - Add backend env support (do NOT edit existing var values): WHATSAPP_GATEWAY_URL, EMAIL_* placeholders
  - Create minimal FastAPI routes: /api/integrations/ping/whatsapp, /api/integrations/ping/email
  - Implement WhatsApp call (per doc) with basic payload, capture success/error clearly
  - If email provider confirmed, send a basic text email; else stub endpoint returns 501 until provider selected
  - Add a tiny React test screen (button → ping endpoints) with toasts and data-testid
- User Stories:
  1) As an admin, I can send a WhatsApp test message to a test number and see success/error.
  2) As an admin, I can trigger a test email and see success/error (or a clear "pending provider" message).
  3) As a pastor, I can view a short audit log of the last 5 test sends.
  4) As an admin, I can configure gateway base URL via env (no code change).
  5) As a user, I see friendly toasts reflecting the result.
- Exit Criteria:
  - WhatsApp test message successfully sent end-to-end and response shape documented
  - Email: either successfully sent or explicitly blocked pending provider decision (clearly flagged)

PHASE 2: V1 App Development (Unauthenticated vertical slice)
- Goal: Working slice from data → dashboard → manual reminder send.
- Backend (FastAPI + Mongo):
  - Models (UUIDs, timezone-aware): Member, CareEvent, NotificationLog
  - Endpoints (all /api/*): CRUD Members, CRUD CareEvents, GET dashboard (upcoming, overdue), POST /care-events/{id}/send-reminder (WhatsApp now; Email later)
- Frontend (React + Shadcn):
  - Design tokens (sage/peach/teal), light/dark, Sonner toasts, data-testid on all interactive elements
  - Screens: Dashboard (stats + upcoming list + recent activity), Members List + Add/Edit, Member Detail (timeline + add event), Simple Integrations Test panel (from Phase 1)
  - Loading/Empty/Error states everywhere; axios client with REACT_APP_BACKEND_URL
- User Stories:
  1) As a pastor, I can add a new member and link family members.
  2) As a pastor, I can create a care event for a member with date/type/notes.
  3) As a pastor, I can see upcoming birthdays and follow-ups on the dashboard.
  4) As a pastor, I can manually send a WhatsApp reminder for a care event and see success/error.
  5) As a pastor, I can browse recent care activities.
- Exit Criteria:
  - End-to-end flow works (add member → add care event → see in dashboard → send WhatsApp reminder)
  - One round of automated E2E testing executed and major issues fixed

PHASE 3: Authentication & Roles
- Goal: Restrict access and separate admin-only actions.
- Steps:
  - Simple JWT auth (email/password), roles: ADMIN, PASTOR; protect routes
  - Login UI, token storage, axios interceptor, logout
  - Admin screens for settings (gateway URL read-only display) and user management (basic)
- User Stories:
  1) As a user, I can log in with email/password and access the app.
  2) As an admin, I can manage users and roles.
  3) As a pastor, I can access member/care features but not admin settings.
  4) As a user, I remain signed in across refresh until token expires.
  5) As a user, I see clear feedback for invalid credentials.
- Exit Criteria:
  - Protected endpoints enforce roles; core flows remain functional under auth
  - Testing pass for auth flows and role restrictions

PHASE 4: Automated Reminders & Scheduling
- Goal: Automate daily reminders and logs.
- Steps:
  - Implement schedule runner (e.g., APScheduler or periodic endpoint hit) scanning upcoming events per rules (e.g., birthdays 7/3/1 days prior; grief immediate follow-up; configurable later)
  - Templated WhatsApp messages; integrate Email provider once chosen; write NotificationLog entries
  - Add dashboard widget for "Overdue Follow-ups" and "Reminders sent today"
- User Stories:
  1) As a pastor, I see a list of members who need contact today.
  2) As an admin, I can run reminders now with a button (manual trigger).
  3) As a pastor, I can view the history of reminders per member/event.
  4) As a pastor, I can retry failed reminders.
  5) As a user, I can see which channel(s) were used (WhatsApp/Email).
- Exit Criteria:
  - Daily run creates sends and logs with clear success/failure; manual trigger works
  - Email reminders enabled with chosen provider; WhatsApp stable

PHASE 5: Enhancements & Polish
- Scope:
  - Calendar view (month) with color-coded events; search/filter; export CSV
  - Assignment of members to caregivers; tags/status; simple analytics
  - UI/UX polish per design system; performance and accessibility checks
- User Stories:
  1) As a pastor, I can see a calendar of upcoming care events by type.
  2) As a pastor, I can filter members by tag/status to plan weekly outreach.
  3) As a leader, I can export care events to CSV.
  4) As a pastor, I can be assigned a set of members and see my list.
  5) As a leader, I can view weekly stats of contacts made vs pending.
- Exit Criteria:
  - Feature set above demonstrably working; tests clear; UI matches design tokens

## 3) Next Actions (Blocking → Unblocking)
1) Confirm email provider (SMTP creds vs SendGrid/Mailgun). If none, proceed WhatsApp-first and leave email POC pending.
2) Provide a test WhatsApp recipient number and preferred sender identity (if applicable in gateway).
3) Confirm default timezone and locale (e.g., Africa/Lagos or Asia/Jakarta) for reminder timings.
4) Confirm initial event categories and default reminder windows (e.g., birthdays: 7/3/1 days).
5) Approve minimal templates for WhatsApp/email messages (tone, sign-off, church name).

## 4) Success Criteria (Project-level)
- Core: Verified outbound WhatsApp sends; Email sends verified or clearly pending provider
- MVP: Add member → log care event → dashboard visibility → manual reminder send (WhatsApp) fully functional
- Auth: Role-based access enforced without breaking core flows
- Automation: Daily reminders and logs with retry; manual run works
- Design: Uses sage/peach/teal tokens, light/dark, shadcn components, data-testid in all interactive elements
- Testing: One automated test cycle per phase with fixes applied
