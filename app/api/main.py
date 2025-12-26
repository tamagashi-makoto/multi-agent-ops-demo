"""FastAPI application for multi-agent workflow API."""

from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import router
from app.api.schemas import HealthResponse
from app.common.config import get_settings
from app.common.logger import get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI app.
    """
    settings = get_settings()

    app = FastAPI(
        title="Multi-Agent Ops Demo API",
        description="""
        Production-ready multi-agent AI system for generating proposals.

        ## Features
        - **Multi-Agent Orchestration**: Planner, Researcher, Writer, Critic agents
        - **RAG Integration**: FAISS-based document retrieval
        - **Guardrails**: Tool allowlist, path restrictions, approval gates
        - **Observability**: Full trace logging with PII masking

        ## Workflow
        1. **POST /run**: Start a new workflow
        2. **GET /status/{run_id}**: Check progress
        3. **POST /approve/{run_id}**: Approve final output
        4. **GET /run/{run_id}**: Get detailed results
        """,
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routes
    app.include_router(router, prefix="/api/v1", tags=["Workflow"])

    # Health check
    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    async def health_check() -> HealthResponse:
        """Health check endpoint."""
        return HealthResponse(
            status="healthy",
            version=__version__,
            timestamp=datetime.utcnow().isoformat(),
        )

    # Root redirect
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with API info."""
        return {
            "name": "Multi-Agent Ops Demo API",
            "version": __version__,
            "docs": "/docs",
            "health": "/health",
        }

    logger.info(f"Created FastAPI app version {__version__}")

    return app


# Create default app instance
app = create_app()


def run_server():
    """Run the API server."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )


if __name__ == "__main__":
    run_server()
