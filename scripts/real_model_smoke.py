"""Real model, open-set, semantic RAG, and secure API integration smoke tests."""

from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.fruit_agent import FruitScannerAgent
from agent.state import AgentState
from api.app import create_app
from evaluation.manifest import sha256_file
from evaluation.stress import synthetic_ood_cases
from utils.config import MODEL_PATH


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden-manifest", required=True, type=Path)
    parser.add_argument("--golden-root", required=True, type=Path)
    parser.add_argument("--synthetic-ood-count", type=int, default=96)
    parser.add_argument("--maximum-ood-far", type=float, default=0.10)
    args = parser.parse_args()

    manifest = json.loads(args.golden_manifest.read_text(encoding="utf-8"))
    samples = manifest.get("samples", [])
    if manifest.get("schema_version") != 1 or not samples:
        raise RuntimeError("Golden manifest is empty or invalid.")

    agent = FruitScannerAgent(model_path=MODEL_PATH)
    if not agent.retriever_tool.semantic_ready:
        raise RuntimeError("Semantic RAG did not initialize from the immutable bundle.")

    for sample in samples:
        path = args.golden_root / sample["path"]
        if sha256_file(path) != sample["sha256"]:
            raise RuntimeError(f"Golden image checksum mismatch: {path}")
        with Image.open(path) as source:
            state = _model_policy(agent, source.convert("RGB"))
        if state.decision != "accept_prediction" or state.prediction is None:
            raise RuntimeError(f"Golden supported image was withheld: {path}")
        if state.prediction.class_name != sample["expected_label"]:
            raise RuntimeError(
                f"Golden prediction mismatch for {path}: {state.prediction.class_name}"
            )

    ood_cases = list(synthetic_ood_cases(args.synthetic_ood_count, seed=20260717))
    ood_accepted = 0
    for _, image in ood_cases:
        state = _model_policy(agent, image)
        if state.decision == "accept_prediction":
            ood_accepted += 1
    ood_far = ood_accepted / len(ood_cases)
    if ood_far > args.maximum_ood_far:
        raise RuntimeError(
            f"Synthetic unsupported false-acceptance rate {ood_far:.2%} exceeds "
            f"{args.maximum_ood_far:.2%}."
        )

    first_path = args.golden_root / samples[0]["path"]
    ci_api_key = "freshsense-real-model-ci-key-2026"
    app = create_app(
        agent_factory=lambda: agent,
        api_key=ci_api_key,
        require_api_key=True,
        require_semantic_rag=True,
        allowed_hosts=("testserver",),
        json_logs=False,
    )
    with TestClient(app) as client:
        media_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }[first_path.suffix.lower()]
        rejected = client.post(
            "/api/v1/analyze",
            files={"file": (first_path.name, first_path.read_bytes(), media_type)},
        )
        if rejected.status_code != 401:
            raise RuntimeError("Secure API accepted an unauthenticated analysis request.")
        accepted = client.post(
            "/api/v1/analyze",
            headers={"X-API-Key": ci_api_key},
            files={"file": (first_path.name, first_path.read_bytes(), media_type)},
        )
        if accepted.status_code != 200:
            raise RuntimeError(f"Secure API smoke failed: {accepted.text}")

    print(f"Golden predictions: {len(samples)} passed")
    print(f"Synthetic unsupported FAR: {ood_far:.2%}")
    print("Semantic RAG and authenticated API smoke: passed")
    return 0


def _model_policy(agent: FruitScannerAgent, image: Image.Image) -> AgentState:
    """Exercise the exact gate/classifier/confidence policy without UI advisories."""
    state = AgentState(image=image)
    state = agent.vision_tool.run(state)
    if state.decision != "unsupported_input":
        state = agent.confidence_tool.run(state)
    return state


if __name__ == "__main__":
    raise SystemExit(main())
