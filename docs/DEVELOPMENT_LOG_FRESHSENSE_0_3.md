# FreshSense 0.3 Development Log

## Goal

Move FreshSense from six-way softmax-only confidence toward defensible model
reliability, calibrated abstention, unsupported-input rejection, reproducible
evaluation, immutable artifacts, real-model CI, and a controlled pilot workflow.

## Dataset audit

- Located two near-duplicate dataset trees and selected the more complete
  13,600-image canonical tree.
- Reconstructed 1,512 source groups by removing known augmentation prefixes.
- Found 1,310 legacy test source groups and confirmed that every one appears in
  legacy training, making the overlap fraction 100%.
- Created a deterministic 70/15/15 source-grouped manifest with per-image hashes.

## Safety gate

- Added a required, model-bound open-set artifact using DenseNet `avg_pool`
  features.
- Represented each supported fruit with fresh and rotten prototypes, while the
  gate decision answers one fruit-identity question.
- Added model hash, catalog hash, manifest hash, feature layer, prototype order,
  thresholds, calibration source, and calibration settings to the artifact.
- Added fail-closed startup, fruit/gate disagreement handling, desktop/API
  unsupported results, and removal of fruit-specific reasoning on rejection.
- Used separate synthetic calibration and test seeds and capped threshold tuning
  to preserve at least 90% validation coverage per class.

## Evaluation

- Added per-class precision, recall, F1, confusion matrix, rotten-to-fresh rate,
  unsupported false acceptance, calibration error, Brier score,
  coverage/accuracy, subgroup metrics, and CPU latency.
- Added JSON, CSV, confusion, reliability, and coverage report artifacts.
- Added a real-world annotation template and manifest builder that prevents
  physical-source leakage.
- Frozen software-behavior test result: 96.48% legacy supported coverage and
  5.73% separate-seed synthetic unsupported false acceptance. These are not
  independent field metrics.

## Reproducibility and operations

- Added a model card and benchmark collection protocol.
- Added a cryptographic runtime/evaluation artifact manifest and verifier.
- Added golden-suite generation, real-model/RAG/secure-API smoke testing, an
  immutable runtime bundle, and scheduled/manual Windows integration workflow.
- Added metadata-only controlled-pilot recording, summary, and export tooling.
- Updated the Windows package inputs to include the required gate and evaluation
  association artifacts.

## Remaining evidence

Independent photographs, adjudicated labels, retraining with source-group
isolation, an untouched real-world test run, and real pilot observations remain
human/data collection work. FreshSense 0.3 intentionally reports those gaps
instead of converting legacy or synthetic results into production claims.
