"""
Integration tests for cache provider and service.
"""

import pytest
import time
from unittest.mock import patch, MagicMock

from src.providers.cache import cache_provider
from src.services.cache_service import cache_service


@pytest.mark.integration
class TestCacheIntegration:
    """Test cache provider and service integration."""
    
    def setup_method(self):
        """Setup test environment."""
        # Test configuration
        self.test_config = {
            "cache": {
                "redis": {
                    "host": "localhost",
                    "port": 6379,
                    "db": 1,  # Use separate DB for tests
                    "password": "",
                    "timeout": 5
                }
            }
        }
    
    def test_cache_provider_initialization(self):
        """Test cache provider initializes correctly."""
        # Initialize with test config
        cache_provider.initialize(self.test_config)
        
        # Check if initialized
        assert cache_provider.is_initialized()
        
        # Test health check
        health = cache_provider.health_check()
        assert health["status"] in ["healthy", "error"]  # Either works or fails gracefully
        
    def test_cache_basic_operations(self):
        """Test basic cache operations."""
        if not cache_provider.is_initialized():
            cache_provider.initialize(self.test_config)
        
        # Skip if cache is not healthy (Redis not available)
        health = cache_provider.health_check()
        if health["status"] != "healthy":
            pytest.skip("Redis not available for testing")
        
        # Test set and get
        test_key = "test:basic_ops"
        test_value = {"test": "data", "timestamp": time.time()}
        
        # Set value
        result = cache_provider.set(test_key, test_value, ttl=60)
        assert result is True
        
        # Get value
        cached_value = cache_provider.get(test_key)
        assert cached_value is not None
        assert cached_value["test"] == "data"
        
        # Check existence
        assert cache_provider.exists(test_key) is True
        
        # Check TTL
        ttl = cache_provider.get_ttl(test_key)
        assert ttl is not None
        assert ttl > 0
        
        # Delete key
        result = cache_provider.delete(test_key)
        assert result is True
        
        # Verify deletion
        assert cache_provider.exists(test_key) is False
        assert cache_provider.get(test_key) is None
        
    def test_cache_service_system_overview(self):
        """Test cache service system overview functionality."""
        if not cache_provider.is_initialized():
            cache_provider.initialize(self.test_config)
        
        # Skip if cache is not healthy
        health = cache_provider.health_check()
        if health["status"] != "healthy":
            pytest.skip("Redis not available for testing")
        
        # Clear any existing cache
        cache_service.invalidate_system_overview()
        
        # Mock data fetcher
        mock_data = {
            "timestamp": time.time(),
            "healthStatus": {"status": "healthy"},
            "taskStats": {"total": 10},
            "workflowCount": 5
        }
        
        def mock_fetch_func():
            return mock_data
        
        # First call should fetch fresh data
        result1 = cache_service.get_system_overview_data(mock_fetch_func)
        assert result1 is not None
        assert result1["taskStats"]["total"] == 10
        
        # Second call should return cached data (same timestamp)
        result2 = cache_service.get_system_overview_data(mock_fetch_func)
        assert result2 is not None
        assert result2["timestamp"] == result1["timestamp"]
        
        # Test cache invalidation
        invalidated = cache_service.invalidate_system_overview()
        assert invalidated is True
        
        # After invalidation, should fetch fresh data again
        result3 = cache_service.get_system_overview_data(mock_fetch_func)
        assert result3 is not None
        
    def test_cache_service_info(self):
        """Test cache service information retrieval."""
        if not cache_provider.is_initialized():
            cache_provider.initialize(self.test_config)
        
        # Get cache info
        info = cache_service.get_cache_info()
        assert "system_overview" in info
        assert "health_status" in info
        assert "task_stats" in info
        assert "cache_provider" in info
        
        # Check cache provider info
        provider_info = info["cache_provider"]
        assert "initialized" in provider_info
        assert "stats" in provider_info
        
    def test_cache_graceful_degradation(self):
        """Test cache behaves gracefully when Redis is unavailable."""
        # Test with uninitialized cache
        cache_provider.close()
        
        # Operations should fail gracefully
        assert cache_provider.get("test:key") is None
        assert cache_provider.set("test:key", "value") is False
        assert cache_provider.delete("test:key") is False
        assert cache_provider.exists("test:key") is False
        
        # Cache service should still work without cache
        def mock_fetch_func():
            return {"test": "data"}
        
        result = cache_service.get_system_overview_data(mock_fetch_func)
        assert result is not None
        assert result["test"] == "data"
        
    def test_cache_stats(self):
        """Test cache statistics retrieval."""
        if not cache_provider.is_initialized():
            cache_provider.initialize(self.test_config)
        
        # Skip if cache is not healthy
        health = cache_provider.health_check()
        if health["status"] != "healthy":
            pytest.skip("Redis not available for testing")
        
        # Get cache stats
        stats = cache_provider.get_stats()
        assert stats is not None
        assert "status" in stats
        
        if stats["status"] == "healthy":
            # Should have Redis stats
            assert "connected_clients" in stats
            assert "used_memory_human" in stats
            
    def test_cache_get_or_set_pattern(self):
        """Test cache-aside pattern implementation."""
        if not cache_provider.is_initialized():
            cache_provider.initialize(self.test_config)
        
        # Skip if cache is not healthy
        health = cache_provider.health_check()
        if health["status"] != "healthy":
            pytest.skip("Redis not available for testing")
        
        test_key = "test:get_or_set"
        call_count = 0
        
        def mock_fetch_func():
            nonlocal call_count
            call_count += 1
            return {"call_count": call_count, "timestamp": time.time()}
        
        # Clean up any existing cache
        cache_provider.delete(test_key)
        
        # First call should fetch data
        result1 = cache_provider.get_or_set(test_key, mock_fetch_func, ttl=60)
        assert result1 is not None
        assert result1["call_count"] == 1
        
        # Second call should return cached data (same call_count)
        result2 = cache_provider.get_or_set(test_key, mock_fetch_func, ttl=60)
        assert result2 is not None
        assert result2["call_count"] == 1  # Should be cached
        
        # Clean up
        cache_provider.delete(test_key)
        
    def teardown_method(self):
        """Cleanup after tests."""
        # Clean up test data
        if cache_provider.is_initialized():
            # Clean up any test keys
            cache_provider.invalidate_pattern("test:*")
            cache_provider.close() 