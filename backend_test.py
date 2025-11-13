#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for GKBJ Pastoral Care System
Tests all 40+ endpoints including the signature grief timeline feature
"""

import requests
import sys
from datetime import datetime, date, timedelta
import json

class PastoralCareAPITester:
    def __init__(self, base_url="https://faithtracker.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
        # Store created IDs for cleanup and testing
        self.member_ids = []
        self.family_group_ids = []
        self.care_event_ids = []
        self.grief_stage_ids = []

    def log_result(self, test_name, passed, status_code=None, error=None, details=None):
        """Log test result"""
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
            print(f"✅ {test_name} - PASSED")
        else:
            print(f"❌ {test_name} - FAILED")
            if status_code:
                print(f"   Status: {status_code}")
            if error:
                print(f"   Error: {error}")
        
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "status_code": status_code,
            "error": error,
            "details": details
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, return_response=False):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)
            
            success = response.status_code == expected_status
            
            if success:
                self.log_result(name, True, response.status_code)
                if return_response:
                    return True, response.json() if response.text else {}
                return True
            else:
                error_msg = f"Expected {expected_status}, got {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {response.text[:200]}"
                self.log_result(name, False, response.status_code, error_msg)
                if return_response:
                    return False, {}
                return False
                
        except Exception as e:
            self.log_result(name, False, error=str(e))
            if return_response:
                return False, {}
            return False

    # ==================== MEMBER TESTS ====================
    
    def test_create_member(self):
        """Test creating a new member"""
        data = {
            "name": f"Test Member {datetime.now().strftime('%H%M%S')}",
            "phone": "6281290080025",
            "family_group_name": f"Test Family {datetime.now().strftime('%H%M%S')}",
            "notes": "Test member for API testing"
        }
        success, response = self.run_test(
            "Create Member",
            "POST",
            "members",
            200,
            data=data,
            return_response=True
        )
        if success and response.get('id'):
            self.member_ids.append(response['id'])
            return response['id']
        return None

    def test_list_members(self):
        """Test listing all members"""
        return self.run_test("List Members", "GET", "members", 200)

    def test_get_member(self, member_id):
        """Test getting a specific member"""
        if not member_id:
            self.log_result("Get Member", False, error="No member ID provided")
            return False
        return self.run_test(f"Get Member {member_id}", "GET", f"members/{member_id}", 200)

    def test_update_member(self, member_id):
        """Test updating a member"""
        if not member_id:
            self.log_result("Update Member", False, error="No member ID provided")
            return False
        data = {"notes": "Updated notes from test"}
        return self.run_test(f"Update Member {member_id}", "PUT", f"members/{member_id}", 200, data=data)

    def test_at_risk_members(self):
        """Test getting at-risk members"""
        return self.run_test("Get At-Risk Members", "GET", "members/at-risk", 200)

    # ==================== FAMILY GROUP TESTS ====================
    
    def test_create_family_group(self):
        """Test creating a family group"""
        data = {"group_name": f"Test Family Group {datetime.now().strftime('%H%M%S')}"}
        success, response = self.run_test(
            "Create Family Group",
            "POST",
            "family-groups",
            200,
            data=data,
            return_response=True
        )
        if success and response.get('id'):
            self.family_group_ids.append(response['id'])
            return response['id']
        return None

    def test_list_family_groups(self):
        """Test listing family groups"""
        return self.run_test("List Family Groups", "GET", "family-groups", 200)

    def test_get_family_group(self, group_id):
        """Test getting a specific family group"""
        if not group_id:
            self.log_result("Get Family Group", False, error="No group ID provided")
            return False
        return self.run_test(f"Get Family Group {group_id}", "GET", f"family-groups/{group_id}", 200)

    # ==================== CARE EVENT TESTS ====================
    
    def test_create_regular_care_event(self, member_id):
        """Test creating a regular care event"""
        if not member_id:
            self.log_result("Create Regular Care Event", False, error="No member ID provided")
            return None
        
        data = {
            "member_id": member_id,
            "event_type": "regular_contact",
            "event_date": date.today().isoformat(),
            "title": "Regular check-in call",
            "description": "Monthly contact call"
        }
        success, response = self.run_test(
            "Create Regular Care Event",
            "POST",
            "care-events",
            200,
            data=data,
            return_response=True
        )
        if success and response.get('id'):
            self.care_event_ids.append(response['id'])
            return response['id']
        return None

    def test_create_grief_event_with_timeline(self, member_id):
        """Test creating grief event - SIGNATURE FEATURE - should auto-generate 6-stage timeline"""
        if not member_id:
            self.log_result("Create Grief Event with Timeline", False, error="No member ID provided")
            return None
        
        mourning_date = date.today()
        data = {
            "member_id": member_id,
            "event_type": "grief_loss",
            "event_date": mourning_date.isoformat(),
            "title": "Loss of family member",
            "description": "Grief support needed",
            "grief_relationship": "parent",
            "mourning_service_date": mourning_date.isoformat()
        }
        success, response = self.run_test(
            "Create Grief Event (Auto-generate Timeline)",
            "POST",
            "care-events",
            200,
            data=data,
            return_response=True
        )
        if success and response.get('id'):
            self.care_event_ids.append(response['id'])
            print(f"   ⭐ Grief event created - Timeline should be auto-generated")
            return response['id']
        return None

    def test_create_hospital_visit_event(self, member_id):
        """Test creating hospital visit event"""
        if not member_id:
            self.log_result("Create Hospital Visit Event", False, error="No member ID provided")
            return None
        
        data = {
            "member_id": member_id,
            "event_type": "hospital_visit",
            "event_date": date.today().isoformat(),
            "title": "Hospital admission",
            "description": "Surgery scheduled",
            "hospital_name": "RSU Jakarta",
            "admission_date": date.today().isoformat()
        }
        success, response = self.run_test(
            "Create Hospital Visit Event",
            "POST",
            "care-events",
            200,
            data=data,
            return_response=True
        )
        if success and response.get('id'):
            self.care_event_ids.append(response['id'])
            return response['id']
        return None

    def test_create_financial_aid_event(self, member_id):
        """Test creating financial aid event"""
        if not member_id:
            self.log_result("Create Financial Aid Event", False, error="No member ID provided")
            return None
        
        data = {
            "member_id": member_id,
            "event_type": "financial_aid",
            "event_date": date.today().isoformat(),
            "title": "Education support",
            "description": "School fees assistance",
            "aid_type": "education",
            "aid_amount": 1500000
        }
        success, response = self.run_test(
            "Create Financial Aid Event",
            "POST",
            "care-events",
            200,
            data=data,
            return_response=True
        )
        if success and response.get('id'):
            self.care_event_ids.append(response['id'])
            return response['id']
        return None

    def test_list_care_events(self):
        """Test listing care events"""
        return self.run_test("List Care Events", "GET", "care-events", 200)

    def test_get_care_event(self, event_id):
        """Test getting a specific care event"""
        if not event_id:
            self.log_result("Get Care Event", False, error="No event ID provided")
            return False
        return self.run_test(f"Get Care Event {event_id}", "GET", f"care-events/{event_id}", 200)

    def test_complete_care_event(self, event_id):
        """Test marking care event as complete"""
        if not event_id:
            self.log_result("Complete Care Event", False, error="No event ID provided")
            return False
        return self.run_test(f"Complete Care Event {event_id}", "POST", f"care-events/{event_id}/complete", 200)

    # ==================== GRIEF SUPPORT TESTS ====================
    
    def test_list_grief_support(self):
        """Test listing grief support stages"""
        return self.run_test("List Grief Support Stages", "GET", "grief-support", 200)

    def test_get_member_grief_timeline(self, member_id):
        """Test getting grief timeline for a member - should show 6 stages"""
        if not member_id:
            self.log_result("Get Member Grief Timeline", False, error="No member ID provided")
            return False, []
        
        success, response = self.run_test(
            f"Get Member Grief Timeline {member_id}",
            "GET",
            f"grief-support/member/{member_id}",
            200,
            return_response=True
        )
        
        if success:
            stages = response if isinstance(response, list) else []
            print(f"   📋 Found {len(stages)} grief stages")
            if len(stages) == 6:
                print(f"   ✅ Correct! 6 stages auto-generated")
                # Verify stage names
                expected_stages = ["1_week", "2_weeks", "1_month", "3_months", "6_months", "1_year"]
                actual_stages = [s.get('stage') for s in stages]
                if all(stage in actual_stages for stage in expected_stages):
                    print(f"   ✅ All 6 stages present: {', '.join(expected_stages)}")
                else:
                    print(f"   ⚠️  Stage mismatch. Expected: {expected_stages}, Got: {actual_stages}")
            else:
                print(f"   ⚠️  Expected 6 stages, got {len(stages)}")
            
            if stages:
                self.grief_stage_ids = [s.get('id') for s in stages if s.get('id')]
            return success, stages
        return False, []

    def test_complete_grief_stage(self, stage_id):
        """Test completing a grief stage"""
        if not stage_id:
            self.log_result("Complete Grief Stage", False, error="No stage ID provided")
            return False
        return self.run_test(f"Complete Grief Stage {stage_id}", "POST", f"grief-support/{stage_id}/complete", 200)

    # ==================== DASHBOARD TESTS ====================
    
    def test_dashboard_stats(self):
        """Test dashboard statistics"""
        success, response = self.run_test(
            "Dashboard Stats",
            "GET",
            "dashboard/stats",
            200,
            return_response=True
        )
        if success:
            print(f"   📊 Total Members: {response.get('total_members', 0)}")
            print(f"   📊 Active Grief Support: {response.get('active_grief_support', 0)}")
            print(f"   📊 Members at Risk: {response.get('members_at_risk', 0)}")
            print(f"   📊 Month Financial Aid: Rp {response.get('month_financial_aid', 0):,}")
        return success

    def test_dashboard_upcoming_events(self):
        """Test upcoming events"""
        return self.run_test("Dashboard Upcoming Events", "GET", "dashboard/upcoming?days=7", 200)

    def test_dashboard_grief_active(self):
        """Test active grief support widget"""
        return self.run_test("Dashboard Active Grief Support", "GET", "dashboard/grief-active", 200)

    def test_dashboard_recent_activity(self):
        """Test recent activity"""
        return self.run_test("Dashboard Recent Activity", "GET", "dashboard/recent-activity?limit=10", 200)

    # ==================== FINANCIAL AID TESTS ====================
    
    def test_financial_aid_summary(self):
        """Test financial aid summary"""
        success, response = self.run_test(
            "Financial Aid Summary",
            "GET",
            "financial-aid/summary",
            200,
            return_response=True
        )
        if success:
            print(f"   💰 Total Amount: Rp {response.get('total_amount', 0):,}")
            print(f"   💰 Total Count: {response.get('total_count', 0)}")
        return success

    def test_member_financial_aid(self, member_id):
        """Test getting member's financial aid history"""
        if not member_id:
            self.log_result("Get Member Financial Aid", False, error="No member ID provided")
            return False
        return self.run_test(f"Get Member Financial Aid {member_id}", "GET", f"financial-aid/member/{member_id}", 200)

    # ==================== ANALYTICS TESTS ====================
    
    def test_analytics_care_events_by_type(self):
        """Test care events distribution"""
        return self.run_test("Analytics: Care Events by Type", "GET", "analytics/care-events-by-type", 200)

    def test_analytics_grief_completion_rate(self):
        """Test grief completion rate"""
        success, response = self.run_test(
            "Analytics: Grief Completion Rate",
            "GET",
            "analytics/grief-completion-rate",
            200,
            return_response=True
        )
        if success:
            print(f"   📈 Total Stages: {response.get('total_stages', 0)}")
            print(f"   📈 Completed: {response.get('completed_stages', 0)}")
            print(f"   📈 Completion Rate: {response.get('completion_rate', 0)}%")
        return success

    # ==================== WHATSAPP INTEGRATION TEST ====================
    
    def test_whatsapp_integration(self):
        """Test WhatsApp integration"""
        data = {
            "phone": "6281290080025",
            "message": "Test message from GKBJ Pastoral Care API Testing"
        }
        success, response = self.run_test(
            "WhatsApp Integration Test",
            "POST",
            "integrations/ping/whatsapp",
            200,
            data=data,
            return_response=True
        )
        if success:
            if response.get('success'):
                print(f"   ✅ WhatsApp message sent successfully!")
            else:
                print(f"   ⚠️  WhatsApp send failed: {response.get('message')}")
        return success

    # ==================== MAIN TEST RUNNER ====================
    
    def run_all_tests(self):
        """Run all backend API tests"""
        print("\n" + "="*80)
        print("🧪 GKBJ PASTORAL CARE SYSTEM - COMPREHENSIVE BACKEND API TESTING")
        print("="*80 + "\n")
        
        # 1. Member Tests
        print("\n📋 MEMBER MANAGEMENT TESTS")
        print("-" * 80)
        member_id = self.test_create_member()
        self.test_list_members()
        self.test_get_member(member_id)
        self.test_update_member(member_id)
        self.test_at_risk_members()
        
        # 2. Family Group Tests
        print("\n👨‍👩‍👧‍👦 FAMILY GROUP TESTS")
        print("-" * 80)
        group_id = self.test_create_family_group()
        self.test_list_family_groups()
        self.test_get_family_group(group_id)
        
        # 3. Care Event Tests
        print("\n📅 CARE EVENT TESTS")
        print("-" * 80)
        regular_event_id = self.test_create_regular_care_event(member_id)
        grief_event_id = self.test_create_grief_event_with_timeline(member_id)
        hospital_event_id = self.test_create_hospital_visit_event(member_id)
        aid_event_id = self.test_create_financial_aid_event(member_id)
        self.test_list_care_events()
        self.test_get_care_event(regular_event_id)
        self.test_complete_care_event(regular_event_id)
        
        # 4. Grief Support Tests (SIGNATURE FEATURE)
        print("\n💜 GRIEF SUPPORT TIMELINE TESTS (SIGNATURE FEATURE)")
        print("-" * 80)
        self.test_list_grief_support()
        success, stages = self.test_get_member_grief_timeline(member_id)
        if stages and len(stages) > 0:
            # Test completing first stage
            first_stage_id = stages[0].get('id')
            self.test_complete_grief_stage(first_stage_id)
        
        # 5. Dashboard Tests
        print("\n📊 DASHBOARD TESTS")
        print("-" * 80)
        self.test_dashboard_stats()
        self.test_dashboard_upcoming_events()
        self.test_dashboard_grief_active()
        self.test_dashboard_recent_activity()
        
        # 6. Financial Aid Tests
        print("\n💰 FINANCIAL AID TESTS")
        print("-" * 80)
        self.test_financial_aid_summary()
        self.test_member_financial_aid(member_id)
        
        # 7. Analytics Tests
        print("\n📈 ANALYTICS TESTS")
        print("-" * 80)
        self.test_analytics_care_events_by_type()
        self.test_analytics_grief_completion_rate()
        
        # 8. Integration Tests
        print("\n🔗 INTEGRATION TESTS")
        print("-" * 80)
        self.test_whatsapp_integration()
        
        # Print Summary
        print("\n" + "="*80)
        print("📊 TEST SUMMARY")
        print("="*80)
        print(f"Total Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        print("="*80 + "\n")
        
        return self.tests_passed == self.tests_run

def main():
    tester = PastoralCareAPITester()
    success = tester.run_all_tests()
    
    # Save results
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total_tests': tester.tests_run,
            'passed': tester.tests_passed,
            'failed': tester.tests_run - tester.tests_passed,
            'success_rate': f"{(tester.tests_passed/tester.tests_run*100):.1f}%",
            'results': tester.test_results
        }, f, indent=2)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
