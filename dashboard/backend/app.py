"""FastAPI dashboard app — setup, lifespan, middleware."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.constants import APP_TITLE, MASTER_KEY_PATH
from backend.endpoints import router
from backend.utils import autofill_settings
from db.connection import connect, close


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Connect to DB on startup, close on shutdown."""
    await connect()
    await autofill_settings(MASTER_KEY_PATH)
    yield
    await close()


app = FastAPI(title=APP_TITLE, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
