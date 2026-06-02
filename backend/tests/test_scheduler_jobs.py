"""
Tests for scheduler heavy job functions (previously 0% coverage).

Covers:
- send_daily_digest_to_pastoral_team() (~180 stmts)
- member_reconciliation_job() / daily_member_reconciliation (~85 stmts)
- refresh_all_dashboard_caches() (~50 stmts)
- daily_reminder_job() (~25 stmts)
- schedule_daily_digest() (~25 stmts)
- reschedule_daily_digest() / init_daily_digest_schedule() (~12 stmts)
- check_missed_reconciliation() (~40 stmts)
- send_whatsapp retry edge cases
- generate_daily_digest_for_campus() overdue / formatting edge cases
- start_scheduler() / stop_scheduler()

All tests mock the database layer so no running MongoDB is required.
"""

import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure environment variables are set before importing scheduler
os.environ.update(
    {
        "MONGO_URL": "mongodb://mock:27017",
        "DB_NAME": "faithtracker_test",
        "JWT_SECRET_KEY": "test-secret",
        "ENCRYPTION_KEY": "dGVzdC1lbmNyeXB0aW9uLWtleS0xMjM0NTY3ODkwYWI=",
        "DRAGONFLY_URL": "redis://mock:6379",
    }
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import contextlib

from scheduler import (
    JAKARTA_TZ,
    check_missed_digest,
    check_missed_reconciliation,
    daily_reminder_job,
    generate_daily_digest_for_campus,
    init_daily_digest_schedule,
    member_reconciliation_job,
    refresh_all_dashboard_caches,
    reschedule_daily_digest,
    schedule_daily_digest,
    send_daily_digest_to_pastoral_team,
    send_email_alert,
    send_whatsapp,
    start_scheduler,
    stop_scheduler,
)

# ---------------------------------------------------------------------------
# Shared helpers for building mock objects
# ---------------------------------------------------------------------------


def make_mock_db():
    """Create a mock database with all collections used by the scheduler."""
    mock_db = MagicMock()

    # job_locks
    mock_db.job_locks.update_one = AsyncMock()
    mock_db.job_locks.delete_one = AsyncMock()
    mock_db.job_locks.find_one = AsyncMock(return_value=None)

    # members
    _members_cursor = MagicMock()
    _members_cursor.to_list = AsyncMock(return_value=[])
    mock_db.members.find = MagicMock(return_value=_members_cursor)
    mock_db.members.find_one = AsyncMock(return_value=None)

    # care_events
    _care_cursor = MagicMock()
    _care_cursor.to_list = AsyncMock(return_value=[])
    mock_db.care_events.find = MagicMock(return_value=_care_cursor)
    mock_db.care_events.find_one = AsyncMock(return_value=None)

    # grief_support
    _grief_cursor = MagicMock()
    _grief_cursor.to_list = AsyncMock(return_value=[])
    mock_db.grief_support.find = MagicMock(return_value=_grief_cursor)

    # accident_followup
    _acc_cursor = MagicMock()
    _acc_cursor.to_list = AsyncMock(return_value=[])
    mock_db.accident_followup.find = MagicMock(return_value=_acc_cursor)

    # financial_aid_schedules
    _fin_cursor = MagicMock()
    _fin_cursor.to_list = AsyncMock(return_value=[])
    mock_db.financial_aid_schedules.find = MagicMock(return_value=_fin_cursor)

    # pastoral_notes
    _notes_cursor = MagicMock()
    _notes_cursor.to_list = AsyncMock(return_value=[])
    mock_db.pastoral_notes.find = MagicMock(return_value=_notes_cursor)

    # notification_logs
    mock_db.notification_logs.insert_one = AsyncMock()
    mock_db.notification_logs.count_documents = AsyncMock(return_value=0)

    # settings
    mock_db.settings.find_one = AsyncMock(return_value=None)

    # campuses
    _campus_cursor = MagicMock()
    _campus_cursor.to_list = AsyncMock(return_value=[])
    mock_db.campuses.find = MagicMock(return_value=_campus_cursor)

    # users
    _user_cursor = MagicMock()
    _user_cursor.to_list = AsyncMock(return_value=[])
    mock_db.users.find = MagicMock(return_value=_user_cursor)

    # sync_configs
    _sync_cursor = MagicMock()
    _sync_cursor.to_list = AsyncMock(return_value=[])
    mock_db.sync_configs.find = MagicMock(return_value=_sync_cursor)

    # dashboard_cache
    mock_db.dashboard_cache.update_one = AsyncMock()
    mock_db.dashboard_cache.delete_many = AsyncMock()

    return mock_db


def make_update_result(matched=0, upserted_id=None):
    """Create a mock MongoDB UpdateResult."""
    result = MagicMock()
    result.matched_count = matched
    result.upserted_id = upserted_id
    return result


def make_test_campus(campus_id="campus-1", name="Test Campus"):
    return {"id": campus_id, "campus_name": name, "is_active": True, "timezone": "Asia/Jakarta"}


def make_test_user(user_id=None, campus_id="campus-1", role="pastor", phone="+6281234567890", name="Pastor John"):
    return {
        "id": user_id or str(uuid.uuid4()),
        "campus_id": campus_id,
        "role": role,
        "phone": phone,
        "name": name,
        "email": f"{name.lower().replace(' ', '.')}@test.com",
        "is_active": True,
    }


def make_digest_result(campus_id="campus-1", campus_name="Test Campus", has_tasks=True):
    """Create a fake digest result for testing send_daily_digest_to_pastoral_team."""
    stats = {
        "birthdays_today": 2 if has_tasks else 0,
        "birthdays_week": 1,
        "grief_due": 1 if has_tasks else 0,
        "hospital_followups": 0,
        "financial_aid": 0,
        "overdue_grief": 0,
        "overdue_hospital": 0,
        "overdue_financial": 0,
        "at_risk": 3 if has_tasks else 0,
        "notes_due_today": 0,
        "overdue_notes": 0,
    }
    return {
        "campus_id": campus_id,
        "campus_name": campus_name,
        "message": f"Digest for {campus_name}",
        "stats": stats,
    }


# ===========================================================================
# 1. send_daily_digest_to_pastoral_team() tests
# ===========================================================================


class TestSendDailyDigestToPastoralTeam:
    """Tests for the main digest distribution function."""

    @pytest.mark.asyncio
    async def test_sends_digest_to_pastoral_team_members(self):
        """Should send digest to campus_admin and pastor users."""
        mock_db = make_mock_db()
        campus = make_test_campus()
        user1 = make_test_user(phone="+6281111111111", name="Pastor A")
        user2 = make_test_user(phone="+6281222222222", name="Admin B", role="campus_admin")

        # campuses.find returns our campus
        mock_db.campuses.find.return_value.to_list = AsyncMock(return_value=[campus])
        # users.find returns the pastoral team
        mock_db.users.find.return_value.to_list = AsyncMock(return_value=[user1, user2])

        digest = make_digest_result()

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.generate_daily_digest_for_campus", new_callable=AsyncMock, return_value=digest),
            patch("scheduler.send_whatsapp", new_callable=AsyncMock, return_value={"success": True}),
            patch("scheduler.send_email_alert", new_callable=AsyncMock),
        ):
            await send_daily_digest_to_pastoral_team()

    @pytest.mark.asyncio
    async def test_skips_campus_with_no_tasks(self):
        """Should skip campuses where digest has zero tasks."""
        mock_db = make_mock_db()
        campus = make_test_campus()
        mock_db.campuses.find.return_value.to_list = AsyncMock(return_value=[campus])

        no_task_digest = make_digest_result(has_tasks=False)

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.generate_daily_digest_for_campus", new_callable=AsyncMock, return_value=no_task_digest),
            patch("scheduler.send_whatsapp", new_callable=AsyncMock) as mock_send,
        ):
            await send_daily_digest_to_pastoral_team()
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_campus_when_digest_is_none(self):
        """Should skip campus when generate_daily_digest returns None (error)."""
        mock_db = make_mock_db()
        campus = make_test_campus()
        mock_db.campuses.find.return_value.to_list = AsyncMock(return_value=[campus])

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.generate_daily_digest_for_campus", new_callable=AsyncMock, return_value=None),
            patch("scheduler.send_whatsapp", new_callable=AsyncMock) as mock_send,
        ):
            await send_daily_digest_to_pastoral_team()
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_empty_campuses_list(self):
        """Should handle gracefully when no campuses exist."""
        mock_db = make_mock_db()
        mock_db.campuses.find.return_value.to_list = AsyncMock(return_value=[])

        with patch("scheduler.db", mock_db), patch("scheduler.send_whatsapp", new_callable=AsyncMock) as mock_send:
            await send_daily_digest_to_pastoral_team()
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_deduplicates_by_user_id(self):
        """Should not send to same user_id twice (e.g., user in multiple roles)."""
        mock_db = make_mock_db()
        campus1 = make_test_campus("c1", "Campus 1")
        make_test_campus("c2", "Campus 2")

        shared_user_id = str(uuid.uuid4())
        user_c1 = make_test_user(user_id=shared_user_id, campus_id="c1", phone="+6281111111111")
        # Same user appears in full_admin list
        full_admin = make_test_user(user_id=shared_user_id, campus_id="c1", phone="+6281111111111", role="full_admin")

        mock_db.campuses.find.return_value.to_list = AsyncMock(return_value=[campus1])

        # First call: pastoral team for campus; Second call: full_admins
        call_count = [0]

        async def mock_users_find_to_list(_):
            call_count[0] += 1
            if call_count[0] <= 1:
                return [user_c1]
            return [full_admin]

        mock_db.users.find.return_value.to_list = mock_users_find_to_list

        digest = make_digest_result("c1", "Campus 1")

        send_call_count = 0

        async def counting_send(*args, **kwargs):
            nonlocal send_call_count
            send_call_count += 1
            return {"success": True}

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.generate_daily_digest_for_campus", new_callable=AsyncMock, return_value=digest),
            patch("scheduler.send_whatsapp", side_effect=counting_send),
            patch("scheduler.send_email_alert", new_callable=AsyncMock),
        ):
            await send_daily_digest_to_pastoral_team()

        # Should only send once since same user_id
        assert send_call_count == 1

    @pytest.mark.asyncio
    async def test_deduplicates_by_phone_number(self):
        """Should not send to same phone number twice (different user IDs, same phone)."""
        mock_db = make_mock_db()
        campus = make_test_campus()
        user1 = make_test_user(user_id="u1", phone="+6281111111111", name="User A")
        user2 = make_test_user(user_id="u2", phone="+6281111111111", name="User B")

        mock_db.campuses.find.return_value.to_list = AsyncMock(return_value=[campus])
        mock_db.users.find.return_value.to_list = AsyncMock(return_value=[user1, user2])

        digest = make_digest_result()

        send_count = 0

        async def counting_send(*args, **kwargs):
            nonlocal send_count
            send_count += 1
            return {"success": True}

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.generate_daily_digest_for_campus", new_callable=AsyncMock, return_value=digest),
            patch("scheduler.send_whatsapp", side_effect=counting_send),
            patch("scheduler.send_email_alert", new_callable=AsyncMock),
            patch("scheduler.normalize_phone_number", side_effect=lambda p: p),
        ):
            await send_daily_digest_to_pastoral_team()

        assert send_count == 1

    @pytest.mark.asyncio
    async def test_handles_send_failure(self):
        """Should increment failure count and continue on send failure."""
        mock_db = make_mock_db()
        campus = make_test_campus()
        user = make_test_user()

        mock_db.campuses.find.return_value.to_list = AsyncMock(return_value=[campus])
        mock_db.users.find.return_value.to_list = AsyncMock(return_value=[user])

        digest = make_digest_result()

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.generate_daily_digest_for_campus", new_callable=AsyncMock, return_value=digest),
            patch(
                "scheduler.send_whatsapp", new_callable=AsyncMock, return_value={"success": False, "error": "timeout"}
            ),
            patch("scheduler.send_email_alert", new_callable=AsyncMock) as mock_email,
        ):
            await send_daily_digest_to_pastoral_team()
            # Should send failure alert email
            mock_email.assert_called()

    @pytest.mark.asyncio
    async def test_handles_send_exception_per_user(self):
        """Should catch per-user exception and continue to next user."""
        mock_db = make_mock_db()
        campus = make_test_campus()
        user1 = make_test_user(user_id="u1", phone="+6281111111111", name="Fail User")
        user2 = make_test_user(user_id="u2", phone="+6281222222222", name="OK User")

        mock_db.campuses.find.return_value.to_list = AsyncMock(return_value=[campus])

        # First call returns pastoral team; subsequent calls return empty (no full_admins)
        user_call_count = [0]

        async def users_to_list(_):
            user_call_count[0] += 1
            if user_call_count[0] == 1:
                return [user1, user2]
            return []

        mock_db.users.find.return_value.to_list = users_to_list

        digest = make_digest_result()
        send_call_count = [0]

        async def send_with_exception(*args, **kwargs):
            send_call_count[0] += 1
            if send_call_count[0] == 1:
                raise ConnectionError("Network error")
            return {"success": True}

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.generate_daily_digest_for_campus", new_callable=AsyncMock, return_value=digest),
            patch("scheduler.send_whatsapp", side_effect=send_with_exception),
            patch("scheduler.send_email_alert", new_callable=AsyncMock),
        ):
            await send_daily_digest_to_pastoral_team()

        # Both users were attempted
        assert send_call_count[0] == 2

    @pytest.mark.asyncio
    async def test_full_admin_receives_first_campus_digest(self):
        """Full admins should receive digest from first campus with tasks."""
        mock_db = make_mock_db()
        campus = make_test_campus("c1", "Campus 1")
        admin = make_test_user(user_id="admin1", role="full_admin", phone="+6280000000000", name="Admin")

        mock_db.campuses.find.return_value.to_list = AsyncMock(return_value=[campus])

        # First call: pastoral team (empty); second call: full_admins
        call_idx = [0]

        async def users_to_list(_):
            call_idx[0] += 1
            if call_idx[0] == 1:
                return []  # No pastoral team
            return [admin]

        mock_db.users.find.return_value.to_list = users_to_list

        digest = make_digest_result("c1", "Campus 1")

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.generate_daily_digest_for_campus", new_callable=AsyncMock, return_value=digest),
            patch("scheduler.send_whatsapp", new_callable=AsyncMock, return_value={"success": True}) as mock_send,
            patch("scheduler.send_email_alert", new_callable=AsyncMock),
        ):
            await send_daily_digest_to_pastoral_team()
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_overall_exception_sends_error_email(self):
        """If the entire function crashes, should send error email alert."""
        mock_db = make_mock_db()
        mock_db.campuses.find.return_value.to_list = AsyncMock(side_effect=Exception("DB crash"))

        with patch("scheduler.db", mock_db), patch("scheduler.send_email_alert", new_callable=AsyncMock) as mock_email:
            await send_daily_digest_to_pastoral_team()
            mock_email.assert_called_once()
            # send_email_alert is called with keyword args (subject=..., body=...)
            subject = mock_email.call_args.kwargs.get(
                "subject", mock_email.call_args[0][0] if mock_email.call_args[0] else ""
            )
            assert "Failed" in subject

    @pytest.mark.asyncio
    async def test_user_with_empty_phone_handled(self):
        """Users with empty phone should be handled without error."""
        mock_db = make_mock_db()
        campus = make_test_campus()
        user = make_test_user(phone="", name="No Phone User")

        mock_db.campuses.find.return_value.to_list = AsyncMock(return_value=[campus])
        mock_db.users.find.return_value.to_list = AsyncMock(return_value=[user])

        digest = make_digest_result()

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.generate_daily_digest_for_campus", new_callable=AsyncMock, return_value=digest),
            patch("scheduler.send_whatsapp", new_callable=AsyncMock, return_value={"success": True}),
            patch("scheduler.send_email_alert", new_callable=AsyncMock),
        ):
            # Should not raise
            await send_daily_digest_to_pastoral_team()


