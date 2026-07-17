"""Hardened FastAPI application factory for FreshSense integrations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from contextlib import asynccontextmanager
from io import BytesIO
import logging
import os
import time
import warnings

from fastapi import APIRouter, Depends, FastAPI, File, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from agent.fruit_agent import FruitScannerAgent
from api.errors import ApiProblem
from api.models import AnalyzeResponse, ErrorResponse, HealthResponse, MetricsResponse
from api.observability import (
    MetricsRegistry,
    configure_json_logging,
    request_id_from_header,
)
from api.security import (
    InMemoryRateLimiter,
    RateLimitDecision,
    authenticate_api_key,
    authenticate_request,
    enforce_rate_limit,
    resolve_api_key,
    validate_api_key_configuration,
)
from api.serialization import serialize_agent_state
from utils.config import (
    API_ALLOWED_HOSTS,
    API_CORS_ORIGINS,
    API_JSON_LOGS,
    API_KEY_FILE,
    API_MAX_IMAGE_PIXELS,
    API_MAX_UPLOAD_BYTES,
    API_RATE_LIMIT_PER_MINUTE,
    API_REQUIRE_API_KEY,
    API_REQUIRE_SEMANTIC_RAG,
    FRUIT_CATALOG_PATH,
    KNOWLEDGE_BASE_PATH,
    MODEL_PATH,
    OPEN_SET_GATE_PATH,
    REQUIRE_OPEN_SET_GATE,
)
from utils.startup import StartupValidationError, validate_startup


logger = logging.getLogger("freshsense.api")
AgentFactory = Callable[[], FruitScannerAgent]

ACCEPTED_IMAGE_FORMATS = {
    "image/jpeg": "JPEG",
    "image/jpg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}
MULTIPART_OVERHEAD_ALLOWANCE = 64 * 1024
PROTECTED_API_PATHS = frozenset({"/api/v1/analyze", "/api/v1/metrics"})


def _production_agent_factory() -> FruitScannerAgent:
    validate_startup(
        model_path=MODEL_PATH,
        knowledge_base_path=KNOWLEDGE_BASE_PATH,
        fruit_catalog_path=FRUIT_CATALOG_PATH,
        open_set_gate_path=OPEN_SET_GATE_PATH,
        require_open_set_gate=REQUIRE_OPEN_SET_GATE,
    )
    return FruitScannerAgent(
        model_path=MODEL_PATH,
        catalog_path=FRUIT_CATALOG_PATH,
        knowledge_base_path=KNOWLEDGE_BASE_PATH,
        open_set_gate_path=OPEN_SET_GATE_PATH,
        require_open_set_gate=REQUIRE_OPEN_SET_GATE,
    )


def create_app(
    *,
    agent_factory: AgentFactory | None = None,
    max_upload_bytes: int = API_MAX_UPLOAD_BYTES,
    max_image_pixels: int = API_MAX_IMAGE_PIXELS,
    api_key: str | None = None,
    api_key_file: str | None = API_KEY_FILE,
    require_api_key: bool = API_REQUIRE_API_KEY,
    rate_limit_per_minute: int = API_RATE_LIMIT_PER_MINUTE,
    allowed_hosts: Sequence[str] = API_ALLOWED_HOSTS,
    cors_origins: Sequence[str] = API_CORS_ORIGINS,
    json_logs: bool = API_JSON_LOGS,
    require_semantic_rag: bool = API_REQUIRE_SEMANTIC_RAG,
) -> FastAPI:
    """Create a secured API instance while keeping tests model-free."""
    if max_upload_bytes <= 0:
        raise ValueError("max_upload_bytes must be positive.")
    if max_image_pixels <= 0:
        raise ValueError("max_image_pixels must be positive.")
    if rate_limit_per_minute <= 0:
        raise ValueError("rate_limit_per_minute must be positive.")

    active_hosts = _validate_hosts(allowed_hosts)
    active_origins = _validate_origins(cors_origins)
    factory = agent_factory or _production_agent_factory

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if json_logs:
            configure_json_logging(logger)

        resolved_api_key = resolve_api_key(
            explicit_value=api_key,
            environment_value=os.getenv("FRESHSENSE_API_KEY"),
            secret_file=api_key_file,
        )
        validate_api_key_configuration(resolved_api_key, required=require_api_key)

        agent = await run_in_threadpool(factory)
        if require_semantic_rag and not agent.retriever_tool.semantic_ready:
            raise StartupValidationError(
                "Semantic RAG is required but the local embedding model did not load."
            )

        application.state.agent = agent
        application.state.inference_lock = asyncio.Lock()
        application.state.max_upload_bytes = max_upload_bytes
        application.state.max_image_pixels = max_image_pixels
        application.state.api_key = resolved_api_key
        application.state.authentication_enabled = bool(resolved_api_key) or require_api_key
        application.state.rate_limit_per_minute = rate_limit_per_minute
        application.state.rate_limiter = InMemoryRateLimiter(rate_limit_per_minute)
        application.state.metrics = MetricsRegistry()

        logger.info(
            "FreshSense API started",
            extra={
                "event": "service_started",
                "retrieval_mode": (
                    "semantic" if agent.retriever_tool.semantic_ready else "keyword_fallback"
                ),
            },
        )
        try:
            yield
        finally:
            application.state.agent = None
            application.state.api_key = None
            logger.info("FreshSense API stopped", extra={"event": "service_stopped"})

    application = FastAPI(
        title="FreshSense AI API",
        summary="Private fruit-freshness analysis with local semantic retrieval.",
        description=(
            "A versioned HTTP interface around the FreshSense vision and reasoning agent. "
            "Uploaded images are decoded only for the current request and are not retained "
            "in application storage."
        ),
        version="1.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(active_hosts),
        www_redirect=False,
    )
    if active_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(active_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "X-API-Key", "X-Request-ID"],
            expose_headers=[
                "X-Request-ID",
                "X-RateLimit-Limit",
                "X-RateLimit-Remaining",
                "X-RateLimit-Reset",
            ],
            max_age=600,
        )

    @application.middleware("http")
    async def security_and_observability_middleware(request: Request, call_next):
        request_id = request_id_from_header(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id
        metrics = getattr(request.app.state, "metrics", None)
        if metrics is not None:
            await metrics.request_started()

        started = time.perf_counter()
        status_code = 500
        try:
            problem = _request_preflight_problem(
                request,
                max_upload_bytes=max_upload_bytes,
            )
            if problem is not None:
                response = _problem_response(problem)
            else:
                response = await call_next(request)
            status_code = response.status_code
        finally:
            if metrics is not None:
                await metrics.request_finished(status_code)

        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'"
            )

        logger.info(
            "HTTP request completed",
            extra={
                "event": "request_completed",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    @application.exception_handler(ApiProblem)
    async def api_problem_handler(_request: Request, exc: ApiProblem) -> JSONResponse:
        return _problem_response(exc)

    router = APIRouter(prefix="/api/v1")

    @router.get(
        "/health",
        response_model=HealthResponse,
        tags=["system"],
        summary="Report model and semantic-retrieval readiness",
    )
    async def health(request: Request) -> HealthResponse:
        agent = _active_agent(request)
        retriever = agent.retriever_tool
        semantic_ready = bool(retriever.semantic_ready)
        embedder = retriever.embedder if semantic_ready else None
        return HealthResponse(
            model_loaded=True,
            semantic_retrieval_ready=semantic_ready,
            retrieval_mode="semantic" if semantic_ready else "keyword_fallback",
            semantic_model=(embedder.model_name if embedder is not None else None),
            supported_fruits=[
                fruit.display_name for fruit in agent.catalog.fruits.values()
            ],
            authentication_required=request.app.state.authentication_enabled,
            rate_limit_per_minute=request.app.state.rate_limit_per_minute,
        )

    @router.get(
        "/metrics",
        response_model=MetricsResponse,
        tags=["system"],
        summary="Return process-local operational metrics",
        responses={
            401: {"model": ErrorResponse, "description": "Invalid or missing API key."},
        },
    )
    async def metrics(
        request: Request,
        _identity: str = Depends(authenticate_request),
    ) -> MetricsResponse:
        return await request.app.state.metrics.snapshot()

    @router.post(
        "/analyze",
        response_model=AnalyzeResponse,
        tags=["analysis"],
        summary="Analyze one supported fruit image",
        description=(
            "Accepts one JPEG, PNG, or WebP image. The upload is read only for the "
            "current request, is never copied into application storage, and is disposed "
            "after the response is created."
        ),
        responses={
            400: {"model": ErrorResponse, "description": "Empty or invalid image."},
            401: {"model": ErrorResponse, "description": "Invalid or missing API key."},
            413: {"model": ErrorResponse, "description": "Upload or decoded image too large."},
            415: {"model": ErrorResponse, "description": "Unsupported or mismatched media type."},
            429: {"model": ErrorResponse, "description": "Analysis rate limit exceeded."},
            500: {"model": ErrorResponse, "description": "Analysis failed safely."},
            503: {"model": ErrorResponse, "description": "Model is not ready."},
        },
    )
    async def analyze(
        request: Request,
        response: Response,
        include_explanation: bool = Query(
            False,
            description=(
                "Include an in-memory base64 PNG Grad-CAM overlay when an accepted "
                "prediction has an explanation. The image is still not retained."
            ),
        ),
        file: UploadFile = File(
            ...,
            description="A JPEG, PNG, or WebP photo containing one supported fruit type.",
        ),
        rate_limit: RateLimitDecision = Depends(enforce_rate_limit),
    ) -> AnalyzeResponse:
        for name, value in rate_limit.headers.items():
            response.headers[name] = value

        content_type, data = await _read_upload(
            file,
            max_upload_bytes=request.app.state.max_upload_bytes,
        )
        image = _decode_image(
            data,
            content_type=content_type,
            max_image_pixels=request.app.state.max_image_pixels,
        )
        analysis_started = time.perf_counter()
        success = False
        try:
            agent = _active_agent(request)
            try:
                async with request.app.state.inference_lock:
                    state = await run_in_threadpool(agent.run, image)
                result = serialize_agent_state(
                    state,
                    agent.catalog,
                    include_explanation_overlay=include_explanation,
                )
                success = True
                return result
            except ApiProblem:
                raise
            except Exception as exc:
                logger.exception(
                    "FreshSense analysis failed",
                    extra={
                        "event": "analysis_failed",
                        "request_id": request.state.request_id,
                    },
                )
                raise ApiProblem(
                    500,
                    "ANALYSIS_FAILED",
                    "FreshSense could not complete this analysis.",
                ) from exc
        finally:
            image.close()
            await request.app.state.metrics.analysis_finished(
                success=success,
                duration_seconds=time.perf_counter() - analysis_started,
            )

    application.include_router(router)
    return application


def _active_agent(request: Request) -> FruitScannerAgent:
    agent = getattr(request.app.state, "agent", None)
    if agent is None:
        raise ApiProblem(
            503,
            "SERVICE_NOT_READY",
            "FreshSense has not finished loading its models.",
        )
    return agent


def _request_preflight_problem(
    request: Request,
    *,
    max_upload_bytes: int,
) -> ApiProblem | None:
    """Reject unauthenticated or oversized requests before multipart parsing."""
    if request.method == "OPTIONS" or request.url.path not in PROTECTED_API_PATHS:
        return None

    try:
        authenticate_api_key(request, request.headers.get("X-API-Key"))
    except ApiProblem as exc:
        return exc

    if request.url.path != "/api/v1/analyze":
        return None

    raw_content_length = request.headers.get("Content-Length")
    if raw_content_length is None:
        return None
    try:
        content_length = int(raw_content_length)
    except ValueError:
        return ApiProblem(
            400,
            "INVALID_CONTENT_LENGTH",
            "The Content-Length header is invalid.",
        )
    if content_length < 0:
        return ApiProblem(
            400,
            "INVALID_CONTENT_LENGTH",
            "The Content-Length header is invalid.",
        )
    if content_length > max_upload_bytes + MULTIPART_OVERHEAD_ALLOWANCE:
        return ApiProblem(
            413,
            "REQUEST_TOO_LARGE",
            "The request body exceeds the configured upload allowance.",
        )
    return None


def _problem_response(problem: ApiProblem) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status_code,
        content={"error": {"code": problem.code, "message": problem.message}},
        headers=problem.headers,
    )


def _validate_hosts(values: Sequence[str]) -> tuple[str, ...]:
    hosts = tuple(value.strip() for value in values if value.strip())
    if not hosts or "*" in hosts:
        raise ValueError("allowed_hosts must contain explicit hostnames.")
    return hosts


def _validate_origins(values: Sequence[str]) -> tuple[str, ...]:
    origins = tuple(value.strip().rstrip("/") for value in values if value.strip())
    if "*" in origins:
        raise ValueError("Wildcard CORS origins are not allowed.")
    return origins


async def _read_upload(
    upload: UploadFile,
    *,
    max_upload_bytes: int,
) -> tuple[str, bytes]:
    content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
    try:
        if content_type not in ACCEPTED_IMAGE_FORMATS:
            raise ApiProblem(
                415,
                "UNSUPPORTED_MEDIA_TYPE",
                "Upload a JPEG, PNG, or WebP image.",
            )
        data = await upload.read(max_upload_bytes + 1)
    finally:
        await upload.close()

    if not data:
        raise ApiProblem(400, "EMPTY_FILE", "The uploaded image is empty.")
    if len(data) > max_upload_bytes:
        raise ApiProblem(
            413,
            "FILE_TOO_LARGE",
            f"The uploaded image exceeds the {max_upload_bytes}-byte limit.",
        )
    return content_type, data


def _decode_image(
    data: bytes,
    *,
    content_type: str,
    max_image_pixels: int,
) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as uploaded:
                detected_format = (uploaded.format or "").upper()
                if detected_format != ACCEPTED_IMAGE_FORMATS[content_type]:
                    raise ApiProblem(
                        415,
                        "MEDIA_TYPE_MISMATCH",
                        "The declared media type does not match the uploaded image.",
                    )
                width, height = uploaded.size
                if width <= 0 or height <= 0:
                    raise ApiProblem(400, "INVALID_IMAGE", "The image dimensions are invalid.")
                if width * height > max_image_pixels:
                    raise ApiProblem(
                        413,
                        "IMAGE_TOO_LARGE",
                        f"The decoded image exceeds the {max_image_pixels}-pixel limit.",
                    )
                uploaded.load()
                return ImageOps.exif_transpose(uploaded).convert("RGB")
    except ApiProblem:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ApiProblem(
            400,
            "INVALID_IMAGE",
            "The upload is not a valid, decodable image.",
        ) from exc
