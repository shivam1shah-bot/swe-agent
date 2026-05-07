"""
Asynchronous outbound HTTP wrapper (aiohttp).

This wraps an existing `aiohttp.ClientSession` so we can:
- keep connection pooling (caller owns the session)
- instrument external dependency metrics consistently
"""

from __future__ import annotations

import re
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

import aiohttp

from src.providers.logger import Logger
from src.providers.telemetry.instrumentation.http_client import record_external_api_call

logger = Logger("AsyncHTTPClient")

_SAFE_LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def _sanitize_label(value: Optional[str], *, default: str) -> str:
    if not value:
        return default
    v = value.strip().lower()
    if not v:
        return default
    if _SAFE_LABEL_RE.match(v):
        return v
    return default


@asynccontextmanager
async def aiohttp_request(
    session: aiohttp.ClientSession,
    *,
    service: str,
    operation: str,
    endpoint_template: str,
    method: str,
    url: str,
    **kwargs: Any,
) -> AsyncGenerator[aiohttp.ClientResponse, None]:
    """
    Async context manager wrapping `session.request(...)` with dependency metrics.

    Usage:
        async with aiohttp_request(session, service="github", operation="e2e-onboarding",
                                  endpoint_template="/rate_limit", method="GET",
                                  url="https://api.github.com/rate_limit") as resp:
            data = await resp.json()
    """
    svc = _sanitize_label(service, default="other")
    op = _sanitize_label(operation, default="other")

    tpl = (endpoint_template or "unknown").strip()
    if len(tpl) > 128:
        tpl = tpl[:128]

    m = (method or "GET").strip().upper()
    start = time.perf_counter()
    status_code: int | str = "error"

    try:
        async with session.request(method=m, url=url, **kwargs) as resp:
            status_code = resp.status
            yield resp
    finally:
        duration = time.perf_counter() - start
        try:
            record_external_api_call(
                service=svc,
                operation=op,
                endpoint_template=tpl,
                method=m,
                status_code=status_code,
                duration=duration,
            )
        except Exception as e:
            logger.debug(
                "Failed to record external API metric",
                extra={
                    "service": svc,
                    "operation": op,
                    "endpoint_template": tpl,
                    "method": m,
                    "url": url,
                    "error": str(e),
                },
            )