# ===========================================================================
# 2. member_reconciliation_job() tests
# ===========================================================================


class TestMemberReconciliationJob:
    """Tests for the daily member reconciliation job."""

    @pytest.mark.asyncio
    async def test_skips_when_lock_not_acquired(self):
        """Should skip reconciliation when lock is already held."""
        with patch("scheduler.acquire_job_lock", new_callable=AsyncMock, return_value=False):
            await member_reconciliation_job()
            # No exception, just returns

    @pytest.mark.asyncio
    async def test_skips_when_no_sync_configs(self):
        """Should skip when no campuses are configured for reconciliation."""
        mock_db = make_mock_db()
        mock_db.sync_configs.find.return_value.to_list = AsyncMock(return_value=[])

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.acquire_job_lock", new_callable=AsyncMock, return_value=True),
            patch("scheduler.release_job_lock", new_callable=AsyncMock) as mock_release,
        ):
            await member_reconciliation_job()
            mock_release.assert_called_once_with("member_reconciliation")

    @pytest.mark.asyncio
    async def test_successful_reconciliation(self):
        """Should call perform_member_sync_for_campus for each config."""
        mock_db = make_mock_db()
        configs = [
            {"campus_id": "c1", "is_enabled": True, "reconciliation_enabled": True},
            {"campus_id": "c2", "is_enabled": True, "reconciliation_enabled": True},
        ]
        mock_db.sync_configs.find.return_value.to_list = AsyncMock(return_value=configs)

        sync_result = {
            "success": True,
            "stats": {"fetched": 10, "created": 2, "updated": 3, "matched_by_name_phone": 1, "matched_by_name_only": 0},
        }

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.acquire_job_lock", new_callable=AsyncMock, return_value=True),
            patch("scheduler.release_job_lock", new_callable=AsyncMock),
            patch(
                "server.perform_member_sync_for_campus", new_callable=AsyncMock, return_value=sync_result, create=True
            ),
        ):
            # The function does `from server import perform_member_sync_for_campus`
            # We need to mock at the import level
            mock_perform = AsyncMock(return_value=sync_result)
            with patch.dict("sys.modules", {"server": MagicMock(perform_member_sync_for_campus=mock_perform)}):
                await member_reconciliation_job()
                assert mock_perform.call_count == 2

    @pytest.mark.asyncio
    async def test_error_handling_per_campus(self):
        """Should continue processing other campuses when one fails."""
        mock_db = make_mock_db()
        configs = [
            {"campus_id": "c1", "is_enabled": True, "reconciliation_enabled": True},
            {"campus_id": "c2", "is_enabled": True, "reconciliation_enabled": True},
        ]
        mock_db.sync_configs.find.return_value.to_list = AsyncMock(return_value=configs)

        call_idx = [0]

        async def sync_with_error(campus_id, sync_type=None):
            call_idx[0] += 1
            if call_idx[0] == 1:
                raise ConnectionError("API down")
            return {
                "success": True,
                "stats": {
                    "fetched": 5,
                    "created": 0,
                    "updated": 0,
                    "matched_by_name_phone": 0,
                    "matched_by_name_only": 0,
                },
            }

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.acquire_job_lock", new_callable=AsyncMock, return_value=True),
            patch("scheduler.release_job_lock", new_callable=AsyncMock),
            patch("scheduler.send_email_alert", new_callable=AsyncMock) as mock_email,
            patch.dict("sys.modules", {"server": MagicMock(perform_member_sync_for_campus=sync_with_error)}),
        ):
            await member_reconciliation_job()
            # Should send email alert for errors
            mock_email.assert_called()

    @pytest.mark.asyncio
    async def test_sync_failure_result(self):
        """Should handle sync returning success=False."""
        mock_db = make_mock_db()
        configs = [{"campus_id": "c1", "is_enabled": True, "reconciliation_enabled": True}]
        mock_db.sync_configs.find.return_value.to_list = AsyncMock(return_value=configs)

        fail_result = {"success": False, "error": "Auth failed"}
        mock_perform = AsyncMock(return_value=fail_result)

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.acquire_job_lock", new_callable=AsyncMock, return_value=True),
            patch("scheduler.release_job_lock", new_callable=AsyncMock),
            patch("scheduler.send_email_alert", new_callable=AsyncMock) as mock_email,
            patch.dict("sys.modules", {"server": MagicMock(perform_member_sync_for_campus=mock_perform)}),
        ):
            await member_reconciliation_job()
            mock_email.assert_called()

    @pytest.mark.asyncio
    async def test_always_releases_lock(self):
        """Lock should be released even if an exception occurs."""
        mock_db = make_mock_db()
        mock_db.sync_configs.find.return_value.to_list = AsyncMock(side_effect=Exception("DB error"))

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.acquire_job_lock", new_callable=AsyncMock, return_value=True),
            patch("scheduler.release_job_lock", new_callable=AsyncMock) as mock_release,
            patch("scheduler.send_email_alert", new_callable=AsyncMock),
        ):
            await member_reconciliation_job()
            mock_release.assert_called_once_with("member_reconciliation")


