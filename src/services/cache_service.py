"""
Cache Service

Provides high-level caching functionality for system data with specific
cache keys and TTL configurations.
"""

import logging
from typing import Any, Dict, Optional, Callable
from datetime import datetime, timedelta

from src.providers.cache import cache_provider

logger = logging.getLogger(__name__)


class CacheService:
    """
    Service for managing cached system data with predefined cache keys and TTLs.
    """
    
    # Cache key constants with swe-agent prefix for namespacing
    SYSTEM_OVERVIEW_KEY = "swe-agent:system_overview:data"
    HEALTH_STATUS_KEY = "swe-agent:health:status"
    TASK_STATS_KEY = "swe-agent:tasks:stats"
    # WORKFLOW_COUNT_KEY = "swe-agent:workflows:count"  # Removed - workflow system deleted
    HEALTH_METRICS_KEY = "swe-agent:health:metrics"
    AGENTS_STATUS_KEY = "swe-agent:agents:status"
    MCP_SERVERS_STATUS_KEY = "swe-agent:mcp_servers:status"
    
    # Repository metrics cache key pattern
    REPOSITORY_METRICS_KEY_PATTERN = "code-review:metrics:{repository}:{date}"
    
    # TTL constants (in seconds) - Business logic, not environment-specific
    # These values should remain consistent across all environments
    SYSTEM_OVERVIEW_TTL = 120  # 2 minutes for system overview
    HEALTH_STATUS_TTL = 60    # 1 minute for health status (more frequent updates)
    TASK_STATS_TTL = 120      # 2 minutes for task stats
    DEFAULT_TTL = 60          # 1 minute default for other cached data
    REPOSITORY_METRICS_TTL = 45 * 24 * 60 * 60  # 45 days for repository metrics
    
    def __init__(self):
        """Initialize the cache service."""
        self.cache = cache_provider
    
    def get_system_overview_data(self, fetch_func: Callable) -> Optional[Dict[str, Any]]:
        """
        Get system overview data from cache or fetch if not available.
        
        Args:
            fetch_func: Function to fetch fresh system overview data
            
        Returns:
            System overview data or None if unavailable
        """
        return self.cache.get_or_set(
            key=self.SYSTEM_OVERVIEW_KEY,
            value_func=fetch_func,
            ttl=self.SYSTEM_OVERVIEW_TTL
        )
    
    def get_health_status(self, fetch_func: Callable) -> Optional[Dict[str, Any]]:
        """
        Get health status from cache or fetch if not available.
        
        Args:
            fetch_func: Function to fetch fresh health status
            
        Returns:
            Health status data or None if unavailable
        """
        return self.cache.get_or_set(
            key=self.HEALTH_STATUS_KEY,
            value_func=fetch_func,
            ttl=self.HEALTH_STATUS_TTL
        )
    
    def get_task_stats(self, fetch_func: Callable) -> Optional[Dict[str, Any]]:
        """
        Get task statistics from cache or fetch if not available.
        
        Args:
            fetch_func: Function to fetch fresh task stats
            
        Returns:
            Task statistics data or None if unavailable
        """
        return self.cache.get_or_set(
            key=self.TASK_STATS_KEY,
            value_func=fetch_func,
            ttl=self.TASK_STATS_TTL
        )
    
    # get_workflow_count method removed - workflow system deleted
    
    def get_health_metrics(self, fetch_func: Callable) -> Optional[Dict[str, Any]]:
        """
        Get health metrics from cache or fetch if not available.
        
        Args:
            fetch_func: Function to fetch fresh health metrics
            
        Returns:
            Health metrics data or None if unavailable
        """
        return self.cache.get_or_set(
            key=self.HEALTH_METRICS_KEY,
            value_func=fetch_func,
            ttl=self.DEFAULT_TTL
        )
    
    def get_agents_status(self, fetch_func: Callable) -> Optional[Dict[str, Any]]:
        """
        Get agents status from cache or fetch if not available.
        
        Args:
            fetch_func: Function to fetch fresh agents status
            
        Returns:
            Agents status data or None if unavailable
        """
        return self.cache.get_or_set(
            key=self.AGENTS_STATUS_KEY,
            value_func=fetch_func,
            ttl=self.DEFAULT_TTL
        )
    
    def get_mcp_servers_status(self, fetch_func: Callable) -> Optional[Dict[str, Any]]:
        """
        Get MCP servers status from cache or fetch if not available.
        
        Args:
            fetch_func: Function to fetch fresh MCP servers status
            
        Returns:
            MCP servers status data or None if unavailable
        """
        return self.cache.get_or_set(
            key=self.MCP_SERVERS_STATUS_KEY,
            value_func=fetch_func,
            ttl=self.DEFAULT_TTL
        )
    
    def invalidate_system_overview(self) -> bool:
        """
        Invalidate system overview cache.
        
        Returns:
            True if successful, False otherwise
        """
        return self.cache.delete(self.SYSTEM_OVERVIEW_KEY)
    
    def invalidate_health_data(self) -> int:
        """
        Invalidate all health-related cache data.
        
        Returns:
            Number of keys invalidated
        """
        patterns = ["swe-agent:health:*", "swe-agent:system_overview:*"]
        total_deleted = 0
        
        for pattern in patterns:
            deleted = self.cache.invalidate_pattern(pattern)
            total_deleted += deleted
            
        return total_deleted
    
    def invalidate_all_system_data(self) -> int:
        """
        Invalidate all system-related cache data.
        
        Returns:
            Number of keys invalidated
        """
        patterns = [
            "swe-agent:system_overview:*", 
            "swe-agent:health:*", 
            "swe-agent:tasks:*", 
            # "swe-agent:workflows:*",  # Removed - workflow system deleted
            "swe-agent:agents:*",
            "swe-agent:mcp_servers:*"
        ]
        total_deleted = 0
        
        for pattern in patterns:
            deleted = self.cache.invalidate_pattern(pattern)
            total_deleted += deleted
            
        return total_deleted
    
    def invalidate_all_swe_agent_data(self) -> int:
        """
        Invalidate all swe-agent cache data using pattern matching.
        
        Returns:
            Number of keys invalidated
        """
        return self.cache.invalidate_pattern("swe-agent:*")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about cached system data.
        
        Returns:
            Dictionary with cache information
        """
        cache_info = {
            "system_overview": {
                "key": self.SYSTEM_OVERVIEW_KEY,
                "exists": self.cache.exists(self.SYSTEM_OVERVIEW_KEY),
                "ttl": self.cache.get_ttl(self.SYSTEM_OVERVIEW_KEY)
            },
            "health_status": {
                "key": self.HEALTH_STATUS_KEY,
                "exists": self.cache.exists(self.HEALTH_STATUS_KEY),
                "ttl": self.cache.get_ttl(self.HEALTH_STATUS_KEY)
            },
            "task_stats": {
                "key": self.TASK_STATS_KEY,
                "exists": self.cache.exists(self.TASK_STATS_KEY),
                "ttl": self.cache.get_ttl(self.TASK_STATS_KEY)
            },
            "cache_provider": {
                "initialized": self.cache.is_initialized(),
                "stats": self.cache.get_stats()
            }
        }
                
        return cache_info
    
    def get_repository_metrics_key(self, repository: str, date: str) -> str:
        """
        Generate cache key for repository metrics.
        
        Args:
            repository: Repository name
            date: Date string in YYYY-MM-DD format
            
        Returns:
            Cache key for the repository metrics
        """
        return self.REPOSITORY_METRICS_KEY_PATTERN.format(repository=repository, date=date)
    
    def get_repository_metrics(self, repository: str, date: str) -> Optional[Dict[str, Any]]:
        """
        Get repository metrics from cache.
        
        Args:
            repository: Repository name
            date: Date string in YYYY-MM-DD format
            
        Returns:
            Repository metrics data or None if not found
        """
        cache_key = self.get_repository_metrics_key(repository, date)
        return self.cache.get(cache_key)
    
    def set_repository_metrics(self, repository: str, date: str, metrics_data: Dict[str, Any]) -> bool:
        """
        Store repository metrics in cache.
        
        Args:
            repository: Repository name
            date: Date string in YYYY-MM-DD format
            metrics_data: Repository metrics data to store
            
        Returns:
            True if successful, False otherwise
        """
        cache_key = self.get_repository_metrics_key(repository, date)
        return self.cache.set(
            key=cache_key,
            value=metrics_data,
            ttl=self.REPOSITORY_METRICS_TTL
        )
    
    def delete_repository_metrics(self, repository: str, date: str) -> bool:
        """
        Delete repository metrics from cache.
        
        Args:
            repository: Repository name
            date: Date string in YYYY-MM-DD format
            
        Returns:
            True if successful, False otherwise
        """
        cache_key = self.get_repository_metrics_key(repository, date)
        return self.cache.delete(cache_key)
    
    def repository_metrics_exists(self, repository: str, date: str) -> bool:
        """
        Check if repository metrics exist in cache.
        
        Args:
            repository: Repository name
            date: Date string in YYYY-MM-DD format
            
        Returns:
            True if metrics exist, False otherwise
        """
        cache_key = self.get_repository_metrics_key(repository, date)
        return self.cache.exists(cache_key)

    def refresh_system_overview(self, fetch_func: Callable) -> Optional[Dict[str, Any]]:
        """
        Force refresh system overview data by invalidating cache and fetching fresh data.
        
        Args:
            fetch_func: Function to fetch fresh system overview data
            
        Returns:
            Fresh system overview data or None if unavailable
        """
        # Invalidate existing cache
        self.invalidate_system_overview()
        
        # Fetch fresh data
        try:
            fresh_data = fetch_func()
            if fresh_data:
                # Cache the fresh data
                self.cache.set(
                    key=self.SYSTEM_OVERVIEW_KEY,
                    value=fresh_data,
                    ttl=self.SYSTEM_OVERVIEW_TTL
                )
            return fresh_data
        except Exception as e:
            logger.error(f"Failed to refresh system overview data: {e}")
            return None


# Global cache service instance
cache_service = CacheService() 