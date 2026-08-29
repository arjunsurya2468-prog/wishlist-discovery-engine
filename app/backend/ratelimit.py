"""Live-run rate limiting — P5 (§7.8, §10).

In-memory session-based limiter: config.LIVE_RUN_MAX_PER_SESSION runs per session,
with config.LIVE_RUN_COOLDOWN_SEC between runs. A rate-limited run degrades
silently — the static baseline stays visible.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from pipeline import config


@dataclass
class _Session:
    count: int = 0
    last_run: float = 0.0


# In-memory store keyed by session_id. Acceptable for a single-service deploy
# with low traffic (evaluator tool, not production).
_sessions: dict[str, _Session] = {}


def check(session_id: str) -> tuple[bool, str]:
    """Return (allowed, reason). If not allowed, reason explains why."""
    sess = _sessions.setdefault(session_id, _Session())

    if sess.count >= config.LIVE_RUN_MAX_PER_SESSION:
        return False, f"Session limit reached ({config.LIVE_RUN_MAX_PER_SESSION} runs max)"

    elapsed = time.time() - sess.last_run
    if sess.last_run and elapsed < config.LIVE_RUN_COOLDOWN_SEC:
        remaining = int(config.LIVE_RUN_COOLDOWN_SEC - elapsed)
        return False, f"Cooldown active — wait {remaining}s"

    return True, ""


def record(session_id: str) -> None:
    """Record a completed run for the session."""
    sess = _sessions.setdefault(session_id, _Session())
    sess.count += 1
    sess.last_run = time.time()


def status(session_id: str) -> dict:
    """Return current session status for UI display."""
    sess = _sessions.get(session_id, _Session())
    remaining = max(0, config.LIVE_RUN_MAX_PER_SESSION - sess.count)
    cooldown_left = 0
    if sess.last_run:
        cooldown_left = max(0, int(config.LIVE_RUN_COOLDOWN_SEC - (time.time() - sess.last_run)))
    return {
        "runs_remaining": remaining,
        "cooldown_seconds": cooldown_left,
        "max_per_session": config.LIVE_RUN_MAX_PER_SESSION,
    }


# ---- Per-IP limiter (independent of the cookie session) ----
# The session cap keys on a client-controlled cookie, so dropping the cookie bypasses
# it. This rolling-window per-IP cap closes that hole and bounds total cost/frequency.
@dataclass
class _IpBucket:
    hits: list[float] = field(default_factory=list)


_ip_buckets: dict[str, _IpBucket] = {}


def check_ip(ip: str, *, max_per_window: int | None = None, noun: str = "runs") -> tuple[bool, str]:
    """Return (allowed, reason) for the given bucket key over the rolling window.

    `ip` is a BUCKET KEY, not necessarily a bare address. Callers that guard a different
    endpoint must namespace it (e.g. f"suggest:{ip}") — otherwise two endpoints share one
    budget and clicks on the cheap one lock the expensive one out. `max_per_window` defaults
    to the live-run cap so existing callers are unchanged.
    """
    cap = config.LIVE_RUN_IP_MAX_PER_WINDOW if max_per_window is None else max_per_window
    now = time.time()
    bucket = _ip_buckets.setdefault(ip, _IpBucket())
    bucket.hits = [t for t in bucket.hits if now - t < config.LIVE_RUN_IP_WINDOW_SEC]
    if len(bucket.hits) >= cap:
        window_min = config.LIVE_RUN_IP_WINDOW_SEC // 60
        return False, f"Too many {noun} from this network ({cap}/{window_min}min) — try later"
    return True, ""


def record_ip(ip: str) -> None:
    """Record a completed run against the bucket key's rolling window."""
    _ip_buckets.setdefault(ip, _IpBucket()).hits.append(time.time())