# ===========================================================================
# 3. refresh_all_dashboard_caches() tests
# ===========================================================================


class TestRefreshAllDashboardCaches:
    """Tests for the dashboard cache refresh job."""

    @pytest.mark.asyncio
    async def test_skips_when_lock_not_acquired(self):
        """Should skip when another worker already holds the lock."""
        with patch("scheduler.acquire_job_lock", new_callable=AsyncMock, return_value=False):
            await refresh_all_dashboard_caches()

    @pytest.mark.asyncio
    async def test_refreshes_cache_for_each_campus(self):
        """Should calculate and store dashboard data for each active campus."""
        mock_db = MagicMock()
        mock_db.dashboard_cache.update_one = AsyncMock()
        mock_db.dashboard_cache.delete_many = AsyncMock()
        mock_db.job_locks.update_one = AsyncMock()
        mock_db.job_locks.delete_one = AsyncMock()

        campuses = [
            {"id": "c1", "campus_name": "Campus 1", "timezone": "Asia/Jakarta"},
            {"id": "c2", "campus_name": "Campus 2", "timezone": "Asia/Jakarta"},
        ]

        mock_calculate = AsyncMock(return_value={"total_tasks": 5})
        mock_get_tz = MagicMock(return_value="Asia/Jakarta")
        mock_get_date = MagicMock(return_value="2026-03-29")
        mock_writeoff = AsyncMock(return_value={})

        campus_cursor = MagicMock()
        campus_cursor.to_list = AsyncMock(return_value=campuses)
        mock_db.campuses.find = MagicMock(return_value=campus_cursor)

        mock_server = MagicMock()
        mock_server.db = mock_db
        mock_server.get_campus_timezone = mock_get_tz
        mock_server.get_date_in_timezone = mock_get_date
        mock_server.get_writeoff_settings = mock_writeoff
        mock_server.SECRET_KEY = "test-key"

        mock_dashboard = MagicMock()
        mock_dashboard.calculate_dashboard_reminders = mock_calculate
        mock_dashboard.init_dashboard_routes = MagicMock()

        mock_deps = MagicMock()
        mock_deps.init_dependencies = MagicMock()

        with (
            patch("scheduler.acquire_job_lock", new_callable=AsyncMock, return_value=True),
            patch("scheduler.release_job_lock", new_callable=AsyncMock) as mock_release,
            patch.dict(
                "sys.modules",
                {
                    "server": mock_server,
                    "routes": MagicMock(),
                    "routes.dashboard": mock_dashboard,
                    "dependencies": mock_deps,
                },
            ),
        ):
            await refresh_all_dashboard_caches()
            assert mock_calculate.call_count == 2
            assert mock_db.dashboard_cache.update_one.call_count == 2
            mock_release.assert_called_once_with("cache_refresh")

    @pytest.mark.asyncio
    async def test_cleans_up_old_cache_entries(self):
        """Should delete cache entries older than 2 days."""
        mock_db = MagicMock()
        mock_db.dashboard_cache.update_one = AsyncMock()
        mock_db.dashboard_cache.delete_many = AsyncMock()
        mock_db.job_locks.update_one = AsyncMock()
        mock_db.job_locks.delete_one = AsyncMock()

        campus_cursor = MagicMock()
        campus_cursor.to_list = AsyncMock(
            return_value=[{"id": "c1", "campus_name": "Campus 1", "timezone": "Asia/Jakarta"}]
        )
        mock_db.campuses.find = MagicMock(return_value=campus_cursor)

        mock_server = MagicMock()
        mock_server.db = mock_db
        mock_server.get_campus_timezone = MagicMock(return_value="Asia/Jakarta")
        mock_server.get_date_in_timezone = MagicMock(return_value="2026-03-29")
        mock_server.get_writeoff_settings = AsyncMock(return_value={})
        mock_server.SECRET_KEY = "test-key"

        mock_dashboard = MagicMock()
        mock_dashboard.calculate_dashboard_reminders = AsyncMock(return_value={"total_tasks": 0})
        mock_dashboard.init_dashboard_routes = MagicMock()

        mock_deps = MagicMock()
        mock_deps.init_dependencies = MagicMock()

        with (
            patch("scheduler.acquire_job_lock", new_callable=AsyncMock, return_value=True),
            patch("scheduler.release_job_lock", new_callable=AsyncMock),
            patch.dict(
                "sys.modules",
                {
                    "server": mock_server,
                    "routes": MagicMock(),
                    "routes.dashboard": mock_dashboard,
                    "dependencies": mock_deps,
                },
            ),
        ):
            await refresh_all_dashboard_caches()
            mock_db.dashboard_cache.delete_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_error_gracefully(self):
        """Should catch exceptions and release lock."""
        with (
            patch("scheduler.acquire_job_lock", new_callable=AsyncMock, return_value=True),
            patch("scheduler.release_job_lock", new_callable=AsyncMock) as mock_release,
        ):
            # Import will fail because 'server' module is not real
            # The function catches the ImportError/Exception
            with (
                patch.dict("sys.modules", {"server": MagicMock(side_effect=Exception("import error"))}),
                contextlib.suppress(Exception),
            ):
                await refresh_all_dashboard_caches()
            mock_release.assert_called_with("cache_refresh")


