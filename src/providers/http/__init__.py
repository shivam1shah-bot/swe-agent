"""
HTTP provider layer.

Central place for outbound HTTP calls so we can:
- apply consistent timeouts / headers (when desired)
- instrument external dependency metrics in one place
"""

from .client import http_request
from .async_client import aiohttp_request

__all__ = [
    "http_request",
    "aiohttp_request",
]


