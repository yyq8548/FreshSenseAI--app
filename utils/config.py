# FreshSense AI configuration
# Centralizes thresholds, model paths, and UI settings.

import os
from pathlib import Path
import sys

APP_TITLE = "FreshSense AI"
APP_ICON = "🍎"
APP_LAYOUT = "wide"

PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
MODEL_PATH = os.getenv("FRESHSENSE_MODEL_PATH", str(PROJECT_ROOT / "models" / "densenet201.h5"))
OPEN_SET_GATE_PATH = os.getenv(
    "FRESHSENSE_OPEN_SET_GATE_PATH",
    str(PROJECT_ROOT / "models" / "open_set_gate.npz"),
)
REQUIRE_OPEN_SET_GATE = (
    os.getenv("FRESHSENSE_REQUIRE_OPEN_SET_GATE", "true").lower() == "true"
)
IMAGE_SIZE = (224, 224)
ENABLE_GRADCAM = os.getenv("FRESHSENSE_ENABLE_GRADCAM", "true").lower() == "true"

MIN_CONFIDENCE = 0.70
MIN_PREDICTION_MARGIN = 0.15

DARK_THRESHOLD = 60.0
OVEREXPOSED_THRESHOLD = 235.0
BLUR_THRESHOLD = 80.0

MIN_FOREGROUND_RATIO = 0.005
SMALL_FRUIT_RATIO = 0.015
EDGE_THRESHOLD_FLOOR = 20.0

# LLM settings
USE_LLM_REASONING = os.getenv("USE_LLM_REASONING", "true").lower() == "true"
LLM_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"

# RAG settings
KNOWLEDGE_BASE_PATH = os.getenv(
    "FRESHSENSE_KNOWLEDGE_BASE_PATH",
    str(PROJECT_ROOT / "data" / "food_knowledge_base.json"),
)
FRUIT_CATALOG_PATH = os.getenv(
    "FRESHSENSE_FRUIT_CATALOG_PATH",
    str(PROJECT_ROOT / "data" / "fruit_catalog.json"),
)
RAG_TOP_K = 3
SEMANTIC_RAG_ENABLED = os.getenv("FRESHSENSE_SEMANTIC_RAG", "true").lower() == "true"
EMBEDDING_MODEL_NAME = os.getenv(
    "FRESHSENSE_EMBEDDING_MODEL",
    "BAAI/bge-small-en-v1.5",
)
EMBEDDING_CACHE_DIR = os.getenv(
    "FRESHSENSE_EMBEDDING_CACHE_DIR",
    str(PROJECT_ROOT / "models" / "embedding_cache"),
)
# Production builds bundle the model and never need a first-run download.
EMBEDDING_LOCAL_FILES_ONLY = (
    os.getenv("FRESHSENSE_EMBEDDING_LOCAL_ONLY", "true").lower() == "true"
)
EMBEDDING_THREADS = 2

# REST API limits. Uploads are never retained by the application.
API_MAX_UPLOAD_BYTES = int(
    os.getenv("FRESHSENSE_API_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))
)
API_MAX_IMAGE_PIXELS = int(os.getenv("FRESHSENSE_API_MAX_IMAGE_PIXELS", "25000000"))
API_REQUIRE_API_KEY = os.getenv("FRESHSENSE_REQUIRE_API_KEY", "false").lower() == "true"
API_KEY_FILE = os.getenv("FRESHSENSE_API_KEY_FILE")
API_RATE_LIMIT_PER_MINUTE = int(
    os.getenv("FRESHSENSE_API_RATE_LIMIT_PER_MINUTE", "30")
)
API_ALLOWED_HOSTS = tuple(
    value.strip()
    for value in os.getenv(
        "FRESHSENSE_ALLOWED_HOSTS",
        "127.0.0.1,localhost,testserver",
    ).split(",")
    if value.strip()
)
API_CORS_ORIGINS = tuple(
    value.strip()
    for value in os.getenv("FRESHSENSE_CORS_ORIGINS", "").split(",")
    if value.strip()
)
API_JSON_LOGS = os.getenv("FRESHSENSE_JSON_LOGS", "false").lower() == "true"
API_REQUIRE_SEMANTIC_RAG = (
    os.getenv("FRESHSENSE_REQUIRE_SEMANTIC_RAG", "false").lower() == "true"
)

# Safety copy is centralized so every user-facing surface presents the same
# limitations. This application is decision support, not a food-safety test.
SAFETY_NOTICE = (
    "FreshSense provides visual decision support only. It cannot detect every "
    "food-safety hazard, internal spoilage, contamination, odor, or texture. "
    "When in doubt, do not consume the fruit."
)
