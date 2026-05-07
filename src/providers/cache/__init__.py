"""
Cache Provider Package

This package contains cache provider implementations for Redis/ElastiCache
and other caching solutions.
"""

from .provider import CacheProvider, cache_provider
from .redis_client import RedisClient

__all__ = [
    "CacheProvider",
    "cache_provider", 
    "RedisClient"
]

__version__ = "1.0.0" 