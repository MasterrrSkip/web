import requests
import sys
import json
from datetime import datetime

class MarvelAPITester:
    def __init__(self, base_url="https://avengers-squad.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_user_id = f"test_user_{datetime.now().strftime('%H%M%S')}"

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict) and 'characters' in response_data:
                        print(f"   Found {len(response_data['characters'])} characters")
                    elif isinstance(response_data, list):
                        print(f"   Returned {len(response_data)} items")
                    elif isinstance(response_data, dict) and 'name' in response_data:
                        print(f"   Character: {response_data['name']}")
                except:
                    pass
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error: {error_detail}")
                except:
                    print(f"   Response: {response.text[:200]}")

            return success, response.json() if response.content else {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout (30s)")
            return False, {}
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed - Network error: {str(e)}")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        return self.run_test("Root API", "GET", "", 200)

    def test_get_characters_default(self):
        """Test getting characters without search"""
        return self.run_test("Get Characters (Default)", "GET", "characters", 200)

    def test_search_characters_spider(self):
        """Test searching for characters with 'spider' query"""
        return self.run_test(
            "Search Characters (Spider)", 
            "GET", 
            "characters", 
            200, 
            params={"search": "spider", "limit": 10}
        )

    def test_search_characters_iron(self):
        """Test searching for characters with 'iron' query"""
        return self.run_test(
            "Search Characters (Iron)", 
            "GET", 
            "characters", 
            200, 
            params={"search": "iron", "limit": 5}
        )

    def test_get_character_by_id(self, character_id=1009610):
        """Test getting specific character by ID (Spider-Man)"""
        return self.run_test(
            f"Get Character by ID ({character_id})", 
            "GET", 
            f"characters/{character_id}", 
            200
        )

    def test_get_invalid_character(self):
        """Test getting non-existent character"""
        return self.run_test(
            "Get Invalid Character", 
            "GET", 
            "characters/999999999", 
            404
        )

    def test_favorites_workflow(self):
        """Test complete favorites workflow"""
        print(f"\n🔄 Testing Favorites Workflow for user: {self.test_user_id}")
        
        # 1. Get initial favorites (should be empty)
        success, response = self.run_test(
            "Get Initial Favorites", 
            "GET", 
            f"favorites/{self.test_user_id}", 
            200
        )
        if not success:
            return False
        
        initial_count = len(response) if isinstance(response, list) else 0
        print(f"   Initial favorites count: {initial_count}")
        
        # 2. Add a favorite character (Spider-Man)
        favorite_data = {
            "user_id": self.test_user_id,
            "character_id": 1009610,
            "character_name": "Spider-Man"
        }
        success, response = self.run_test(
            "Add Favorite Character", 
            "POST", 
            "favorites", 
            200,
            data=favorite_data
        )
        if not success:
            return False
        
        # 3. Get favorites again (should have 1 item)
        success, response = self.run_test(
            "Get Favorites After Add", 
            "GET", 
            f"favorites/{self.test_user_id}", 
            200
        )
        if not success:
            return False
        
        new_count = len(response) if isinstance(response, list) else 0
        print(f"   Favorites count after add: {new_count}")
        
        # 4. Try to add same favorite again (should fail)
        success, response = self.run_test(
            "Add Duplicate Favorite", 
            "POST", 
            "favorites", 
            400,
            data=favorite_data
        )
        
        # 5. Remove the favorite
        success, response = self.run_test(
            "Remove Favorite Character", 
            "DELETE", 
            f"favorites/{self.test_user_id}/1009610", 
            200
        )
        if not success:
            return False
        
        # 6. Get favorites again (should be back to initial count)
        success, response = self.run_test(
            "Get Favorites After Remove", 
            "GET", 
            f"favorites/{self.test_user_id}", 
            200
        )
        if not success:
            return False
        
        final_count = len(response) if isinstance(response, list) else 0
        print(f"   Final favorites count: {final_count}")
        
        return True

    def test_pagination(self):
        """Test pagination parameters"""
        return self.run_test(
            "Test Pagination", 
            "GET", 
            "characters", 
            200, 
            params={"limit": 5, "offset": 10}
        )

    def test_invalid_search_params(self):
        """Test invalid search parameters"""
        return self.run_test(
            "Invalid Limit Parameter", 
            "GET", 
            "characters", 
            200,  # Should still work, just clamp the limit
            params={"limit": 200}  # Over Marvel API limit
        )

def main():
    print("🚀 Starting Marvel Character Database API Tests")
    print("=" * 60)
    
    tester = MarvelAPITester()
    
    # Test all endpoints
    tests = [
        tester.test_root_endpoint,
        tester.test_get_characters_default,
        tester.test_search_characters_spider,
        tester.test_search_characters_iron,
        tester.test_get_character_by_id,
        tester.test_get_invalid_character,
        tester.test_favorites_workflow,
        tester.test_pagination,
        tester.test_invalid_search_params
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"❌ Test failed with exception: {str(e)}")
    
    # Print final results
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())