#!/bin/bash

# GKBJ Pastoral Care System - Backend API Testing Script
# This script tests all major backend endpoints

API_URL="http://localhost:8001/api"
echo "🧪 Testing GKBJ Pastoral Care Backend API"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Dashboard Stats
echo -e "${BLUE}1. Testing Dashboard Stats${NC}"
curl -s "$API_URL/dashboard/stats" | python3 -m json.tool
echo ""

# Test 2: Create Family Group
echo -e "${BLUE}2. Creating Family Group${NC}"
FAMILY_RESPONSE=$(curl -s -X POST "$API_URL/family-groups" \
  -H "Content-Type: application/json" \
  -d '{"group_name": "Keluarga Budi"}')
echo "$FAMILY_RESPONSE" | python3 -m json.tool
FAMILY_ID=$(echo "$FAMILY_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
echo -e "${GREEN}Family Group ID: $FAMILY_ID${NC}"
echo ""

# Test 3: Create Member
echo -e "${BLUE}3. Creating Member (Budi Santoso)${NC}"
MEMBER_RESPONSE=$(curl -s -X POST "$API_URL/members" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"Budi Santoso\", \"phone\": \"6281290080025\", \"family_group_id\": \"$FAMILY_ID\", \"notes\": \"Active church member\"}")
echo "$MEMBER_RESPONSE" | python3 -m json.tool
MEMBER_ID=$(echo "$MEMBER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
echo -e "${GREEN}Member ID: $MEMBER_ID${NC}"
echo ""

# Test 4: List Members
echo -e "${BLUE}4. Listing All Members${NC}"
curl -s "$API_URL/members" | python3 -m json.tool
echo ""

# Test 5: Create Birthday Event
echo -e "${BLUE}5. Creating Birthday Care Event${NC}"
BIRTHDAY_RESPONSE=$(curl -s -X POST "$API_URL/care-events" \
  -H "Content-Type: application/json" \
  -d "{\"member_id\": \"$MEMBER_ID\", \"event_type\": \"birthday\", \"event_date\": \"2025-01-15\", \"title\": \"Ulang Tahun Budi Santoso\", \"description\": \"Birthday celebration\"}")
echo "$BIRTHDAY_RESPONSE" | python3 -m json.tool
BIRTHDAY_ID=$(echo "$BIRTHDAY_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
echo ""

# Test 6: Create Grief/Loss Event (This will auto-generate grief timeline!)
echo -e "${BLUE}6. Creating Grief/Loss Event (Auto-generates 6-stage timeline!)${NC}"
GRIEF_RESPONSE=$(curl -s -X POST "$API_URL/care-events" \
  -H "Content-Type: application/json" \
  -d "{\"member_id\": \"$MEMBER_ID\", \"event_type\": \"grief_loss\", \"event_date\": \"2024-12-01\", \"mourning_service_date\": \"2024-12-03\", \"grief_relationship\": \"spouse\", \"title\": \"Loss of Spouse\", \"description\": \"Member lost their spouse\"}")
echo "$GRIEF_RESPONSE" | python3 -m json.tool
GRIEF_EVENT_ID=$(echo "$GRIEF_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
echo ""

# Test 7: Check Grief Support Timeline (Should show 6 stages!)
echo -e "${YELLOW}⭐ 7. Checking Auto-Generated Grief Support Timeline (6 stages)${NC}"
curl -s "$API_URL/grief-support/member/$MEMBER_ID" | python3 -m json.tool
echo ""

# Test 8: List All Grief Support Stages
echo -e "${BLUE}8. Listing All Grief Support Stages${NC}"
curl -s "$API_URL/grief-support?completed=false" | python3 -m json.tool
echo ""

# Test 9: Create Hospital Visit Event
echo -e "${BLUE}9. Creating Hospital Visit Event${NC}"
HOSPITAL_RESPONSE=$(curl -s -X POST "$API_URL/care-events" \
  -H "Content-Type: application/json" \
  -d "{\"member_id\": \"$MEMBER_ID\", \"event_type\": \"hospital_visit\", \"event_date\": \"2024-11-10\", \"title\": \"Hospital Visit - RSU Jakarta\", \"hospital_name\": \"RSU Jakarta\", \"admission_date\": \"2024-11-10\", \"discharge_date\": \"2024-11-13\", \"initial_visitation\": {\"visitor_name\": \"Pastor John\", \"visit_date\": \"2024-11-11\", \"notes\": \"Visited and prayed with family\", \"prayer_offered\": true}}")
echo "$HOSPITAL_RESPONSE" | python3 -m json.tool
HOSPITAL_ID=$(echo "$HOSPITAL_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
echo ""

# Test 10: Add Visitation Log
echo -e "${BLUE}10. Adding Hospital Visitation Log${NC}"
curl -s -X POST "$API_URL/care-events/$HOSPITAL_ID/visitation-log" \
  -H "Content-Type: application/json" \
  -d '{"visitor_name": "Pastor Maria", "visit_date": "2024-11-12", "notes": "Second visit, patient recovering well", "prayer_offered": true}' | python3 -m json.tool
echo ""

# Test 11: Create Financial Aid Event
echo -e "${BLUE}11. Creating Financial Aid Event${NC}"
AID_RESPONSE=$(curl -s -X POST "$API_URL/care-events" \
  -H "Content-Type: application/json" \
  -d "{\"member_id\": \"$MEMBER_ID\", \"event_type\": \"financial_aid\", \"event_date\": \"2024-11-15\", \"title\": \"Medical Bill Assistance\", \"aid_type\": \"medical\", \"aid_amount\": 2000000, \"aid_notes\": \"Assistance for hospital bills\"}")
echo "$AID_RESPONSE" | python3 -m json.tool
echo ""

# Test 12: Get Financial Aid Summary
echo -e "${BLUE}12. Financial Aid Summary${NC}"
curl -s "$API_URL/financial-aid/summary" | python3 -m json.tool
echo ""

# Test 13: Get Member's Financial Aid History
echo -e "${BLUE}13. Member's Financial Aid History${NC}"
curl -s "$API_URL/financial-aid/member/$MEMBER_ID" | python3 -m json.tool
echo ""

# Test 14: Dashboard Stats (Updated)
echo -e "${BLUE}14. Updated Dashboard Stats${NC}"
curl -s "$API_URL/dashboard/stats" | python3 -m json.tool
echo ""

# Test 15: Dashboard - Active Grief Support
echo -e "${YELLOW}⭐ 15. Active Grief Support (Should show member with 6 pending stages)${NC}"
curl -s "$API_URL/dashboard/grief-active" | python3 -m json.tool
echo ""

# Test 16: Dashboard - Upcoming Events
echo -e "${BLUE}16. Upcoming Events (Next 7 days)${NC}"
curl -s "$API_URL/dashboard/upcoming" | python3 -m json.tool
echo ""

# Test 17: Dashboard - Recent Activity
echo -e "${BLUE}17. Recent Activity${NC}"
curl -s "$API_URL/dashboard/recent-activity" | python3 -m json.tool
echo ""

# Test 18: Analytics - Care Events by Type
echo -e "${BLUE}18. Analytics - Care Events by Type${NC}"
curl -s "$API_URL/analytics/care-events-by-type" | python3 -m json.tool
echo ""

# Test 19: Analytics - Grief Completion Rate
echo -e "${BLUE}19. Analytics - Grief Completion Rate${NC}"
curl -s "$API_URL/analytics/grief-completion-rate" | python3 -m json.tool
echo ""

# Test 20: Get Member Details (Shows engagement status)
echo -e "${BLUE}20. Get Member Details (with engagement status)${NC}"
curl -s "$API_URL/members/$MEMBER_ID" | python3 -m json.tool
echo ""

# Test 21: Send WhatsApp Reminder for Care Event
echo -e "${YELLOW}⭐ 21. Sending WhatsApp Reminder for Birthday${NC}"
echo "This will send an actual WhatsApp message to 6281290080025!"
read -p "Press Enter to send WhatsApp message (or Ctrl+C to skip)..."
curl -s -X POST "$API_URL/care-events/$BIRTHDAY_ID/send-reminder" | python3 -m json.tool
echo ""

# Test 22: Get Hospital Follow-up Due
echo -e "${BLUE}22. Hospital Follow-ups Due${NC}"
curl -s "$API_URL/care-events/hospital/due-followup" | python3 -m json.tool
echo ""

# Test 23: List All Care Events
echo -e "${BLUE}23. All Care Events${NC}"
curl -s "$API_URL/care-events" | python3 -m json.tool
echo ""

# Test 24: Export Members to CSV
echo -e "${BLUE}24. Export Members to CSV${NC}"
curl -s "$API_URL/export/members/csv" -o /tmp/members_export.csv
echo "Exported to /tmp/members_export.csv"
head -n 5 /tmp/members_export.csv
echo ""

echo -e "${GREEN}=========================================="
echo "✅ Backend Testing Complete!"
echo "=========================================="
echo ""
echo "Summary of what was tested:"
echo "- ✅ Family Groups"
echo "- ✅ Members (CRUD, engagement status)"
echo "- ✅ Care Events (birthday, grief, hospital, financial aid)"
echo "- ⭐ Grief Support Auto-Timeline (6 stages)"
echo "- ✅ Hospital Visitation Logs"
echo "- ✅ Financial Aid Tracking"
echo "- ✅ Dashboard Stats & Widgets"
echo "- ✅ Analytics"
echo "- ✅ CSV Export"
echo "- ✅ WhatsApp Integration (optional)"
echo ""
echo "Test Data Created:"
echo "- Member ID: $MEMBER_ID"
echo "- Family Group ID: $FAMILY_ID"
echo "- Grief Event ID: $GRIEF_EVENT_ID"
echo "- Hospital Event ID: $HOSPITAL_ID"
echo ""
echo "To clean up test data, you can delete the member:"
echo "curl -X DELETE '$API_URL/members/$MEMBER_ID'"
echo -e "${NC}"
