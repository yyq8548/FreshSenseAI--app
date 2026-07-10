# FreshSense AI configuration
# Centralizes thresholds, model paths, and UI settings.

import os
from pathlib import Path
import sys

APP_TITLE = "FreshSense AI"
APP_ICON = "🍎"
APP_LAYOUT = "centered"

PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
MODEL_PATH = os.getenv("FRESHSENSE_MODEL_PATH", str(PROJECT_ROOT / "models" / "densenet201.h5"))
IMAGE_SIZE = (224, 224)

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

# Safety copy is centralized so every user-facing surface presents the same
# limitations. This application is decision support, not a food-safety test.
SAFETY_NOTICE = (
    "FreshSense provides visual decision support only. It cannot detect every "
    "food-safety hazard, internal spoilage, contamination, odor, or texture. "
    "When in doubt, do not consume the fruit."
)
