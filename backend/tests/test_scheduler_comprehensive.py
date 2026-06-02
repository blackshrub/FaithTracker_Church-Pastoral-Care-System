"""
Comprehensive scheduler tests for FaithTracker Pastoral Care System

Covers:
- Helper functions: now_jakarta(), today_jakarta(), safe_parse_date()
- Job lock system: acquire_job_lock(), release_job_lock(), concurrency
- Digest/reminder functions: check_missed_digest(), timezone correctness
- Birthday reminder logic: month/day matching, duplicate detection
- Engagement status and settings retrieval
- Email alert and WhatsApp send flows

All tests use mocks for the database layer so no running MongoDB is required.
"""

import os
import sys
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scheduler import (
    JAKARTA_TZ,
    acquire_job_lock,
    check_missed_digest,
    generate_daily_digest_for_campus,
    get_digest_time_from_db,
    now_jakarta,
    release_job_lock,
    safe_parse_date,
    send_email_alert,
    send_whatsapp,
    today_jakarta,
)

# ---------------------------------------------------------------------------
# Helpers for building mock DB objects
# ---------------------------------------------------------------------------


def make_mock_db():
    """Create a mock database with all collections used by the scheduler."""
    mock_db = MagicMock()

    # job_locks
    mock_db.job_locks.update_one = AsyncMock()
    mock_db.job_locks.delete_one = AsyncMock()
    mock_db.job_locks.find_one = AsyncMock(return_value=None)

    # members
    mock_db.members.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.members.find_one = AsyncMock(return_value=None)

    # care_events
    mock_db.care_events.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.care_events.find_one = AsyncMock(return_value=None)

    # grief_support
    mock_db.grief_support.find.return_value.to_list = AsyncMock(return_value=[])

    # accident_followup
    mock_db.accident_followup.find.return_value.to_list = AsyncMock(return_value=[])

    # financial_aid_schedules
    mock_db.financial_aid_schedules.find.return_value.to_list = AsyncMock(return_value=[])

    # pastoral_notes
    mock_db.pastoral_notes.find.return_value.to_list = AsyncMock(return_value=[])

    # notification_logs
    mock_db.notification_logs.insert_one = AsyncMock()
    mock_db.notification_logs.count_documents = AsyncMock(return_value=0)

    # settings
    mock_db.settings.find_one = AsyncMock(return_value=None)

    # campuses
    mock_db.campuses.find.return_value.to_list = AsyncMock(return_value=[])

    # users
    mock_db.users.find.return_value.to_list = AsyncMock(return_value=[])

    return mock_db


def make_update_result(matched=0, upserted_id=None):
    """Create a mock UpdateResult from MongoDB."""
    result = MagicMock()
    result.matched_count = matched
    result.upserted_id = upserted_id
    return result


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestNowJakarta:
    """Tests for now_jakarta() helper function"""

    @pytest.mark.unit
    def test_returns_datetime_with_jakarta_timezone(self):
        """now_jakarta() must return a datetime with Asia/Jakarta tzinfo"""
        result = now_jakarta()
        assert isinstance(result, datetime)
        assert result.tzinfo is not None
        assert str(result.tzinfo) == "Asia/Jakarta"

    @pytest.mark.unit
    def test_is_timezone_aware(self):
        """The returned datetime must be timezone-aware, never naive"""
        result = now_jakarta()
        assert result.tzinfo is not None
        assert result.utcoffset() is not None

    @pytest.mark.unit
    def test_utc_offset_is_plus_seven(self):
        """Jakarta timezone is UTC+7"""
        result = now_jakarta()
        offset = result.utcoffset()
        assert offset == timedelta(hours=7)

    @pytest.mark.unit
    def test_close_to_current_time(self):
        """The result should be very close to the actual current time"""
        before = datetime.now(JAKARTA_TZ)
        result = now_jakarta()
        after = datetime.now(JAKARTA_TZ)
        assert before <= result <= after


class TestTodayJakarta:
    """Tests for today_jakarta() helper function"""

    @pytest.mark.unit
    def test_returns_date_object(self):
        """today_jakarta() must return a date, not datetime"""
        result = today_jakarta()
        assert isinstance(result, date)
        assert not isinstance(result, datetime)

    @pytest.mark.unit
    def test_matches_jakarta_date(self):
        """The returned date matches the current Jakarta date"""
        expected = datetime.now(JAKARTA_TZ).date()
        result = today_jakarta()
        assert result == expected

    @pytest.mark.unit
    def test_may_differ_from_utc_date(self):
        """
        Jakarta is UTC+7, so between 00:00 and 06:59 UTC
        the Jakarta date is already the next day.
        This test documents the behavior rather than asserting a
        specific mismatch since the test could run at any time.
        """
        utc_date = datetime.now(UTC).date()
        jakarta_date = today_jakarta()
        diff = abs((jakarta_date - utc_date).days)
        assert diff <= 1


class TestSafeParseDate:
    """Tests for safe_parse_date() - robust date string parsing"""

    @pytest.mark.unit
    def test_valid_iso_date(self):
        result = safe_parse_date("2024-03-15")
        assert result == date(2024, 3, 15)

    @pytest.mark.unit
    def test_valid_iso_datetime(self):
        result = safe_parse_date("2024-03-15T10:30:00")
        assert result == date(2024, 3, 15)

    @pytest.mark.unit
    def test_valid_iso_datetime_with_timezone(self):
        result = safe_parse_date("2024-03-15T10:30:00+07:00")
        assert result == date(2024, 3, 15)

    @pytest.mark.unit
    def test_empty_string(self):
        assert safe_parse_date("") is None

    @pytest.mark.unit
    def test_none_input(self):
        assert safe_parse_date(None) is None

    @pytest.mark.unit
    def test_short_string(self):
        assert safe_parse_date("2024-03") is None

    @pytest.mark.unit
    def test_very_short_string(self):
        assert safe_parse_date("abc") is None

    @pytest.mark.unit
    def test_invalid_date_values(self):
        assert safe_parse_date("2024-13-01") is None

    @pytest.mark.unit
    def test_invalid_date_feb_30(self):
        assert safe_parse_date("2024-02-30") is None

    @pytest.mark.unit
    def test_non_date_string(self):
        assert safe_parse_date("not-a-date") is None

    @pytest.mark.unit
    def test_non_string_input_integer(self):
        assert safe_parse_date(20240315) is None

    @pytest.mark.unit
    def test_non_string_input_list(self):
        assert safe_parse_date(["2024-03-15"]) is None

    @pytest.mark.unit
    def test_whitespace_only(self):
        assert safe_parse_date("   ") is None

    @pytest.mark.unit
    def test_leap_year_date(self):
        assert safe_parse_date("2024-02-29") == date(2024, 2, 29)

    @pytest.mark.unit
    def test_non_leap_year_feb_29(self):
        assert safe_parse_date("2023-02-29") is None

    @pytest.mark.unit
    def test_date_with_trailing_content(self):
        result = safe_parse_date("2024-03-15 some extra stuff")
        assert result == date(2024, 3, 15)

    @pytest.mark.unit
    def test_boundary_date_min(self):
        assert safe_parse_date("0001-01-01") == date(1, 1, 1)

    @pytest.mark.unit
    def test_far_future_date(self):
        assert safe_parse_date("9999-12-31") == date(9999, 12, 31)


