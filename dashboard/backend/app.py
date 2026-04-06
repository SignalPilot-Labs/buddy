"""FastAPI dashboard app — setup, lifespan, middleware."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.constants import APP_TITLE, MASTER_KEY_PATH
from backend.endpoints.runs import router as runs_router
from backend.endpoints.settings import router as settings_router
from backend.endpoints.streaming import router as streaming_router
from backend.endpoints.network import router as network_router
from backend.endpoints.parallel import router as parallel_router
from backend.endpoints.tunnel import router as tunnel_router
from backend.utils import autofill_settings
from db.connection import connect, close

_DEFAULT_CORS_ORIGINS = "http://localhost:3400"
_ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
_ALLOWED_HEADERS = ["Content-Type", "X-API-Key", "Authorization"]

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ALLOWED_ORIGINS", _DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_application: FastAPI):
    """Connect to DB on startup, close on shutdown."""
    await connect()
    await autofill_settings(MASTER_KEY_PATH)
    yield
    await close()


app = FastAPI(title=APP_TITLE, lifespan=lifespan)


@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    for header, value in _SECURITY_HEADERS.items():
        response.headers[header] = value
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=_ALLOWED_METHODS,
    allow_headers=_ALLOWED_HEADERS,
)
app.include_router(runs_router)
app.include_router(settings_router)
app.include_router(streaming_router)
app.include_router(network_router)
app.include_router(parallel_router)
app.include_router(tunnel_router)
