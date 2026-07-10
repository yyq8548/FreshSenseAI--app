# Development Log: Unsupported and Uncertain Result

**Date:** July 10, 2026

## Goal

Prevent ambiguous model outputs from being presented as confident fruit
freshness guidance, while accurately describing the limits of the current
three-fruit classifier.

## Completed

- Added a configurable top-confidence threshold and top-two prediction-margin
  threshold.
- Added the `uncertain_input` decision and `unsupported_or_uncertain` status.
- Withheld tentative fruit classes when a result fails either confidence gate.
- Prevented RAG, shelf-life reasoning, and fruit-specific storage advice from
  running for uncertain results.
- Added a dedicated desktop result titled **Unsupported or uncertain photo**.
- Added equivalent behavior to the Streamlit interface.
- Added a catalog-derived notice showing that the app supports Apple, Banana,
  and Orange, with one fruit type per photo.
- Added regression tests for low confidence, small top-two margins, hidden
  tentative classes, supported-scope copy, and uncertainty recommendations.

## Safety Boundary

The new gate identifies ambiguous outputs; it does not prove that a photo is a
supported fruit. Six-class softmax confidence alone cannot reliably detect all
non-fruit or out-of-distribution images. A future dedicated OOD detector or
negative-data training phase is required for stronger unsupported-image
recognition.