# ===========================================================================
# 4. daily_reminder_job() tests
# ===========================================================================


class TestDailyReminderJob:
    """Tests for the main daily reminder job orchestrator."""

    @pytest.mark.asyncio
    async def test_skips_when_lock_not_acquired(self):
        """Should skip when lock cannot be acquired."""
        with (
            patch("scheduler.acquire_job_lock", new_callable=AsyncMock, return_value=False),
            patch("scheduler.refresh_all_dashboard_caches", new_callable=AsyncMock) as mock_refresh,
            patch("scheduler.send_daily_digest_to_pastoral_team", new_callable=AsyncMock) as mock_digest,
        ):
            await daily_reminder_job()
            mock_refresh.assert_not_called()
            mock_digest.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_both_sub_functions(self):
        """Should call refresh_all_dashboard_caches and send_daily_digest."""
        with (
            patch("scheduler.acquire_job_lock", new_callable=AsyncMock, return_value=True),
            patch("scheduler.release_job_lock", new_callable=AsyncMock) as mock_release,
            patch("scheduler.refresh_all_dashboard_caches", new_callable=AsyncMock) as mock_refresh,
            patch("scheduler.ensure_whatsapp_connected", new_callable=AsyncMock) as mock_preflight,
            patch("scheduler.send_daily_digest_to_pastoral_team", new_callable=AsyncMock) as mock_digest,
        ):
            await daily_reminder_job()
            mock_refresh.assert_called_once()
            mock_preflight.assert_called_once()
            mock_digest.assert_called_once()
            mock_release.assert_called_once_with("daily_reminder")

    @pytest.mark.asyncio
    async def test_releases_lock_even_on_error(self):
        """Should release lock even if sub-functions raise."""
        with (
            patch("scheduler.acquire_job_lock", new_callable=AsyncMock, return_value=True),
            patch("scheduler.release_job_lock", new_callable=AsyncMock) as mock_release,
            patch("scheduler.refresh_all_dashboard_caches", new_callable=AsyncMock, side_effect=Exception("Crash")),
            patch("scheduler.send_daily_digest_to_pastoral_team", new_callable=AsyncMock),
        ):
            # finally block should still release lock
            with contextlib.suppress(Exception):
                await daily_reminder_job()
            mock_release.assert_called_once_with("daily_reminder")


# ===========================================================================
# 5. schedule_daily_digest() tests
# ===========================================================================


class TestScheduleDailyDigest:
    """Tests for scheduling the daily digest cron job."""

    def test_adds_job_with_correct_time(self):
        """Should add a cron job at the specified hour and minute."""
        mock_sched = MagicMock()
        mock_sched.remove_job = MagicMock()
        mock_sched.add_job = MagicMock()

        with patch("scheduler.scheduler", mock_sched):
            schedule_daily_digest(7, 30)
            mock_sched.add_job.assert_called_once()
            call_kwargs = mock_sched.add_job.call_args
            assert call_kwargs.kwargs.get("hour") or call_kwargs[1].get("hour") == 7

    def test_removes_existing_job_before_adding(self):
        """Should remove existing 'daily_reminders' job first."""
        mock_sched = MagicMock()
        mock_sched.remove_job = MagicMock()
        mock_sched.add_job = MagicMock()

        with patch("scheduler.scheduler", mock_sched):
            schedule_daily_digest(8, 0)
            mock_sched.remove_job.assert_called_once_with("daily_reminders")

    def test_handles_remove_job_exception(self):
        """Should continue even if remove_job raises (job doesn't exist)."""
        mock_sched = MagicMock()
        mock_sched.remove_job = MagicMock(side_effect=Exception("Job not found"))
        mock_sched.add_job = MagicMock()

        with patch("scheduler.scheduler", mock_sched):
            schedule_daily_digest(9, 15)
            mock_sched.add_job.assert_called_once()

    def test_handles_add_job_exception(self):
        """Should not raise if add_job fails."""
        mock_sched = MagicMock()
        mock_sched.remove_job = MagicMock()
        mock_sched.add_job = MagicMock(side_effect=Exception("Scheduler not running"))

        with patch("scheduler.scheduler", mock_sched):
            # Should not raise
            schedule_daily_digest(8, 0)

    def test_job_id_is_daily_reminders(self):
        """Job should use 'daily_reminders' as its ID."""
        mock_sched = MagicMock()
        mock_sched.remove_job = MagicMock()
        mock_sched.add_job = MagicMock()

        with patch("scheduler.scheduler", mock_sched):
            schedule_daily_digest(10, 0)
            call_kwargs = mock_sched.add_job.call_args
            assert call_kwargs.kwargs.get("id") == "daily_reminders" or (
                len(call_kwargs) > 1 and "daily_reminders" in str(call_kwargs)
            )


# ===========================================================================
# 6. reschedule_daily_digest() and init_daily_digest_schedule() tests
# ===========================================================================


class TestRescheduleAndInit:
    """Tests for reschedule_daily_digest() and init_daily_digest_schedule()."""

    @pytest.mark.asyncio
    async def test_reschedule_parses_time_and_schedules(self):
        """Should parse HH:MM from DB and call schedule_daily_digest."""
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(return_value={"type": "automation", "data": {"digestTime": "07:45"}})

        with patch("scheduler.db", mock_db), patch("scheduler.schedule_daily_digest") as mock_schedule:
            await reschedule_daily_digest()
            mock_schedule.assert_called_once_with(7, 45)

    @pytest.mark.asyncio
    async def test_reschedule_uses_default_on_invalid_format(self):
        """Should default to 08:00 if time format is invalid."""
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(return_value={"type": "automation", "data": {"digestTime": "invalid"}})

        with patch("scheduler.db", mock_db), patch("scheduler.schedule_daily_digest") as mock_schedule:
            await reschedule_daily_digest()
            mock_schedule.assert_called_once_with(8, 0)

    @pytest.mark.asyncio
    async def test_reschedule_uses_default_when_no_setting(self):
        """Should use 08:00 when no digest time is configured."""
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(return_value=None)

        with patch("scheduler.db", mock_db), patch("scheduler.schedule_daily_digest") as mock_schedule:
            await reschedule_daily_digest()
            mock_schedule.assert_called_once_with(8, 0)

    @pytest.mark.asyncio
    async def test_init_daily_digest_schedule_calls_reschedule(self):
        """init_daily_digest_schedule should wait then call reschedule."""
        with (
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("scheduler.reschedule_daily_digest", new_callable=AsyncMock) as mock_reschedule,
        ):
            await init_daily_digest_schedule()
            mock_sleep.assert_called_once_with(2)
            mock_reschedule.assert_called_once()


# ===========================================================================
# 7. check_missed_reconciliation() tests
# ===========================================================================


