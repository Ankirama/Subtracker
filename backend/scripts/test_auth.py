"""
Test script for authentication endpoints.
Run this after starting the backend to verify auth works.

Usage:
    python scripts/test_auth.py
"""
import requests
import json
from typing import Optional

BASE_URL = "http://localhost:8000"


class AuthTester:
    def __init__(self):
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.user_id: Optional[str] = None

    def test_health(self):
        """Test health check endpoint."""
        print("\n🏥 Testing health check...")
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        assert response.status_code == 200, "Health check failed"
        print("✅ Health check passed")

    def test_register(self, email: str = "test@example.com", password: str = "Test1234"):
        """Test user registration."""
        print(f"\n📝 Testing registration for {email}...")
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": password}
        )
        print(f"Status: {response.status_code}")

        if response.status_code == 201:
            data = response.json()
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            self.user_id = data["user"]["id"]
            print(f"✅ Registration successful")
            print(f"User ID: {self.user_id}")
            print(f"Access Token: {self.access_token[:20]}...")
            print(f"Refresh Token: {self.refresh_token[:20]}...")
        elif response.status_code == 400:
            print(f"⚠️  Registration failed: {response.json()['detail']}")
            print("(This might be expected if user already exists)")
        else:
            print(f"❌ Registration failed: {response.text}")
            raise Exception("Registration failed")

    def test_login(self, email: str = "test@example.com", password: str = "Test1234"):
        """Test user login."""
        print(f"\n🔐 Testing login for {email}...")
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": email, "password": password}
        )
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            self.user_id = data["user"]["id"]
            print(f"✅ Login successful")
            print(f"User ID: {self.user_id}")
            print(f"Access Token: {self.access_token[:20]}...")
        else:
            print(f"❌ Login failed: {response.text}")
            raise Exception("Login failed")

    def test_get_me(self):
        """Test getting current user info."""
        print("\n👤 Testing get current user...")
        if not self.access_token:
            print("❌ No access token available. Login first.")
            return

        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Get current user successful")
            print(f"User info: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Get current user failed: {response.text}")

    def test_refresh_token(self):
        """Test refreshing access token."""
        print("\n🔄 Testing token refresh...")
        if not self.refresh_token:
            print("❌ No refresh token available. Login first.")
            return

        response = requests.post(
            f"{BASE_URL}/api/auth/refresh",
            json={"refresh_token": self.refresh_token}
        )
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            old_token = self.access_token[:20] if self.access_token else "None"
            self.access_token = data["access_token"]
            print(f"✅ Token refresh successful")
            print(f"Old token: {old_token}...")
            print(f"New token: {self.access_token[:20]}...")
        else:
            print(f"❌ Token refresh failed: {response.text}")

    def test_logout(self):
        """Test user logout."""
        print("\n👋 Testing logout...")
        if not self.access_token:
            print("❌ No access token available. Login first.")
            return

        response = requests.post(
            f"{BASE_URL}/api/auth/logout",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Logout successful: {data['message']}")
        else:
            print(f"❌ Logout failed: {response.text}")

    def test_invalid_token(self):
        """Test with invalid token."""
        print("\n🚫 Testing with invalid token...")
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        print(f"Status: {response.status_code}")

        if response.status_code == 401:
            print("✅ Invalid token correctly rejected")
        else:
            print(f"❌ Expected 401, got {response.status_code}")

    def run_all_tests(self):
        """Run all authentication tests."""
        print("=" * 60)
        print("🧪 Starting Authentication Tests")
        print("=" * 60)

        try:
            # Test 1: Health check
            self.test_health()

            # Test 2: Register new user
            self.test_register()

            # Test 3: Login (will work even if registration failed due to existing user)
            self.test_login()

            # Test 4: Get current user info
            self.test_get_me()

            # Test 5: Refresh access token
            self.test_refresh_token()

            # Test 6: Test with invalid token
            self.test_invalid_token()

            # Test 7: Logout
            self.test_logout()

            print("\n" + "=" * 60)
            print("✅ All tests completed successfully!")
            print("=" * 60)

        except Exception as e:
            print("\n" + "=" * 60)
            print(f"❌ Tests failed with error: {str(e)}")
            print("=" * 60)
            raise


if __name__ == "__main__":
    tester = AuthTester()
    tester.run_all_tests()
