#!/usr/bin/env python3
"""
Test script to verify CORS configuration with different environments.
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

def test_cors_config():
    """Test CORS configuration with different environments."""
    
    # Mock config class for testing
    class MockConfig:
        def __init__(self, data):
            self.data = data
        
        def get(self, key, default=None):
            parts = key.split('.')
            current = self.data
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default
            return current
    
    # Test development environment
    dev_config = MockConfig({
        "app": {
            "ui_base_url": "http://localhost:8001",
            "api_base_url": "http://localhost:8002"
        },
        "environment": {"name": "dev"}
    })
    
    print("🧪 Testing Development Environment:")
    print(f"  UI Base URL: {dev_config.get('app.ui_base_url')}")
    print(f"  API Base URL: {dev_config.get('app.api_base_url')}")
    print(f"  Environment: {dev_config.get('environment.name')}")
    
    # Test staging environment
    stage_config = MockConfig({
        "app": {
            "ui_base_url": "https://swe-agent.concierge.stage.razorpay.in",
            "api_base_url": "https://swe-agent-api.concierge.stage.razorpay.in"
        },
        "environment": {"name": "stage"}
    })
    
    print("\n🧪 Testing Staging Environment:")
    print(f"  UI Base URL: {stage_config.get('app.ui_base_url')}")
    print(f"  API Base URL: {stage_config.get('app.api_base_url')}")
    print(f"  Environment: {stage_config.get('environment.name')}")
    
    # Test production environment
    prod_config = MockConfig({
        "app": {
            "ui_base_url": "https://swe-agent.prod.razorpay.com",
            "api_base_url": "https://swe-agent-api.prod.razorpay.com"
        },
        "environment": {"name": "prod"}
    })
    
    print("\n🧪 Testing Production Environment:")
    print(f"  UI Base URL: {prod_config.get('app.ui_base_url')}")
    print(f"  API Base URL: {prod_config.get('app.api_base_url')}")
    print(f"  Environment: {prod_config.get('environment.name')}")
    
    # Test CORS configuration logic
    def mock_configure_cors(config):
        """Mock version of _configure_cors for testing."""
        ui_base_url = config.get("app.ui_base_url", "")
        api_base_url = config.get("app.api_base_url", "")
        env_name = config.get("environment.name", "dev")
        
        # Determine CORS origins based on environment
        if env_name in ["dev", "development", "dev_docker"]:
            # Development: Allow common localhost ports for flexibility
            # Focus on common frontend development ports to reduce security risk
            frontend_ports = [3000, 3001, 3002, 3003, 4200, 4201, 5173, 5174]  # React, Angular, Vite
            api_ports = [8000, 8001, 8002]  # Common API development ports
            common_ports = frontend_ports + api_ports
            
            allowed_origins = []
            
            # Add HTTP and HTTPS for common development ports (show only first few for testing)
            test_ports = common_ports[:3]  # Show only first 3 ports for readability
            for port in test_ports:
                allowed_origins.extend([
                    f"http://localhost:{port}",
                    f"https://localhost:{port}",
                    f"http://127.0.0.1:{port}",
                    f"https://127.0.0.1:{port}",
                ])
            
            # Add indicator for additional ports
            allowed_origins.append(f"... and {len(common_ports) - len(test_ports)} more port combinations")
            
            # Also add the specific UI URL if it's not localhost
            if ui_base_url and not any(localhost in ui_base_url for localhost in ["localhost", "127.0.0.1"]):
                allowed_origins.append(ui_base_url)
                
        else:
            # Staging/Production: Strict origin control
            allowed_origins = []
            
            # Add environment-specific UI URL
            if ui_base_url:
                allowed_origins.append(ui_base_url)
            
            # Optionally add API URL for staging if needed for debugging
            if env_name in ["stage", "staging"] and api_base_url:
                allowed_origins.append(api_base_url)
        
        # Remove duplicates while preserving order
        unique_origins = []
        for origin in allowed_origins:
            if origin not in unique_origins:
                unique_origins.append(origin)
        
        return unique_origins
    
    print("\n📋 CORS Configuration Results:")
    
    for env_name, config in [("Development", dev_config), ("Staging", stage_config), ("Production", prod_config)]:
        origins = mock_configure_cors(config)
        print(f"\n{env_name} Environment CORS Origins:")
        for i, origin in enumerate(origins, 1):
            print(f"  {i}. {origin}")
    
    print("\n✅ CORS configuration test completed!")
    print("\n📝 Key Features:")
    print("  • Always includes localhost URLs for development")
    print("  • Dynamically adds environment-specific UI URLs")
    print("  • Prevents duplicate origins")
    print("  • Configures based on environment name")

if __name__ == "__main__":
    test_cors_config() 