# ---------------------------------------------------------------------------
# Job Lock System tests (using mocks)
# ---------------------------------------------------------------------------


class TestAcquireJobLock:
    """Tests for acquire_job_lock() distributed locking.

    Production acquires a Redis ``SET NX`` lock first and falls back to a
    token-based Mongo ``find_one_and_update`` when Redis is unavailable. These
    unit tests pin ``get_redis_client()`` to ``None`` so they deterministically
    exercise the Mongo fallback without needing a live Redis, and they mock
    ``find_one_and_update`` (the call the current implementation actually makes).
    """

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_successful_acquisition_via_upsert(self):
        """A fresh lock (upsert) echoes back our token -> acquired."""
        mock_db = make_mock_db()

        async def fake_fnu(query, update, **kwargs):
            # Mongo with return_document=AFTER returns the doc we just wrote,
            # including the random token acquire_job_lock() generated.
            return update["$set"]

        mock_db.job_locks.find_one_and_update = fake_fnu

        with patch("scheduler.db", mock_db), patch("scheduler.get_redis_client", return_value=None):
            assert await acquire_job_lock("test_job", ttl_seconds=60) is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_successful_acquisition_via_match(self):
        """Re-acquiring an expired lock (matched) also returns our token."""
        mock_db = make_mock_db()
        mock_db.job_locks.find_one_and_update = AsyncMock(side_effect=lambda query, update, **kw: update["$set"])

        with patch("scheduler.db", mock_db), patch("scheduler.get_redis_client", return_value=None):
            assert await acquire_job_lock("test_job", ttl_seconds=60) is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_already_locked_duplicate_key(self):
        """A live lock makes the upsert raise E11000 -> returns False."""
        mock_db = make_mock_db()
        mock_db.job_locks.find_one_and_update = AsyncMock(side_effect=Exception("E11000 duplicate key error"))

        with patch("scheduler.db", mock_db), patch("scheduler.get_redis_client", return_value=None):
            assert await acquire_job_lock("test_job", ttl_seconds=60) is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_already_locked_no_match_no_upsert(self):
        """Another worker's token in the returned doc -> returns False."""
        mock_db = make_mock_db()
        mock_db.job_locks.find_one_and_update = AsyncMock(return_value={"token": "another-worker-token"})

        with patch("scheduler.db", mock_db), patch("scheduler.get_redis_client", return_value=None):
            assert await acquire_job_lock("test_job", ttl_seconds=60) is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_unexpected_error_returns_false(self):
        """Non-duplicate-key errors should return False and log error."""
        mock_db = make_mock_db()
        mock_db.job_locks.find_one_and_update = AsyncMock(side_effect=Exception("Connection reset by peer"))

        with patch("scheduler.db", mock_db), patch("scheduler.get_redis_client", return_value=None):
            assert await acquire_job_lock("test_job", ttl_seconds=60) is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_lock_id_contains_job_name_and_date(self):
        """Lock ID should be formatted as job_lock_{name}_{date}."""
        mock_db = make_mock_db()
        mock_db.job_locks.find_one_and_update = AsyncMock(side_effect=lambda query, update, **kw: update["$set"])

        with patch("scheduler.db", mock_db), patch("scheduler.get_redis_client", return_value=None):
            await acquire_job_lock("my_job", ttl_seconds=60)

        # First positional arg to find_one_and_update is the filter.
        query = mock_db.job_locks.find_one_and_update.call_args[0][0]
        expected = f"job_lock_my_job_{today_jakarta().isoformat()}"
        assert query["lock_id"] == expected

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_ttl_sets_correct_expiry(self):
        """The expires_at field should be approximately now + ttl_seconds."""
        mock_db = make_mock_db()
        mock_db.job_locks.find_one_and_update = AsyncMock(side_effect=lambda query, update, **kw: update["$set"])

        with patch("scheduler.db", mock_db), patch("scheduler.get_redis_client", return_value=None):
            await acquire_job_lock("ttl_test", ttl_seconds=300)

        # Second positional arg is the update document.
        update_doc = mock_db.job_locks.find_one_and_update.call_args[0][1]
        expires_at = update_doc["$set"]["expires_at"]
        diff = abs((expires_at - datetime.now(UTC)).total_seconds())
        assert diff < 305


