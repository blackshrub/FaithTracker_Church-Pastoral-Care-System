# 🧪 Backend Testing Guide - GKBJ Pastoral Care System

## Quick Start Testing

### **Option 1: Automated Test Script (Recommended)**

Run the complete test suite:

```bash
cd /app/backend
./test_api.sh
```

This will test ALL features including grief support auto-timeline generation (6 stages)!

---

### **Option 2: Quick Manual Tests**

#### Test 1: Dashboard Stats
```bash
curl http://localhost:8001/api/dashboard/stats | python3 -m json.tool
```

#### Test 2: Create Member
```bash
curl -X POST http://localhost:8001/api/members \
  -H "Content-Type: application/json" \
  -d '{"name": "Test User", "phone": "6281234567890"}'
```

#### Test 3: ⭐ Test Grief Timeline Auto-Generation
```bash
# Get member ID from test 2, then:
curl -X POST http://localhost:8001/api/care-events \
  -H "Content-Type: application/json" \
  -d '{
    "member_id": "MEMBER_ID_HERE",
    "event_type": "grief_loss",
    "event_date": "2024-12-01",
    "mourning_service_date": "2024-12-03",
    "grief_relationship": "spouse",
    "title": "Loss of Spouse"
  }'

# Then check the auto-generated timeline (should show 6 stages!):
curl http://localhost:8001/api/grief-support | python3 -m json.tool
```

---

### **Option 3: Browser Testing**

Visit these URLs in your browser:
- http://localhost:8001/api/dashboard/stats
- http://localhost:8001/api/members
- http://localhost:8001/api/care-events
- http://localhost:8001/api/grief-support

---

## Key Features to Validate

✅ Member CRUD operations
⭐ Grief support auto-timeline (6 stages)
✅ Hospital visitation logs
✅ Financial aid tracking
✅ Dashboard statistics
✅ WhatsApp integration
✅ CSV import/export

See test_api.sh for complete examples!

---

## Pytest Suite

Run the full unit + integration suite (1232 tests, ~3 min):

```bash
cd /app/backend
pytest tests/ -p no:cacheprovider --tb=line -ra --timeout=10 \
  --deselect 'tests/test_integration_server.py::TestSSEStream' \
  --deselect 'tests/test_new_features.py::TestChangeStreamWatcherStartStop' \
  --deselect 'tests/test_new_features.py::TestChangeStreamWatcherIsRunning' \
  --deselect 'tests/test_new_features.py::TestChangeStreamWatcherIsReplicaSetAvailable' \
  --deselect 'tests/test_new_features.py::TestModuleLevelFunctions' \
  --ignore=tests/test_scheduler.py \
  --ignore=tests/test_scheduler_comprehensive.py \
  --ignore=tests/test_scheduler_jobs.py \
  --ignore=tests/test_server_coverage.py
```

### Why are some tests deselected?

These tests block indefinitely because they exercise long-running async
infrastructure that isn't safe to call inside pytest's blocking test client:

- **`TestSSEStream`** — calls `/stream/test` which produces a 20s SSE stream
  (`for i in range(10): asyncio.sleep(2)`). The sync test client blocks
  waiting for the response to complete.
- **`test_scheduler*.py` (3 files)** — start real APScheduler jobs that
  don't tear down cleanly between tests.
- **`TestChangeStreamWatcher{StartStop,IsRunning,IsReplicaSetAvailable}` +
  `TestModuleLevelFunctions`** — start the change-stream `_watch_loop`
  with `async for change in stream` against a `MagicMock`, which blocks
  indefinitely waiting for items the mock never yields.
- **`tests/test_server_coverage.py`** — contains a test that hangs in the
  same change-stream pattern; the file is ignored wholesale rather than
  deselecting individual classes.

These behaviors require dedicated integration tests against a real Redis +
Mongo replica set or proper async-mock cancellation harnesses; they are
intentionally excluded from the default suite to keep CI green and fast.
