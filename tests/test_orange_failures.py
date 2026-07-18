from pathlib import Path

import pytest
from PIL import Image

from agent.state import AgentState, PredictionResult
from evaluation.orange_failures import (
    OrangeFailureManifestError,
    load_orange_failure_manifest,
    serialize_orange_failure,
)


HEADER = "sample_id,image_path,physical_fruit_id,expected_freshness,device,lighting,background,split\n"


def test_orange_manifest_preserves_physical_fruit_split(tmp_path: Path):
    manifest = tmp_path / "orange.csv"
    manifest.write_text(
        HEADER
        + "orange-1,a.png,fruit-a,fresh,phone-a,daylight,table,validation\n"
        + "orange-2,b.png,fruit-a,fresh,phone-a,daylight,table,test\n",
        encoding="utf-8",
    )

    with pytest.raises(OrangeFailureManifestError, match="physical fruit"):
        load_orange_failure_manifest(manifest)


def test_orange_failure_serialization_includes_full_distribution():
    state = AgentState(image=Image.new("RGB", (8, 8)))
    state.decision = "accept_prediction"
    state.status = "prediction_accepted"
    state.prediction = PredictionResult("freshoranges", 0.7, [0.2, 0.7, 0.1])

    result = serialize_orange_failure(
        state,
        sample_id="orange-1",
        class_names=("freshapples", "freshoranges", "rottenoranges"),
    )

    assert result["sample_id"] == "orange-1"
    assert result["prediction_distribution"][0] == {
        "class_name": "freshoranges",
        "probability": 0.7,
    }
