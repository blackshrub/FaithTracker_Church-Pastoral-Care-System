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