class TestCheckMissedReconciliation:
    """Tests for the missed reconciliation checker."""

    @pytest.mark.asyncio
    async def test_skips_when_no_sync_configs(self):
        """Should skip when no campuses have reconciliation enabled."""
        mock_db = make_mock_db()
        mock_db.sync_configs.find.return_value.to_list = AsyncMock(return_value=[])

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.member_reconciliation_job", new_callable=AsyncMock) as mock_recon,
        ):
            await check_missed_reconciliation()
            mock_recon.assert_not_called()

    @pytest.mark.asyncio
    async def test_runs_reconciliation_when_sync_overdue(self):
        """Should trigger reconciliation if last sync was >24 hours ago."""
        mock_db = make_mock_db()
        old_sync = (datetime.now(UTC) - timedelta(hours=30)).isoformat()
        configs = [
            {
                "campus_id": "c1",
                "is_enabled": True,
                "reconciliation_enabled": True,
                "last_sync_at": old_sync,
            }
        ]
        mock_db.sync_configs.find.return_value.to_list = AsyncMock(return_value=configs)

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.member_reconciliation_job", new_callable=AsyncMock) as mock_recon,
        ):
            await check_missed_reconciliation()
            mock_recon.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_when_sync_is_recent(self):
        """Should skip reconciliation if last sync was within 24 hours."""
        mock_db = make_mock_db()
        recent_sync = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
        configs = [
            {
                "campus_id": "c1",
                "is_enabled": True,
                "reconciliation_enabled": True,
                "last_sync_at": recent_sync,
            }
        ]
        mock_db.sync_configs.find.return_value.to_list = AsyncMock(return_value=configs)

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.member_reconciliation_job", new_callable=AsyncMock) as mock_recon,
        ):
            await check_missed_reconciliation()
            mock_recon.assert_not_called()

    @pytest.mark.asyncio
    async def test_runs_initial_reconciliation_when_no_previous_sync(self):
        """Should trigger reconciliation if last_sync_at is None."""
        mock_db = make_mock_db()
        configs = [
            {
                "campus_id": "c1",
                "is_enabled": True,
                "reconciliation_enabled": True,
                "last_sync_at": None,
            }
        ]
        mock_db.sync_configs.find.return_value.to_list = AsyncMock(return_value=configs)

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.member_reconciliation_job", new_callable=AsyncMock) as mock_recon,
        ):
            await check_missed_reconciliation()
            mock_recon.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_naive_datetime_from_mongodb(self):
        """Should handle MongoDB naive datetime (assumes UTC)."""
        mock_db = make_mock_db()
        # MongoDB stores/returns naive datetimes in UTC. Build a naive *UTC*
        # timestamp 30h ago (not datetime.now(), which is local Jakarta time and
        # would be misread as UTC, shrinking the gap to ~23h on a WIB host).
        naive_dt = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=30)
        configs = [
            {
                "campus_id": "c1",
                "is_enabled": True,
                "reconciliation_enabled": True,
                "last_sync_at": naive_dt,
            }
        ]
        mock_db.sync_configs.find.return_value.to_list = AsyncMock(return_value=configs)

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.member_reconciliation_job", new_callable=AsyncMock) as mock_recon,
        ):
            await check_missed_reconciliation()
            mock_recon.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_z_suffix_in_datetime_string(self):
        """Should handle ISO datetime strings ending with Z."""
        mock_db = make_mock_db()
        old_sync = (datetime.now(UTC) - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        configs = [
            {
                "campus_id": "c1",
                "is_enabled": True,
                "reconciliation_enabled": True,
                "last_sync_at": old_sync,
            }
        ]
        mock_db.sync_configs.find.return_value.to_list = AsyncMock(return_value=configs)

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.member_reconciliation_job", new_callable=AsyncMock) as mock_recon,
        ):
            await check_missed_reconciliation()
            mock_recon.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self):
        """Should catch exceptions and not propagate them."""
        mock_db = make_mock_db()
        mock_db.sync_configs.find.return_value.to_list = AsyncMock(side_effect=Exception("DB error"))

        with patch("scheduler.db", mock_db), patch("scheduler.asyncio.sleep", new_callable=AsyncMock):
            # Should not raise
            await check_missed_reconciliation()

    @pytest.mark.asyncio
    async def test_only_triggers_once_for_multiple_overdue_campuses(self):
        """Should trigger reconciliation only once even with multiple overdue campuses."""
        mock_db = make_mock_db()
        old_sync = (datetime.now(UTC) - timedelta(hours=30)).isoformat()
        configs = [
            {"campus_id": "c1", "is_enabled": True, "reconciliation_enabled": True, "last_sync_at": old_sync},
            {"campus_id": "c2", "is_enabled": True, "reconciliation_enabled": True, "last_sync_at": old_sync},
        ]
        mock_db.sync_configs.find.return_value.to_list = AsyncMock(return_value=configs)

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.member_reconciliation_job", new_callable=AsyncMock) as mock_recon,
        ):
            await check_missed_reconciliation()
            # The function returns after first trigger
            mock_recon.assert_called_once()


# ===========================================================================
# 8. generate_daily_digest_for_campus() additional edge case tests
# ===========================================================================


