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

**Default `pytest` command** (1231 tests, ~40 s on 8-core host):

```bash
cd /app/backend
uv run pytest        # all defaults already in pytest.ini
```

`pytest.ini` provides: parallel `-n auto` via xdist (per-worker MongoDB
isolation), default `-m "not slow"` to skip network-bound tests,
deselects for the SSE/scheduler/change-stream classes that hang the
sync TestClient, and Faker/cacheprovider plugin pruning.

### Common workflows

```bash
make test                # full suite (~40 s)
make test-slow           # include @pytest.mark.slow tests too
make test-incremental    # only tests touched by code changes (testmon)
make test-failed         # re-run only last-failed tests
make test-fast           # failed-first + stop on first failure (-x)
make test-profile        # show 20 slowest tests
make test-serial         # disable parallelism (debug shared state)
```

### Performance journey

| Configuration                          | Wall time |
|----------------------------------------|-----------|
| Baseline (single worker, all tests)    | 168 s     |
| `+pytest-xdist -n auto` (8 cores)      | 45 s      |
| `+per-worker MongoDB DB`               | 41 s      |
| Bytecode cache + plugin pruning        | ~40 s     |
| `--testmon` after no-op change         | 5 s       |

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
