# FaithTracker REST API Documentation v2.0

**Base URL:** `{BACKEND_URL}/api`  
**Authentication:** Bearer token (JWT) in `Authorization` header  
**All requests/responses:** `Content-Type: application/json`

---

## 🆕 What's New (v2.0)

- ✅ **Campus Timezone Configuration:** Per-campus timezone settings (45+ international timezones)
- ✅ **Birthday Auto-Generation:** Birthdays created from birth_date, manual entry disabled
- ✅ **Enhanced Photo Support:** photo_url in all member responses
- ✅ **Bilingual Support:** 180+ translation keys (Indonesian/English)
- ✅ **Performance Optimizations:** Faster responses, better caching

---

## Authentication

### POST `/auth/register`
Create new user (admin only)

### POST `/auth/login`  
User login - Returns JWT token

### GET `/auth/me`
Get current user info

---

## Campus Management 🆕

### GET `/campuses`
List all campuses

### GET `/campuses/{campus_id}` 🆕 Updated
Get campus details **including timezone**
```json
Response: {
  "id": "uuid",
  "campus_name": "string",
  "location": "string",
  "timezone": "Asia/Jakarta",  // 🆕 NEW FIELD
  "is_active": boolean
}
```

### PUT `/campuses/{campus_id}` 🆕 Updated
Update campus **including timezone**
```json
Request: {
  "timezone": "Asia/Singapore"  // 🆕 Update timezone
}
```

**Available Timezones:**
- Asia: Jakarta, Singapore, Tokyo, Seoul, Manila, Bangkok, Dubai, Riyadh, Kolkata, Hong Kong, Shanghai, Taipei
- Australia/Pacific: Sydney, Melbourne, Perth, Auckland, Fiji
- Americas: New York, Los Angeles, Toronto, Mexico City, São Paulo
- Europe: London, Paris, Berlin, Moscow, Istanbul
- Africa: Cairo, Johannesburg, Lagos, Nairobi

---

## Members

### GET `/members`
List with search, pagination, filtering

**Query Params:**
- `search`: Name or phone search
- `skip`, `limit`: Pagination
- `engagement_status`: Filter by status

### GET `/members/{member_id}` 🆕 Updated
Includes `photo_url`, `engagement_status`, `days_since_last_contact`

### POST `/members`
Create member

### PUT `/members/{member_id}`
Update member

### DELETE `/members/{member_id}`
Delete member + all related events

### POST `/members/{member_id}/photo`
Upload photo - Returns `photo_url`

---

## Care Events 🆕 Updated

### GET `/care-events`
List events with filters

**Event Types:**
- ✅ `childbirth` - Childbirth
- ✅ `grief_loss` - Grief/Loss (auto-generates 6-stage timeline)
- ✅ `new_house` - New House
- ✅ `accident_illness` - Accident/Illness (auto-generates 3-stage follow-up)
- ✅ `hospital_visit` - Hospital Visit
- ✅ `financial_aid` - Financial Aid
- ✅ `regular_contact` - Regular Contact
- ⚠️ `birthday` - **AUTO-GENERATED ONLY** (do not allow manual creation)

### POST `/care-events` 🆕 Updated
**Important:** Do NOT allow `event_type: "birthday"` from mobile app
- Birthdays auto-created from member's `birth_date`
- Use completion endpoint to mark birthdays complete

### POST `/care-events/{event_id}/complete` 🆕
Mark event complete (including birthdays)

**Use for:**
- Birthday completion (updates engagement status)
- Regular contact logging
- Event follow-up tracking

---

## Financial Aid 🆕 Updated

### GET `/financial-aid/summary`
Total aid statistics by type

### GET `/financial-aid/recipients` 🆕 Enhanced
Recipients with photo URLs
```json
Response: [
  {
    "member_id": "uuid",
    "member_name": "string",
    "photo_url": "string",  // 🆕 Includes photo
    "total_amount": float,
    "aid_count": int
  }
]
```

### GET `/financial-aid/member/{member_id}`
All aid for specific member

### GET `/financial-aid-schedules`
List all recurring schedules

### POST `/financial-aid-schedules`
Create recurring aid schedule

### POST `/financial-aid-schedules/{id}/mark-distributed`
Mark monthly distribution complete

---

## Analytics

### GET `/analytics/grief-completion-rate`
Grief support metrics

### GET `/analytics/engagement-summary`
Member engagement statistics

---

## Mobile App Development Guide

### 1. Initial Setup
```javascript
// On app start/login:
const user = await login(email, password);
const campus = await getCampus(user.campus_id);
const timezone = campus.timezone; // Store globally

// Load translations
import id from './locales/id.json';
import en from './locales/en.json';
```

### 2. Date/Time Handling 🆕
```javascript
// Always use campus timezone for display
import { formatInTimeZone } from 'date-fns-tz';

const displayDate = formatInTimeZone(
  serverDate,
  campusTimezone,  // From campus.timezone
  'dd MMM yyyy'
);

// Send dates in ISO format
const dateToSend = '2025-11-14'; // YYYY-MM-DD
```

### 3. Birthday Handling 🆕
```javascript
// DO NOT create birthday events manually
// ❌ BAD:
await createCareEvent({ event_type: 'birthday', ... });

// ✅ GOOD: Birthdays auto-generated from birth_date
// Just display and allow completion:
const birthdays = events.filter(e => 
  e.event_type === 'birthday' && !e.completed
);

// Show in UI with Mark Complete button:
await axios.post(`/api/care-events/${birthdayId}/complete`);
```

### 4. Translation Keys 🆕
Use translation keys from `/app/frontend/src/locales/`:
```javascript
t('dashboard')  // "Dasbor" (ID) / "Dashboard" (EN)
t('total_members')  // "Total Jemaat" / "Total Members"
t('event_types.grief_loss')  // "Dukacita/Kehilangan" / "Grief/Loss"
```

### 5. Photo Display 🆕
```javascript
// Photos now included in member responses
const photoUrl = `${BACKEND_URL}${member.photo_url}`;
// Or use in recipient lists:
const recipients = await getFinancialAidRecipients();
// Each recipient has photo_url field
```

### 6. Engagement Status
```javascript
// Auto-calculated, read-only
member.engagement_status;  // "active" | "at_risk" | "inactive" | "disconnected"
member.days_since_last_contact;  // Number of days

// Updates automatically when care events added/completed
```

---

## Breaking Changes from v1.0

### ⚠️ Birthday Events
- **OLD:** Could create birthday events manually
- **NEW:** Birthday events auto-generated only, manual creation disabled

### 🆕 Required Fields
- **Campus:** Now includes `timezone` field (default: "Asia/Jakarta")
- **Financial Aid Recipients:** Now includes `photo_url`

### 🆕 Recommended Updates
- Implement timezone-aware date display
- Add Indonesian/English language toggle
- Remove birthday from event type selectors
- Show birthdays 7 days before actual date

---

## Testing Endpoints

**Base URL:** https://member-pulse-3.preview.emergentagent.com/api

**Test Account:**
- Email: `admin@gkbj.church`
- Password: `admin123`
- Role: Full Administrator

**Sample Data:**
- 805 members imported
- 1000+ care events
- Multiple grief timelines
- Financial aid schedules active

---

**API Version:** 2.0  
**Last Updated:** 2025-11-14  
**Total Endpoints:** 85+  
**Mobile-Ready:** ✅ Fully supported  
**Timezone-Aware:** ✅ Campus-level configuration  
**Bilingual:** ✅ Indonesian & English (180+ keys)  
**Photo Support:** ✅ All member/recipient endpoints