class TestGenerateDigestEdgeCases:
    """Additional edge case tests for digest generation."""

    @pytest.mark.asyncio
    async def test_overdue_hospital_followups_in_message(self):
        """Overdue hospital follow-ups should appear in the overdue section."""
        today = datetime.now(JAKARTA_TZ).date()
        yesterday = (today - timedelta(days=2)).isoformat()
        member = {"id": "m1", "name": "Overdue Hospital", "phone": "+6281999999999"}

        mock_db = make_mock_db()

        # Members with birthday
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)

        # accident_followup: two calls - today (empty) and overdue (one item)
        acc_call = [0]

        async def acc_to_list(_):
            acc_call[0] += 1
            if acc_call[0] == 1:
                return []  # today
            return [
                {
                    "campus_id": "c1",
                    "member_id": "m1",
                    "stage": "first_followup",
                    "scheduled_date": yesterday,
                    "completed": False,
                    "ignored": False,
                }
            ]

        mock_db.accident_followup.find.return_value.to_list = acc_to_list

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["overdue_hospital"] == 1
        assert "Overdue Hospital" in digest["message"]
        assert "TUGAS TERLAMBAT" in digest["message"]

    @pytest.mark.asyncio
    async def test_overdue_financial_aid_in_message(self):
        """Overdue financial aid should appear in the overdue section."""
        today = datetime.now(JAKARTA_TZ).date()
        overdue_date = (today - timedelta(days=5)).isoformat()
        member = {"id": "m1", "name": "Overdue Aid", "phone": "+6281888888888"}

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)

        fin_call = [0]

        async def fin_to_list(_):
            fin_call[0] += 1
            if fin_call[0] == 1:
                return []  # today
            return [
                {
                    "campus_id": "c1",
                    "member_id": "m1",
                    "aid_type": "education",
                    "next_occurrence": overdue_date,
                    "is_active": True,
                }
            ]

        mock_db.financial_aid_schedules.find.return_value.to_list = fin_to_list

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["overdue_financial"] == 1

    @pytest.mark.asyncio
    async def test_overdue_pastoral_notes_in_message(self):
        """Overdue pastoral notes should appear in the overdue section."""
        today = datetime.now(JAKARTA_TZ).date()
        overdue_date = (today - timedelta(days=3)).isoformat()
        member = {"id": "m1", "name": "Note Overdue Person", "phone": "+6281777777777"}

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)
        mock_db.pastoral_notes.find.return_value.to_list = AsyncMock(
            return_value=[
                {
                    "campus_id": "c1",
                    "member_id": "m1",
                    "title": "Follow up on family counseling session",
                    "category": "family",
                    "follow_up_date": overdue_date,
                    "follow_up_completed": False,
                    "is_private": False,
                }
            ]
        )

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["overdue_notes"] == 1
        assert "Note Overdue Person" in digest["message"]
        assert "Keluarga" in digest["message"]  # category_names mapping

    @pytest.mark.asyncio
    async def test_pastoral_note_due_today_in_message(self):
        """Pastoral notes due today should appear in the today section."""
        today = datetime.now(JAKARTA_TZ).date()
        member = {"id": "m1", "name": "Today Note Person", "phone": "+6281666666666"}

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)
        mock_db.pastoral_notes.find.return_value.to_list = AsyncMock(
            return_value=[
                {
                    "campus_id": "c1",
                    "member_id": "m1",
                    "title": "Check health status update",
                    "category": "health",
                    "follow_up_date": today.isoformat(),
                    "follow_up_completed": False,
                    "is_private": False,
                }
            ]
        )

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["notes_due_today"] == 1
        assert "Today Note Person" in digest["message"]

    @pytest.mark.asyncio
    async def test_phone_with_whatsapp_suffix_cleaned(self):
        """Phone numbers with @s.whatsapp.net should be cleaned in digest."""
        today = datetime.now(JAKARTA_TZ).date()
        member = {
            "id": "m1",
            "name": "Suffix Member",
            "phone": "6281111111111@s.whatsapp.net",
            "birth_date": f"1990-{today.month:02d}-{today.day:02d}",
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)
        mock_db.care_events.find_one = AsyncMock(
            return_value={"member_id": "m1", "event_type": "birthday", "completed": False}
        )

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        # Should have cleaned phone (no @s.whatsapp.net in the message)
        assert "@s.whatsapp.net" not in digest["message"]
        assert "wa.me/6281111111111" in digest["message"]

    @pytest.mark.asyncio
    async def test_all_task_types_present(self):
        """Digest should include all task types when all are present."""
        today = datetime.now(JAKARTA_TZ).date()
        member = {
            "id": "m1",
            "name": "All Tasks Member",
            "phone": "+6281555555555",
            "birth_date": f"1990-{today.month:02d}-{today.day:02d}",
            "last_contact_date": None,
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)
        mock_db.care_events.find_one = AsyncMock(
            return_value={"member_id": "m1", "event_type": "birthday", "completed": False}
        )

        # grief today
        grief_call = [0]

        async def grief_list(_):
            grief_call[0] += 1
            if grief_call[0] == 1:
                return [
                    {
                        "campus_id": "c1",
                        "member_id": "m1",
                        "stage": "1_week",
                        "scheduled_date": today.isoformat(),
                        "completed": False,
                    }
                ]
            return []

        mock_db.grief_support.find.return_value.to_list = grief_list

        # hospital today
        hosp_call = [0]

        async def hosp_list(_):
            hosp_call[0] += 1
            if hosp_call[0] == 1:
                return [
                    {
                        "campus_id": "c1",
                        "member_id": "m1",
                        "stage": "first_followup",
                        "scheduled_date": today.isoformat(),
                        "completed": False,
                        "ignored": False,
                    }
                ]
            return []

        mock_db.accident_followup.find.return_value.to_list = hosp_list

        # financial aid today
        fin_call = [0]

        async def fin_list(_):
            fin_call[0] += 1
            if fin_call[0] == 1:
                return [
                    {
                        "campus_id": "c1",
                        "member_id": "m1",
                        "aid_type": "medical",
                        "next_occurrence": today.isoformat(),
                        "is_active": True,
                    }
                ]
            return []

        mock_db.financial_aid_schedules.find.return_value.to_list = fin_list

        # pastoral notes today
        mock_db.pastoral_notes.find.return_value.to_list = AsyncMock(
            return_value=[
                {
                    "campus_id": "c1",
                    "member_id": "m1",
                    "title": "Note title",
                    "category": "spiritual",
                    "follow_up_date": today.isoformat(),
                    "follow_up_completed": False,
                    "is_private": False,
                }
            ]
        )

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["birthdays_today"] >= 1
        assert digest["stats"]["grief_due"] >= 1
        assert digest["stats"]["hospital_followups"] >= 1
        assert digest["stats"]["financial_aid"] >= 1
        assert digest["stats"]["notes_due_today"] >= 1
        assert digest["stats"]["at_risk"] >= 1

        # Check message sections
        assert "ULANG TAHUN HARI INI" in digest["message"]
        assert "DUKUNGAN DUKACITA" in digest["message"]
        assert "TINDAK LANJUT RUMAH SAKIT" in digest["message"]
        assert "BANTUAN KEUANGAN" in digest["message"]
        assert "CATATAN PASTORAL" in digest["message"]
        assert "JEMAAT BERISIKO" in digest["message"]

    @pytest.mark.asyncio
    async def test_grief_member_without_phone_skipped(self):
        """Grief stage member without phone should be skipped."""
        today = datetime.now(JAKARTA_TZ).date()
        member_no_phone = {"id": "m1", "name": "No Phone Grief"}

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member_no_phone])
        mock_db.members.find_one = AsyncMock(return_value=member_no_phone)

        grief_call = [0]

        async def grief_list(_):
            grief_call[0] += 1
            if grief_call[0] == 1:
                return [
                    {
                        "campus_id": "c1",
                        "member_id": "m1",
                        "stage": "1_week",
                        "scheduled_date": today.isoformat(),
                        "completed": False,
                    }
                ]
            return []

        mock_db.grief_support.find.return_value.to_list = grief_list

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["grief_due"] == 0

    @pytest.mark.asyncio
    async def test_overdue_grief_with_invalid_date_skipped(self):
        """Overdue grief with invalid scheduled_date should be skipped."""
        datetime.now(JAKARTA_TZ).date()
        member = {"id": "m1", "name": "Bad Date Grief", "phone": "+6281444444444"}

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)

        grief_call = [0]

        async def grief_list(_):
            grief_call[0] += 1
            if grief_call[0] == 1:
                return []
            return [
                {
                    "campus_id": "c1",
                    "member_id": "m1",
                    "stage": "1_month",
                    "scheduled_date": "invalid-date",
                    "completed": False,
                }
            ]

        mock_db.grief_support.find.return_value.to_list = grief_list

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["overdue_grief"] == 0

    @pytest.mark.asyncio
    async def test_overdue_hospital_with_invalid_date_skipped(self):
        """Overdue hospital follow-up with invalid date should be skipped."""
        member = {"id": "m1", "name": "Bad Date Hospital", "phone": "+6281333333333"}

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)

        acc_call = [0]

        async def acc_list(_):
            acc_call[0] += 1
            if acc_call[0] == 1:
                return []
            return [
                {
                    "campus_id": "c1",
                    "member_id": "m1",
                    "stage": "second_followup",
                    "scheduled_date": "bad-date",
                    "completed": False,
                    "ignored": False,
                }
            ]

        mock_db.accident_followup.find.return_value.to_list = acc_list

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["overdue_hospital"] == 0

    @pytest.mark.asyncio
    async def test_overdue_financial_with_invalid_date_skipped(self):
        """Overdue financial aid with invalid date should be skipped."""
        member = {"id": "m1", "name": "Bad Date Finance", "phone": "+6281222222222"}

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)

        fin_call = [0]

        async def fin_list(_):
            fin_call[0] += 1
            if fin_call[0] == 1:
                return []
            return [
                {
                    "campus_id": "c1",
                    "member_id": "m1",
                    "aid_type": "living",
                    "next_occurrence": "not-a-date",
                    "is_active": True,
                }
            ]

        mock_db.financial_aid_schedules.find.return_value.to_list = fin_list

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["overdue_financial"] == 0

    @pytest.mark.asyncio
    async def test_pastoral_note_with_invalid_date_skipped(self):
        """Pastoral note with invalid follow_up_date should be skipped."""
        member = {"id": "m1", "name": "Bad Date Note", "phone": "+6281111111111"}

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)
        mock_db.pastoral_notes.find.return_value.to_list = AsyncMock(
            return_value=[
                {
                    "campus_id": "c1",
                    "member_id": "m1",
                    "title": "Bad date note",
                    "category": "other",
                    "follow_up_date": "invalid",
                    "follow_up_completed": False,
                    "is_private": False,
                }
            ]
        )

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["notes_due_today"] == 0
        assert digest["stats"]["overdue_notes"] == 0

    @pytest.mark.asyncio
    async def test_pastoral_note_long_title_truncated(self):
        """Long pastoral note titles should be truncated to 50 chars."""
        today = datetime.now(JAKARTA_TZ).date()
        member = {"id": "m1", "name": "Long Title", "phone": "+6281111111111"}

        long_title = "A" * 80  # 80 characters, should be truncated to 50

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)
        mock_db.pastoral_notes.find.return_value.to_list = AsyncMock(
            return_value=[
                {
                    "campus_id": "c1",
                    "member_id": "m1",
                    "title": long_title,
                    "category": "health",
                    "follow_up_date": today.isoformat(),
                    "follow_up_completed": False,
                    "is_private": False,
                }
            ]
        )

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        # Title should be truncated with ellipsis
        assert "A" * 50 + "..." in digest["message"]
        assert "A" * 51 not in digest["message"]

    @pytest.mark.asyncio
    async def test_member_with_datetime_last_contact(self):
        """Should handle datetime objects for last_contact_date (not just strings)."""
        old_dt = datetime.now(UTC) - timedelta(days=60)
        member = {
            "id": "m1",
            "name": "Datetime Contact",
            "phone": "+6281000000000",
            "last_contact_date": old_dt,  # datetime object, not string
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["at_risk"] >= 1

    @pytest.mark.asyncio
    async def test_member_with_naive_datetime_last_contact(self):
        """Should handle naive datetime (no timezone) for last_contact_date."""
        naive_dt = datetime.now() - timedelta(days=60)  # No timezone
        member = {
            "id": "m1",
            "name": "Naive Datetime",
            "phone": "+6281000000001",
            "last_contact_date": naive_dt,
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["at_risk"] >= 1

    @pytest.mark.asyncio
    async def test_financial_aid_type_mapping(self):
        """Financial aid type names should be mapped to Indonesian."""
        today = datetime.now(JAKARTA_TZ).date()
        member = {"id": "m1", "name": "Aid Type Test", "phone": "+6281444444444"}

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)

        fin_call = [0]

        async def fin_list(_):
            fin_call[0] += 1
            if fin_call[0] == 1:
                return [
                    {
                        "campus_id": "c1",
                        "member_id": "m1",
                        "aid_type": "medical",
                        "next_occurrence": today.isoformat(),
                        "is_active": True,
                    }
                ]
            return []

        mock_db.financial_aid_schedules.find.return_value.to_list = fin_list

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert "Kesehatan" in digest["message"]  # "medical" -> "Kesehatan"

    @pytest.mark.asyncio
    async def test_grief_stage_name_mapping(self):
        """Grief stage names should be mapped to Indonesian."""
        today = datetime.now(JAKARTA_TZ).date()
        member = {"id": "m1", "name": "Grief Stage Test", "phone": "+6281555555555"}

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)

        grief_call = [0]

        async def grief_list(_):
            grief_call[0] += 1
            if grief_call[0] == 1:
                return [
                    {
                        "campus_id": "c1",
                        "member_id": "m1",
                        "stage": "3_months",
                        "scheduled_date": today.isoformat(),
                        "completed": False,
                    }
                ]
            return []

        mock_db.grief_support.find.return_value.to_list = grief_list

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert "3 bulan" in digest["message"]  # "3_months" -> "3 bulan"

    @pytest.mark.asyncio
    async def test_hospital_stage_name_mapping(self):
        """Hospital follow-up stage names should be mapped to Indonesian."""
        today = datetime.now(JAKARTA_TZ).date()
        member = {"id": "m1", "name": "Hospital Stage Test", "phone": "+6281666666666"}

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)

        hosp_call = [0]

        async def hosp_list(_):
            hosp_call[0] += 1
            if hosp_call[0] == 1:
                return [
                    {
                        "campus_id": "c1",
                        "member_id": "m1",
                        "stage": "final_followup",
                        "scheduled_date": today.isoformat(),
                        "completed": False,
                        "ignored": False,
                    }
                ]
            return []

        mock_db.accident_followup.find.return_value.to_list = hosp_list

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert "tindak lanjut akhir" in digest["message"]


