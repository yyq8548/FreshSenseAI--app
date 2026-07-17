from evaluation.metrics import compute_metrics


LABELS = ("freshapple", "rottenapple")
FRESHNESS = {"freshapple": "fresh", "rottenapple": "rotten"}


def _result(**overrides):
    value = {
        "supported": True,
        "accepted": True,
        "gate_accepted": True,
        "true_label": "freshapple",
        "predicted_label": "freshapple",
        "confidence": 0.9,
        "probabilities": [0.9, 0.1],
        "latency_seconds": 0.01,
        "device": "phone-a",
        "lighting": "daylight",
        "background": "plain",
        "collection": "unit-test",
    }
    value.update(overrides)
    return value


def test_metrics_include_safety_critical_rates_and_abstention():
    results = [
        _result(),
        _result(
            true_label="rottenapple",
            predicted_label="freshapple",
            probabilities=[0.8, 0.2],
            confidence=0.8,
        ),
        _result(
            true_label="rottenapple",
            predicted_label=None,
            accepted=False,
            gate_accepted=False,
            confidence=0.55,
            probabilities=[0.55, 0.45],
        ),
        _result(
            supported=False,
            true_label=None,
            predicted_label=None,
            accepted=False,
            gate_accepted=False,
            confidence=0.6,
            probabilities=[0.6, 0.4],
        ),
    ]

    metrics = compute_metrics(
        results, class_labels=LABELS, freshness_by_label=FRESHNESS
    )

    assert metrics["summary"]["coverage"] == 2 / 3
    assert metrics["summary"]["rotten_to_fresh_rate"] == 1 / 2
    assert metrics["summary"]["unsupported_false_acceptance_rate"] == 0.0
    assert metrics["confusion_matrix"]["columns"][-1] == "__withheld__"
    assert metrics["coverage_accuracy_curve"][-1]["coverage"] == 2 / 3
