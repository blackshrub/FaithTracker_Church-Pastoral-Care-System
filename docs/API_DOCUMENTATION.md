# FaithTracker REST API Documentation

**Version**: 2.1
**Base URL**: `{BACKEND_URL}/api`
**Authentication**: Bearer token (JWT)
**Content-Type**: `application/json`

---

## Table of Contents

- [Authentication](#authentication)
- [Health Endpoints](#health-endpoints)
- [Members](#members)
- [Care Events](#care-events)
- [Dashboard](#dashboard)
- [Analytics](#analytics)
- [Reports](#reports)
- [Data Export](#data-export)
- [API Sync](#api-sync)
- [Real-Time Activity Stream (SSE)](#real-time-activity-stream-sse)
- [Activity Logs](#activity-logs)
- [Campuses](#campuses)
- [Users](#users)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Postman Collection](#postman-collection)

---

## Authentication

### Login
```http
POST /api/auth/login
Content-Type: application/json
```

**Request Body**:
```json
{
  "email": "admin@church.org",
  "password": "your-password"
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "admin@church.org",
    "name": "Admin User",
    "role": "full_admin",
    "campus_id": null,
    "campus_name": null,
    "phone": "+6281234567890",
    "photo_url": "/api/uploads/users/admin-photo.jpg"
  }
}
```

**Error Response** (401 Unauthorized):
```json
{
  "detail": "Incorrect email or password"
}
```

**Rate Limit**: 5 requests per minute

### Using the Token
Include the token in all subsequent requests:
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Health Endpoints

These endpoints do not require authentication.

### Liveness Probe
```http
GET /health
```

**Response** (200 OK):
```json
{
  "status": "healthy",
  "service": "faithtracker-api",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

### Readiness Probe
```http
GET /ready
```

**Response** (200 OK):
```json
{
  "status": "ready",
  "database": "connected",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

**Response** (503 Service Unavailable):
```json
{
  "status": "not_ready",
  "database": "disconnected",
  "error": "Connection refused"
}
```

---

## Members

### List Members
```http
GET /api/members?page=1&limit=25&engagement_status=active&search=john
Authorization: Bearer {token}
```

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| page | int | 1 | Page number |
| limit | int | 50 | Items per page (max 1000) |
| engagement_status | string | - | Filter: active, at_risk, disconnected |
| search | string | - | Search by name or phone |
| show_archived | bool | false | Include archived members |

**Response Headers**:
```
X-Total-Count: 150
```

**Response** (200 OK):
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "name": "John Doe",
    "phone": "+6281234567890",
    "campus_id": "campus-001",
    "photo_url": "/api/uploads/members/john-doe.jpg",
    "engagement_status": "active",
    "days_since_last_contact": 5,
    "last_contact_date": "2024-01-10T08:00:00.000Z",
    "age": 35,
    "gender": "male"
  }
]
```

### Get Member
```http
GET /api/members/{id}
Authorization: Bearer {token}
```

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "name": "John Doe",
  "phone": "+6281234567890",
  "email": "john@example.com",
  "birth_date": "1990-01-15",
  "gender": "male",
  "address": "123 Main St",
  "campus_id": "campus-001",
  "photo_url": "/api/uploads/members/john-doe.jpg",
  "engagement_status": "active",
  "days_since_last_contact": 5,
  "last_contact_date": "2024-01-10T08:00:00.000Z",
  "notes": "Active church member",
  "family_group_name": "Doe Family",
  "created_at": "2023-06-01T10:00:00.000Z"
}
```

### Create Member
```http
POST /api/members
Authorization: Bearer {token}
Content-Type: application/json
```

**Request Body**:
```json
{
  "name": "Jane Smith",
  "phone": "+6289876543210",
  "email": "jane@example.com",
  "birth_date": "1985-05-20",
  "gender": "female",
  "address": "456 Oak Ave",
  "notes": "New member"
}
```

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "name": "Jane Smith",
  "phone": "+6289876543210",
  "email": "jane@example.com",
  "birth_date": "1985-05-20",
  "gender": "female",
  "campus_id": "campus-001",
  "engagement_status": "active",
  "created_at": "2024-01-15T10:30:00.000Z"
}
```

### Update Member
```http
PUT /api/members/{id}
Authorization: Bearer {token}
Content-Type: application/json
```

**Request Body**:
```json
{
  "name": "Jane Smith-Johnson",
  "phone": "+6289876543210",
  "address": "789 New Address"
}
```

### Delete Member
```http
DELETE /api/members/{id}
Authorization: Bearer {token}
```

### Upload Member Photo
```http
POST /api/members/{id}/photo
Authorization: Bearer {token}
Content-Type: multipart/form-data
```

**Form Data**:
- `file`: Image file (JPEG, PNG)

---

## Care Events

### List Care Events
```http
GET /api/care-events?member_id={member_id}
Authorization: Bearer {token}
```

**Response** (200 OK):
```json
[
  {
    "id": "event-001",
    "member_id": "550e8400-e29b-41d4-a716-446655440001",
    "event_type": "birthday",
    "event_date": "2024-01-15",
    "completed": false,
    "ignored": false,
    "notes": "35th birthday",
    "created_at": "2024-01-01T00:00:00.000Z",
    "created_by": "admin-user-id",
    "created_by_name": "Admin User"
  }
]
```

### Create Care Event
```http
POST /api/care-events
Authorization: Bearer {token}
Content-Type: application/json
```

**Request Body**:
```json
{
  "member_id": "550e8400-e29b-41d4-a716-446655440001",
  "event_type": "grief_loss",
  "event_date": "2024-01-15",
  "notes": "Loss of father"
}
```

**Event Types**:
- `birthday` - Birthday celebration
- `grief_loss` - Grief/loss support (auto-generates 6-stage timeline)
- `accident_illness` - Hospital/illness visits (auto-generates follow-ups)
- `financial_aid` - Financial assistance
- `childbirth` - New baby celebration
- `new_house` - New house blessing
- `regular_contact` - Regular check-in

**Response** (200 OK) - Grief Loss Example:
```json
{
  "id": "event-002",
  "member_id": "550e8400-e29b-41d4-a716-446655440001",
  "event_type": "grief_loss",
  "event_date": "2024-01-15",
  "notes": "Loss of father",
  "created_at": "2024-01-15T10:30:00.000Z",
  "grief_stages": [
    {"stage": "mourning_service", "scheduled_date": "2024-01-15"},
    {"stage": "3_day", "scheduled_date": "2024-01-18"},
    {"stage": "7_day", "scheduled_date": "2024-01-22"},
    {"stage": "40_day", "scheduled_date": "2024-02-24"},
    {"stage": "100_day", "scheduled_date": "2024-04-24"},
    {"stage": "1_year", "scheduled_date": "2025-01-15"}
  ]
}
```

### Complete Care Event
```http
POST /api/care-events/{id}/complete
Authorization: Bearer {token}
```

### Ignore Care Event
```http
POST /api/care-events/{id}/ignore
Authorization: Bearer {token}
```

### Delete Care Event
```http
DELETE /api/care-events/{id}
Authorization: Bearer {token}
```

---

## Dashboard

### Get Dashboard Data
```http
GET /api/dashboard/reminders
Authorization: Bearer {token}
```

**Response** (200 OK):
```json
{
  "birthdays_today": [
    {
      "id": "event-001",
      "member_id": "member-001",
      "member_name": "John Doe",
      "member_phone": "+6281234567890",
      "member_photo_url": "/api/uploads/members/john.jpg",
      "member_age": 35,
      "completed": false
    }
  ],
  "overdue_birthdays": [],
  "upcoming_birthdays": [],
  "today_tasks": [],
  "grief_today": [],
  "accident_followup": [],
  "at_risk_members": [],
  "disconnected_members": [],
  "financial_aid_due": [],
  "upcoming_tasks": [],
  "total_tasks": 5,
  "total_members": 150
}
```

---

## Analytics

### Get Analytics Dashboard
```http
GET /api/analytics/dashboard
Authorization: Bearer {token}
```

**Response** (200 OK):
```json
{
  "members": {
    "total": 500,
    "with_photos": 350,
    "active": 400,
    "at_risk": 75,
    "disconnected": 25
  },
  "demographics": {
    "age_distribution": [
      {"range": "0-17", "count": 50},
      {"range": "18-35", "count": 150},
      {"range": "36-50", "count": 180},
      {"range": "51-65", "count": 80},
      {"range": "65+", "count": 40}
    ],
    "gender_distribution": {"male": 240, "female": 260},
    "membership_status": {"active": 400, "inactive": 50, "new": 50}
  },
  "financial_aid": {
    "total_distributed": 50000000,
    "active_schedules": 15,
    "by_type": [
      {"type": "medical", "amount": 20000000},
      {"type": "educational", "amount": 15000000}
    ]
  },
  "grief_support": {
    "total_stages": 120,
    "completed_stages": 95,
    "completion_rate": 79.2
  },
  "average_age": 38.5
}
```

### Get Engagement Trends
```http
GET /api/analytics/engagement-trends
Authorization: Bearer {token}
```

**Response** (200 OK):
```json
{
  "trends": [
    {"date": "2024-01-01", "care_events": 15},
    {"date": "2024-01-02", "care_events": 22}
  ]
}
```

### Get Demographic Trends
```http
GET /api/analytics/demographic-trends
Authorization: Bearer {token}
```

**Response** (200 OK):
```json
{
  "age_groups": [
    {"range": "18-35", "count": 150, "percentage": 30}
  ],
  "membership_trends": {...},
  "care_needs_by_age": {...},
  "insights": {
    "population": ["Largest age group is 36-50 (36%)"],
    "care_adaptations": ["Focus on family-oriented care programs"],
    "strategic_recommendations": {
      "high_priority": ["Develop youth engagement programs"],
      "medium_term": ["Expand elderly care services"],
      "long_term": ["Plan for demographic shifts"]
    }
  }
}
```

---

## Reports

### Get Monthly Report
```http
GET /api/reports/monthly?year=2024&month=12
Authorization: Bearer {token}
```

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| year | int | current | Report year |
| month | int | current | Report month (1-12) |

**Response** (200 OK):
```json
{
  "period": {"year": 2024, "month": 12},
  "executive_summary": {
    "total_members": 500,
    "active_members": 400,
    "at_risk_members": 75,
    "inactive_members": 25
  },
  "kpis": {
    "care_completion_rate": 85.5,
    "engagement_rate": 80.0,
    "member_reach_rate": 65.0,
    "birthday_completion": {"celebrated": 45, "ignored": 5, "total": 50}
  },
  "ministry_highlights": {
    "grief_support": {"families": 8, "touchpoints": 24},
    "hospital_visits": {"patients": 12, "total_visits": 36},
    "birthdays": {"celebrated": 45, "skipped": 5},
    "financial_aid": {"total": 15000000, "recipients": 10}
  },
  "weekly_trends": [...],
  "insights": ["Engagement increased 5% from last month"],
  "recommendations": ["Focus on re-engaging at-risk members"]
}
```

### Download Monthly Report PDF
```http
GET /api/reports/monthly/pdf?year=2024&month=12
Authorization: Bearer {token}
```

**Response**: PDF file download
- Content-Type: `application/pdf`
- Filename: `Pastoral_Care_Report_December_2024.pdf`

### Get Staff Performance Report
```http
GET /api/reports/staff-performance?year=2024&month=12
Authorization: Bearer {token}
```

**Response** (200 OK):
```json
{
  "team_overview": {
    "total_staff": 10,
    "balanced": 6,
    "overworked": 2,
    "underworked": 2
  },
  "metrics": {
    "total_tasks_completed": 450,
    "avg_tasks_per_staff": 45,
    "max_min_difference": 30
  },
  "top_performers": [
    {"name": "Pastor John", "tasks": 75, "photo_url": "/api/uploads/users/john.jpg"},
    {"name": "Pastor Sarah", "tasks": 68, "photo_url": null}
  ],
  "individual_performance": [
    {
      "user_id": "user-001",
      "name": "Pastor John",
      "role": "pastor",
      "tasks_completed": 75,
      "members_contacted": 45,
      "active_days": 22,
      "workload_status": "balanced"
    }
  ],
  "recommendations": [
    {"priority": "high", "action": "Redistribute tasks from overworked staff"}
  ]
}
```

### Get Yearly Summary
```http
GET /api/reports/yearly-summary?year=2024
Authorization: Bearer {token}
```

**Response** (200 OK):
```json
{
  "year": 2024,
  "totals": {
    "members": 500,
    "care_events": 2400,
    "completion_rate": 82.5,
    "financial_aid": 180000000
  },
  "monthly_breakdown": [
    {"month": 1, "care_events": 180, "completed": 150}
  ],
  "care_by_type": [
    {"type": "birthday", "total": 600, "completed": 580}
  ]
}
```

---

## Data Export

### Export Members to CSV
```http
GET /api/export/members/csv
Authorization: Bearer {token}
```

**Response**: CSV file download
- Content-Type: `text/csv`
- Fields: id, name, phone, external_member_id, last_contact_date, engagement_status, days_since_last_contact, notes

### Export Care Events to CSV
```http
GET /api/export/care-events/csv
Authorization: Bearer {token}
```

**Response**: CSV file download
- Content-Type: `text/csv`
- Fields: id, member_id, event_type, event_date, title, description, completed, aid_type, aid_amount, hospital_name

---

## API Sync

Integration with FaithFlow Enterprise or external church management systems.

### Save Sync Configuration
```http
POST /api/sync/config
Authorization: Bearer {token}
Content-Type: application/json
```

**Request Body**:
```json
{
  "sync_method": "polling",
  "api_base_url": "https://faithflow.example.com",
  "api_path_prefix": "/api",
  "api_login_endpoint": "/auth/login",
  "api_members_endpoint": "/members/",
  "api_email": "sync@church.org",
  "api_password": "your-password",
  "polling_interval_hours": 6,
  "is_enabled": true,
  "filter_mode": "include",
  "filter_rules": [
    {"field": "gender", "operator": "equals", "value": "Female"},
    {"field": "age", "operator": "between", "value": [18, 35]}
  ],
  "reconciliation_enabled": true,
  "reconciliation_time": "03:00"
}
```

**Filter Operators**:
| Operator | Description | Example Value |
|----------|-------------|---------------|
| `equals` | Exact match | `"active"` |
| `not_equals` | Not equal | `"inactive"` |
| `contains` | Substring match | `"Smith"` |
| `in` | Value in list | `["active", "new"]` |
| `not_in` | Value not in list | `["deleted"]` |
| `greater_than` | Numeric > | `18` |
| `less_than` | Numeric < | `65` |
| `between` | Numeric range | `[18, 35]` |
| `is_true` | Boolean true | `null` |
| `is_false` | Boolean false | `null` |

### Get Sync Configuration
```http
GET /api/sync/config
Authorization: Bearer {token}
```

### Test Connection
```http
POST /api/sync/test-connection
Authorization: Bearer {token}
Content-Type: application/json
```

**Request Body**:
```json
{
  "api_base_url": "https://faithflow.example.com",
  "api_path_prefix": "/api",
  "api_login_endpoint": "/auth/login",
  "api_email": "sync@church.org",
  "api_password": "your-password"
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Connection successful"
}
```

### Discover Fields
```http
POST /api/sync/discover-fields
Authorization: Bearer {token}
```

Analyzes the external API to discover available fields for filtering.

**Response** (200 OK):
```json
{
  "fields": [
    {"name": "gender", "type": "string", "values": ["male", "female"]},
    {"name": "age", "type": "number", "min": 0, "max": 100},
    {"name": "membership_status", "type": "string", "values": ["active", "inactive"]}
  ]
}
```

### Trigger Manual Sync
```http
POST /api/sync/members/pull
Authorization: Bearer {token}
```

**Response** (200 OK):
```json
{
  "status": "success",
  "members_fetched": 500,
  "members_created": 10,
  "members_updated": 45,
  "members_archived": 2,
  "duration_seconds": 12.5
}
```

### Receive Webhook
```http
POST /api/sync/webhook
X-Signature: {hmac-sha256-signature}
Content-Type: application/json
```

**Request Body**:
```json
{
  "event": "member.updated",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "id": "ext-member-001",
    "name": "John Doe",
    "phone": "+6281234567890"
  }
}
```

**Event Types**:
- `member.created` - New member added
- `member.updated` - Member data changed
- `member.deleted` - Member removed
- `ping` - Test webhook connectivity

### Regenerate Webhook Secret
```http
POST /api/sync/regenerate-secret
Authorization: Bearer {token}
```

**Response** (200 OK):
```json
{
  "webhook_secret": "new-256-bit-secret"
}
```

### Get Sync Logs
```http
GET /api/sync/logs?page=1&limit=20
Authorization: Bearer {token}
```

**Response** (200 OK):
```json
{
  "logs": [
    {
      "id": "log-001",
      "sync_type": "scheduled",
      "status": "success",
      "members_fetched": 500,
      "members_created": 5,
      "members_updated": 20,
      "members_archived": 1,
      "started_at": "2024-01-15T03:00:00+07:00",
      "completed_at": "2024-01-15T03:00:15+07:00",
      "duration_seconds": 15.2
    }
  ],
  "total": 100,
  "page": 1,
  "limit": 20
}
```

---

## Real-Time Activity Stream (SSE)

FaithTracker supports real-time team activity updates via Server-Sent Events (SSE).

### Connect to Activity Stream
```http
GET /stream/activity?token={jwt_token}
Accept: text/event-stream
```

**Note:** EventSource doesn't support custom headers, so JWT token is passed via query parameter.

**Event Types:**

| Event | Description |
|-------|-------------|
| `heartbeat` | Keep-alive ping (every 30 seconds) |
| `activity` | New activity from a team member |

**Activity Event Data:**
```json
{
  "id": "log-001",
  "campus_id": "campus-001",
  "user_id": "user-001",
  "user_name": "Pastor John",
  "user_photo_url": "/api/uploads/users/john.jpg",
  "action_type": "complete",
  "member_id": "member-001",
  "member_name": "Jane Doe",
  "care_event_id": "event-001",
  "event_type": "birthday",
  "notes": "Called and wished happy birthday",
  "timestamp": "2024-01-15T10:30:00+07:00"
}
```

**Action Types:**
| Action | Description |
|--------|-------------|
| `complete` | Task marked as done |
| `ignore` | Task skipped |
| `create_event` | New care event created |
| `update_event` | Care event modified |
| `delete_event` | Care event removed |
| `create_member` | New member added |
| `update_member` | Member profile updated |
| `delete_member` | Member removed |
| `complete_stage` | Grief/accident stage completed |
| `ignore_stage` | Grief/accident stage skipped |
| `undo_stage` | Grief/accident stage undone |
| `send_reminder` | WhatsApp reminder sent |
| `distribute_aid` | Financial aid distributed |

**JavaScript Example:**
```javascript
const token = 'your-jwt-token';
const eventSource = new EventSource(`/stream/activity?token=${encodeURIComponent(token)}`);

eventSource.addEventListener('activity', (event) => {
  const activity = JSON.parse(event.data);
  console.log(`${activity.user_name} completed a task for ${activity.member_name}`);
});

eventSource.addEventListener('heartbeat', () => {
  console.log('Connection alive');
});

eventSource.onerror = () => {
  console.log('Connection lost, will auto-reconnect');
};
```

**Notes:**
- Activities are filtered to exclude the connected user's own actions
- Stream only shows activities from the same campus
- Connection auto-reconnects on failure (browser handles this)
- Angie (reverse proxy) must have compression disabled for SSE endpoints

---

## Activity Logs

### Get Activity Logs
```http
GET /api/activity-logs?page=1&limit=50&action_type=complete_task&user_id={user_id}
Authorization: Bearer {token}
```

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| page | int | Page number |
| limit | int | Items per page |
| action_type | string | Filter by action type |
| user_id | string | Filter by user |
| start_date | string | Start date (YYYY-MM-DD) |
| end_date | string | End date (YYYY-MM-DD) |

**Action Types**:
- `complete_task`, `ignore_task`, `undo_task`
- `create_event`, `delete_event`
- `complete_grief`, `ignore_grief`, `undo_grief`
- `complete_accident`, `ignore_accident`, `undo_accident`
- `financial_distributed`, `financial_stopped`, `financial_ignored`
- `send_reminder`, `contact_member`

**Response** (200 OK):
```json
{
  "logs": [
    {
      "id": "log-001",
      "user_id": "user-001",
      "user_name": "Pastor John",
      "user_photo_url": "/api/uploads/users/john.jpg",
      "action_type": "complete_task",
      "member_id": "member-001",
      "member_name": "Jane Doe",
      "event_type": "birthday",
      "notes": "Called and wished happy birthday",
      "timestamp": "2024-01-15T10:30:00+07:00"
    }
  ],
  "total": 100,
  "page": 1,
  "limit": 50
}
```

---

## Campuses

### List Campuses
```http
GET /api/campuses
Authorization: Bearer {token}
```

**Response** (200 OK):
```json
[
  {
    "id": "campus-001",
    "campus_name": "Main Campus",
    "location": "Jakarta",
    "timezone": "Asia/Jakarta",
    "is_active": true
  }
]
```

### Create Campus (Admin Only)
```http
POST /api/campuses
Authorization: Bearer {token}
Content-Type: application/json
```

**Request Body**:
```json
{
  "campus_name": "North Campus",
  "location": "North Jakarta",
  "timezone": "Asia/Jakarta"
}
```

---

## Users

### List Users (Admin Only)
```http
GET /api/users
Authorization: Bearer {token}
```

### Create User (Admin Only)
```http
POST /api/auth/register
Authorization: Bearer {token}
Content-Type: application/json
```

**Request Body**:
```json
{
  "email": "pastor@church.org",
  "password": "secure-password",
  "name": "Pastor Name",
  "role": "pastor",
  "campus_id": "campus-001",
  "phone": "+6281234567890"
}
```

**Roles**:
- `full_admin` - Access all campuses
- `campus_admin` - Manage single campus
- `pastor` - Regular staff

**Rate Limit**: 10 requests per minute

---

## Error Handling

### Error Response Format
```json
{
  "detail": "Error message here"
}
```

### HTTP Status Codes
| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Invalid/missing token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 422 | Validation Error - Invalid data format |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |

### Validation Error Example
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

---

## Rate Limiting

| Endpoint | Limit |
|----------|-------|
| POST /api/auth/login | 5/minute |
| POST /api/auth/register | 10/minute |
| All other endpoints | No limit |

**Rate Limit Exceeded Response** (429):
```json
{
  "error": "Rate limit exceeded: 5 per 1 minute"
}
```

---

## Postman Collection

### Import to Postman

1. Open Postman
2. Click "Import"
3. Select "Link" tab
4. Enter: `{BACKEND_URL}/openapi.json`
5. Click "Import"

### Environment Variables

Create a Postman environment with:
```
base_url: http://localhost:8001
token: (set after login)
```

### Collection Runner

Use the collection runner for automated testing:
1. Run "Login" request first
2. Set `token` variable from response
3. Run other requests

### Export OpenAPI

Download the OpenAPI specification:
```bash
curl {BACKEND_URL}/openapi.json > openapi.json
```

Convert to Postman collection:
```bash
npx openapi-to-postmanv2 -s openapi.json -o faithtracker.postman_collection.json
```

---

## SDK Generation

Generate client SDKs from OpenAPI spec:

### Python
```bash
pip install openapi-python-client
openapi-python-client generate --url {BACKEND_URL}/openapi.json
```

### TypeScript
```bash
npx openapi-typescript-codegen --input {BACKEND_URL}/openapi.json --output ./api-client
```

### Mobile (React Native / Flutter)
```bash
# React Native (using openapi-generator)
npx @openapitools/openapi-generator-cli generate \
  -i {BACKEND_URL}/openapi.json \
  -g typescript-fetch \
  -o ./mobile-api-client

# Flutter
npx @openapitools/openapi-generator-cli generate \
  -i {BACKEND_URL}/openapi.json \
  -g dart \
  -o ./flutter-api-client
```

---

## Interactive Documentation

- **Swagger UI**: `{BACKEND_URL}/docs`
- **ReDoc**: `{BACKEND_URL}/redoc`

Both provide interactive API exploration with request/response examples.
