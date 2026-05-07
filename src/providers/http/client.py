"""
Synchronous outbound HTTP wrapper (requests).

Why this exists:
- Centralize external dependency metrics (service + operation grouping)
- Keep Prometheus labels low-cardinality via endpoint templates

IMPORTANT:
- Do NOT pass resolved/dynamic URLs into metric labels.
- Use `endpoint_template` (bounded) + optional `operation` (bounded) for grouping.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, Optional

import requests
from requests import Response

from src.providers.logger import Logger
from src.providers.telemetry.instrumentation.http_client import record_external_api_call

logger = Logger("HTTPClient")

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


def http_request(
    *,
    service: str,
    operation: str,
    endpoint_template: str,
    method: str,
    url: str,
    timeout: Optional[float] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    data: Any = None,
    **kwargs: Any,
) -> Response:
    """
    Make a synchronous HTTP request using `requests`, with dependency metrics.

    Args:
        service: Bounded service label (e.g., "github", "slack")
        operation: Bounded operation/workflow label (e.g., "e2e-onboarding")
        endpoint_template: Low-cardinality endpoint template (e.g., "/repos/{owner}/{repo}/pulls")
        method: HTTP method
        url: Resolved URL (may contain dynamic path/query) - this is NOT used as a label.

    Returns:
        `requests.Response`
    """
    svc = _sanitize_label(service, default="other")
    op = _sanitize_label(operation, default="other")

    # Keep endpoint_template low-cardinality. Truncate defensively.
    tpl = (endpoint_template or "unknown").strip()
    if len(tpl) > 128:
        tpl = tpl[:128]

    m = (method or "GET").strip().upper()
    start = time.perf_counter()
    status_code: int | str = "error"

    try:
        resp = requests.request(
            method=m,
            url=url,
            timeout=timeout,
            headers=headers,
            params=params,
            json=json,
            data=data,
            **kwargs,
        )
        status_code = resp.status_code
        return resp
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


