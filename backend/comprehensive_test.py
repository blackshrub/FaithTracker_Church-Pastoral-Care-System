#!/usr/bin/env python3
"""
Comprehensive Functionality Test Suite for FaithTracker Pastoral Care System
Tests EVERY endpoint and functionality systematically
"""

import asyncio
import httpx
import json
import sys
from datetime import datetime, date, timedelta
from typing import Optional
import uuid

# Configuration
BASE_URL = "http://localhost:8001"
ADMIN_EMAIL = "admin@gkbj.church"
ADMIN_PASSWORD = "admin123"

# Test results tracking
results = {
    "passed": 0,
    "failed": 0,
    "errors": [],
    "warnings": []
}

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

def log_pass(test_name: str, details: str = ""):
    results["passed"] += 1
    print(f"{GREEN}✓ PASS{RESET} {test_name} {details}")

def log_fail(test_name: str, error: str):
    results["failed"] += 1
    results["errors"].append({"test": test_name, "error": error})
    print(f"{RED}✗ FAIL{RESET} {test_name}: {error}")

def log_warn(test_name: str, warning: str):
    results["warnings"].append({"test": test_name, "warning": warning})
    print(f"{YELLOW}⚠ WARN{RESET} {test_name}: {warning}")

def log_section(title: str):
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}{title}{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}")

