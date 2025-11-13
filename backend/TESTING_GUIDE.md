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
