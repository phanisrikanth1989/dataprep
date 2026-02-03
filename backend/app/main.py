"""
FastAPI application factory
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    app = FastAPI(
        title="RecDataPrep UI API",
        description="API for RecDataPrep ETL visual designer",
        version="0.1.0",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:4200",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:4200",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import routes
    from app.routes import jobs, components, execution, metadata, filesystem, connections

    # Include routers
    app.include_router(jobs.router)
    app.include_router(components.router)
    app.include_router(execution.router)
    app.include_router(metadata.router)
    app.include_router(filesystem.router)
    app.include_router(connections.router)

    # Health check endpoint
    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "name": "RecDataPrep UI API",
            "version": "0.1.0",
            "docs": "/docs",
        }

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Global exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    logger.info("FastAPI application created successfully")
    return app


app = create_app()
