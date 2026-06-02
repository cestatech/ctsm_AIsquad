from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.exceptions import (
    ArtifactLockedError,
    AuthenticationError,
    CeleriusError,
    RateLimitError,
    WorkflowError,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connection, warm caches
    from app.db.session import engine

    async with engine.begin() as conn:
        await conn.run_sync(lambda c: None)  # connection check
    yield
    # Shutdown: close DB pool
    await engine.dispose()


app = FastAPI(
    title="TrialGenesis Clinical Trial Lifecycle Platform",
    version=settings.APP_VERSION,
    description="AI-native multi-tenant platform for clinical trial lifecycle management.",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)

# CORS — never wildcard in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.APP_ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(api_v1_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Exception handlers — structured error responses, no stack traces to clients
# ---------------------------------------------------------------------------


@app.exception_handler(WorkflowError)
async def workflow_error_handler(request: Request, exc: WorkflowError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(ArtifactLockedError)
async def locked_error_handler(
    request: Request, exc: ArtifactLockedError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(AuthenticationError)
async def auth_error_handler(
    request: Request, exc: AuthenticationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(RateLimitError)
async def rate_limit_handler(request: Request, exc: RateLimitError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": exc.message, "code": exc.code},
        headers={"Retry-After": str(exc.retry_after_seconds)},
    )


@app.exception_handler(CeleriusError)
async def celerius_error_handler(request: Request, exc: CeleriusError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": exc.message, "code": exc.code},
    )


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Health check endpoint for load balancers."""
    return {"status": "ok", "version": settings.APP_VERSION}
