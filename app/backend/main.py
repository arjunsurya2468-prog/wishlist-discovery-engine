"""FastAPI app.

Serves GET /healthz + POST /api/live-run (and the built static artifact once a
publish run has produced one). Keys stay server-side. The static fallback
(app/static/analysis.json) must render even with this backend down — it is the
uptime guarantee, not the live run.

STEP 7: startup is gated on the taxonomy corpus fingerprint (see _lifespan). A
deployment carrying a taxonomy from another corpus fails to boot rather than serving
plausible wrong answers.

Deferred imports (fastapi) so the pipeline never depends on the web stack.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import live_run as lr
from . import ratelimit

log = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent.parent  # /app
FRONTEND_DIR = APP_DIR / "frontend"
STATIC_DIR = APP_DIR / "static"

SESSION_COOKIE = "wde_session"


class LiveRunRequest(BaseModel):
    app: str  # a key of config.APPS — "Myntra" | "AJIO" | "Nykaa Fashion"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """STEP 7 HARD GATE — verify the taxonomy's corpus fingerprint before serving.

    This runs BEFORE the port binds. A taxonomy that cannot prove it came from this
    project's corpus raises here and the deploy fails loudly, which is the entire point:
    a mismatched taxonomy does not error at request time, it silently returns confident
    wrong answers. Failing at boot is the only cheap place to catch it.

    ALLOW_UNVERIFIED_TAXONOMY exists for local development against a partially built
    taxonomy. It is deliberately awkward to set, logs a loud warning, and must never be
    set in a deployed environment.
    """
    import os

    from pipeline import config

    try:
        app.state.taxonomy_fingerprint = lr.assert_taxonomy_ready()
    except Exception as e:
        if os.getenv("ALLOW_UNVERIFIED_TAXONOMY") == "i-know-this-is-wrong":
            log.warning(
                "TAXONOMY GATE BYPASSED — serving an unverified taxonomy. "
                "Cluster assignments may be meaningless. Never do this in a deploy. (%s)", e
            )
            app.state.taxonomy_fingerprint = None
        else:
            log.error("TAXONOMY GATE FAILED — refusing to start.\n%s", e)
            raise

    if not config.OPENROUTER_API_KEY:
        log.warning("no OPENROUTER_API_KEY — embedding calls on the live path will fail")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Wishlist Discovery Engine",
        description="Discovery Intelligence Dashboard — Static Fallback + Bounded Live Run",
        version="1.0.0",
        lifespan=_lifespan,
    )

    # CORS — permissive for evaluator use (single-origin deploy anyway)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- Health Check ----
    @app.get("/healthz")
    async def healthz():
        """Liveness + which corpus the serving taxonomy was actually built from.

        Surfacing the fingerprint here makes "is this deploy serving the right
        taxonomy?" answerable from outside the box, without reading logs.
        """
        fingerprint = getattr(app.state, "taxonomy_fingerprint", None)
        return {
            "status": "ok",
            "taxonomy_verified": fingerprint is not None,
            "taxonomy": {
                "domain": (fingerprint or {}).get("domain"),
                "apps": (fingerprint or {}).get("apps"),
                "corpus_hash": (fingerprint or {}).get("corpus_hash"),
                "n_records": (fingerprint or {}).get("n_records"),
                "embedding_model": (fingerprint or {}).get("embedding_model"),
            },
        }

    # ---- Session management ----
    def _session_id(request: Request, response: Response) -> str:
        sid = request.cookies.get(SESSION_COOKIE)
        if not sid:
            sid = uuid.uuid4().hex[:16]
            response.set_cookie(SESSION_COOKIE, sid, httponly=True, samesite="lax", max_age=86400)
        return sid

    def _client_ip(request: Request) -> str:
        """Client IP for the per-IP cap. Behind Render's proxy, trust the first
        X-Forwarded-For hop; fall back to the socket peer."""
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    # ---- Rate limit status ----
    @app.get("/api/rate-status")
    async def rate_status(request: Request, response: Response):
        sid = _session_id(request, response)
        return ratelimit.status(sid)

    # ---- Live Run ----
    @app.post("/api/live-run")
    async def live_run_endpoint(body: LiveRunRequest, request: Request, response: Response):
        from pipeline import config

        sid = _session_id(request, response)
        ip = _client_ip(request)

        # Per-session cap (cookie) AND per-IP cap (independent — closes the cookie-drop bypass).
        allowed, reason = ratelimit.check(sid)
        if allowed:
            allowed, reason = ratelimit.check_ip(ip)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": reason, **ratelimit.status(sid)},
            )

        # Validate app
        if body.app not in config.APPS:
            raise HTTPException(400, f"Unknown app: {body.app}. Choose from: {list(config.APPS)}")

        try:
            # Bound total run time: run the blocking pipeline in a thread and cap it so a
            # provider hang returns a fast 504 instead of blocking the request for minutes.
            result = await asyncio.wait_for(
                asyncio.to_thread(lr.run, body.app),
                timeout=config.LIVE_RUN_TIMEOUT_SEC,
            )
            ratelimit.record(sid)
            ratelimit.record_ip(ip)
            return {**result, **ratelimit.status(sid)}
        except asyncio.TimeoutError:
            log.warning("Live run timed out for %s (>%ss)", body.app, config.LIVE_RUN_TIMEOUT_SEC)
            return JSONResponse(
                status_code=504,
                content={
                    "error": "Live run timed out — the pre-computed analysis above is unaffected.",
                    **ratelimit.status(sid),
                },
            )
        except Exception as e:
            log.exception("Live run failed for %s", body.app)
            return JSONResponse(
                status_code=500,
                content={"error": f"Live run failed: {str(e)}", **ratelimit.status(sid)},
            )

    # NOTE: the previous build's MVP endpoints (/api/personas, /api/suggest, /engine)
    # were NOT carried forward. They served a cart-suggestion prototype with no analogue
    # in this brief. The MVP for this brief is not yet built.

    # ---- Serve static files ----
    # analysis.json and other static assets. Created by the publish step; mounted only
    # if present so a fresh clone boots before the first pipeline run.
    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    # No frontend was carried forward from the previous build — its dashboard was built
    # around the old brief. Mount one here when this brief's UI exists.
    if FRONTEND_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

    return app


# Entry point: uvicorn app.backend.main:app
app = create_app()
