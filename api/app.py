"""FastAPI application for DataPrep ETL Engine."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.jobs import router as jobs_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="DataPrep ETL Engine API",
    version="1.0.0",
    description="API for uploading, running, and monitoring ETL jobs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router, prefix="/api/jobs", tags=["jobs"])


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
