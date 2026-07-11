"""Run a real-model API security and semantic-retrieval smoke test."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from api.app import create_app


def main() -> None:
    api_key = os.getenv("FRESHSENSE_API_KEY", "").strip()
    if len(api_key) < 32:
        raise SystemExit(
            "Set FRESHSENSE_API_KEY to an ephemeral value of at least 32 characters."
        )

    sample = next((PROJECT_ROOT / "sample_images" / "bananas").glob("*.png"))
    app = create_app(
        api_key=api_key,
        api_key_file=None,
        require_api_key=True,
        require_semantic_rag=True,
        json_logs=True,
    )

    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        unauthorized = client.post(
            "/api/v1/analyze",
            files={"file": (sample.name, b"not read", "image/png")},
        )
        with sample.open("rb") as image_file:
            analysis = client.post(
                "/api/v1/analyze",
                files={"file": (sample.name, image_file, "image/png")},
                headers={"X-API-Key": api_key},
            )
        metrics = client.get(
            "/api/v1/metrics",
            headers={"X-API-Key": api_key},
        )

    health_body = health.json()
    analysis_body = analysis.json()
    metrics_body = metrics.json()
    if health.status_code != 200 or not health_body["authentication_required"]:
        raise SystemExit("API authentication was not reported as enabled.")
    if not health_body["semantic_retrieval_ready"]:
        raise SystemExit("The required semantic retriever was not ready.")
    if unauthorized.status_code != 401:
        raise SystemExit("The protected analysis route accepted a missing API key.")
    if analysis.status_code != 200:
        raise SystemExit(f"Real-model analysis failed with HTTP {analysis.status_code}.")
    if analysis_body["retrieval"]["method"] != "semantic":
        raise SystemExit("The analysis did not use semantic retrieval.")
    if metrics.status_code != 200 or metrics_body["analysis_count"] != 1:
        raise SystemExit("API metrics did not record the analysis.")
    if api_key in analysis.text or api_key in metrics.text:
        raise SystemExit("The API key appeared in an API response.")

    print(
        "FreshSense secure API source smoke passed: "
        f"prediction={analysis_body['prediction']['class_name']}, "
        f"retrieval={analysis_body['retrieval']['method']}, "
        f"analysis_count={metrics_body['analysis_count']}"
    )


if __name__ == "__main__":
    main()
