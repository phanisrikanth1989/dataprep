"""FastAPI application for DataPrep ETL Engine."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.jobs import router as jobs_router
from .routes.routines import router as routines_router
from .routes.python_routines import router as python_routines_router

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
app.include_router(routines_router, prefix="/api/routines/java", tags=["routines"])
app.include_router(python_routines_router, prefix="/api/routines/python", tags=["python-routines"])


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
