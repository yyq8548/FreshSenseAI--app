# FreshSense 0.4 development log

## Objective

Reframe FreshSense as a business-driven, explainable, evaluated AI MVP with
clear stakeholder validation and Technology-team handoff evidence.

## Implemented

- Added a stakeholder case study with workflow, value hypothesis, success
  criteria, evidence, assumptions, and pilot design.
- Added a Technology handoff covering architecture, dependencies, API,
  privacy, security, observability, AI governance, and production gaps.
- Added Grad-CAM influence maps for accepted predictions. The desktop renders
  overlays in memory, while the REST API includes PNG bytes only when
  `include_explanation=true` is requested.
- Added a grouped MobileNetV2 comparison pipeline tracked by MLflow 3.14 in a
  local SQLite backend. The pipeline logs manifest checksums, parameters,
  metrics, model artifacts, and reports.
- Replaced the pilot JSONL default with SQLite and added task time,
  comprehension, warning usefulness, willingness-to-reuse, usability rating,
  migration, aggregation, and CSV export.
- Added a separate fictional insurance-policy RAG example with citations,
  semantic/keyword retrieval, abstention, a typed FastAPI surface, human-review
  constraints, and an eight-question evaluation.
- Added an evidence-based Azure readiness gate. It intentionally blocks
  deployment until independent benchmark, pilot, automated tests, security
  review, and accountable-owner approvals exist.

## Validation completed during development

- Grad-CAM generated a 7x7 influence map from the actual DenseNet201 model.
- Focused Grad-CAM, API, and safety tests passed.
- A small untrained MobileNetV2 smoke run completed and verified the MLflow
  path. The full five-epoch ImageNet-initialized comparison then reached 98.97%
  grouped classification accuracy, 98.92% macro F1, a 0.69% rotten-to-fresh
  rate, 3.44 ms/image batch CPU inference, and a 9.72 MB saved artifact.
- SQLite pilot initialization, empty summary, and focused tests passed.
- The fictional insurance RAG passed all eight evaluation questions in both
  semantic and keyword-fallback modes.
- The Azure gate passed its positive/negative unit tests and correctly returned
  `blocked` for the current project evidence.
- The complete automated suite passed on Windows: 119 tests, 0 failures. Model
  artifact verification and Python bytecode compilation also completed.

## Remaining human/data work

- Collect and review the independent phone-photo benchmark.
- Run the multi-reviewer stakeholder pilot.
- Obtain business, Technology, and security approval before cloud deployment.
