"""Application factory: each worker owns its pool and closes it on graceful shutdown."""

from typing import AsyncGenerator
# from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.core.database import create_engine
from app.core.errors import ErrorHandler
from app.core.security import Security
from app.modules.auth.routes import router as auth_router
from app.modules.tasks.routes import router as tasks_router
from app.modules.users.routes import router as users_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    config = settings or Settings() # type: ignore[call-arg]

    # Application lifespan context manager for resource setup and teardown.
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        engine = create_engine(config)
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            app.state.engine = engine
            app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app.state.security = Security(config)
            app.state.security.dummy_hash = await app.state.security.hash_password(
                "dummy-password-never-used"
            )
            yield
        finally:
            await engine.dispose()

    # Initialize the FastAPI application with the configured lifespan context.
    app = FastAPI(
        title="FastAPI Backend Architecture Showcase",
        version="0.1.0",
        lifespan=lifespan,
        description="Async PostgreSQL, stateless access tokens, rotating refresh sessions and owned tasks.",
    )

    # Configure CORS middleware for cross-origin requests.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[config.client_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Next-Cursor"],
    )

    # Register global exception handlers
    ErrorHandler.register(app)

    # Include application routers for different modules.
    app.include_router(users_router)
    app.include_router(auth_router)
    app.include_router(tasks_router)

    # Health check endpoints for liveness and readiness probes.
    @app.get("/health", tags=["Health"])
    async def health() -> dict[str, str]:
        """Liveness checks the process independently of database availability."""
        return {"status": "ok", "timestamp": datetime.now(UTC).isoformat()}

    # Database readiness check endpoint.
    @app.get("/health/db", tags=["Health"])
    async def ready() -> JSONResponse:
        """Readiness checks dependencies before routing traffic to this worker."""
        try:
            async with app.state.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ok", "database": "postgresql"})

    return app
