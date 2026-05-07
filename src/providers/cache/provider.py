"""
Cache Provider

Main cache provider implementation with support for Redis/ElastiCache.
"""

import logging
import time
from typing import Callable
from typing import Any, Dict, Optional

from .redis_client import RedisClient
from src.providers.telemetry.instrumentation.cache import track_cache_op

logger = logging.getLogger(__name__)

# Ordered list of (prefix, pattern_label) tuples for cache key categorization.
# Order matters: more specific prefixes should come before generic ones.
# This keeps cardinality low while providing meaningful context.
_CACHE_KEY_PATTERNS = (
    # GitHub authentication & health
    ("github:token", "github:auth"),
    ("github_health", "github:health"),
    ("github:", "github:*"),
    # SWE Agent domain-specific keys
    ("swe-agent:health", "health:*"),
    ("swe-agent:tasks", "tasks:*"),
    ("swe-agent:agents", "agents:*"),
    ("swe-agent:mcp_servers", "mcp:*"),
    ("swe-agent:system_overview", "system:*"),
    ("swe-agent:repo_metrics", "repo_metrics:*"),
    ("swe-agent:", "swe-agent:*"),
    # Legacy/generic patterns
    ("user:", "user:*"),
    ("task:", "task:*"),
    ("session:", "session:*"),
)


