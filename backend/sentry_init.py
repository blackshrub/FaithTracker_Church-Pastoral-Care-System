"""
Sentry initialization for FaithTracker (Litestar + self-hosted GlitchTip).

Activates on the presence of `SENTRY_DSN`; otherwise stays dormant so dev
boxes don't ship to the prod dashboard. sentry-sdk auto-wraps ASGI apps,
so no Litestar-specific integration is required — exceptions from route
handlers, middleware, and lifespan all flow through automatically.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

logger = logging.getLogger(__name__)

_SENSITIVE_KEY = re.compile(
    r"^(authorization|cookie|set-cookie|password|passwd|token|secret|api[_-]?key)$",
    re.IGNORECASE,
)


def _redact(value: Any, seen: set[int] | None = None) -> Any:
    """Recursively scrub sensitive header/body fields before they ship."""
    if seen is None:
        seen = set()
    if isinstance(value, dict):
        if id(value) in seen:
            return value
        seen.add(id(value))
        return {
            k: ("[redacted]" if _SENSITIVE_KEY.match(k) else _redact(v, seen))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v, seen) for v in value]
    return value


def _before_send(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    # Drop health-probe 503s. /health/scheduler intentionally raises
    # HTTPException(503) as a liveness signal when the digest looks stale;
    # that's by-design probe output, not an application error.
    exc_info = _hint.get("exc_info")
    if exc_info and len(exc_info) >= 2:
        status = getattr(exc_info[1], "status_code", None)
        if status == 503:
            url = (event.get("request") or {}).get("url") or event.get("transaction") or ""
            if "/health" in url:
                return None

    # Drop transient connection errors — they're noise vs real bugs.
    exc = event.get("exception", {}).get("values", [])
    for v in exc:
        msg = (v.get("value") or "").lower()
        if any(p in msg for p in ("connection reset", "broken pipe", "client disconnected")):
            return None
    return _redact(event)


def init_sentry() -> bool:
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        logger.info("Sentry: SENTRY_DSN not set; staying dormant.")
        return False

    try:
        traces_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.05"))
    except ValueError:
        traces_rate = 0.05

    environment = os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "unknown"

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_rate,
        profiles_sample_rate=0.0,
        send_default_pii=False,
        integrations=[
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        before_send=_before_send,
    )
    logger.info(f"Sentry: initialized (env={environment}, traces={traces_rate})")
    return True
