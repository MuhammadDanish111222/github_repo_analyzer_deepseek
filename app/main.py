from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.exceptions import RepoAnalyzerError
from app.schemas import AnalyzeRepoRequest, AnalyzeRepoResponse, ErrorResponse
from app.services.deepseek_service import DeepSeekAnalyzerService
from app.services.github_service import GitHubRepositoryService


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    logging.getLogger(__name__).info("Starting %s in %s mode", settings.app_name, settings.app_env)
    yield


app = FastAPI(
    title="Live GitHub Repository Analyzer API",
    version="1.0.0",
    description="Fetches a public GitHub repository's primary source file and analyzes it with DeepSeek.",
    lifespan=lifespan,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)

def get_cors_origins() -> list[str]:
    settings = get_settings()
    configured_origins = [
        origin.strip()
        for origin in settings.allowed_origins.split(",")
        if origin.strip()
    ]

    # In production, do not use a wildcard CORS policy. The API is intended
    # for server-to-server POST requests and same-origin Swagger testing.
    if settings.app_env == "production":
        return configured_origins

    return configured_origins or ["http://localhost:3000", "http://localhost:8000"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.exception_handler(RepoAnalyzerError)
async def repo_analyzer_error_handler(_: Request, exc: RepoAnalyzerError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "detail": exc.public_message},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"status": "error", "detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logging.getLogger(__name__).exception("Unhandled server error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "detail": "Internal server error."},
    )


def get_github_service(settings: Settings = Depends(get_settings)) -> GitHubRepositoryService:
    return GitHubRepositoryService(settings)


def get_deepseek_service(settings: Settings = Depends(get_settings)) -> DeepSeekAnalyzerService:
    return DeepSeekAnalyzerService(settings)


@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    return {
        "status": "running",
        "message": "Live GitHub Repository Analyzer API",
        "docs": "/docs",
        "analyze_endpoint": "/api/analyze-repo",
    }


@app.get("/healthz", tags=["Health"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/analyze-repo",
    response_model=AnalyzeRepoResponse,
    tags=["Analyzer"],
    summary="Analyze a public GitHub repository with DeepSeek",
)
async def analyze_repo(
    payload: AnalyzeRepoRequest,
    github_service: GitHubRepositoryService = Depends(get_github_service),
    deepseek_service: DeepSeekAnalyzerService = Depends(get_deepseek_service),
) -> AnalyzeRepoResponse:
    source_file = await github_service.fetch_primary_source_file(payload.repo_url)
    analysis = await deepseek_service.analyze_source(source_file)

    return AnalyzeRepoResponse(
        status="success",
        repo_name=source_file.repo_name,
        vulnerabilities_found=analysis.vulnerabilities_found,
        suggestions=analysis.suggestions,
    )
