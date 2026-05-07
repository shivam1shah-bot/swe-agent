"""
Redis client implementation for caching.
"""

import json
import logging
import time
import redis
from typing import Any, Dict, Optional
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Redis client wrapper for caching operations.
    
    Provides a simplified interface for cache operations with proper
    error handling and serialization.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Redis client with configuration.
        
        Args:
            config: Redis configuration dictionary
        """
        self.config = config
        self.client: Optional[redis.Redis] = None
        self._initialized = False
        
    def initialize(self) -> None:
        """Initialize the Redis connection."""
        if self._initialized:
            logger.warning("Redis client already initialized")
            return
            
        try:
            self.client = redis.Redis(
                host=self.config.get('host', 'localhost'),
                port=self.config.get('port', 6379),
                db=self.config.get('db', 0),
                password=self.config.get('password', '') or None,
                socket_timeout=self.config.get('timeout', 5),
                socket_connect_timeout=self.config.get('timeout', 5),
                health_check_interval=30,
                decode_responses=True
            )
            
            # Test connection
            self.client.ping()
            self._initialized = True
            logger.info(f"Redis client initialized successfully (host: {self.config.get('host')})")
            
        except RedisConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            raise
    
    def is_initialized(self) -> bool:
        """Check if Redis client is initialized."""
        return self._initialized
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        if not self._initialized or not self.client:
            logger.warning("Redis client not initialized")
            return None
            
        try:
            value = self.client.get(key)
            if value is None:
                return None
                
            # Try to deserialize JSON, fallback to string
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
                
        except RedisError as e:
            logger.error(f"Failed to get key {key} from Redis: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None, nx: bool = False) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            nx: Only set if key does not exist
            
        Returns:
            True if successful, False otherwise
        """
        if not self._initialized or not self.client:
            logger.warning("Redis client not initialized")
            return False
            
        try:
            # Serialize value to JSON if it's not a string
            if isinstance(value, (dict, list, int, float, bool)):
                serialized_value = json.dumps(value)
            else:
                serialized_value = str(value)
                
            result = self.client.set(key, serialized_value, ex=ttl, nx=nx)
            return bool(result)
            
        except RedisError as e:
            logger.error(f"Failed to set key {key} in Redis: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error setting key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not self._initialized or not self.client:
            logger.warning("Redis client not initialized")
            return False
            
        try:
            result = self.client.delete(key)
            return result > 0
            
        except RedisError as e:
            logger.error(f"Failed to delete key {key} from Redis: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting key {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key to check
            
        Returns:
            True if key exists, False otherwise
        """
        if not self._initialized or not self.client:
            return False
            
        try:
            return bool(self.client.exists(key))
        except RedisError as e:
            logger.error(f"Failed to check existence of key {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking key {key}: {e}")
            return False
    
    def get_ttl(self, key: str) -> Optional[int]:
        """
        Get time to live for a key.
        
        Args:
            key: Cache key
            
        Returns:
            TTL in seconds, -1 if no expiry, -2 if key doesn't exist, None on error
        """
        if not self._initialized or not self.client:
            return None
            
        try:
            return self.client.ttl(key)
        except RedisError as e:
            logger.error(f"Failed to get TTL for key {key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting TTL for key {key}: {e}")
            return None
    
    def flush_db(self) -> bool:
        """
        Flush all keys from current database.
        
        Returns:
            True if successful, False otherwise
        """
        if not self._initialized or not self.client:
            logger.warning("Redis client not initialized")
            return False
            
        try:
            self.client.flushdb()
            return True
        except RedisError as e:
            logger.error(f"Failed to flush Redis database: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error flushing database: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Redis connection.
        
        Returns:
            Health check results
        """
        if not self._initialized or not self.client:
            return {
                "status": "error",
                "message": "Redis client not initialized"
            }
            
        try:
            start_time = time.time()
            self.client.ping()
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "message": "Redis connection successful",
                "response_time_ms": round(response_time, 2)
            }
        except RedisConnectionError as e:
            return {
                "status": "error", 
                "message": f"Redis connection failed: {str(e)}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Redis health check failed: {str(e)}"
            }
    
    def ping(self) -> bool:
        """
        Ping Redis server to check connection.
        
        Returns:
            True if ping successful, False otherwise
        """
        if not self._initialized or not self.client:
            logger.warning("Redis client not initialized")
            return False
            
        try:
            result = self.client.ping()
            return bool(result)
        except RedisError as e:
            logger.error(f"Redis ping failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error pinging Redis: {e}")
            return False

    def close(self) -> None:
        """Close Redis connection."""
        if self.client:
            try:
                self.client.close()
                logger.info("Redis client connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
            finally:
                self.client = None
                self._initialized = False


# Global Redis client instance
_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    """
    Get a singleton Redis client instance.
    
    Returns:
        RedisClient: Configured Redis client instance
    """
    global _redis_client
    
    if _redis_client is None:
        from ..config_loader import get_config
        config = get_config()
        redis_config = config.get('cache', {}).get('redis', {})
        
        _redis_client = RedisClient(redis_config)
        _redis_client.initialize()
    
    return _redis_client 