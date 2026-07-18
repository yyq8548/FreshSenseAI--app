from urllib.parse import parse_qs, urlparse

from PIL import Image

from agent.state import AgentState, PredictionResult
from utils.feedback import build_feedback_url


def test_feedback_url_contains_version_and_result_but_no_photo_data():
    state = AgentState(image=Image.new("RGB", (8, 8)))
    state.decision = "accept_prediction"
    state.status = "prediction_accepted"
    state.prediction = PredictionResult("freshoranges", 0.91, [0.91])

    body = parse_qs(urlparse(build_feedback_url(state)).query)["body"][0]

    assert "FreshSense version: 0.5.1" in body
    assert "freshoranges" in body
    assert "0.9100" in body
    assert "photo path" not in body.lower()
    assert "image bytes" not in body.lower()


def test_feedback_url_withholds_tentative_prediction():
    state = AgentState(image=Image.new("RGB", (8, 8)))
    state.decision = "uncertain_input"
    state.prediction = PredictionResult("freshoranges", 0.51, [0.51])

    body = parse_qs(urlparse(build_feedback_url(state)).query)["body"][0]

    assert "Exposed prediction: withheld" in body
    assert "freshoranges" not in body