async def get_auth_token(client: httpx.AsyncClient) -> Optional[str]:
    """Get authentication token"""
    try:
        # First get campus ID for full_admin login
        campuses_resp = await client.get(f"{BASE_URL}/campuses")
        campus_id = None
        if campuses_resp.status_code == 200:
            campuses = campuses_resp.json()
            if campuses:
                campus_id = campuses[0]["id"]

        response = await client.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "campus_id": campus_id
            }
        )
        if response.status_code in [200, 201]:
            return response.json().get("access_token")
        print(f"Login failed: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        print(f"Auth error: {e}")
        return None

async def test_health_endpoints(client: httpx.AsyncClient):
    """Test health and readiness endpoints"""
    log_section("HEALTH & READINESS ENDPOINTS")

    # Health check
    try:
        r = await client.get(f"{BASE_URL}/health")
        if r.status_code == 200 and r.json().get("status") == "healthy":
            log_pass("GET /health", f"- {r.json()}")
        else:
            log_fail("GET /health", f"Unexpected response: {r.text}")
    except Exception as e:
        log_fail("GET /health", str(e))

    # Ready check
    try:
        r = await client.get(f"{BASE_URL}/ready")
        if r.status_code == 200:
            log_pass("GET /ready", f"- {r.json()}")
        else:
            log_fail("GET /ready", f"Unexpected response: {r.text}")
    except Exception as e:
        log_fail("GET /ready", str(e))

async def test_auth_endpoints(client: httpx.AsyncClient, token: str):
    """Test authentication endpoints"""
    log_section("AUTHENTICATION ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}

    # Login (already tested to get token)
    log_pass("POST /auth/login", "- Token obtained successfully")

    # Get current user
    try:
        r = await client.get(f"{BASE_URL}/auth/me", headers=headers)
        if r.status_code == 200:
            user = r.json()
            log_pass("GET /auth/me", f"- User: {user.get('email')}")
        else:
            log_fail("GET /auth/me", f"Status {r.status_code}: {r.text}")
    except Exception as e:
        log_fail("GET /auth/me", str(e))

    # Get users list
    try:
        r = await client.get(f"{BASE_URL}/users", headers=headers)
        if r.status_code == 200:
            users = r.json()
            log_pass("GET /users", f"- Found {len(users)} users")
        else:
            log_fail("GET /users", f"Status {r.status_code}: {r.text}")
    except Exception as e:
        log_fail("GET /users", str(e))

async def test_campus_endpoints(client: httpx.AsyncClient, token: str):
    """Test campus management endpoints"""
    log_section("CAMPUS MANAGEMENT ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}

    # Get campuses
    try:
        r = await client.get(f"{BASE_URL}/campuses", headers=headers)
        if r.status_code == 200:
            campuses = r.json()
            log_pass("GET /campuses", f"- Found {len(campuses)} campuses")
            if campuses:
                campus_id = campuses[0]["id"]
                # Get specific campus
                r2 = await client.get(f"{BASE_URL}/campuses/{campus_id}", headers=headers)
                if r2.status_code == 200:
                    log_pass(f"GET /campuses/{{id}}", f"- {r2.json().get('campus_name')}")
                else:
                    log_fail(f"GET /campuses/{{id}}", f"Status {r2.status_code}")
        else:
            log_fail("GET /campuses", f"Status {r.status_code}: {r.text}")
    except Exception as e:
        log_fail("GET /campuses", str(e))

async def test_member_endpoints(client: httpx.AsyncClient, token: str, campus_id: str):
    """Test member management endpoints"""
    log_section("MEMBER MANAGEMENT ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}
    test_member_id = None

    # Get members list
    try:
        r = await client.get(f"{BASE_URL}/members", headers=headers)
        if r.status_code == 200:
            data = r.json()
            members = data.get("members", data) if isinstance(data, dict) else data
            log_pass("GET /members", f"- Found {len(members)} members")
            if members:
                test_member_id = members[0]["id"]
        else:
            log_fail("GET /members", f"Status {r.status_code}: {r.text}")
    except Exception as e:
        log_fail("GET /members", str(e))

    # Get members with pagination
    try:
        r = await client.get(f"{BASE_URL}/members?page=1&per_page=10", headers=headers)
        if r.status_code == 200:
            log_pass("GET /members?page=1&per_page=10", "- Pagination works")
        else:
            log_fail("GET /members (paginated)", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /members (paginated)", str(e))

    # Get members with search
    try:
        r = await client.get(f"{BASE_URL}/members?search=test", headers=headers)
        if r.status_code == 200:
            log_pass("GET /members?search=test", "- Search works")
        else:
            log_fail("GET /members (search)", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /members (search)", str(e))

    # Get members with engagement filter
    try:
        r = await client.get(f"{BASE_URL}/members?engagement_status=active", headers=headers)
        if r.status_code == 200:
            log_pass("GET /members?engagement_status=active", "- Filter works")
        else:
            log_fail("GET /members (filter)", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /members (filter)", str(e))

    # Get specific member
    if test_member_id:
        try:
            r = await client.get(f"{BASE_URL}/members/{test_member_id}", headers=headers)
            if r.status_code == 200:
                member = r.json()
                log_pass(f"GET /members/{{id}}", f"- {member.get('name')}")
            else:
                log_fail("GET /members/{id}", f"Status {r.status_code}")
        except Exception as e:
            log_fail("GET /members/{id}", str(e))

    # Get at-risk members
    try:
        r = await client.get(f"{BASE_URL}/members/at-risk", headers=headers)
        if r.status_code == 200:
            at_risk = r.json()
            log_pass("GET /members/at-risk", f"- Found {len(at_risk)} at-risk members")
        else:
            log_fail("GET /members/at-risk", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /members/at-risk", str(e))

    # Create a test member
    try:
        test_member_data = {
            "name": f"Test Member {uuid.uuid4().hex[:8]}",
            "campus_id": campus_id,  # Required field
            "phone": f"+628{uuid.uuid4().hex[:10]}",
            "address": "Test Address",
            "notes": "Created by automated test"
        }
        r = await client.post(f"{BASE_URL}/members", json=test_member_data, headers=headers)
        if r.status_code in [200, 201]:
            created = r.json()
            created_id = created.get("id")
            log_pass("POST /members", f"- Created member {created_id}")

            # Update the member
            try:
                update_data = {"name": test_member_data["name"] + " Updated"}
                r2 = await client.put(f"{BASE_URL}/members/{created_id}", json=update_data, headers=headers)
                if r2.status_code == 200:
                    log_pass("PUT /members/{id}", "- Updated successfully")
                else:
                    log_fail("PUT /members/{id}", f"Status {r2.status_code}: {r2.text}")
            except Exception as e:
                log_fail("PUT /members/{id}", str(e))

            # Delete the test member
            try:
                r3 = await client.delete(f"{BASE_URL}/members/{created_id}", headers=headers)
                if r3.status_code == 200:
                    log_pass("DELETE /members/{id}", "- Deleted successfully")
                else:
                    log_fail("DELETE /members/{id}", f"Status {r3.status_code}")
            except Exception as e:
                log_fail("DELETE /members/{id}", str(e))
        else:
            log_fail("POST /members", f"Status {r.status_code}: {r.text}")
    except Exception as e:
        log_fail("POST /members", str(e))

async def test_care_event_endpoints(client: httpx.AsyncClient, token: str):
    """Test care event endpoints"""
    log_section("CARE EVENT ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}

    # Get care events
    try:
        r = await client.get(f"{BASE_URL}/care-events", headers=headers)
        if r.status_code == 200:
            events = r.json()
            log_pass("GET /care-events", f"- Found {len(events)} events")
            if events:
                event_id = events[0]["id"]
                # Get specific event
                r2 = await client.get(f"{BASE_URL}/care-events/{event_id}", headers=headers)
                if r2.status_code == 200:
                    log_pass("GET /care-events/{id}", "- Retrieved successfully")
                else:
                    log_fail("GET /care-events/{id}", f"Status {r2.status_code}")
        else:
            log_fail("GET /care-events", f"Status {r.status_code}: {r.text}")
    except Exception as e:
        log_fail("GET /care-events", str(e))

    # Get hospital followups due
    try:
        r = await client.get(f"{BASE_URL}/care-events/hospital/due-followup", headers=headers)
        if r.status_code == 200:
            log_pass("GET /care-events/hospital/due-followup", f"- {len(r.json())} due")
        else:
            log_fail("GET /care-events/hospital/due-followup", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /care-events/hospital/due-followup", str(e))

async def test_dashboard_endpoints(client: httpx.AsyncClient, token: str):
    """Test dashboard endpoints"""
    log_section("DASHBOARD ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}

    # Dashboard stats
    try:
        r = await client.get(f"{BASE_URL}/dashboard/stats", headers=headers)
        if r.status_code == 200:
            stats = r.json()
            log_pass("GET /dashboard/stats", f"- {stats}")
        else:
            log_fail("GET /dashboard/stats", f"Status {r.status_code}: {r.text}")
    except Exception as e:
        log_fail("GET /dashboard/stats", str(e))

    # Dashboard reminders
    try:
        r = await client.get(f"{BASE_URL}/dashboard/reminders", headers=headers)
        if r.status_code == 200:
            data = r.json()
            log_pass("GET /dashboard/reminders", f"- {data.get('total_tasks', 'N/A')} tasks")
        else:
            log_fail("GET /dashboard/reminders", f"Status {r.status_code}: {r.text}")
    except Exception as e:
        log_fail("GET /dashboard/reminders", str(e))

    # Dashboard upcoming
    try:
        r = await client.get(f"{BASE_URL}/dashboard/upcoming", headers=headers)
        if r.status_code == 200:
            log_pass("GET /dashboard/upcoming", f"- Retrieved")
        else:
            log_fail("GET /dashboard/upcoming", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /dashboard/upcoming", str(e))

    # Dashboard grief active
    try:
        r = await client.get(f"{BASE_URL}/dashboard/grief-active", headers=headers)
        if r.status_code == 200:
            log_pass("GET /dashboard/grief-active", f"- Retrieved")
        else:
            log_fail("GET /dashboard/grief-active", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /dashboard/grief-active", str(e))

    # Dashboard recent activity
    try:
        r = await client.get(f"{BASE_URL}/dashboard/recent-activity", headers=headers)
        if r.status_code == 200:
            log_pass("GET /dashboard/recent-activity", f"- Retrieved")
        else:
            log_fail("GET /dashboard/recent-activity", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /dashboard/recent-activity", str(e))

async def test_grief_support_endpoints(client: httpx.AsyncClient, token: str):
    """Test grief support endpoints"""
    log_section("GRIEF SUPPORT ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}

    # Get grief support stages
    try:
        r = await client.get(f"{BASE_URL}/grief-support", headers=headers)
        if r.status_code == 200:
            stages = r.json()
            log_pass("GET /grief-support", f"- Found {len(stages)} stages")
        else:
            log_fail("GET /grief-support", f"Status {r.status_code}: {r.text}")
    except Exception as e:
        log_fail("GET /grief-support", str(e))

async def test_accident_followup_endpoints(client: httpx.AsyncClient, token: str):
    """Test accident followup endpoints"""
    log_section("ACCIDENT FOLLOWUP ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}

    # Get accident followups
    try:
        r = await client.get(f"{BASE_URL}/accident-followup", headers=headers)
        if r.status_code == 200:
            followups = r.json()
            log_pass("GET /accident-followup", f"- Found {len(followups)} followups")
        else:
            log_fail("GET /accident-followup", f"Status {r.status_code}: {r.text}")
    except Exception as e:
        log_fail("GET /accident-followup", str(e))

async def test_financial_aid_endpoints(client: httpx.AsyncClient, token: str):
    """Test financial aid endpoints"""
    log_section("FINANCIAL AID ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}

    # Get financial aid schedules
    try:
        r = await client.get(f"{BASE_URL}/financial-aid-schedules", headers=headers)
        if r.status_code == 200:
            schedules = r.json()
            log_pass("GET /financial-aid-schedules", f"- Found {len(schedules)} schedules")
        else:
            log_fail("GET /financial-aid-schedules", f"Status {r.status_code}: {r.text}")
    except Exception as e:
        log_fail("GET /financial-aid-schedules", str(e))

    # Get financial aid summary
    try:
        r = await client.get(f"{BASE_URL}/financial-aid/summary", headers=headers)
        if r.status_code == 200:
            log_pass("GET /financial-aid/summary", f"- {r.json()}")
        else:
            log_fail("GET /financial-aid/summary", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /financial-aid/summary", str(e))

    # Get financial aid recipients
    try:
        r = await client.get(f"{BASE_URL}/financial-aid/recipients", headers=headers)
        if r.status_code == 200:
            log_pass("GET /financial-aid/recipients", f"- Found {len(r.json())} recipients")
        else:
            log_fail("GET /financial-aid/recipients", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /financial-aid/recipients", str(e))

    # Get schedules due today
    try:
        r = await client.get(f"{BASE_URL}/financial-aid-schedules/due-today", headers=headers)
        if r.status_code == 200:
            log_pass("GET /financial-aid-schedules/due-today", f"- {len(r.json())} due")
        else:
            log_fail("GET /financial-aid-schedules/due-today", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /financial-aid-schedules/due-today", str(e))

async def test_analytics_endpoints(client: httpx.AsyncClient, token: str):
    """Test analytics endpoints"""
    log_section("ANALYTICS ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}

    # Analytics dashboard
    try:
        r = await client.get(f"{BASE_URL}/analytics/dashboard", headers=headers)
        if r.status_code == 200:
            log_pass("GET /analytics/dashboard", "- Retrieved")
        else:
            log_fail("GET /analytics/dashboard", f"Status {r.status_code}: {r.text}")
    except Exception as e:
        log_fail("GET /analytics/dashboard", str(e))

    # Engagement trends
    try:
        r = await client.get(f"{BASE_URL}/analytics/engagement-trends", headers=headers)
        if r.status_code == 200:
            log_pass("GET /analytics/engagement-trends", "- Retrieved")
        else:
            log_fail("GET /analytics/engagement-trends", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /analytics/engagement-trends", str(e))

    # Care events by type
    try:
        r = await client.get(f"{BASE_URL}/analytics/care-events-by-type", headers=headers)
        if r.status_code == 200:
            log_pass("GET /analytics/care-events-by-type", "- Retrieved")
        else:
            log_fail("GET /analytics/care-events-by-type", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /analytics/care-events-by-type", str(e))

    # Grief completion rate
    try:
        r = await client.get(f"{BASE_URL}/analytics/grief-completion-rate", headers=headers)
        if r.status_code == 200:
            log_pass("GET /analytics/grief-completion-rate", "- Retrieved")
        else:
            log_fail("GET /analytics/grief-completion-rate", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /analytics/grief-completion-rate", str(e))

    # Demographic trends
    try:
        r = await client.get(f"{BASE_URL}/analytics/demographic-trends", headers=headers)
        if r.status_code == 200:
            log_pass("GET /analytics/demographic-trends", "- Retrieved")
        else:
            log_fail("GET /analytics/demographic-trends", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /analytics/demographic-trends", str(e))

async def test_reports_endpoints(client: httpx.AsyncClient, token: str):
    """Test reports endpoints"""
    log_section("REPORTS ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}

    # Monthly report
    try:
        r = await client.get(f"{BASE_URL}/reports/monthly?year=2025&month=12", headers=headers)
        if r.status_code == 200:
            log_pass("GET /reports/monthly", "- Retrieved")
        else:
            log_fail("GET /reports/monthly", f"Status {r.status_code}: {r.text}")
    except Exception as e:
        log_fail("GET /reports/monthly", str(e))

    # Monthly PDF report
    try:
        r = await client.get(f"{BASE_URL}/reports/monthly/pdf?year=2025&month=12", headers=headers)
        if r.status_code == 200:
            log_pass("GET /reports/monthly/pdf", f"- PDF size: {len(r.content)} bytes")
        else:
            log_fail("GET /reports/monthly/pdf", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /reports/monthly/pdf", str(e))

    # Staff performance
    try:
        r = await client.get(f"{BASE_URL}/reports/staff-performance", headers=headers)
        if r.status_code == 200:
            log_pass("GET /reports/staff-performance", "- Retrieved")
        else:
            log_fail("GET /reports/staff-performance", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /reports/staff-performance", str(e))

    # Yearly summary
    try:
        r = await client.get(f"{BASE_URL}/reports/yearly-summary?year=2025", headers=headers)
        if r.status_code == 200:
            log_pass("GET /reports/yearly-summary", "- Retrieved")
        else:
            log_fail("GET /reports/yearly-summary", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /reports/yearly-summary", str(e))

async def test_settings_endpoints(client: httpx.AsyncClient, token: str):
    """Test settings endpoints"""
    log_section("SETTINGS ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}

    # Engagement settings
    try:
        r = await client.get(f"{BASE_URL}/settings/engagement", headers=headers)
        if r.status_code == 200:
            log_pass("GET /settings/engagement", f"- {r.json()}")
        else:
            log_fail("GET /settings/engagement", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /settings/engagement", str(e))

    # Automation settings
    try:
        r = await client.get(f"{BASE_URL}/settings/automation", headers=headers)
        if r.status_code == 200:
            log_pass("GET /settings/automation", f"- {r.json()}")
        else:
            log_fail("GET /settings/automation", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /settings/automation", str(e))

    # Overdue writeoff settings
    try:
        r = await client.get(f"{BASE_URL}/settings/overdue_writeoff", headers=headers)
        if r.status_code == 200:
            log_pass("GET /settings/overdue_writeoff", f"- {r.json()}")
        else:
            log_fail("GET /settings/overdue_writeoff", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /settings/overdue_writeoff", str(e))

    # Grief stages settings
    try:
        r = await client.get(f"{BASE_URL}/settings/grief-stages", headers=headers)
        if r.status_code == 200:
            log_pass("GET /settings/grief-stages", "- Retrieved")
        else:
            log_fail("GET /settings/grief-stages", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /settings/grief-stages", str(e))

    # Accident followup settings
    try:
        r = await client.get(f"{BASE_URL}/settings/accident-followup", headers=headers)
        if r.status_code == 200:
            log_pass("GET /settings/accident-followup", "- Retrieved")
        else:
            log_fail("GET /settings/accident-followup", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /settings/accident-followup", str(e))

async def test_config_endpoints(client: httpx.AsyncClient, token: str):
    """Test configuration endpoints"""
    log_section("CONFIGURATION ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}

    configs = [
        "/config/aid-types",
        "/config/event-types",
        "/config/relationship-types",
        "/config/user-roles",
        "/config/engagement-statuses",
        "/config/weekdays",
        "/config/months",
        "/config/frequency-types",
        "/config/membership-statuses",
        "/config/all"
    ]

    for config in configs:
        try:
            r = await client.get(f"{BASE_URL}{config}", headers=headers)
            if r.status_code == 200:
                log_pass(f"GET {config}", "- Retrieved")
            else:
                log_fail(f"GET {config}", f"Status {r.status_code}")
        except Exception as e:
            log_fail(f"GET {config}", str(e))

async def test_import_export_endpoints(client: httpx.AsyncClient, token: str):
    """Test import/export endpoints"""
    log_section("IMPORT/EXPORT ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}

    # Export members CSV
    try:
        r = await client.get(f"{BASE_URL}/export/members/csv", headers=headers)
        if r.status_code == 200:
            log_pass("GET /export/members/csv", f"- CSV size: {len(r.content)} bytes")
        else:
            log_fail("GET /export/members/csv", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /export/members/csv", str(e))

    # Export care events CSV
    try:
        r = await client.get(f"{BASE_URL}/export/care-events/csv", headers=headers)
        if r.status_code == 200:
            log_pass("GET /export/care-events/csv", f"- CSV size: {len(r.content)} bytes")
        else:
            log_fail("GET /export/care-events/csv", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /export/care-events/csv", str(e))

async def test_notification_endpoints(client: httpx.AsyncClient, token: str):
    """Test notification endpoints"""
    log_section("NOTIFICATION ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}

    # Notification logs
    try:
        r = await client.get(f"{BASE_URL}/notification-logs", headers=headers)
        if r.status_code == 200:
            logs = r.json()
            log_pass("GET /notification-logs", f"- Found {len(logs)} logs")
        else:
            log_fail("GET /notification-logs", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /notification-logs", str(e))

    # Reminder stats
    try:
        r = await client.get(f"{BASE_URL}/reminders/stats", headers=headers)
        if r.status_code == 200:
            log_pass("GET /reminders/stats", f"- {r.json()}")
        else:
            log_fail("GET /reminders/stats", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /reminders/stats", str(e))

async def test_activity_log_endpoints(client: httpx.AsyncClient, token: str):
    """Test activity log endpoints"""
    log_section("ACTIVITY LOG ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}

    # Activity logs
    try:
        r = await client.get(f"{BASE_URL}/activity-logs", headers=headers)
        if r.status_code == 200:
            data = r.json()
            logs = data.get("logs", data) if isinstance(data, dict) else data
            log_pass("GET /activity-logs", f"- Found {len(logs)} logs")
        else:
            log_fail("GET /activity-logs", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /activity-logs", str(e))

    # Activity logs summary
    try:
        r = await client.get(f"{BASE_URL}/activity-logs/summary", headers=headers)
        if r.status_code == 200:
            log_pass("GET /activity-logs/summary", "- Retrieved")
        else:
            log_fail("GET /activity-logs/summary", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /activity-logs/summary", str(e))

async def test_search_endpoint(client: httpx.AsyncClient, token: str):
    """Test search endpoint"""
    log_section("SEARCH ENDPOINT")

    headers = {"Authorization": f"Bearer {token}"}

    try:
        r = await client.get(f"{BASE_URL}/search?q=test", headers=headers)
        if r.status_code == 200:
            log_pass("GET /search?q=test", f"- Found {len(r.json())} results")
        else:
            log_fail("GET /search?q=test", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /search?q=test", str(e))

async def test_suggestions_endpoint(client: httpx.AsyncClient, token: str):
    """Test suggestions endpoint"""
    log_section("SUGGESTIONS ENDPOINT")

    headers = {"Authorization": f"Bearer {token}"}

    try:
        r = await client.get(f"{BASE_URL}/suggestions/follow-up", headers=headers)
        if r.status_code == 200:
            log_pass("GET /suggestions/follow-up", f"- Found {len(r.json())} suggestions")
        else:
            log_fail("GET /suggestions/follow-up", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /suggestions/follow-up", str(e))

async def test_sync_endpoints(client: httpx.AsyncClient, token: str):
    """Test sync configuration endpoints"""
    log_section("SYNC CONFIGURATION ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}

    # Get sync config
    try:
        r = await client.get(f"{BASE_URL}/sync/config", headers=headers)
        if r.status_code == 200:
            log_pass("GET /sync/config", "- Retrieved")
        elif r.status_code == 404:
            log_pass("GET /sync/config", "- No config yet (expected)")
        else:
            log_fail("GET /sync/config", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /sync/config", str(e))

    # Get sync logs
    try:
        r = await client.get(f"{BASE_URL}/sync/logs", headers=headers)
        if r.status_code == 200:
            log_pass("GET /sync/logs", f"- Found {len(r.json())} logs")
        else:
            log_fail("GET /sync/logs", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /sync/logs", str(e))

async def test_setup_endpoints(client: httpx.AsyncClient, token: str):
    """Test setup endpoints"""
    log_section("SETUP ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}

    # Get setup status
    try:
        r = await client.get(f"{BASE_URL}/setup/status", headers=headers)
        if r.status_code == 200:
            log_pass("GET /setup/status", f"- {r.json()}")
        else:
            log_fail("GET /setup/status", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /setup/status", str(e))

async def test_sse_endpoints(client: httpx.AsyncClient, token: str):
    """Test SSE (Server-Sent Events) endpoints"""
    log_section("SSE ENDPOINTS")

    # Test SSE endpoint (just check it's accessible, don't keep connection open)
    try:
        r = await client.get(f"{BASE_URL}/stream/test")
        if r.status_code == 200:
            log_pass("GET /stream/test", "- SSE test endpoint works")
        else:
            log_fail("GET /stream/test", f"Status {r.status_code}")
    except Exception as e:
        log_fail("GET /stream/test", str(e))

async def test_integrations_endpoints(client: httpx.AsyncClient, token: str):
    """Test integrations endpoints"""
    log_section("INTEGRATIONS ENDPOINTS")

    headers = {"Authorization": f"Bearer {token}"}

    # Ping WhatsApp (may fail if not configured, but should not error)
    try:
        r = await client.post(f"{BASE_URL}/integrations/ping/whatsapp", headers=headers)
        if r.status_code in [200, 400, 503]:
            log_pass("POST /integrations/ping/whatsapp", f"- Status {r.status_code}")
        else:
            log_warn("POST /integrations/ping/whatsapp", f"Status {r.status_code}")
    except Exception as e:
        log_fail("POST /integrations/ping/whatsapp", str(e))

async def run_all_tests():
    """Run all tests"""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}FAITHTRACKER COMPREHENSIVE FUNCTIONALITY TEST SUITE{RESET}")
    print(f"{BOLD}Started at: {datetime.now().isoformat()}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get campus ID first (needed for member creation)
        campuses_resp = await client.get(f"{BASE_URL}/campuses")
        campus_id = campuses_resp.json()[0]["id"] if campuses_resp.status_code == 200 else None

        # Get auth token
        token = await get_auth_token(client)
        if not token:
            print(f"{RED}FATAL: Could not authenticate. Aborting tests.{RESET}")
            return

        # Run all test suites
        await test_health_endpoints(client)
        await test_auth_endpoints(client, token)
        await test_campus_endpoints(client, token)
        await test_member_endpoints(client, token, campus_id)
        await test_care_event_endpoints(client, token)
        await test_dashboard_endpoints(client, token)
        await test_grief_support_endpoints(client, token)
        await test_accident_followup_endpoints(client, token)
        await test_financial_aid_endpoints(client, token)
        await test_analytics_endpoints(client, token)
        await test_reports_endpoints(client, token)
        await test_settings_endpoints(client, token)
        await test_config_endpoints(client, token)
        await test_import_export_endpoints(client, token)
        await test_notification_endpoints(client, token)
        await test_activity_log_endpoints(client, token)
        await test_search_endpoint(client, token)
        await test_suggestions_endpoint(client, token)
        await test_sync_endpoints(client, token)
        await test_setup_endpoints(client, token)
        await test_sse_endpoints(client, token)
        await test_integrations_endpoints(client, token)

    # Print summary
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}TEST SUMMARY{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{GREEN}Passed: {results['passed']}{RESET}")
    print(f"{RED}Failed: {results['failed']}{RESET}")
    print(f"{YELLOW}Warnings: {len(results['warnings'])}{RESET}")

    if results["errors"]:
        print(f"\n{RED}{BOLD}FAILED TESTS:{RESET}")
        for err in results["errors"]:
            print(f"  {RED}• {err['test']}: {err['error']}{RESET}")

    if results["warnings"]:
        print(f"\n{YELLOW}{BOLD}WARNINGS:{RESET}")
        for warn in results["warnings"]:
            print(f"  {YELLOW}• {warn['test']}: {warn['warning']}{RESET}")

    total = results["passed"] + results["failed"]
    if total > 0:
        success_rate = (results["passed"] / total) * 100
        print(f"\n{BOLD}Success Rate: {success_rate:.1f}%{RESET}")

    print(f"\n{BOLD}Completed at: {datetime.now().isoformat()}{RESET}")

    # Return exit code
    return 0 if results["failed"] == 0 else 1

if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
