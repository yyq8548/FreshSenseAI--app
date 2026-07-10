"""FastAPI application factory for the FreshSense inference service."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from io import BytesIO
import logging
import warnings

from fastapi import APIRouter, FastAPI, File, Request, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from agent.fruit_agent import FruitScannerAgent
from api.models import AnalyzeResponse, ErrorResponse, HealthResponse
from api.serialization import serialize_agent_state
from utils.config import (
    API_MAX_IMAGE_PIXELS,
    API_MAX_UPLOAD_BYTES,
    FRUIT_CATALOG_PATH,
    KNOWLEDGE_BASE_PATH,
    MODEL_PATH,
)
from utils.startup import validate_startup


logger = logging.getLogger(__name__)
AgentFactory = Callable[[], FruitScannerAgent]

ACCEPTED_IMAGE_FORMATS = {
    "image/jpeg": "JPEG",
    "image/jpg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


class ApiProblem(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _production_agent_factory() -> FruitScannerAgent:
    validate_startup(
        model_path=MODEL_PATH,
        knowledge_base_path=KNOWLEDGE_BASE_PATH,
        fruit_catalog_path=FRUIT_CATALOG_PATH,
    )
    return FruitScannerAgent(
        model_path=MODEL_PATH,
        catalog_path=FRUIT_CATALOG_PATH,
        knowledge_base_path=KNOWLEDGE_BASE_PATH,
    )


def create_app(
    *,
    agent_factory: AgentFactory | None = None,
    max_upload_bytes: int = API_MAX_UPLOAD_BYTES,
    max_image_pixels: int = API_MAX_IMAGE_PIXELS,
) -> FastAPI:
    """Create an API instance; dependency injection keeps tests model-free."""
    if max_upload_bytes <= 0:
        raise ValueError("max_upload_bytes must be positive.")
    if max_image_pixels <= 0:
        raise ValueError("max_image_pixels must be positive.")

    factory = agent_factory or _production_agent_factory

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        agent = await run_in_threadpool(factory)
        application.state.agent = agent
        application.state.inference_lock = asyncio.Lock()
        application.state.max_upload_bytes = max_upload_bytes
        application.state.max_image_pixels = max_image_pixels
        try:
            yield
        finally:
            application.state.agent = None

    application = FastAPI(
        title="FreshSense AI API",
        summary="Private fruit-freshness analysis with local semantic retrieval.",
        description=(
            "A versioned HTTP interface around the FreshSense vision and reasoning agent. "
            "Uploaded images are decoded only for the current request and are not retained "
            "in application storage."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    @application.exception_handler(ApiProblem)
    async def api_problem_handler(_request: Request, exc: ApiProblem) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

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
        )

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
            413: {"model": ErrorResponse, "description": "Upload or decoded image too large."},
            415: {"model": ErrorResponse, "description": "Unsupported or mismatched media type."},
            500: {"model": ErrorResponse, "description": "Analysis failed safely."},
            503: {"model": ErrorResponse, "description": "Model is not ready."},
        },
    )
    async def analyze(
        request: Request,
        file: UploadFile = File(
            ...,
            description="A JPEG, PNG, or WebP photo containing one supported fruit type.",
        ),
    ) -> AnalyzeResponse:
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
            agent = _active_agent(request)
            try:
                async with request.app.state.inference_lock:
                    state = await run_in_threadpool(agent.run, image)
                return serialize_agent_state(state, agent.catalog)
            except ApiProblem:
                raise
            except Exception as exc:
                logger.exception("FreshSense analysis failed", exc_info=exc)
                raise ApiProblem(
                    500,
                    "ANALYSIS_FAILED",
                    "FreshSense could not complete this analysis.",
                ) from exc
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
