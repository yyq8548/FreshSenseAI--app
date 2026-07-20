"""Hardened FastAPI application factory for FreshSense integrations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from contextlib import asynccontextmanager
from contextlib import suppress
from io import BytesIO
import logging
import os
from pathlib import Path
import time
from typing import TYPE_CHECKING
import warnings

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    File,
    Form,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from api.errors import ApiProblem
from api.identity import AuthContext, EntraTokenValidator, TokenValidationError
from api.models import (
    AnalyzeResponse,
    AuthenticatedUserResponse,
    DashboardResponse,
    ErrorResponse,
    HealthResponse,
    InspectionAnalyzeResponse,
    InspectionListResponse,
    InspectionResponse,
    InspectionReviewRequest,
    MetricsResponse,
    WorkspaceInvitationAcceptRequest,
    WorkspaceInvitationCreateRequest,
    WorkspaceInvitationResponse,
    WorkspaceResponse,
)
from api.observability import (
    MetricsRegistry,
    configure_json_logging,
    request_id_from_header,
)
from api.security import (
    InMemoryRateLimiter,
    RateLimitDecision,
    authenticate_for_request,
    authenticate_request,
    authenticated_context,
    enforce_rate_limit,
    resolve_api_key,
    validate_api_key_configuration,
)
from api.serialization import serialize_agent_state
from saas.store import InspectionNotFoundError, SaaSStore, SaaSStoreError
from utils.config import (
    API_AUTH_MODE,
    API_ALLOWED_HOSTS,
    API_CORS_ORIGINS,
    API_JSON_LOGS,
    API_KEY_FILE,
    API_MAX_IMAGE_PIXELS,
    API_MAX_UPLOAD_BYTES,
    API_RATE_LIMIT_PER_MINUTE,
    API_REQUIRE_API_KEY,
    API_REQUIRE_SEMANTIC_RAG,
    ENTRA_ALLOWED_CLIENT_IDS,
    ENTRA_API_CLIENT_ID,
    ENTRA_AUTHORITY,
    ENTRA_REQUIRED_SCOPE,
    ENTRA_TENANT_ID,
    FRUIT_CATALOG_PATH,
    KNOWLEDGE_BASE_PATH,
    MODEL_PATH,
    OPEN_SET_GATE_PATH,
    REQUIRE_OPEN_SET_GATE,
    SAAS_DATABASE_PATH,
)
from utils.startup import StartupValidationError, validate_startup
from utils.version import APP_VERSION

if TYPE_CHECKING:
    from agent.fruit_agent import FruitScannerAgent


logger = logging.getLogger("freshsense.api")
AgentFactory = Callable[[], "FruitScannerAgent"]

ACCEPTED_IMAGE_FORMATS = {
    "image/jpeg": "JPEG",
    "image/jpg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}
MULTIPART_OVERHEAD_ALLOWANCE = 64 * 1024
PROTECTED_API_PATHS = frozenset(
    {"/api/v1/analyze", "/api/v1/me", "/api/v1/metrics"}
)
PROTECTED_API_PREFIXES = (
    "/api/v1/workspace",
    "/api/v1/dashboard",
    "/api/v1/inspections",
)
UPLOAD_API_PATHS = frozenset({"/api/v1/analyze", "/api/v1/inspections/analyze"})


def _production_agent_factory() -> FruitScannerAgent:
    # TensorFlow is intentionally imported only inside the background model task.
    # Importing it while Uvicorn imports ``api.main`` prevents App Service from
    # opening its HTTP port until the entire ML runtime has initialized.
    from agent.fruit_agent import FruitScannerAgent

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
    saas_database_path: str | Path = SAAS_DATABASE_PATH,
    auth_mode: str | None = API_AUTH_MODE,
    entra_tenant_id: str = ENTRA_TENANT_ID,
    entra_api_client_id: str = ENTRA_API_CLIENT_ID,
    entra_authority: str = ENTRA_AUTHORITY,
    entra_required_scope: str = ENTRA_REQUIRED_SCOPE,
    entra_allowed_client_ids: Sequence[str] = ENTRA_ALLOWED_CLIENT_IDS,
    entra_token_validator: object | None = None,
    background_agent_initialization: bool | None = None,
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
    initialize_agent_in_background = (
        agent_factory is None
        if background_agent_initialization is None
        else background_agent_initialization
    )
    if auth_mode not in {None, "local", "api_key", "entra"}:
        raise ValueError("auth_mode must be local, api_key, or entra.")

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if json_logs:
            configure_json_logging(logger)

        resolved_api_key = resolve_api_key(
            explicit_value=api_key,
            environment_value=os.getenv("FRESHSENSE_API_KEY"),
            secret_file=api_key_file,
        )
        active_auth_mode = auth_mode or (
            "api_key" if resolved_api_key is not None or require_api_key else "local"
        )
        validate_api_key_configuration(
            resolved_api_key,
            required=active_auth_mode == "api_key",
        )

        active_entra_validator = None
        if active_auth_mode == "entra":
            if not all((entra_tenant_id, entra_api_client_id, entra_authority)):
                raise StartupValidationError(
                    "Microsoft Entra authentication requires tenant, API client, "
                    "and authority configuration."
                )
            try:
                active_entra_validator = entra_token_validator or EntraTokenValidator(
                    authority=entra_authority,
                    tenant_id=entra_tenant_id,
                    audience=entra_api_client_id,
                    required_scopes=(entra_required_scope,),
                    allowed_client_ids=entra_allowed_client_ids,
                )
                initialize_validator = getattr(active_entra_validator, "initialize", None)
                if initialize_validator is not None:
                    await run_in_threadpool(initialize_validator)
            except TokenValidationError as exc:
                raise StartupValidationError(
                    "Microsoft Entra authentication could not be initialized."
                ) from exc

        saas_store = SaaSStore(saas_database_path)
        application.state.agent = None
        application.state.agent_status = "starting"
        application.state.agent_startup_error = None
        application.state.saas_store = saas_store
        application.state.saas_store_status = "starting"
        application.state.inference_lock = asyncio.Lock()

        async def initialize_saas_store() -> None:
            initialization_started = time.perf_counter()
            try:
                await run_in_threadpool(saas_store.initialize)
                application.state.saas_store_status = "ok"
                logger.info(
                    "FreshSense workspace store initialized",
                    extra={
                        "event": "workspace_store_initialization_completed",
                        "duration_ms": round(
                            (time.perf_counter() - initialization_started) * 1000,
                            1,
                        ),
                        "database_backend": saas_store.backend,
                    },
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                application.state.saas_store_status = "failed"
                logger.exception(
                    "FreshSense workspace store initialization failed",
                    extra={"event": "workspace_store_initialization_failed"},
                )

        async def initialize_and_warm_agent() -> None:
            initialization_started = time.perf_counter()
            try:
                agent = await run_in_threadpool(factory)
                if require_semantic_rag and not agent.retriever_tool.semantic_ready:
                    raise StartupValidationError(
                        "Semantic RAG is required but the local embedding model did not load."
                    )

                warm_up = getattr(agent, "warm_up", None)
                if warm_up is not None:
                    async with application.state.inference_lock:
                        await run_in_threadpool(warm_up)

                application.state.agent = agent
                application.state.agent_status = "ok"
                logger.info(
                    "FreshSense model initialized and warmed",
                    extra={
                        "event": "model_initialization_completed",
                        "duration_ms": round(
                            (time.perf_counter() - initialization_started) * 1000,
                            1,
                        ),
                        "retrieval_mode": (
                            "semantic"
                            if agent.retriever_tool.semantic_ready
                            else "keyword_fallback"
                        ),
                    },
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                application.state.agent = None
                application.state.agent_status = "failed"
                application.state.agent_startup_error = type(exc).__name__
                logger.exception(
                    "FreshSense model initialization failed",
                    extra={"event": "model_initialization_failed"},
                )

        application.state.max_upload_bytes = max_upload_bytes
        application.state.max_image_pixels = max_image_pixels
        application.state.api_key = resolved_api_key
        application.state.auth_mode = active_auth_mode
        application.state.authentication_enabled = active_auth_mode != "local"
        application.state.entra_token_validator = active_entra_validator
        application.state.rate_limit_per_minute = rate_limit_per_minute
        application.state.rate_limiter = InMemoryRateLimiter(rate_limit_per_minute)
        application.state.metrics = MetricsRegistry()

        agent_initialization_task: asyncio.Task[None] | None = None
        store_initialization_task: asyncio.Task[None] | None = None
        if initialize_agent_in_background:
            store_initialization_task = asyncio.create_task(initialize_saas_store())
            agent_initialization_task = asyncio.create_task(initialize_and_warm_agent())
        else:
            await initialize_saas_store()
            if application.state.saas_store_status != "ok":
                raise StartupValidationError(
                    "FreshSense could not initialize its workspace store."
                )
            await initialize_and_warm_agent()
            if application.state.agent_status != "ok":
                raise StartupValidationError(
                    "FreshSense could not initialize its model pipeline."
                )

        logger.info(
            "FreshSense API started",
            extra={
                "event": "service_started",
                "model_status": application.state.agent_status,
            },
        )
        try:
            yield
        finally:
            if (
                agent_initialization_task is not None
                and not agent_initialization_task.done()
            ):
                agent_initialization_task.cancel()
                with suppress(asyncio.CancelledError):
                    await agent_initialization_task
            if (
                store_initialization_task is not None
                and not store_initialization_task.done()
            ):
                store_initialization_task.cancel()
                with suppress(asyncio.CancelledError):
                    await store_initialization_task
            await run_in_threadpool(saas_store.database.dispose)
            application.state.agent = None
            application.state.api_key = None
            application.state.entra_token_validator = None
            application.state.saas_store = None
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
            allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "X-API-Key",
                "X-Request-ID",
            ],
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
        agent = getattr(request.app.state, "agent", None)
        status = getattr(request.app.state, "agent_status", "starting")
        if agent is None:
            return HealthResponse(
                status="failed" if status == "failed" else "starting",
                model_loaded=False,
                semantic_retrieval_ready=False,
                retrieval_mode="keyword_fallback",
                semantic_model=None,
                supported_fruits=[],
                database_backend=request.app.state.saas_store.backend,
                authentication_required=request.app.state.authentication_enabled,
                rate_limit_per_minute=request.app.state.rate_limit_per_minute,
            )
        retriever = agent.retriever_tool
        semantic_ready = bool(retriever.semantic_ready)
        embedder = retriever.embedder if semantic_ready else None
        return HealthResponse(
            status="ok",
            model_loaded=True,
            semantic_retrieval_ready=semantic_ready,
            retrieval_mode="semantic" if semantic_ready else "keyword_fallback",
            semantic_model=(embedder.model_name if embedder is not None else None),
            supported_fruits=[
                fruit.display_name for fruit in agent.catalog.fruits.values()
            ],
            database_backend=request.app.state.saas_store.backend,
            authentication_required=request.app.state.authentication_enabled,
            rate_limit_per_minute=request.app.state.rate_limit_per_minute,
        )

    @router.get(
        "/metrics",
        response_model=MetricsResponse,
        tags=["system"],
        summary="Return process-local operational metrics",
        responses={
            401: {"model": ErrorResponse, "description": "Invalid authentication credentials."},
        },
    )
    async def metrics(
        request: Request,
        _identity: str = Depends(authenticate_request),
    ) -> MetricsResponse:
        return await request.app.state.metrics.snapshot()

    @router.get(
        "/me",
        response_model=AuthenticatedUserResponse,
        tags=["identity"],
        summary="Return the authenticated account and workspace role",
    )
    async def me(
        request: Request,
        context: AuthContext = Depends(authenticated_context),
    ) -> AuthenticatedUserResponse:
        store = _active_saas_store(request)
        try:
            value = await run_in_threadpool(
                store.workspace,
                context.identity,
                email=context.email,
                display_name=context.display_name,
            )
        except SaaSStoreError as exc:
            raise _store_problem() from exc
        return AuthenticatedUserResponse(
            account_id=context.identity[:12],
            display_name=context.display_name,
            email=context.email,
            authentication_scheme=context.scheme,
            scopes=sorted(context.scopes),
            workspace_id=value["workspace_id"],
            workspace_role=value["current_role"],
        )

    @router.get(
        "/workspace",
        response_model=WorkspaceResponse,
        tags=["workspace"],
        summary="Return the authenticated pilot workspace",
        responses={
            401: {"model": ErrorResponse, "description": "Invalid authentication credentials."},
            503: {"model": ErrorResponse, "description": "Workspace storage unavailable."},
        },
    )
    async def workspace(
        request: Request,
        context: AuthContext = Depends(authenticated_context),
    ) -> WorkspaceResponse:
        store = _active_saas_store(request)
        try:
            value = await run_in_threadpool(
                store.workspace,
                context.identity,
                email=context.email,
                display_name=context.display_name,
            )
        except SaaSStoreError as exc:
            raise _store_problem() from exc
        return WorkspaceResponse.model_validate(value)

    @router.post(
        "/workspace/invitations",
        response_model=WorkspaceInvitationResponse,
        status_code=201,
        tags=["workspace"],
        summary="Create a one-time workspace invitation",
    )
    async def create_workspace_invitation(
        payload: WorkspaceInvitationCreateRequest,
        request: Request,
        context: AuthContext = Depends(authenticated_context),
    ) -> WorkspaceInvitationResponse:
        await _require_workspace_role(request, context.identity, {"manager"})
        store = _active_saas_store(request)
        try:
            value = await run_in_threadpool(
                store.create_invitation,
                identity_hash=context.identity,
                email=payload.email,
                role=payload.role,
                expires_days=payload.expires_days,
            )
        except SaaSStoreError as exc:
            raise ApiProblem(400, "INVALID_WORKSPACE_INVITATION", str(exc)) from exc
        return WorkspaceInvitationResponse.model_validate(value)

    @router.post(
        "/workspace/invitations/accept",
        response_model=WorkspaceResponse,
        tags=["workspace"],
        summary="Accept a workspace invitation for the signed-in account",
    )
    async def accept_workspace_invitation(
        payload: WorkspaceInvitationAcceptRequest,
        request: Request,
        context: AuthContext = Depends(authenticated_context),
    ) -> WorkspaceResponse:
        store = _active_saas_store(request)
        try:
            value = await run_in_threadpool(
                store.accept_invitation,
                identity_hash=context.identity,
                email=context.email,
                display_name=context.display_name,
                invitation_token=payload.invitation_token,
            )
        except SaaSStoreError as exc:
            raise ApiProblem(400, "INVALID_WORKSPACE_INVITATION", str(exc)) from exc
        return WorkspaceResponse.model_validate(value)

    @router.get(
        "/dashboard",
        response_model=DashboardResponse,
        tags=["workspace"],
        summary="Return workspace inspection and review metrics",
        responses={
            401: {"model": ErrorResponse, "description": "Invalid authentication credentials."},
            503: {"model": ErrorResponse, "description": "Workspace storage unavailable."},
        },
    )
    async def dashboard(
        request: Request,
        identity: str = Depends(authenticate_request),
    ) -> DashboardResponse:
        store = _active_saas_store(request)
        try:
            value = await run_in_threadpool(store.dashboard, identity)
        except SaaSStoreError as exc:
            raise _store_problem() from exc
        return DashboardResponse.model_validate(value)

    @router.get(
        "/inspections",
        response_model=InspectionListResponse,
        tags=["inspections"],
        summary="List workspace-scoped inspection metadata",
        responses={
            401: {"model": ErrorResponse, "description": "Invalid authentication credentials."},
            503: {"model": ErrorResponse, "description": "Workspace storage unavailable."},
        },
    )
    async def inspections(
        request: Request,
        limit: int = Query(50, ge=1, le=200),
        review_status: str | None = Query(None),
        identity: str = Depends(authenticate_request),
    ) -> InspectionListResponse:
        store = _active_saas_store(request)
        try:
            values = await run_in_threadpool(
                store.list_inspections,
                identity,
                limit=limit,
                review_status=review_status,
            )
        except SaaSStoreError as exc:
            raise ApiProblem(400, "INVALID_INSPECTION_FILTER", str(exc)) from exc
        return InspectionListResponse(inspections=values, count=len(values))

    @router.patch(
        "/inspections/{inspection_id}/review",
        response_model=InspectionResponse,
        tags=["inspections"],
        summary="Record a human review for one inspection",
        responses={
            400: {"model": ErrorResponse, "description": "Invalid review data."},
            401: {"model": ErrorResponse, "description": "Invalid authentication credentials."},
            404: {"model": ErrorResponse, "description": "Inspection not found."},
            503: {"model": ErrorResponse, "description": "Workspace storage unavailable."},
        },
    )
    async def review_inspection(
        inspection_id: str,
        payload: InspectionReviewRequest,
        request: Request,
        identity: str = Depends(authenticate_request),
    ) -> InspectionResponse:
        await _require_workspace_role(request, identity, {"manager", "reviewer"})
        store = _active_saas_store(request)
        try:
            value = await run_in_threadpool(
                store.review_inspection,
                identity_hash=identity,
                inspection_id=inspection_id,
                review_status=payload.review_status,
                reviewed_outcome=payload.reviewed_outcome,
                note=payload.note,
            )
        except InspectionNotFoundError as exc:
            raise ApiProblem(404, "INSPECTION_NOT_FOUND", str(exc)) from exc
        except SaaSStoreError as exc:
            raise ApiProblem(400, "INVALID_REVIEW", str(exc)) from exc
        return InspectionResponse.model_validate(value)

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
            401: {"model": ErrorResponse, "description": "Invalid authentication credentials."},
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
        identity: str = Depends(authenticate_request),
    ) -> AnalyzeResponse:
        _active_agent(request)
        await _require_workspace_role(request, identity, {"manager", "inspector"})
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
        try:
            return await _analyze_image(
                request,
                image,
                include_explanation_overlay=include_explanation,
            )
        finally:
            image.close()

    @router.post(
        "/inspections/analyze",
        response_model=InspectionAnalyzeResponse,
        tags=["inspections"],
        summary="Analyze a fruit photo and save reviewable metadata",
        description=(
            "Runs the existing FreshSense analysis, stores only workspace-scoped "
            "result metadata, and discards the uploaded image and filename."
        ),
        responses={
            400: {"model": ErrorResponse, "description": "Invalid image or metadata."},
            401: {"model": ErrorResponse, "description": "Invalid authentication credentials."},
            413: {"model": ErrorResponse, "description": "Upload or image too large."},
            415: {"model": ErrorResponse, "description": "Unsupported image type."},
            429: {"model": ErrorResponse, "description": "Rate limit exceeded."},
            503: {"model": ErrorResponse, "description": "Model or storage unavailable."},
        },
    )
    async def analyze_inspection(
        request: Request,
        response: Response,
        location_name: str = Form("Main store", min_length=1, max_length=80),
        batch_reference: str = Form("", max_length=100),
        operator_note: str = Form("", max_length=1000),
        include_explanation: bool = Query(False),
        file: UploadFile = File(...),
        rate_limit: RateLimitDecision = Depends(enforce_rate_limit),
        identity: str = Depends(authenticate_request),
    ) -> InspectionAnalyzeResponse:
        _active_agent(request)
        await _require_workspace_role(request, identity, {"manager", "inspector"})
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
        try:
            analysis = await _analyze_image(
                request,
                image,
                include_explanation_overlay=include_explanation,
            )
            store = _active_saas_store(request)
            try:
                inspection = await run_in_threadpool(
                    store.record_inspection,
                    identity_hash=identity,
                    location_name=location_name,
                    batch_reference=batch_reference,
                    operator_note=operator_note,
                    analysis=analysis.model_dump(mode="json"),
                    model_version=APP_VERSION,
                )
            except SaaSStoreError as exc:
                raise _store_problem() from exc
            return InspectionAnalyzeResponse(
                inspection=InspectionResponse.model_validate(inspection),
                analysis=analysis,
            )
        finally:
            image.close()

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


def _active_saas_store(request: Request) -> SaaSStore:
    store = getattr(request.app.state, "saas_store", None)
    status = getattr(request.app.state, "saas_store_status", "starting")
    if store is None or status != "ok":
        raise _store_problem()
    return store


def _store_problem() -> ApiProblem:
    return ApiProblem(
        503,
        "WORKSPACE_STORE_UNAVAILABLE",
        "FreshSense could not access the workspace metadata store.",
    )


async def _require_workspace_role(
    request: Request,
    identity: str,
    allowed_roles: set[str],
) -> str:
    store = _active_saas_store(request)
    try:
        role = await run_in_threadpool(store.member_role, identity)
    except SaaSStoreError as exc:
        raise _store_problem() from exc
    if role not in allowed_roles:
        raise ApiProblem(
            403,
            "INSUFFICIENT_WORKSPACE_ROLE",
            "Your workspace role does not permit this action.",
        )
    return role


async def _analyze_image(
    request: Request,
    image: Image.Image,
    *,
    include_explanation_overlay: bool,
) -> AnalyzeResponse:
    analysis_started = time.perf_counter()
    lock_wait_seconds: float | None = None
    inference_ms: float | None = None
    success = False
    logger.info(
        "FreshSense analysis started",
        extra={
            "event": "analysis_started",
            "request_id": request.state.request_id,
        },
    )
    try:
        agent = _active_agent(request)
        lock_wait_started = time.perf_counter()
        async with request.app.state.inference_lock:
            lock_wait_seconds = time.perf_counter() - lock_wait_started
            run_for_api = getattr(agent, "run_for_api", None)
            if run_for_api is not None:
                state = await run_in_threadpool(
                    run_for_api,
                    image,
                    include_explanation=include_explanation_overlay,
                )
            else:
                state = await run_in_threadpool(agent.run, image)
            inference_ms = state.metadata.get("performance_ms")
        result = serialize_agent_state(
            state,
            agent.catalog,
            include_explanation_overlay=include_explanation_overlay,
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
        duration_seconds = time.perf_counter() - analysis_started
        await request.app.state.metrics.analysis_finished(
            success=success,
            duration_seconds=duration_seconds,
        )
        logger.info(
            "FreshSense analysis finished",
            extra={
                "event": "analysis_finished",
                "request_id": request.state.request_id,
                "success": success,
                "duration_ms": round(duration_seconds * 1000, 3),
                "inference_ms": inference_ms,
                "inference_lock_wait_ms": (
                    round(lock_wait_seconds * 1000, 3)
                    if lock_wait_seconds is not None
                    else None
                ),
            },
        )


def _request_preflight_problem(
    request: Request,
    *,
    max_upload_bytes: int,
) -> ApiProblem | None:
    """Reject unauthenticated or oversized requests before multipart parsing."""
    protected = request.url.path in PROTECTED_API_PATHS or request.url.path.startswith(
        PROTECTED_API_PREFIXES
    )
    if request.method == "OPTIONS" or not protected:
        return None

    authorization = request.headers.get("Authorization", "").strip()
    bearer_token = (
        authorization[7:].strip()
        if authorization.lower().startswith("bearer ")
        else None
    )
    try:
        authenticate_for_request(
            request,
            supplied_key=request.headers.get("X-API-Key"),
            bearer_token=bearer_token,
        )
    except ApiProblem as exc:
        return exc

    if request.url.path not in UPLOAD_API_PATHS:
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
