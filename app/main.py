"""
FastAPI application entry point.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from app.portal.client import portal_client
from app.routers import meters as meters_router
from app.routers import transformers as transformers_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up - authenticating with portal...")
    await portal_client.login()
    yield
    logger.info("Shutting down - closing portal connection...")
    await portal_client.close()


app = FastAPI(
    title="Urja Meter Ops API",
    description=(
        "A clean REST API service over the Urja Meter Ops portal. "
        "Exposes smart-meter inventories, consumption readings, and the distribution "
        "network hierarchy."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

# Routers
app.include_router(meters_router.router)
app.include_router(transformers_router.router)


@app.get("/health", tags=["Health"], summary="Service health check")
async def health():
    return {"status": "ok", "service": "urja-meter-ops-api", "version": "1.0.0"}


@app.get("/docs", include_in_schema=False, response_class=HTMLResponse)
async def scalar_docs():
    """Interactive documentation rendered via Scalar UI."""
    return HTMLResponse("""<!DOCTYPE html>
<html>
<head>
  <title>Urja Meter Ops API</title>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
</head>
<body>
  <script
    id="api-reference"
    data-url="/openapi.json"
    src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>""")


@app.get("/openapi.json", include_in_schema=False)
async def openapi_spec():
    """Serve OpenAPI 3.1 specification."""
    return JSONResponse(app.openapi())
