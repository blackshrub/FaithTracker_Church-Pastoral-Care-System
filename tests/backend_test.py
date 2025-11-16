import requests
import sys
from datetime import datetime

class DashboardAPITester:
    def __init__(self, base_url="https://member-pulse-3.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.user_info = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        if headers is None:
            headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"   Response: {response.text[:200]}")
                except:
                    pass
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_login(self, email, password):
        """Test login and get token"""
        print("\n" + "="*60)
        print("TESTING AUTHENTICATION")
        print("="*60)
        
        success, response = self.run_test(
            "Login API",
            "POST",
            "api/auth/login",
            200,
            data={"email": email, "password": password}
        )
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user_info = response.get('user', {})
            print(f"   User: {self.user_info.get('name')} ({self.user_info.get('role')})")
            print(f"   Campus: {self.user_info.get('campus_name')}")
            return True
        return False

    def test_dashboard_reminders(self):
        """Test dashboard reminders endpoint"""
        print("\n" + "="*60)
        print("TESTING DASHBOARD API")
        print("="*60)
        
        success, response = self.run_test(
            "Dashboard Reminders API",
            "GET",
            "api/dashboard/reminders",
            200
        )
        
        if success:
            print(f"\n📊 Dashboard Data Summary:")
            print(f"   Birthdays Today: {len(response.get('birthdays_today', []))}")
            print(f"   Overdue Birthdays: {len(response.get('overdue_birthdays', []))}")
            print(f"   Today Tasks: {len(response.get('today_tasks', []))}")
            print(f"   Grief Support: {len(response.get('grief_today', []))}")
            print(f"   Accident Follow-ups: {len(response.get('accident_followup', []))}")
            print(f"   Financial Aid Due: {len(response.get('financial_aid_due', []))}")
            print(f"   At Risk Members: {len(response.get('at_risk_members', []))}")
            print(f"   Disconnected Members: {len(response.get('disconnected_members', []))}")
            print(f"   Upcoming Tasks: {len(response.get('upcoming_tasks', []))}")
            
            # Check if we have data for testing
            if response.get('birthdays_today'):
                print(f"\n   Sample Birthday Today:")
                bday = response['birthdays_today'][0]
                print(f"      Member: {bday.get('member_name')}")
                print(f"      Phone: {bday.get('member_phone')}")
                print(f"      Age: {bday.get('member_age')}")
            
            if response.get('today_tasks'):
                print(f"\n   Sample Today Task:")
                task = response['today_tasks'][0]
                print(f"      Type: {task.get('type')}")
                print(f"      Member: {task.get('member_name')}")
                print(f"      Details: {task.get('details')}")
            
            if response.get('financial_aid_due'):
                print(f"\n   Sample Financial Aid:")
                aid = response['financial_aid_due'][0]
                print(f"      Member: {aid.get('member_name')}")
                print(f"      Amount: Rp {aid.get('aid_amount')}")
                print(f"      Frequency: {aid.get('frequency')}")
                print(f"      Type: {aid.get('aid_type')}")
        
        return success

    def test_campuses(self):
        """Test campuses endpoint"""
        print("\n" + "="*60)
        print("TESTING CAMPUSES API")
        print("="*60)
        
        success, response = self.run_test(
            "List Campuses API",
            "GET",
            "api/campuses",
            200
        )
        
        if success and response:
            print(f"\n   Found {len(response)} campuses")
            for campus in response[:3]:
                print(f"      - {campus.get('campus_name')} ({campus.get('location', 'N/A')})")
        
        return success

def main():
    print("\n" + "="*60)
    print("FAITHTRACKER DASHBOARD - BACKEND API TESTING")
    print("="*60)
    print(f"Testing Backend: https://member-pulse-3.preview.emergentagent.com")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tester = DashboardAPITester()
    
    # Test 1: Login
    if not tester.test_login("admin@gkbj.church", "admin123"):
        print("\n❌ Login failed, stopping tests")
        return 1
    
    # Test 2: Campuses
    tester.test_campuses()
    
    # Test 3: Dashboard Reminders (main endpoint)
    tester.test_dashboard_reminders()
    
    # Print final results
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)
    print(f"✅ Tests Passed: {tester.tests_passed}/{tester.tests_run}")
    print(f"❌ Tests Failed: {tester.tests_run - tester.tests_passed}/{tester.tests_run}")
    
    if tester.tests_passed == tester.tests_run:
        print("\n🎉 All backend API tests passed!")
        return 0
    else:
        print(f"\n⚠️  {tester.tests_run - tester.tests_passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