class CacheProvider:
    """
    Main cache provider that manages caching operations.
    
    This provider supports Redis/ElastiCache as the backend and provides
    a unified interface for caching operations with TTL support.
    """
    
    def __init__(self):
        """Initialize the cache provider."""
        self._initialized = False
        self._client: Optional[RedisClient] = None
        self._config: Dict[str, Any] = {}
        
    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the cache provider with configuration.
        
        Args:
            config: Configuration dictionary containing cache settings
        """
        if self._initialized:
            logger.warning("Cache provider already initialized")
            return
            
        logger.info("Initializing cache provider")
        
        # Extract cache configuration
        cache_config = config.get("cache", {}).get("redis", {})
        if not cache_config:
            logger.warning("No cache configuration found, using defaults")
            cache_config = self._get_default_config()
        else:
            # Log configuration with sensitive data masked
            masked_config = self._mask_sensitive_config(cache_config)
            logger.info(f"Using cache configuration: {masked_config}")
        
        self._config = cache_config
        
        # Initialize Redis client
        self._client = RedisClient(cache_config)
        
        try:
            self._client.initialize()
            self._initialized = True
            logger.info("Cache provider initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize cache provider: {e}")
            # Don't raise the exception - allow the system to continue without cache
            self._client = None
            self._initialized = False
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default cache configuration."""
        return {
            "host": "localhost",
            "port": 6379,
            "db": 0,
            "password": "",
            "timeout": 5
        }
    
    def _mask_sensitive_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive configuration values."""
        masked = config.copy()
        if 'password' in masked and masked['password']:
            masked['password'] = '***masked***'
        return masked
    
    def is_initialized(self) -> bool:
        """Check if the cache provider is initialized."""
        return self._initialized and self._client is not None

    def _key_pattern(self, key: str) -> str:
        """
        Convert a cache key into a low-cardinality pattern label.
        
        Uses ordered prefix matching to categorize keys into meaningful groups
        while keeping metric cardinality low.
        
        Examples:
            - "github:token" -> "github:auth"
            - "github:token:metadata" -> "github:auth"
            - "swe-agent:tasks:stats" -> "tasks:*"
            - "swe-agent:health:status" -> "health:*"
            - "unknown_key" -> "misc:*"
        """
        if not key:
            return "misc:*"
        for prefix, pattern_label in _CACHE_KEY_PATTERNS:
            if key.startswith(prefix):
                return pattern_label
        return "misc:*"
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or cache unavailable
        """
        if not self.is_initialized():
            logger.debug("Cache provider not initialized, returning None")
            return None
            
        try:
            with track_cache_op("get", self._key_pattern(key)):
                return self._client.get(key)
        except Exception as e:
            logger.error(f"Cache get operation failed for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: no expiry)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_initialized():
            logger.debug("Cache provider not initialized, skipping set operation")
            return False
            
        try:
            with track_cache_op("set", self._key_pattern(key)):
                return self._client.set(key, value, ttl)
        except Exception as e:
            logger.error(f"Cache set operation failed for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_initialized():
            logger.debug("Cache provider not initialized, skipping delete operation")
            return False
            
        try:
            with track_cache_op("delete", self._key_pattern(key)):
                return self._client.delete(key)
        except Exception as e:
            logger.error(f"Cache delete operation failed for key {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key to check
            
        Returns:
            True if key exists, False otherwise
        """
        if not self.is_initialized():
            return False
            
        try:
            with track_cache_op("exists", self._key_pattern(key)):
                return self._client.exists(key)
        except Exception as e:
            logger.error(f"Cache exists operation failed for key {key}: {e}")
            return False
    
    def get_ttl(self, key: str) -> Optional[int]:
        """
        Get time to live for a key.
        
        Args:
            key: Cache key
            
        Returns:
            TTL in seconds, -1 if no expiry, -2 if key doesn't exist, None on error
        """
        if not self.is_initialized():
            return None
            
        try:
            with track_cache_op("ttl", self._key_pattern(key)):
                return self._client.get_ttl(key)
        except Exception as e:
            logger.error(f"Cache TTL operation failed for key {key}: {e}")
            return None
    
    def get_or_set(self, key: str, value_func, ttl: Optional[int] = None) -> Any:
        """
        Get value from cache or set it if not found (cache-aside pattern).
        
        Args:
            key: Cache key
            value_func: Function to call to get the value if not in cache
            ttl: Time to live in seconds
            
        Returns:
            Cached value or value from function
        """
        # Try to get from cache first
        cached_value = self.get(key)
        if cached_value is not None:
            logger.debug(f"Cache hit for key: {key}")
            return cached_value
        
        logger.debug(f"Cache miss for key: {key}, fetching fresh data")
        
        # Get fresh value
        try:
            # Count the cache miss as part of 'get_or_set' latency too (bounded label).
            with track_cache_op("get_or_set", self._key_pattern(key)):
                fresh_value = value_func()
                
                # Set in cache for next time
                if fresh_value is not None:
                    self.set(key, fresh_value, ttl)
                    
                return fresh_value
        except Exception as e:
            logger.error(f"Failed to get fresh value for key {key}: {e}")
            return None
    
    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.
        
        Args:
            pattern: Redis pattern (e.g., "system_overview:*")
            
        Returns:
            Number of keys deleted
        """
        if not self.is_initialized():
            return 0
            
        try:
            if not self._client.client:
                return 0
                
            keys = self._client.client.keys(pattern)
            if keys:
                deleted = self._client.client.delete(*keys)
                logger.info(f"Invalidated {deleted} keys matching pattern: {pattern}")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Failed to invalidate pattern {pattern}: {e}")
            return 0
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on cache connection.
        
        Returns:
            Health check results
        """
        if not self.is_initialized():
            return {
                "status": "error",
                "message": "Cache provider not initialized"
            }
            
        try:
            return self._client.health_check()
        except Exception as e:
            return {
                "status": "error",
                "message": f"Cache health check failed: {str(e)}"
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary containing cache statistics
        """
        if not self.is_initialized():
            return {"status": "not_initialized"}
            
        try:
            if not self._client.client:
                return {"status": "no_client"}
                
            info = self._client.client.info()
            return {
                "status": "healthy",
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                )
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"status": "error", "message": str(e)}
    
    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """Calculate cache hit rate percentage."""
        total = hits + misses
        if total == 0:
            return 0.0
        return round((hits / total) * 100, 2)
    
    def close(self) -> None:
        """Close cache provider and cleanup resources."""
        if not self._initialized:
            return
            
        logger.info("Closing cache provider")
        
        if self._client:
            self._client.close()
            
        self._initialized = False
        self._client = None
        self._config = {}
        
        logger.info("Cache provider closed")


# Global cache provider instance
cache_provider = CacheProvider() 