from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from PIL import Image


@dataclass
class WarningMessage:
    level: str
    message: str


@dataclass
class ImageQualityResult:
    brightness: float
    edge_strength: float
    is_dark: bool
    is_blurry: bool
    is_overexposed: bool = False


@dataclass
class SceneAnalysisResult:
    image_width: int
    image_height: int
    foreground_ratio: float
    fruit_is_too_small: bool
    likely_empty_scene: bool
    needs_crop_or_closer_photo: bool


@dataclass
class PredictionResult:
    class_name: str
    confidence: float
    raw_probabilities: List[float] = field(default_factory=list)


@dataclass
class RetrievalResult:
    query: str
    documents: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ReasoningResult:
    explanation: str
    shelf_life_estimate: str
    storage_advice: str
    risk_level: str
    source: str = "rule_based"


@dataclass
class AgentState:
    image: Image.Image
    quality: Optional[ImageQualityResult] = None
    scene: Optional[SceneAnalysisResult] = None
    prediction: Optional[PredictionResult] = None
    retrieval: Optional[RetrievalResult] = None
    reasoning: Optional[ReasoningResult] = None
    decision: str = "pending"
    status: str = "initialized"
    recommendation: str = ""
    warnings: List[str] = field(default_factory=list)
    structured_warnings: List[WarningMessage] = field(default_factory=list)
    trace: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_trace(self, message: str) -> None:
        self.trace.append(message)

    def add_warning(self, message: str, level: str = "warning") -> None:
        self.warnings.append(message)
        self.structured_warnings.append(WarningMessage(level=level, message=message))
