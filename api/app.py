"""Hardened FastAPI application factory for FreshSense integrations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from contextlib import asynccontextmanager
from contextlib import suppress
from datetime import datetime, timezone
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

from agent.autonomous import AutonomousInspectionAgent, ShadowAgentError
from agent.manager_chat import ManagerChatResponder, ManagerChatService
from api.errors import ApiProblem
from api.identity import AuthContext, EntraTokenValidator, TokenValidationError
from api.models import (
    AgentMemoryListResponse,
    AgentRunCreateRequest,
    AgentRunListResponse,
    AgentRunResponse,
    ApprovalListResponse,
    ApprovalResolveRequest,
    ApprovalResponse,
    AnalyzeResponse,
    AuthenticatedUserResponse,
    DashboardResponse,
    DailyQualityReportResponse,
    ErrorResponse,
    HealthResponse,
    InspectionAnalyzeResponse,
    InspectionListResponse,
    InspectionResponse,
    InspectionReviewRequest,
    MetricsResponse,
    ManagerChatMessageCreateRequest,
    ManagerChatReplyResponse,
    ManagerConversationCreateRequest,
    ManagerConversationListResponse,
    ManagerConversationResponse,
    ManagerPreferenceResponse,
    ManagerPreferenceUpdateRequest,
    NotificationListResponse,
    NotificationResponse,
    WorkspaceInvitationAcceptRequest,
    WorkspaceInvitationCreateRequest,
    WorkspaceInvitationResponse,
    WorkspaceResponse,
    WorkflowTaskListResponse,
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
from saas.store import (
    AgentRunNotFoundError,
    ConversationNotFoundError,
    InspectionNotFoundError,
    SaaSStore,
    SaaSStoreError,
)
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
    "/api/v1/agent",
    "/api/v1/approvals",
    "/api/v1/notifications",
    "/api/v1/reports",
    "/api/v1/workflow",
    "/api/v1/workspace",
    "/api/v1/dashboard",
    "/api/v1/inspections",
    "/api/v1/manager",
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
    manager_chat_responder: ManagerChatResponder | None = None,
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
        autonomous_agent = AutonomousInspectionAgent(saas_store)
        manager_chat_service = ManagerChatService(
            saas_store,
            responder=manager_chat_responder,
        )
        application.state.agent = None
        application.state.agent_status = "starting"
        application.state.agent_startup_error = None
        application.state.saas_store = saas_store
        application.state.autonomous_agent = autonomous_agent
        application.state.manager_chat_service = manager_chat_service
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
                retriever = getattr(agent, "retriever_tool", None)
                if callable(getattr(retriever, "retrieve", None)):
                    manager_chat_service.retriever = retriever
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
            application.state.autonomous_agent = None
            application.state.manager_chat_service = None
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
        "/manager/preferences",
        response_model=ManagerPreferenceResponse,
        tags=["manager-chat"],
        summary="Return the signed-in manager's assistant preferences",
    )
    async def manager_preferences(
        request: Request,
        identity: str = Depends(authenticate_request),
    ) -> ManagerPreferenceResponse:
        await _require_workspace_role(request, identity, {"manager"})
        store = _active_saas_store(request)
        try:
            value = await run_in_threadpool(store.manager_preferences, identity)
        except SaaSStoreError as exc:
            raise _store_problem() from exc
        return ManagerPreferenceResponse.model_validate(value)

    @router.patch(
        "/manager/preferences",
        response_model=ManagerPreferenceResponse,
        tags=["manager-chat"],
        summary="Update the signed-in manager's assistant preferences",
    )
    async def update_manager_preferences(
        payload: ManagerPreferenceUpdateRequest,
        request: Request,
        identity: str = Depends(authenticate_request),
    ) -> ManagerPreferenceResponse:
        await _require_workspace_role(request, identity, {"manager"})
        store = _active_saas_store(request)
        try:
            value = await run_in_threadpool(
                store.update_manager_preferences,
                identity_hash=identity,
                **payload.model_dump(),
            )
        except SaaSStoreError as exc:
            raise ApiProblem(400, "INVALID_MANAGER_PREFERENCES", str(exc)) from exc
        return ManagerPreferenceResponse.model_validate(value)

    @router.post(
        "/manager/conversations",
        response_model=ManagerConversationResponse,
        tags=["manager-chat"],
        summary="Create a durable manager conversation",
    )
    async def create_manager_conversation(
        payload: ManagerConversationCreateRequest,
        request: Request,
        identity: str = Depends(authenticate_request),
    ) -> ManagerConversationResponse:
        await _require_workspace_role(request, identity, {"manager"})
        store = _active_saas_store(request)
        try:
            value = await run_in_threadpool(
                store.create_manager_conversation,
                identity_hash=identity,
                title=payload.title,
            )
        except SaaSStoreError as exc:
            raise ApiProblem(400, "INVALID_MANAGER_CONVERSATION", str(exc)) from exc
        return ManagerConversationResponse.model_validate(value)

    @router.get(
        "/manager/conversations",
        response_model=ManagerConversationListResponse,
        tags=["manager-chat"],
        summary="List active manager conversations in this workspace",
    )
    async def manager_conversations(
        request: Request,
        limit: int = Query(30, ge=1, le=100),
        identity: str = Depends(authenticate_request),
    ) -> ManagerConversationListResponse:
        await _require_workspace_role(request, identity, {"manager"})
        store = _active_saas_store(request)
        try:
            values = await run_in_threadpool(
                store.list_manager_conversations,
                identity,
                limit=limit,
            )
        except SaaSStoreError as exc:
            raise _store_problem() from exc
        return ManagerConversationListResponse(
            conversations=values,
            count=len(values),
        )

    @router.get(
        "/manager/conversations/{conversation_id}",
        response_model=ManagerConversationResponse,
        tags=["manager-chat"],
        summary="Return one workspace-scoped manager conversation",
    )
    async def manager_conversation(
        conversation_id: str,
        request: Request,
        identity: str = Depends(authenticate_request),
    ) -> ManagerConversationResponse:
        await _require_workspace_role(request, identity, {"manager"})
        store = _active_saas_store(request)
        try:
            value = await run_in_threadpool(
                store.manager_conversation,
                identity,
                conversation_id,
            )
        except ConversationNotFoundError as exc:
            raise ApiProblem(404, "MANAGER_CONVERSATION_NOT_FOUND", str(exc)) from exc
        except SaaSStoreError as exc:
            raise _store_problem() from exc
        return ManagerConversationResponse.model_validate(value)

    @router.post(
        "/manager/conversations/{conversation_id}/messages",
        response_model=ManagerChatReplyResponse,
        tags=["manager-chat"],
        summary="Ask a grounded, multi-turn manager question",
        description=(
            "Persists the manager's message, retrieves workspace inspections, Agent "
            "audit records, preferences, and reviewed food knowledge, then stores the "
            "grounded answer. Chat never executes operational actions."
        ),
    )
    async def create_manager_message(
        conversation_id: str,
        payload: ManagerChatMessageCreateRequest,
        request: Request,
        identity: str = Depends(authenticate_request),
    ) -> ManagerChatReplyResponse:
        await _require_workspace_role(request, identity, {"manager"})
        service = _active_manager_chat_service(request)
        try:
            result = await run_in_threadpool(
                service.reply,
                identity_hash=identity,
                conversation_id=conversation_id,
                content=payload.content,
            )
        except ConversationNotFoundError as exc:
            raise ApiProblem(404, "MANAGER_CONVERSATION_NOT_FOUND", str(exc)) from exc
        except SaaSStoreError as exc:
            raise ApiProblem(400, "INVALID_MANAGER_MESSAGE", str(exc)) from exc
        return ManagerChatReplyResponse(
            conversation=result.conversation,
            assistant_message=result.assistant_message,
        )

    @router.post(
        "/manager/conversations/{conversation_id}/archive",
        response_model=ManagerConversationResponse,
        tags=["manager-chat"],
        summary="Archive one manager conversation",
    )
    async def archive_manager_conversation(
        conversation_id: str,
        request: Request,
        identity: str = Depends(authenticate_request),
    ) -> ManagerConversationResponse:
        await _require_workspace_role(request, identity, {"manager"})
        store = _active_saas_store(request)
        try:
            value = await run_in_threadpool(
                store.archive_manager_conversation,
                identity_hash=identity,
                conversation_id=conversation_id,
            )
        except ConversationNotFoundError as exc:
            raise ApiProblem(404, "MANAGER_CONVERSATION_NOT_FOUND", str(exc)) from exc
        except SaaSStoreError as exc:
            raise _store_problem() from exc
        return ManagerConversationResponse.model_validate(value)

    @router.post(
        "/agent/runs",
        response_model=AgentRunResponse,
        tags=["agent"],
        summary="Run the bounded inspection supervisor in shadow mode",
        description=(
            "Creates a durable agent run, calls workspace-scoped read tools, and "
            "records one proposed follow-up action. Shadow mode never executes the action."
        ),
        responses={
            401: {"model": ErrorResponse, "description": "Invalid authentication credentials."},
            403: {"model": ErrorResponse, "description": "Workspace role cannot start a run."},
            404: {"model": ErrorResponse, "description": "Inspection not found."},
            500: {"model": ErrorResponse, "description": "Shadow-agent run failed safely."},
            503: {"model": ErrorResponse, "description": "Workspace storage unavailable."},
        },
    )
    async def create_agent_run(
        payload: AgentRunCreateRequest,
        request: Request,
        identity: str = Depends(authenticate_request),
    ) -> AgentRunResponse:
        await _require_workspace_role(request, identity, {"manager", "inspector"})
        agent = _active_autonomous_agent(request)
        try:
            value = await run_in_threadpool(
                agent.run,
                identity_hash=identity,
                inspection_id=payload.inspection_id,
            )
        except InspectionNotFoundError as exc:
            raise ApiProblem(404, "INSPECTION_NOT_FOUND", str(exc)) from exc
        except ShadowAgentError as exc:
            raise ApiProblem(
                500,
                "AGENT_RUN_FAILED",
                "The shadow agent could not complete its bounded run.",
            ) from exc
        except SaaSStoreError as exc:
            raise _store_problem() from exc
        return AgentRunResponse.model_validate(value)

    @router.get(
        "/agent/runs",
        response_model=AgentRunListResponse,
        tags=["agent"],
        summary="List shadow-agent runs in the authenticated workspace",
    )
    async def agent_runs(
        request: Request,
        limit: int = Query(50, ge=1, le=100),
        identity: str = Depends(authenticate_request),
    ) -> AgentRunListResponse:
        await _require_workspace_role(
            request,
            identity,
            {"manager", "inspector", "reviewer"},
        )
        store = _active_saas_store(request)
        try:
            values = await run_in_threadpool(
                store.list_agent_runs,
                identity,
                limit=limit,
            )
        except SaaSStoreError as exc:
            raise _store_problem() from exc
        return AgentRunListResponse(runs=values, count=len(values))

    @router.get(
        "/agent/runs/{run_id}",
        response_model=AgentRunResponse,
        tags=["agent"],
        summary="Return one audited shadow-agent run",
        responses={
            404: {"model": ErrorResponse, "description": "Agent run not found."},
        },
    )
    async def agent_run(
        run_id: str,
        request: Request,
        identity: str = Depends(authenticate_request),
    ) -> AgentRunResponse:
        await _require_workspace_role(
            request,
            identity,
            {"manager", "inspector", "reviewer"},
        )
        store = _active_saas_store(request)
        try:
            value = await run_in_threadpool(store.agent_run, identity, run_id)
        except AgentRunNotFoundError as exc:
            raise ApiProblem(404, "AGENT_RUN_NOT_FOUND", str(exc)) from exc
        except SaaSStoreError as exc:
            raise _store_problem() from exc
        return AgentRunResponse.model_validate(value)

    @router.get(
        "/agent/memory",
        response_model=AgentMemoryListResponse,
        tags=["agent"],
        summary="List durable human-review memory for the workspace agent",
    )
    async def agent_memory(
        request: Request,
        fruit: str | None = Query(None, max_length=80),
        limit: int = Query(50, ge=1, le=200),
        identity: str = Depends(authenticate_request),
    ) -> AgentMemoryListResponse:
        store = _active_saas_store(request)
        try:
            values = await run_in_threadpool(
                store.list_agent_memory,
                identity,
                fruit=fruit,
                limit=limit,
            )
        except SaaSStoreError as exc:
            raise ApiProblem(400, "INVALID_MEMORY_QUERY", str(exc)) from exc
        return AgentMemoryListResponse(memories=values, count=len(values))

    @router.get(
        "/workflow/tasks",
        response_model=WorkflowTaskListResponse,
        tags=["workflow"],
        summary="List AI-created inspection workflow tasks",
    )
    async def workflow_tasks(
        request: Request,
        status: str | None = Query(None),
        identity: str = Depends(authenticate_request),
    ) -> WorkflowTaskListResponse:
        store = _active_saas_store(request)
        try:
            values = await run_in_threadpool(
                store.list_workflow_tasks,
                identity,
                status=status,
            )
        except SaaSStoreError as exc:
            raise ApiProblem(400, "INVALID_TASK_QUERY", str(exc)) from exc
        return WorkflowTaskListResponse(tasks=values, count=len(values))

    @router.get(
        "/notifications",
        response_model=NotificationListResponse,
        tags=["workflow"],
        summary="List role-scoped in-product notifications",
    )
    async def notifications(
        request: Request,
        unread_only: bool = Query(False),
        identity: str = Depends(authenticate_request),
    ) -> NotificationListResponse:
        store = _active_saas_store(request)
        try:
            values = await run_in_threadpool(
                store.list_notifications,
                identity,
                unread_only=unread_only,
            )
        except SaaSStoreError as exc:
            raise _store_problem() from exc
        return NotificationListResponse(
            notifications=values,
            unread_count=sum(item["read_at_utc"] is None for item in values),
        )

    @router.post(
        "/notifications/{notification_id}/read",
        response_model=NotificationResponse,
        tags=["workflow"],
        summary="Mark one in-product notification as read",
    )
    async def mark_notification_read(
        notification_id: str,
        request: Request,
        identity: str = Depends(authenticate_request),
    ) -> NotificationResponse:
        store = _active_saas_store(request)
        try:
            value = await run_in_threadpool(
                store.mark_notification_read,
                identity_hash=identity,
                notification_id=notification_id,
            )
        except SaaSStoreError as exc:
            raise ApiProblem(404, "NOTIFICATION_NOT_FOUND", str(exc)) from exc
        return NotificationResponse.model_validate(value)

    @router.get(
        "/approvals",
        response_model=ApprovalListResponse,
        tags=["workflow"],
        summary="List manager approval requests",
    )
    async def approvals(
        request: Request,
        status: str | None = Query(None),
        identity: str = Depends(authenticate_request),
    ) -> ApprovalListResponse:
        await _require_workspace_role(request, identity, {"manager"})
        store = _active_saas_store(request)
        try:
            values = await run_in_threadpool(store.list_approvals, identity, status=status)
        except SaaSStoreError as exc:
            raise ApiProblem(400, "INVALID_APPROVAL_QUERY", str(exc)) from exc
        return ApprovalListResponse(approvals=values, count=len(values))

    @router.patch(
        "/approvals/{approval_id}",
        response_model=ApprovalResponse,
        tags=["workflow"],
        summary="Approve or reject a high-risk agent proposal",
    )
    async def resolve_approval(
        approval_id: str,
        payload: ApprovalResolveRequest,
        request: Request,
        identity: str = Depends(authenticate_request),
    ) -> ApprovalResponse:
        await _require_workspace_role(request, identity, {"manager"})
        store = _active_saas_store(request)
        try:
            value = await run_in_threadpool(
                store.resolve_approval,
                identity_hash=identity,
                approval_id=approval_id,
                decision=payload.decision,
                note=payload.note,
            )
        except SaaSStoreError as exc:
            raise ApiProblem(400, "INVALID_APPROVAL", str(exc)) from exc
        return ApprovalResponse.model_validate(value)

    @router.get(
        "/reports/daily",
        response_model=DailyQualityReportResponse,
        tags=["workflow"],
        summary="Generate a daily workspace quality report",
    )
    async def daily_report(
        request: Request,
        report_date: str | None = Query(None),
        identity: str = Depends(authenticate_request),
    ) -> DailyQualityReportResponse:
        await _require_workspace_role(request, identity, {"manager", "reviewer"})
        active_date = report_date or datetime.now(timezone.utc).date().isoformat()
        store = _active_saas_store(request)
        try:
            value = await run_in_threadpool(store.daily_report, identity, active_date)
        except SaaSStoreError as exc:
            raise ApiProblem(400, "INVALID_REPORT_DATE", str(exc)) from exc
        return DailyQualityReportResponse.model_validate(value)

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
            agent_run_id: str | None = None
            workflow_status = "completed"
            try:
                workflow_run = await run_in_threadpool(
                    _active_autonomous_agent(request).run,
                    identity_hash=identity,
                    inspection_id=inspection["inspection_id"],
                    mode="supervised",
                )
                agent_run_id = workflow_run["run_id"]
            except Exception:
                workflow_status = "failed"
                logger.exception(
                    "Inspection analysis completed but supervised workflow failed",
                    extra={
                        "event": "supervised_workflow_failed",
                        "inspection_id": inspection["inspection_id"],
                    },
                )
            return InspectionAnalyzeResponse(
                inspection=InspectionResponse.model_validate(inspection),
                analysis=analysis,
                workflow_status=workflow_status,
                agent_run_id=agent_run_id,
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


def _active_autonomous_agent(request: Request) -> AutonomousInspectionAgent:
    agent = getattr(request.app.state, "autonomous_agent", None)
    if agent is None:
        raise ApiProblem(
            503,
            "AGENT_RUNTIME_UNAVAILABLE",
            "FreshSense could not access its workflow-agent runtime.",
        )
    return agent


def _active_saas_store(request: Request) -> SaaSStore:
    store = getattr(request.app.state, "saas_store", None)
    status = getattr(request.app.state, "saas_store_status", "starting")
    if store is None or status != "ok":
        raise _store_problem()
    return store


def _active_manager_chat_service(request: Request) -> ManagerChatService:
    service = getattr(request.app.state, "manager_chat_service", None)
    if service is None:
        raise _store_problem()
    return service


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
