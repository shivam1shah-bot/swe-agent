"""
Test client helper for API testing.
"""
import json
from unittest.mock import Mock

class TestClient:
    """Test client for API testing."""
    
    def __init__(self, app=None):
        self.app = app or Mock()
        self.session = {}
        self.headers = {}
    
    def set_header(self, key, value):
        """Set request header."""
        self.headers[key] = value
    
    def set_auth_token(self, token):
        """Set authentication token."""
        self.set_header("Authorization", f"Bearer {token}")
    
    def get(self, url, params=None):
        """Mock GET request."""
        return MockResponse(200, {"method": "GET", "url": url, "params": params})
    
    def post(self, url, data=None, json_data=None):
        """Mock POST request."""
        return MockResponse(200, {
            "method": "POST",
            "url": url,
            "data": data,
            "json": json_data
        })
    
    def put(self, url, data=None, json_data=None):
        """Mock PUT request."""
        return MockResponse(200, {
            "method": "PUT",
            "url": url,
            "data": data,
            "json": json_data
        })
    
    def delete(self, url):
        """Mock DELETE request."""
        return MockResponse(200, {"method": "DELETE", "url": url})

class MockResponse:
    """Mock HTTP response."""
    
    def __init__(self, status_code, data):
        self.status_code = status_code
        self.data = data
        self.headers = {}
    
    def json(self):
        """Return JSON data."""
        return self.data
    
    def text(self):
        """Return text data."""
        return json.dumps(self.data)

def create_test_client(app=None):
    """Create a test client instance."""
    return TestClient(app) 