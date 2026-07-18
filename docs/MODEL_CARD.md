# FreshSense DenseNet201 Model Card

## Model details

- Application release: FreshSense 0.5.1 Public Beta
- Task: six-class visible fruit freshness classification
- Supported fruit identities: apple, banana, orange
- Output order: `freshapples`, `freshbanana`, `freshoranges`, `rottenapples`, `rottenbanana`, `rottenoranges`
- Architecture: Keras DenseNet201 with a six-class softmax output
- Input: RGB image resized to 224 x 224 and scaled to `[0, 1]`
- Model SHA-256: `81a4ec243781885a6a835bbd94392cd391ed6b7d8274e732911330cff33afbf4`
- Model size: 220,970,424 bytes
- Safety gate: cosine distance to six calibrated feature prototypes, mapped to three fruit identities
- Artifact association: `artifacts/model_manifest.json`

The available training notebook constructs DenseNet201 with `weights=None`, uses
categorical cross-entropy with Adam, and configures 30 epochs. The saved model is
the source of every visual prediction. FreshSense does not substitute random,
placeholder, or GPT-generated visual labels.

## Intended use

FreshSense provides visual decision support for a clear photograph containing
one apple, banana, or orange. It may withhold a result when the image is poor,
the input is unlike calibrated supported fruit, the gate and classifier disagree
on fruit identity, or prediction confidence/margin is insufficient.

It is not a food-safety device. It cannot detect contamination, internal
spoilage, odor, texture, pathogens, chemical hazards, or whether food is safe to
eat. It must not be used as the only basis for consumption or disposal.

## Dataset audit

The canonical local dataset contains 13,600 image files across six classes:

| Class | Legacy train | Legacy test |
| --- | ---: | ---: |
| freshapples | 1,693 | 395 |
| freshbanana | 1,581 | 381 |
| freshoranges | 1,466 | 388 |
| rottenapples | 2,342 | 601 |
| rottenbanana | 2,225 | 530 |
| rottenoranges | 1,595 | 403 |

The files reduce to 1,512 source-image groups after known augmentation prefixes
are removed. The legacy train split contains all 1,512 groups; the legacy test
split contains 1,310 groups, and all 1,310 also occur in training. Therefore the
legacy test-group overlap fraction is 100%.

FreshSense 0.3 creates a deterministic source-grouped manifest with 1,058 train,
227 validation, and 227 test groups. This prevents leakage inside the new
manifest. It does not undo the fact that the existing model was already trained
on the old leaked train split, which contains every source group.

## Current evaluation

The frozen software-behavior report uses the grouped test records and a separate
synthetic unsupported test seed:

| Metric | Result |
| --- | ---: |
| Supported images | 2,043 |
| Accepted supported images | 1,971 |
| Coverage | 96.48% |
| Selective accuracy when accepted | 100.00% |
| Rotten-to-fresh errors | 0 / 1,161 |
| Synthetic unsupported images | 192 |
| Synthetic unsupported false acceptance | 11 / 192 (5.73%) |
| Median model/gate batch latency per image | 14.9 ms |
| P95 model/gate batch latency per image | 50.9 ms |

These supported-image accuracy values are not independent real-world accuracy
and must not be advertised as such. The current model has already seen source
groups represented in this report. Synthetic patterns are useful regression
tests but are not substitutes for real photographs of unsupported content.

## Calibration

The open-set artifact is calibrated on the grouped validation portion using the
DenseNet `avg_pool` feature layer. Six freshness prototypes map to three fruit
identities. Initial thresholds retain 95% of each supported validation class;
synthetic unsupported calibration may raise a threshold, but a coverage cap
prevents it from retaining less than 90% of any class. Synthetic calibration and
test use different deterministic seeds.

The gate is model-bound: startup verifies that its model SHA-256 and prototype
order match the installed model and fruit catalog. It is a safety baseline, not
a validated arbitrary-object detector.

## Known failure modes

- Non-fruit and abstract inputs can still resemble supported features; the
  separate-seed synthetic false-acceptance rate is currently 5.73%.
- Mixed-fruit scenes are outside the intended input contract.
- Lighting, backgrounds, phone cameras, compression, occlusion, cultivars, and
  freshness stages are not yet represented by an independent field benchmark.
- Softmax confidence is often near 100% even for unsupported images and must
  never be interpreted as general certainty.
- The current model was trained on a leaked legacy split.
- Freshness labels are visual categories and do not establish food safety.
- Earlier informal testing reportedly included three incorrectly distinguished
  orange cases. The photos and case-level metadata have not yet been reviewed,
  so no orange error rate or improvement claim is available.

## Required evidence before a production claim

1. Independently collect supported and unsupported photographs using the
   protocol in `docs/BENCHMARK_COLLECTION.md`.
2. Freeze thresholds on the validation split, then evaluate the untouched test
   split once.
3. Retrain the classifier with physical-source grouping and rerun the complete
   evaluation package.
4. Meet reviewed acceptance criteria for false-fresh, false-rotten,
   unsupported false acceptance, calibration, coverage, and subgroup behavior.
5. Complete the limited pilot in `docs/PILOT_GUIDE.md`.

## Reproducibility artifacts

- Grouped legacy manifest: `evaluation/manifests/legacy_grouped_v1.json`
- Gate calibration: `evaluation/reports/gate_calibration_final.json`
- Evaluation report and plots: `evaluation/reports/current_model/`
- Runtime artifact manifest: `artifacts/model_manifest.json`
- Builder: `scripts/build_open_set_gate.py`
- Evaluator: `scripts/run_evaluation.py`
- Verifier: `scripts/verify_model_artifacts.py`
