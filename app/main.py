"""Unified C9 Analytics API - combining Coach, Scout, and Draft assistants."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load .env from api directory
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# Category 1 - Assistant Coach routers
from app.routers import insights, macro_review, what_if

# Category 2 - Scouting Report routers
from app.routers import reports
from app.routers import ask_coach

# Category 3 - Draft Assistant routers
from app.routers import draft, recommendations


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    yield


app = FastAPI(
    title="C9 Analytics API",
    description="Unified Cloud9 esports analytics: Assistant Coach, Scouting Report, and Draft Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Category 1: Assistant Coach ──────────────────────────────────────────────
app.include_router(insights.router, prefix="/api/v1/insights", tags=["coach-insights"])
app.include_router(macro_review.router, prefix="/api/v1/macro-review", tags=["coach-macro-review"])
app.include_router(what_if.router, prefix="/api/v1/what-if", tags=["coach-what-if"])

# ── Category 2: Scouting Report ──────────────────────────────────────────────
app.include_router(reports.router, prefix="/api/v1/report", tags=["scout-reports"])
app.include_router(ask_coach.router, prefix="/api/v1/coach", tags=["scout-coach"])

# ── Category 3: Draft Assistant ───────────────────────────────────────────────
app.include_router(draft.router, prefix="/api/v1/draft", tags=["draft"])
app.include_router(recommendations.router, prefix="/api/v1/recommendations", tags=["draft-recommendations"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "C9 Analytics API",
        "version": "1.0.0",
        "status": "healthy",
        "modules": {
            "coach": "Assistant Coach - Player & team insights, VOD review, what-if analysis",
            "scout": "Scouting Report - Opponent analysis, counter strategies, threat rankings",
            "draft": "Draft Assistant - Champion recommendations, win probability, meta analysis",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
