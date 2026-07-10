"""Backward-compatible constants derived from the runtime fruit catalog."""

from utils.config import FRUIT_CATALOG_PATH
from utils.fruit_catalog import load_fruit_catalog


CLASS_NAMES = list(load_fruit_catalog(FRUIT_CATALOG_PATH).class_names)
