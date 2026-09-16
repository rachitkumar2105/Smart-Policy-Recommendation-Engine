import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.database import Base, engine
from app.logging_config import configure_logging
from app.routers import health, recommend
from app.routers.recommend import limiter

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is owned by Alembic migrations (see alembic/). This create_all is a
    # convenience net for ad-hoc dev/test runs against a throwaway sqlite file and
    # is a no-op once the tables already exist.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Smart Policy Recommendation Engine",
    version="1.0.0",
    description="Simulates an insurance underwriting workflow: risk profile -> "
    "eligibility filter -> suitability scoring -> risk-adjusted premium.",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

allowed_origins = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:8501").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.include_router(health.router)
app.include_router(recommend.router)
