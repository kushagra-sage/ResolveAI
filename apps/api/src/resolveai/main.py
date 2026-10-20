from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from resolveai.adapter_runtime import build_adapter_registry
from resolveai.config import Settings, get_settings
from resolveai.database import create_database_engine, create_session_factory
from resolveai.embeddings import HashEmbeddingProvider
from resolveai.observability import RequestMetricsMiddleware, metrics_response
from resolveai.routers import (
    commerce,
    commerce_facts,
    console,
    customers,
    health,
    identity,
    integrations,
    knowledge,
    operations,
    resolutions,
)
from resolveai.telemetry import configure_telemetry


def create_app(*, settings: Settings | None = None, database_url: str | None = None) -> FastAPI:
    configure_telemetry()
    resolved_settings = settings or get_settings()
    engine = create_database_engine(database_url or resolved_settings.database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> Any:
        yield
        engine.dispose()

    application = FastAPI(
        title="ResolveAI API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.engine = engine
    application.state.session_factory = session_factory
    application.state.embedding_provider = HashEmbeddingProvider()
    application.state.adapter_registry = build_adapter_registry(resolved_settings)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "Traceparent"],
    )
    application.add_middleware(RequestMetricsMiddleware)
    application.include_router(health.router)
    application.include_router(identity.router)
    application.include_router(customers.router)
    application.include_router(knowledge.router)
    application.include_router(integrations.router)
    application.include_router(resolutions.router)
    application.include_router(operations.router)
    application.include_router(commerce.router)
    application.include_router(commerce_facts.router)
    application.include_router(console.router)
    application.add_api_route(
        "/metrics", metrics_response, methods=["GET"], include_in_schema=False
    )
    return application


app = create_app()