class TestReleaseJobLock:
    """Tests for release_job_lock() (Mongo fallback path)."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_release_calls_delete(self):
        """Releasing a held lock should delete it by lock_id + token."""
        mock_db = make_mock_db()
        mock_db.job_locks.find_one_and_update = AsyncMock(side_effect=lambda query, update, **kw: update["$set"])
        mock_db.job_locks.delete_one = AsyncMock()

        with patch("scheduler.db", mock_db), patch("scheduler.get_redis_client", return_value=None):
            # Must acquire first so we own the token release checks for.
            assert await acquire_job_lock("test_job", ttl_seconds=60) is True
            await release_job_lock("test_job")

        mock_db.job_locks.delete_one.assert_called_once()
        call_args = mock_db.job_locks.delete_one.call_args[0][0]
        expected_id = f"job_lock_test_job_{today_jakarta().isoformat()}"
        assert call_args["lock_id"] == expected_id

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_release_nonexistent_does_not_raise(self):
        """Releasing a lock we never acquired is a no-op, not an error."""
        mock_db = make_mock_db()
        mock_db.job_locks.delete_one = AsyncMock()

        with patch("scheduler.db", mock_db), patch("scheduler.get_redis_client", return_value=None):
            await release_job_lock("never_acquired_job")

        # We never held the token, so nothing should be deleted.
        mock_db.job_locks.delete_one.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_release_handles_db_error(self):
        """Release should not propagate DB errors."""
        mock_db = make_mock_db()
        mock_db.job_locks.find_one_and_update = AsyncMock(side_effect=lambda query, update, **kw: update["$set"])
        mock_db.job_locks.delete_one = AsyncMock(side_effect=Exception("DB down"))

        with patch("scheduler.db", mock_db), patch("scheduler.get_redis_client", return_value=None):
            assert await acquire_job_lock("error_job", ttl_seconds=60) is True
            # Should not raise even though delete_one fails.
            await release_job_lock("error_job")


class TestConcurrentLockAcquisition:
    """Tests for concurrent lock behavior in multi-worker scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_first_caller_wins_rest_get_duplicate_key(self):
        """First acquire wins via upsert; the rest hit E11000 duplicate key."""
        call_count = 0

        async def simulated_fnu(query, update, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return update["$set"]
            raise Exception("E11000 duplicate key error collection")

        mock_db = make_mock_db()
        mock_db.job_locks.find_one_and_update = simulated_fnu

        with patch("scheduler.db", mock_db), patch("scheduler.get_redis_client", return_value=None):
            results = [await acquire_job_lock("concurrent_test", ttl_seconds=60) for _ in range(4)]

        assert sum(1 for r in results if r is True) == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_sequential_acquire_release_cycle(self):
        """Multiple sequential acquire-release cycles should all succeed."""
        mock_db = make_mock_db()
        mock_db.job_locks.find_one_and_update = AsyncMock(side_effect=lambda query, update, **kw: update["$set"])
        mock_db.job_locks.delete_one = AsyncMock()

        with patch("scheduler.db", mock_db), patch("scheduler.get_redis_client", return_value=None):
            for _ in range(5):
                assert await acquire_job_lock("cycle_test", ttl_seconds=60) is True
                await release_job_lock("cycle_test")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_lock_cleanup_after_exception(self):
        """Lock should be released even if the job raises an exception."""
        mock_db = make_mock_db()
        mock_db.job_locks.find_one_and_update = AsyncMock(side_effect=lambda query, update, **kw: update["$set"])
        mock_db.job_locks.delete_one = AsyncMock()

        with patch("scheduler.db", mock_db), patch("scheduler.get_redis_client", return_value=None):
            assert await acquire_job_lock("exc_test", ttl_seconds=60) is True

            try:
                raise RuntimeError("Simulated job failure")
            except RuntimeError:
                pass
            finally:
                await release_job_lock("exc_test")

        mock_db.job_locks.delete_one.assert_called_once()


# ---------------------------------------------------------------------------
# check_missed_digest() and timezone correctness tests
# ---------------------------------------------------------------------------


class TestCheckMissedDigest:
    """Tests for check_missed_digest() - the critical timezone fix"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_today_start_uses_jakarta_timezone(self):
        """
        Critical test: today_start in check_missed_digest must use JAKARTA_TZ.

        The bug fix changed:
            today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        To:
            today_start = datetime(now.year, now.month, now.day, tzinfo=JAKARTA_TZ)

        Using UTC would miss digests sent between 00:00-06:59 Jakarta time.
        """
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(return_value={"type": "automation", "data": {"digestTime": "08:00"}})

        captured_queries = []

        async def capture_count_documents(query):
            captured_queries.append(query)
            return 1  # Pretend digest was already sent

        mock_db.notification_logs.count_documents = capture_count_documents

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.now_jakarta") as mock_now,
        ):
            fake_now = datetime(2026, 3, 29, 10, 0, 0, tzinfo=JAKARTA_TZ)
            mock_now.return_value = fake_now

            await check_missed_digest()

        assert len(captured_queries) == 1
        today_start = captured_queries[0]["created_at"]["$gte"]

        # The critical assertion: today_start must use JAKARTA_TZ, not UTC
        assert today_start.tzinfo is not None
        assert today_start.utcoffset() == timedelta(hours=7)
        assert today_start == datetime(2026, 3, 29, 0, 0, 0, tzinfo=JAKARTA_TZ)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_skips_when_before_scheduled_time(self):
        """If current time is before the scheduled digest time, should skip"""
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(return_value={"type": "automation", "data": {"digestTime": "08:00"}})

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.now_jakarta") as mock_now,
        ):
            fake_now = datetime(2026, 3, 29, 7, 0, 0, tzinfo=JAKARTA_TZ)
            mock_now.return_value = fake_now

            mock_db.notification_logs.count_documents = AsyncMock()
            await check_missed_digest()
            mock_db.notification_logs.count_documents.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_runs_digest_when_missed(self):
        """If digest was missed (past time, no logs), should trigger daily_reminder_job"""
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(return_value={"type": "automation", "data": {"digestTime": "08:00"}})
        mock_db.notification_logs.count_documents = AsyncMock(return_value=0)

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.now_jakarta") as mock_now,
            patch("scheduler.daily_reminder_job", new_callable=AsyncMock) as mock_digest,
        ):
            fake_now = datetime(2026, 3, 29, 14, 0, 0, tzinfo=JAKARTA_TZ)
            mock_now.return_value = fake_now

            await check_missed_digest()
            mock_digest.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_skips_when_digest_already_sent(self):
        """If digest was already sent today, should not re-run"""
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(return_value={"type": "automation", "data": {"digestTime": "08:00"}})
        mock_db.notification_logs.count_documents = AsyncMock(return_value=5)

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.now_jakarta") as mock_now,
            patch("scheduler.daily_reminder_job", new_callable=AsyncMock) as mock_digest,
        ):
            fake_now = datetime(2026, 3, 29, 14, 0, 0, tzinfo=JAKARTA_TZ)
            mock_now.return_value = fake_now

            await check_missed_digest()
            mock_digest.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_handles_exception_gracefully(self):
        """check_missed_digest should not propagate exceptions"""
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(side_effect=Exception("DB connection lost"))

        with patch("scheduler.db", mock_db), patch("scheduler.asyncio.sleep", new_callable=AsyncMock):
            await check_missed_digest()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_default_digest_time_when_not_configured(self):
        """When no digest time is in DB, should default to 08:00"""
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(return_value=None)
        mock_db.notification_logs.count_documents = AsyncMock(return_value=0)

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.now_jakarta") as mock_now,
            patch("scheduler.daily_reminder_job", new_callable=AsyncMock) as mock_digest,
        ):
            fake_now = datetime(2026, 3, 29, 10, 0, 0, tzinfo=JAKARTA_TZ)
            mock_now.return_value = fake_now

            await check_missed_digest()
            mock_digest.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_hours_since_scheduled_calculated_correctly(self):
        """Verify the hours_since_scheduled calculation uses Jakarta time"""
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(return_value={"type": "automation", "data": {"digestTime": "08:00"}})
        mock_db.notification_logs.count_documents = AsyncMock(return_value=0)

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.now_jakarta") as mock_now,
            patch("scheduler.daily_reminder_job", new_callable=AsyncMock),
            patch("scheduler.logger") as mock_logger,
        ):
            # 11:30 Jakarta, 3.5 hours past 08:00
            fake_now = datetime(2026, 3, 29, 11, 30, 0, tzinfo=JAKARTA_TZ)
            mock_now.return_value = fake_now

            await check_missed_digest()

            # Check the warning log message includes "3.5h late"
            warning_calls = list(mock_logger.warning.call_args_list)
            assert len(warning_calls) >= 1
            msg = warning_calls[0][0][0]
            assert "3.5" in msg


# ---------------------------------------------------------------------------
# get_digest_time_from_db() tests
# ---------------------------------------------------------------------------


class TestGetDigestTimeFromDb:
    """Tests for get_digest_time_from_db() settings retrieval"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_returns_configured_time(self):
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(return_value={"type": "automation", "data": {"digestTime": "06:30"}})

        with patch("scheduler.db", mock_db):
            result = await get_digest_time_from_db()
            assert result == "06:30"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_returns_default_when_no_settings(self):
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(return_value=None)

        with patch("scheduler.db", mock_db):
            result = await get_digest_time_from_db()
            assert result == "08:00"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_returns_default_when_no_digest_time_key(self):
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(return_value={"type": "automation", "data": {}})

        with patch("scheduler.db", mock_db):
            result = await get_digest_time_from_db()
            assert result == "08:00"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_returns_default_on_exception(self):
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(side_effect=Exception("DB error"))

        with patch("scheduler.db", mock_db):
            result = await get_digest_time_from_db()
            assert result == "08:00"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_returns_default_when_data_is_none(self):
        """Settings doc exists but data is None"""
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(return_value={"type": "automation", "data": None})

        with patch("scheduler.db", mock_db):
            result = await get_digest_time_from_db()
            assert result == "08:00"


# ---------------------------------------------------------------------------
# generate_daily_digest_for_campus() tests (mocked DB)
# ---------------------------------------------------------------------------


class TestGenerateDailyDigestForCampus:
    """Tests for the daily digest generation logic"""

    def _setup_mock_db_for_digest(
        self,
        members=None,
        care_events=None,
        grief_support=None,
        accident_followup=None,
        financial_aid=None,
        pastoral_notes=None,
    ):
        """Helper to set up mock DB with specified data."""
        mock_db = make_mock_db()

        if members is not None:
            mock_db.members.find.return_value.to_list = AsyncMock(return_value=members)

        # care_events.find_one is called per member for birthday checking
        if care_events is not None:
            # Return matching events based on member_id
            async def find_one_care(query, *args, **kwargs):
                for evt in care_events:
                    if (
                        evt.get("member_id") == query.get("member_id")
                        and evt.get("event_type") == query.get("event_type")
                        and not evt.get("completed", False)
                    ):
                        if query.get("ignored", {}).get("$ne") and evt.get("ignored"):
                            continue
                        return evt
                return None

            mock_db.care_events.find_one = find_one_care

        if grief_support is not None:
            # Need multiple calls: first for today, second for overdue
            call_count = [0]
            today = datetime.now(JAKARTA_TZ).date()
            today_items = [g for g in grief_support if g.get("scheduled_date") == today.isoformat()]
            overdue_items = [g for g in grief_support if g.get("scheduled_date") < today.isoformat()]

            async def grief_to_list(_):
                call_count[0] += 1
                if call_count[0] == 1:
                    return today_items
                return overdue_items

            mock_db.grief_support.find.return_value.to_list = grief_to_list

        if accident_followup is not None:
            today = datetime.now(JAKARTA_TZ).date()
            today_items = [a for a in accident_followup if a.get("scheduled_date") == today.isoformat()]
            overdue_items = [a for a in accident_followup if a.get("scheduled_date") < today.isoformat()]

            call_count_acc = [0]

            async def acc_to_list(_):
                call_count_acc[0] += 1
                if call_count_acc[0] == 1:
                    return today_items
                return overdue_items

            mock_db.accident_followup.find.return_value.to_list = acc_to_list

        if financial_aid is not None:
            today = datetime.now(JAKARTA_TZ).date()
            today_items = [f for f in financial_aid if f.get("next_occurrence") == today.isoformat()]
            overdue_items = [f for f in financial_aid if f.get("next_occurrence") < today.isoformat()]

            call_count_fin = [0]

            async def fin_to_list(_):
                call_count_fin[0] += 1
                if call_count_fin[0] == 1:
                    return today_items
                return overdue_items

            mock_db.financial_aid_schedules.find.return_value.to_list = fin_to_list

        if pastoral_notes is not None:
            mock_db.pastoral_notes.find.return_value.to_list = AsyncMock(return_value=pastoral_notes)

        # Default member lookup for grief/hospital/financial that does find_one
        member_map = {}
        if members:
            for m in members:
                member_map[m["id"]] = m

        async def member_find_one(query, *args, **kwargs):
            mid = query.get("id")
            if mid and mid in member_map:
                return member_map[mid]
            return None

        mock_db.members.find_one = member_find_one

        return mock_db

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_basic_structure(self):
        """Digest should contain required keys and stats structure"""
        mock_db = self._setup_mock_db_for_digest()
        os.environ["CHURCH_NAME"] = "Test Church"

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("campus1", "Test Campus")

        assert digest is not None
        assert digest["campus_id"] == "campus1"
        assert digest["campus_name"] == "Test Campus"
        assert "message" in digest
        assert "stats" in digest

        expected_keys = [
            "birthdays_today",
            "birthdays_week",
            "grief_due",
            "hospital_followups",
            "financial_aid",
            "overdue_grief",
            "overdue_hospital",
            "overdue_financial",
            "at_risk",
            "notes_due_today",
            "overdue_notes",
        ]
        for key in expected_keys:
            assert key in digest["stats"], f"Missing stats key: {key}"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_empty_campus_shows_no_urgent_tasks(self):
        """A campus with no data should show 'no tasks' message"""
        mock_db = self._setup_mock_db_for_digest()
        os.environ["CHURCH_NAME"] = "Test Church"

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("empty", "Empty Campus")

        assert "Tidak ada tugas mendesak hari ini!" in digest["message"]
        assert all(v == 0 for v in digest["stats"].values())

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_message_contains_church_name(self):
        mock_db = self._setup_mock_db_for_digest()
        os.environ["CHURCH_NAME"] = "GKBJ Test"

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus 1")

        assert "GKBJ Test" in digest["message"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_message_contains_campus_name(self):
        mock_db = self._setup_mock_db_for_digest()
        os.environ["CHURCH_NAME"] = "Test"

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "My Campus")

        assert "My Campus" in digest["message"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_grief_due_today(self):
        """Grief stages due today should appear in stats"""
        today = datetime.now(JAKARTA_TZ).date()
        member = {"id": "m1", "name": "Grief Person", "phone": "+6281111111111"}
        grief = [
            {
                "campus_id": "c1",
                "member_id": "m1",
                "stage": "1_week",
                "scheduled_date": today.isoformat(),
                "completed": False,
            }
        ]

        mock_db = self._setup_mock_db_for_digest(members=[member], grief_support=grief)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["grief_due"] == 1
        assert "Grief Person" in digest["message"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_overdue_grief(self):
        """Grief stages from past dates should count as overdue"""
        yesterday = (datetime.now(JAKARTA_TZ).date() - timedelta(days=1)).isoformat()
        member = {"id": "m1", "name": "Overdue Grief", "phone": "+6281222222222"}
        grief = [
            {
                "campus_id": "c1",
                "member_id": "m1",
                "stage": "2_weeks",
                "scheduled_date": yesterday,
                "completed": False,
            }
        ]

        mock_db = self._setup_mock_db_for_digest(members=[member], grief_support=grief)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["overdue_grief"] == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_hospital_followup_due_today(self):
        today = datetime.now(JAKARTA_TZ).date()
        member = {"id": "m1", "name": "Hospital Person", "phone": "+6281333333333"}
        followups = [
            {
                "campus_id": "c1",
                "member_id": "m1",
                "stage": "first_followup",
                "scheduled_date": today.isoformat(),
                "completed": False,
                "ignored": False,
            }
        ]

        mock_db = self._setup_mock_db_for_digest(members=[member], accident_followup=followups)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["hospital_followups"] == 1
        assert "Hospital Person" in digest["message"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_financial_aid_due_today(self):
        today = datetime.now(JAKARTA_TZ).date()
        member = {"id": "m1", "name": "Aid Person", "phone": "+6281444444444"}
        aid = [
            {
                "campus_id": "c1",
                "member_id": "m1",
                "aid_type": "education",
                "next_occurrence": today.isoformat(),
                "is_active": True,
            }
        ]

        mock_db = self._setup_mock_db_for_digest(members=[member], financial_aid=aid)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["financial_aid"] == 1
        assert "Aid Person" in digest["message"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_at_risk_members_counted(self):
        """Members with no contact for 30+ days should be counted as at_risk"""
        old_date = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        member = {
            "id": "m1",
            "name": "At Risk Person",
            "phone": "+6281555555555",
            "last_contact_date": old_date,
        }

        mock_db = self._setup_mock_db_for_digest(members=[member])

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["at_risk"] >= 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_returns_none_on_exception(self):
        """If an error occurs during generation, should return None"""
        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(side_effect=Exception("Connection reset"))

        with patch("scheduler.db", mock_db):
            result = await generate_daily_digest_for_campus("bad", "Bad Campus")
            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_skips_completed_birthday_events(self):
        """Completed birthday events should not be counted"""
        today = datetime.now(JAKARTA_TZ).date()
        member = {
            "id": "m1",
            "name": "Completed Birthday",
            "phone": "+6281666666666",
            "birth_date": f"1990-{today.month:02d}-{today.day:02d}",
        }
        care_evt = {
            "member_id": "m1",
            "event_type": "birthday",
            "completed": True,  # Already completed
        }

        mock_db = self._setup_mock_db_for_digest(members=[member], care_events=[care_evt])

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["birthdays_today"] == 0


# ---------------------------------------------------------------------------
# Birthday reminder logic tests
# ---------------------------------------------------------------------------


class TestBirthdayLogic:
    """Tests for birthday detection within digest generation"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_birthday_today_detected(self):
        """A member whose birthday matches today should be counted"""
        today = datetime.now(JAKARTA_TZ).date()
        member = {
            "id": "bday-m1",
            "name": "Birthday Person",
            "phone": "+6281999999999",
            "birth_date": f"1990-{today.month:02d}-{today.day:02d}",
        }
        care_evt = {
            "member_id": "bday-m1",
            "event_type": "birthday",
            "completed": False,
            "ignored": False,
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.care_events.find_one = AsyncMock(return_value=care_evt)
        # For at-risk calculation, return same member list
        mock_db.members.find_one = AsyncMock(return_value=member)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["birthdays_today"] >= 1
        assert "Birthday Person" in digest["message"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_birthday_upcoming_within_week(self):
        """A member with birthday in the next 7 days should be in birthdays_week"""
        today = datetime.now(JAKARTA_TZ).date()
        future_day = today + timedelta(days=3)
        member = {
            "id": "upcoming-m1",
            "name": "Upcoming Birthday",
            "phone": "+6281888888888",
            "birth_date": f"1985-{future_day.month:02d}-{future_day.day:02d}",
        }
        care_evt = {
            "member_id": "upcoming-m1",
            "event_type": "birthday",
            "completed": False,
            "ignored": False,
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.care_events.find_one = AsyncMock(return_value=care_evt)
        mock_db.members.find_one = AsyncMock(return_value=member)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["birthdays_week"] >= 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_birthday_no_phone_skipped(self):
        """Members without a phone number should be skipped"""
        today = datetime.now(JAKARTA_TZ).date()
        member = {
            "id": "nophone-m1",
            "name": "No Phone Person",
            "birth_date": f"1990-{today.month:02d}-{today.day:02d}",
            # No phone field
        }
        care_evt = {
            "member_id": "nophone-m1",
            "event_type": "birthday",
            "completed": False,
            "ignored": False,
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.care_events.find_one = AsyncMock(return_value=care_evt)
        mock_db.members.find_one = AsyncMock(return_value=member)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert "No Phone Person" not in digest["message"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_birthday_ignored_event_skipped(self):
        """Birthday events that are ignored should not count in birthday stats"""
        today = datetime.now(JAKARTA_TZ).date()
        member = {
            "id": "ignored-m1",
            "name": "Ignored Birthday",
            "phone": "+6281777777777",
            "birth_date": f"1990-{today.month:02d}-{today.day:02d}",
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        # Return None for care event (ignored events excluded by query)
        mock_db.care_events.find_one = AsyncMock(return_value=None)
        mock_db.members.find_one = AsyncMock(return_value=member)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        # Should not appear in birthday section (stats should be 0)
        assert digest["stats"]["birthdays_today"] == 0
        # Note: the member may still appear in at-risk section if no contact date

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_birthday_invalid_date_skipped(self):
        """Members with invalid birth_date format should be silently skipped from birthdays"""
        member = {
            "id": "invalid-m1",
            "name": "Invalid Date Person",
            "phone": "+6281666666666",
            "birth_date": "not-a-real-date",
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.care_events.find_one = AsyncMock(return_value=None)
        mock_db.members.find_one = AsyncMock(return_value=member)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest is not None
        # Should not appear in birthday stats
        assert digest["stats"]["birthdays_today"] == 0
        assert digest["stats"]["birthdays_week"] == 0
        # Note: the member may still appear in at-risk section if no contact date

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_leap_year_birthday_feb_29(self):
        """Members born on Feb 29 should be handled without errors"""
        member = {
            "id": "leap-m1",
            "name": "Leap Year Person",
            "phone": "+6281555555555",
            "birth_date": "2000-02-29",
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.care_events.find_one = AsyncMock(return_value=None)
        mock_db.members.find_one = AsyncMock(return_value=member)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest is not None


# ---------------------------------------------------------------------------
# Pastoral notes in digest tests
# ---------------------------------------------------------------------------


class TestPastoralNotesInDigest:
    """Tests for pastoral notes follow-up detection in digests"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_notes_due_today_counted(self):
        """Pastoral notes with follow_up_date of today should be counted"""
        today = datetime.now(JAKARTA_TZ).date()
        member = {"id": "m1", "name": "Note Person", "phone": "+6281111111111"}
        note = {
            "campus_id": "c1",
            "member_id": "m1",
            "title": "Check on family situation",
            "category": "family",
            "follow_up_date": today.isoformat(),
            "follow_up_completed": False,
            "is_private": False,
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)
        mock_db.pastoral_notes.find.return_value.to_list = AsyncMock(return_value=[note])

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["notes_due_today"] >= 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_private_notes_excluded_from_query(self):
        """
        Private pastoral notes should be excluded by the query
        (is_private: {$ne: True}). Here we verify private notes
        are not passed to the digest because the query filters them out.
        """
        datetime.now(JAKARTA_TZ).date()
        # Simulate that the DB query already filtered out private notes
        # (the actual filter is in the MongoDB query)
        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[])
        mock_db.pastoral_notes.find.return_value.to_list = AsyncMock(return_value=[])

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["notes_due_today"] == 0


# ---------------------------------------------------------------------------
# send_email_alert() tests
# ---------------------------------------------------------------------------


class TestSendEmailAlert:
    """Tests for the email alert sending function"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_skips_when_not_configured(self):
        """Should return False when SMTP credentials are not set"""
        with patch("scheduler.SMTP_USER", ""), patch("scheduler.SMTP_PASS", ""), patch("scheduler.ALERT_EMAIL", ""):
            result = await send_email_alert("Test Subject", "Test body")
            assert result is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_returns_false_on_smtp_error(self):
        """Should return False if SMTP connection fails"""
        with (
            patch("scheduler.SMTP_USER", "user@test.com"),
            patch("scheduler.SMTP_PASS", "password"),
            patch("scheduler.ALERT_EMAIL", "alert@test.com"),
            patch("scheduler.smtplib.SMTP", side_effect=Exception("SMTP refused")),
        ):
            result = await send_email_alert("Test Subject", "Test body")
            assert result is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_skips_when_no_alert_email(self):
        """Should return False when ALERT_EMAIL is empty"""
        with (
            patch("scheduler.SMTP_USER", "user@test.com"),
            patch("scheduler.SMTP_PASS", "password"),
            patch("scheduler.ALERT_EMAIL", ""),
        ):
            result = await send_email_alert("Subject", "Body")
            assert result is False


# ---------------------------------------------------------------------------
# send_whatsapp() tests
# ---------------------------------------------------------------------------


class TestSendWhatsapp:
    """Tests for WhatsApp message sending with retry mechanism"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_returns_error_when_gateway_not_configured(self):
        """Should return error when no gateway URL is available"""
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(return_value=None)

        with patch("scheduler.db", mock_db), patch("scheduler.os.environ.get", return_value=None):
            result = await send_whatsapp("+6281234567890", "Hello", {})
            assert result["success"] is False
            assert "not configured" in result["error"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_successful_send(self):
        """Should return success when gateway returns SUCCESS"""
        mock_db = make_mock_db()

        mock_response = MagicMock()
        mock_response.json.return_value = {"code": "SUCCESS"}

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.os.environ.get", return_value="http://wa-gateway:3000"),
            patch("scheduler.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await send_whatsapp("+6281234567890", "Test", {"id": "t1"})
            assert result["success"] is True
            assert result["attempts"] == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_appends_whatsapp_suffix(self):
        """Phone number should get @s.whatsapp.net appended"""
        mock_db = make_mock_db()

        mock_response = MagicMock()
        mock_response.json.return_value = {"code": "SUCCESS"}

        captured_payloads = []

        async def capture_post(url, json=None):
            captured_payloads.append(json)
            return mock_response

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.os.environ.get", return_value="http://wa-gateway:3000"),
            patch("scheduler.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.post = capture_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await send_whatsapp("6281234567890", "Test", {"id": "t1"})

            assert len(captured_payloads) == 1
            assert captured_payloads[0]["phone"] == "6281234567890@s.whatsapp.net"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_does_not_retry_on_invalid_phone(self):
        """Non-retryable errors (INVALID_PHONE) should not be retried"""
        mock_db = make_mock_db()

        mock_response = MagicMock()
        mock_response.json.return_value = {"code": "INVALID_PHONE"}

        call_count = 0

        async def counting_post(url, json=None):
            nonlocal call_count
            call_count += 1
            return mock_response

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.os.environ.get", return_value="http://wa-gateway:3000"),
            patch("scheduler.httpx.AsyncClient") as mock_client_cls,
            patch("scheduler.send_email_alert", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.post = counting_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await send_whatsapp("invalid", "Test", {"id": "t1"})

            assert result["success"] is False
            assert call_count == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_does_not_retry_on_not_registered(self):
        """NOT_REGISTERED errors should not be retried"""
        mock_db = make_mock_db()

        mock_response = MagicMock()
        mock_response.json.return_value = {"code": "NOT_REGISTERED"}

        call_count = 0

        async def counting_post(url, json=None):
            nonlocal call_count
            call_count += 1
            return mock_response

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.os.environ.get", return_value="http://wa-gateway:3000"),
            patch("scheduler.httpx.AsyncClient") as mock_client_cls,
            patch("scheduler.send_email_alert", new_callable=AsyncMock),
        ):
            mock_client = AsyncMock()
            mock_client.post = counting_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await send_whatsapp("+62800000000", "Test", {"id": "t1"})

            assert result["success"] is False
            assert call_count == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_falls_back_to_db_settings_for_gateway(self):
        """When env var is not set, should fall back to database settings"""
        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(
            return_value={"type": "automation", "data": {"whatsappGateway": "http://db-gateway:3000"}}
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"code": "SUCCESS"}

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.os.environ.get", return_value=None),
            patch("scheduler.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await send_whatsapp("+6281234567890", "Test", {"id": "t1"})
            assert result["success"] is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_preserves_existing_whatsapp_suffix(self):
        """Phone already ending with @s.whatsapp.net should not get doubled"""
        mock_db = make_mock_db()

        mock_response = MagicMock()
        mock_response.json.return_value = {"code": "SUCCESS"}

        captured_payloads = []

        async def capture_post(url, json=None):
            captured_payloads.append(json)
            return mock_response

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.os.environ.get", return_value="http://wa:3000"),
            patch("scheduler.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.post = capture_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await send_whatsapp("628123@s.whatsapp.net", "Test", {"id": "t1"})

            assert captured_payloads[0]["phone"] == "628123@s.whatsapp.net"


# ---------------------------------------------------------------------------
# Multi-campus isolation tests in digest
# ---------------------------------------------------------------------------


class TestMultiCampusDigestIsolation:
    """Verify digest generation is isolated per campus"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_campus_a_data_not_in_campus_b_digest(self):
        """Data in campus A should not appear in campus B's digest"""
        datetime.now(JAKARTA_TZ).date()

        mock_db = make_mock_db()
        # grief_support.find filters by campus_id, so campus B should get empty results
        mock_db.grief_support.find.return_value.to_list = AsyncMock(return_value=[])
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[])

        with patch("scheduler.db", mock_db):
            digest_b = await generate_daily_digest_for_campus("campus_b", "Campus B")

        assert digest_b["stats"]["grief_due"] == 0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_each_campus_uses_its_own_campus_id_in_query(self):
        """Verify that generate_daily_digest queries filter by campus_id"""
        call_args_list = []

        mock_db = make_mock_db()

        # Track what the members.find query looks like

        def tracking_find(query, *args, **kwargs):
            call_args_list.append(query)
            result = MagicMock()
            result.to_list = AsyncMock(return_value=[])
            return result

        mock_db.members.find = tracking_find

        with patch("scheduler.db", mock_db):
            await generate_daily_digest_for_campus("campus_xyz", "Campus XYZ")

        # At least one members.find call should filter by campus_id
        campus_ids_queried = [q.get("campus_id") for q in call_args_list if "campus_id" in q]
        assert "campus_xyz" in campus_ids_queried


# ---------------------------------------------------------------------------
# At-risk member detection edge cases
# ---------------------------------------------------------------------------


class TestAtRiskMemberDetection:
    """Tests for at-risk member logic within digest generation"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_member_with_no_contact_date_is_at_risk(self):
        """Members with null last_contact_date are at-risk (999 days)"""
        member = {
            "id": "m1",
            "name": "No Contact Person",
            "phone": "+6281444444444",
            # No last_contact_date
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["at_risk"] >= 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_member_with_empty_contact_date_is_at_risk(self):
        """Members with empty string last_contact_date are at-risk"""
        member = {
            "id": "m1",
            "name": "Empty Contact",
            "phone": "+6281333333333",
            "last_contact_date": "",
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["at_risk"] >= 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_recently_contacted_member_not_at_risk(self):
        """Members contacted within 30 days should NOT be at-risk"""
        recent = (datetime.now(UTC) - timedelta(days=5)).isoformat()
        member = {
            "id": "m1",
            "name": "Recent Contact Person",
            "phone": "+6281222222222",
            "last_contact_date": recent,
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert "Recent Contact Person" not in digest["message"]
        assert digest["stats"]["at_risk"] == 0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_member_without_phone_skipped_from_at_risk(self):
        """Members without phone numbers should be excluded from at-risk list"""
        member = {
            "id": "m1",
            "name": "At Risk No Phone",
            # No phone field
            "last_contact_date": None,
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert "At Risk No Phone" not in digest["message"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_at_risk_randomization_is_seeded(self):
        """
        The at-risk sample should be deterministic within the same day
        (uses today's date + campus_id as seed).
        """
        members = []
        for i in range(15):
            members.append(
                {
                    "id": f"risk-{i}",
                    "name": f"Risky Member {i}",
                    "phone": f"+62810000{i:05d}",
                    "last_contact_date": None,
                }
            )

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=members)
        mock_db.members.find_one = AsyncMock(return_value=None)

        with patch("scheduler.db", mock_db):
            digest1 = await generate_daily_digest_for_campus("c1", "Campus")

        # Reset mock to simulate second run
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=members)

        with patch("scheduler.db", mock_db):
            digest2 = await generate_daily_digest_for_campus("c1", "Campus")

        # Same data, same day -> same message (deterministic randomization)
        assert digest1["message"] == digest2["message"]
        assert digest1["stats"]["at_risk"] == 15
        # Only 10 are shown (sample of min(10, 15))
        count = digest1["message"].count("Risky Member")
        assert count == 10

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_member_with_invalid_contact_date_treated_as_at_risk(self):
        """Members with unparseable last_contact_date should be treated as at-risk"""
        member = {
            "id": "m1",
            "name": "Invalid Contact Date",
            "phone": "+6281111111111",
            "last_contact_date": "not-a-date-at-all",
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["at_risk"] >= 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_member_with_whitespace_contact_date_is_at_risk(self):
        """Members with whitespace-only last_contact_date should be at-risk"""
        member = {
            "id": "m1",
            "name": "Whitespace Contact",
            "phone": "+6281000000000",
            "last_contact_date": "   ",
        }

        mock_db = make_mock_db()
        mock_db.members.find.return_value.to_list = AsyncMock(return_value=[member])
        mock_db.members.find_one = AsyncMock(return_value=member)

        with patch("scheduler.db", mock_db):
            digest = await generate_daily_digest_for_campus("c1", "Campus")

        assert digest["stats"]["at_risk"] >= 1


# ---------------------------------------------------------------------------
# Timezone correctness validation
# ---------------------------------------------------------------------------


class TestTimezoneCorrectness:
    """Validate that Jakarta timezone is used consistently throughout scheduler"""

    @pytest.mark.unit
    def test_jakarta_tz_constant_is_correct(self):
        assert str(JAKARTA_TZ) == "Asia/Jakarta"

    @pytest.mark.unit
    def test_now_jakarta_uses_jakarta_tz(self):
        result = now_jakarta()
        assert result.utcoffset() == timedelta(hours=7)

    @pytest.mark.unit
    def test_jakarta_midnight_differs_from_utc_midnight(self):
        """
        Jakarta midnight on March 29, 2026 is March 28 17:00 UTC.
        This demonstrates the bug: using UTC midnight would miss 7 hours.
        """
        jakarta_midnight = datetime(2026, 3, 29, 0, 0, 0, tzinfo=JAKARTA_TZ)
        utc_equivalent = jakarta_midnight.astimezone(UTC)

        assert utc_equivalent.day == 28
        assert utc_equivalent.hour == 17

        utc_midnight = datetime(2026, 3, 29, 0, 0, 0, tzinfo=UTC)
        jakarta_equivalent = utc_midnight.astimezone(JAKARTA_TZ)
        assert jakarta_equivalent.hour == 7

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_check_missed_digest_query_uses_jakarta_midnight(self):
        """
        The notification_logs query must compare against Jakarta midnight, not UTC midnight.
        This verifies the fix for the bug where using timezone.utc would cause digests
        sent between 00:00-06:59 Jakarta to be missed.
        """
        captured_tz = []

        mock_db = make_mock_db()
        mock_db.settings.find_one = AsyncMock(return_value={"type": "automation", "data": {"digestTime": "08:00"}})

        async def capture_query(query):
            today_start = query["created_at"]["$gte"]
            captured_tz.append(today_start.tzinfo)
            return 1

        mock_db.notification_logs.count_documents = capture_query

        with (
            patch("scheduler.db", mock_db),
            patch("scheduler.asyncio.sleep", new_callable=AsyncMock),
            patch("scheduler.now_jakarta") as mock_now,
        ):
            fake_now = datetime(2026, 3, 29, 10, 0, 0, tzinfo=JAKARTA_TZ)
            mock_now.return_value = fake_now

            await check_missed_digest()

        assert len(captured_tz) == 1
        tz = captured_tz[0]
        assert tz != UTC
        dt_test = datetime(2026, 1, 1, tzinfo=tz)
        assert dt_test.utcoffset() == timedelta(hours=7)

    @pytest.mark.unit
    def test_today_jakarta_gives_jakarta_date_not_utc(self):
        """
        Explicitly verify today_jakarta() returns the Jakarta date,
        which can differ from the UTC date by up to 1 day.
        """
        with patch("scheduler.now_jakarta") as mock_now:
            # 2026-03-29 02:00 Jakarta = 2026-03-28 19:00 UTC
            # Jakarta date should be 29, UTC date is 28
            fake_now = datetime(2026, 3, 29, 2, 0, 0, tzinfo=JAKARTA_TZ)
            mock_now.return_value = fake_now

            result = today_jakarta()
            assert result == date(2026, 3, 29)