# ===========================================================================
# 9. send_whatsapp() retry and edge case tests
# ===========================================================================


class TestSendWhatsappRetryBehavior:
    """Additional tests for WhatsApp send with retry logic."""

    @pytest.mark.asyncio
    async def test_retries_on_connection_error(self):
        """Should retry on connection errors and eventually fail."""
        mock_db = make_mock_db()

        call_count = 0

        async def failing_post(url, json=None):
            nonlocal call_count
            call_count += 1
            raise Exception("Connection refused")

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.os.environ.get", return_value="http://wa:3000"),
            patch("scheduler.httpx.AsyncClient") as mock_client_cls,
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.send_email_alert", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.post = failing_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await send_whatsapp("+6281234567890", "Test", {"id": "t1"})

            assert result["success"] is False
            assert call_count == 3  # WHATSAPP_MAX_RETRIES

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self):
        """Should retry on timeout exceptions."""
        import httpx as real_httpx

        mock_db = make_mock_db()

        call_count = 0

        async def timeout_post(url, json=None):
            nonlocal call_count
            call_count += 1
            raise real_httpx.TimeoutException("Read timeout")

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.os.environ.get", return_value="http://wa:3000"),
            patch("scheduler.httpx.AsyncClient") as mock_client_cls,
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.send_email_alert", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.post = timeout_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await send_whatsapp("+6281234567890", "Test", {"id": "t1"})
            assert result["success"] is False
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_retries_on_non_success_code(self):
        """Should retry when gateway returns non-SUCCESS code (retryable)."""
        mock_db = make_mock_db()

        mock_response = MagicMock()
        mock_response.json.return_value = {"code": "TEMPORARY_ERROR"}

        call_count = 0

        async def counting_post(url, json=None):
            nonlocal call_count
            call_count += 1
            return mock_response

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.os.environ.get", return_value="http://wa:3000"),
            patch("scheduler.httpx.AsyncClient") as mock_client_cls,
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.send_email_alert", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.post = counting_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await send_whatsapp("+6281234567890", "Test", {"id": "t1"})
            assert result["success"] is False
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_logs_failure_notification(self):
        """Should log failure to notification_logs after all retries exhausted."""
        mock_db = make_mock_db()

        async def failing_post(url, json=None):
            raise Exception("Network error")

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.os.environ.get", return_value="http://wa:3000"),
            patch("scheduler.httpx.AsyncClient") as mock_client_cls,
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.send_email_alert", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.post = failing_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await send_whatsapp("+6281234567890", "Test message", {"id": "t1"})

            # Check that notification_logs.insert_one was called with failure
            mock_db.notification_logs.insert_one.assert_called()
            call_args = mock_db.notification_logs.insert_one.call_args[0][0]
            assert call_args["status"] == "failed"
            assert call_args["attempts"] == 3

    @pytest.mark.asyncio
    async def test_sends_email_alert_on_persistent_failure(self):
        """Should send email alert after all retries exhausted."""
        mock_db = make_mock_db()

        async def failing_post(url, json=None):
            raise Exception("Network error")

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.os.environ.get", return_value="http://wa:3000"),
            patch("scheduler.httpx.AsyncClient") as mock_client_cls,
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.send_email_alert", new_callable=AsyncMock) as mock_email,
        ):
            mock_client = AsyncMock()
            mock_client.post = failing_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await send_whatsapp("+6281234567890", "Test", {"id": "t1"})
            mock_email.assert_called_once()
            # send_email_alert is called with keyword args (subject=..., body=...)
            subject = mock_email.call_args.kwargs.get(
                "subject", mock_email.call_args[0][0] if mock_email.call_args[0] else ""
            )
            assert "Failed" in subject

    @pytest.mark.asyncio
    async def test_success_on_second_attempt(self):
        """Should succeed if second attempt works after first fails."""
        mock_db = make_mock_db()

        success_response = MagicMock()
        success_response.json.return_value = {"code": "SUCCESS"}

        call_count = 0

        async def intermittent_post(url, json=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary error")
            return success_response

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.os.environ.get", return_value="http://wa:3000"),
            patch("scheduler.httpx.AsyncClient") as mock_client_cls,
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.post = intermittent_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await send_whatsapp("+6281234567890", "Test", {"id": "t1"})
            assert result["success"] is True
            assert result["attempts"] == 2

    @pytest.mark.asyncio
    async def test_logs_success_notification(self):
        """Should log successful send to notification_logs."""
        mock_db = make_mock_db()

        mock_response = MagicMock()
        mock_response.json.return_value = {"code": "SUCCESS"}

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.os.environ.get", return_value="http://wa:3000"),
            patch("scheduler.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await send_whatsapp("+6281234567890", "Test", {"id": "t1", "campus_id": "c1"})

            mock_db.notification_logs.insert_one.assert_called_once()
            call_args = mock_db.notification_logs.insert_one.call_args[0][0]
            assert call_args["status"] == "sent"
            assert call_args["campus_id"] == "c1"

    @pytest.mark.asyncio
    async def test_retries_on_connect_error(self):
        """Should retry specifically on httpx.ConnectError."""
        import httpx as real_httpx

        mock_db = make_mock_db()

        call_count = 0

        async def connect_error_post(url, json=None):
            nonlocal call_count
            call_count += 1
            raise real_httpx.ConnectError("Connection refused")

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.os.environ.get", return_value="http://wa:3000"),
            patch("scheduler.httpx.AsyncClient") as mock_client_cls,
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.send_email_alert", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.post = connect_error_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await send_whatsapp("+6281234567890", "Test", {"id": "t1"})
            assert result["success"] is False
            assert call_count == 3


# ===========================================================================
# 10. send_email_alert() additional tests
# ===========================================================================


class TestSendEmailAlertAdditional:
    """Additional tests for email alert sending."""

    @pytest.mark.asyncio
    async def test_successful_send(self):
        """Should return True when email is sent successfully."""
        mock_smtp_instance = MagicMock()
        mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_instance.__exit__ = MagicMock(return_value=False)

        with (
            patch("scheduler.SMTP_USER", "user@test.com"),
            patch("scheduler.SMTP_PASS", "password"),
            patch("scheduler.ALERT_EMAIL", "alert@test.com"),
            patch("scheduler.SMTP_FROM", "from@test.com"),
            patch("scheduler.smtplib.SMTP", return_value=mock_smtp_instance),
            patch("scheduler.asyncio.get_event_loop") as mock_loop,
        ):
            mock_loop_instance = MagicMock()
            mock_loop.return_value = mock_loop_instance
            mock_loop_instance.run_in_executor = AsyncMock(return_value=None)

            result = await send_email_alert("Test Subject", "Test body")
            assert result is True

    @pytest.mark.asyncio
    async def test_skips_when_no_password(self):
        """Should return False when SMTP_PASS is empty."""
        with (
            patch("scheduler.SMTP_USER", "user@test.com"),
            patch("scheduler.SMTP_PASS", ""),
            patch("scheduler.ALERT_EMAIL", "alert@test.com"),
        ):
            result = await send_email_alert("Test", "Body")
            assert result is False


# ===========================================================================
# 11. start_scheduler() and stop_scheduler() tests
# ===========================================================================


class TestStartStopScheduler:
    """Tests for scheduler startup and shutdown."""

    def test_start_scheduler_adds_all_jobs(self):
        """Should add all scheduled jobs and start the scheduler."""
        mock_sched = MagicMock()
        mock_sched.add_job = MagicMock()
        mock_sched.start = MagicMock()

        with patch("scheduler.scheduler", mock_sched):
            start_scheduler()
            mock_sched.start.assert_called_once()
            # Should add at least 5 jobs:
            # midnight_cache_refresh, member_reconciliation, daily_reminders,
            # init_digest_schedule, check_missed_reconciliation, check_missed_digest
            assert mock_sched.add_job.call_count >= 5

    def test_start_scheduler_handles_error(self):
        """Should not propagate errors during startup."""
        mock_sched = MagicMock()
        mock_sched.add_job = MagicMock(side_effect=Exception("Scheduler error"))

        with patch("scheduler.scheduler", mock_sched):
            # Should not raise
            start_scheduler()

    def test_stop_scheduler_when_running(self):
        """Should shut down scheduler when it's running."""
        mock_sched = MagicMock()
        mock_sched.running = True
        mock_sched.shutdown = MagicMock()

        with patch("scheduler.scheduler", mock_sched):
            stop_scheduler()
            mock_sched.shutdown.assert_called_once()

    def test_stop_scheduler_when_not_running(self):
        """Should not call shutdown when scheduler isn't running."""
        mock_sched = MagicMock()
        mock_sched.running = False
        mock_sched.shutdown = MagicMock()

        with patch("scheduler.scheduler", mock_sched):
            stop_scheduler()
            mock_sched.shutdown.assert_not_called()

    def test_stop_scheduler_handles_error(self):
        """Should not propagate errors during shutdown."""
        mock_sched = MagicMock()
        mock_sched.running = True
        mock_sched.shutdown = MagicMock(side_effect=Exception("Shutdown error"))

        with patch("scheduler.scheduler", mock_sched):
            # Should not raise
            stop_scheduler()


# ===========================================================================
# 12. check_missed_digest() additional coverage
# ===========================================================================


class TestCheckMissedDigestAdditional:
    """Additional tests for check_missed_digest not covered in comprehensive tests."""

    @pytest.mark.asyncio
    async def test_waits_before_checking(self):
        """Should sleep 4 seconds before checking."""
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(return_value=None)
        mock_db.notification_logs.count_documents = AsyncMock(return_value=0)

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("scheduler.now_jakarta") as mock_now,
            patch("scheduler.daily_reminder_job", new_callable=AsyncMock),
        ):
            fake_now = datetime(2026, 3, 29, 10, 0, 0, tzinfo=JAKARTA_TZ)
            mock_now.return_value = fake_now

            await check_missed_digest()
            mock_sleep.assert_called_once_with(4)

    @pytest.mark.asyncio
    async def test_invalid_digest_time_format_in_check(self):
        """Should handle invalid time format from DB gracefully."""
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(return_value={"type": "automation", "data": {"digestTime": "not-a-time"}})

        with patch("scheduler.db", mock_db), patch("scheduler.asyncio.sleep", new_callable=AsyncMock):
            # Should catch ValueError and not propagate
            await check_missed_digest()


# ===========================================================================
# 13. Birthday week / upcoming birthdays tests
# ===========================================================================


class TestBirthdayWeekDigest:
    """Test upcoming birthday (next 7 days) logic."""

    @pytest.mark.asyncio
    async def test_birthday_week_count_in_stats(self):
        """Members with birthday in next 7 days should be in birthdays_week stat."""
        today = datetime.now(JAKARTA_TZ).date()
        future = today + timedelta(days=5)
        member = {
            "id": "m1",
            "name": "Week Birthday",
            "phone": "+6281234567890",
            "birth_date": f"1985-{future.month:02d}-{future.day:02d}",
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)
        mock_db.care_events.find_one = AsyncMock(
            return_value={"member_id": "m1", "event_type": "birthday", "completed": False}
        )

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["birthdays_week"] >= 1

    @pytest.mark.asyncio
    async def test_birthday_more_than_7_days_away_not_counted(self):
        """Members with birthday more than 7 days away should not be counted."""
        today = datetime.now(JAKARTA_TZ).date()
        far_future = today + timedelta(days=10)
        member = {
            "id": "m1",
            "name": "Far Birthday",
            "phone": "+6281234567890",
            "birth_date": f"1985-{far_future.month:02d}-{far_future.day:02d}",
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)
        mock_db.care_events.find_one = AsyncMock(
            return_value={"member_id": "m1", "event_type": "birthday", "completed": False}
        )

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["birthdays_today"] == 0
        assert digest["stats"]["birthdays_week"] == 0


# ===========================================================================
# 14. Digest message formatting tests
# ===========================================================================


class TestDigestMessageFormatting:
    """Test the message formatting of the daily digest."""

    @pytest.mark.asyncio
    async def test_digest_contains_date(self):
        """Digest message should contain today's date."""
        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[])

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        today = datetime.now(JAKARTA_TZ).date()
        assert today.strftime("%d") in digest["message"]

    @pytest.mark.asyncio
    async def test_digest_ends_with_blessing(self):
        """Digest message should end with blessing text."""
        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[])

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert "Tuhan memberkati pelayanan Anda" in digest["message"]

    @pytest.mark.asyncio
    async def test_digest_includes_contact_instruction(self):
        """Digest should include instruction to contact members."""
        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[])

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert "Silakan hubungi jemaat" in digest["message"]

    @pytest.mark.asyncio
    async def test_overdue_section_includes_all_overdue_types(self):
        """When multiple overdue types exist, all should appear in overdue section."""
        today = datetime.now(JAKARTA_TZ).date()
        yesterday = (today - timedelta(days=1)).isoformat()
        member = {"id": "m1", "name": "Multi Overdue", "phone": "+6281234567890"}

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)

        # Overdue grief
        grief_call = [0]

        async def grief_list(_):
            grief_call[0] += 1
            if grief_call[0] == 1:
                return []
            return [
                {
                    "campus_id": "c1",
                    "member_id": "m1",
                    "stage": "1_week",
                    "scheduled_date": yesterday,
                    "completed": False,
                }
            ]

        mock_db.grief_support.find.return_value.to_list = grief_list

        # Overdue hospital
        hosp_call = [0]

        async def hosp_list(_):
            hosp_call[0] += 1
            if hosp_call[0] == 1:
                return []
            return [
                {
                    "campus_id": "c1",
                    "member_id": "m1",
                    "stage": "first_followup",
                    "scheduled_date": yesterday,
                    "completed": False,
                    "ignored": False,
                }
            ]

        mock_db.accident_followup.find.return_value.to_list = hosp_list

        # Overdue financial
        fin_call = [0]

        async def fin_list(_):
            fin_call[0] += 1
            if fin_call[0] == 1:
                return []
            return [
                {
                    "campus_id": "c1",
                    "member_id": "m1",
                    "aid_type": "education",
                    "next_occurrence": yesterday,
                    "is_active": True,
                }
            ]

        mock_db.financial_aid_schedules.find.return_value.to_list = fin_list

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert "TUGAS TERLAMBAT" in digest["message"]
        assert "_Rumah Sakit:_" in digest["message"]
        assert "_Dukacita:_" in digest["message"]
        assert "_Bantuan Keuangan:_" in digest["message"]

        total_overdue = (
            digest["stats"]["overdue_grief"]
            + digest["stats"]["overdue_hospital"]
            + digest["stats"]["overdue_financial"]
        )
        assert total_overdue == 3
