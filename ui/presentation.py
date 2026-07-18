"""Pure presentation helpers for the Streamlit interface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent.state import AgentState


SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
FRUIT_ORDER = ("apple", "banana", "orange")


@dataclass(frozen=True)
class SampleImage:
    fruit_id: str
    display_name: str
    path: Path


def discover_sample_images(root: Path, per_fruit: int = 2) -> list[SampleImage]:
    """Return a small deterministic gallery without traversing duplicate folders."""
    if per_fruit < 1:
        raise ValueError("per_fruit must be at least one")

    samples: list[SampleImage] = []
    for fruit_id in FRUIT_ORDER:
        folder = root / ("bananas" if fruit_id == "banana" else f"{fruit_id}s")
        files = (
            sorted(
                path
                for path in folder.iterdir()
                if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
            )
            if folder.is_dir()
            else []
        )
        samples.extend(
            SampleImage(fruit_id, fruit_id.title(), path)
            for path in files[:per_fruit]
        )
    return samples


def result_tone(state: AgentState) -> str:
    """Map an agent decision to a stable visual tone."""
    if state.decision == "accept_prediction":
        if state.reasoning and state.reasoning.risk_level.lower() == "high":
            return "danger"
        return "success"
    if state.decision in {"unsupported_input", "uncertain_input"}:
        return "caution"
    return "neutral"


def analysis_signature(source_name: str, image_bytes: bytes) -> str:
    """Build a stable key that prevents stale results after image changes."""
    from hashlib import sha256

    return f"{source_name}:{sha256(image_bytes).hexdigest()[:16]}"
