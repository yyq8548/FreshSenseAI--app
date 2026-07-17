# Real-world Benchmark Collection Protocol

## Objective

Create an independent validation and test benchmark that measures supported
fruit classification, freshness errors, abstention, unsupported false
acceptance, calibration, subgroup behavior, and CPU latency. The existing
augmented dataset cannot provide this evidence because its legacy train and test
source groups overlap completely.

## Collection matrix

Collect independently photographed apples, bananas, and oranges across:

- at least three phone models;
- daylight, warm indoor, cool indoor, dim, and backlit conditions;
- plain, kitchen, store, outdoor, cluttered, and hand-held backgrounds;
- multiple cultivars, sizes, orientations, occlusion levels, and distances;
- fresh, borderline, visibly spoiled, bruised, mold-like, and damaged stages;
- multiple physical specimens per class and condition.

The unsupported set should be at least as large as the supported test set and
include other fruits, vegetables, packaged food, prepared food, household
objects, people, empty scenes, drawings/screens, noise, and mixed-fruit scenes.

## Leakage prevention

Assign one `source_group` to every physical fruit specimen, unsupported object,
scene, or short capture burst. Every photo in one group must remain entirely in
validation or entirely in test. A physical specimen must never cross the split,
even when captured by another phone, angle, or lighting condition.

Use validation data to choose thresholds. Freeze the model, preprocessing,
prototype centroids, confidence threshold, margin threshold, and open-set
thresholds before evaluating test. Do not repeatedly inspect test results and
retune.

## Annotation workflow

1. Copy `evaluation/manifests/real_world_annotations_template.csv`.
2. Use anonymized sample IDs and relative image paths.
3. For supported images, enter the exact six-class label.
4. For unsupported images, set `supported=false` and leave `label` blank.
5. Record device, lighting, background, collection batch, reviewer, and notes.
6. Obtain permission and document licensing/consent outside the repository when
   people or private property appear.
7. Have a second reviewer adjudicate ambiguous freshness labels.

Build the immutable manifest:

```powershell
python scripts\build_real_world_manifest.py `
  --annotations C:\benchmark\annotations.csv `
  --images C:\benchmark\images `
  --output evaluation\manifests\real_world_v1.json
```

The builder hashes each image and rejects missing files, invalid labels,
duplicate IDs, path traversal, and source groups crossing split boundaries.

## Evaluation

Calibrate a new gate with validation only, freeze the resulting artifact, and
evaluate test:

```powershell
python scripts\run_evaluation.py `
  --manifest evaluation\manifests\real_world_v1.json `
  --dataset C:\benchmark\images `
  --split test `
  --synthetic-ood-count 0 `
  --output evaluation\reports\real_world_v1
```

Review per-class precision, recall, F1, confusion matrix, rotten-to-fresh rate,
unsupported false acceptance, calibration error, coverage/accuracy, device,
lighting and background segments, and CPU latency. Establish acceptance criteria
before opening the test report.

## Status

The manifest builder, validation rules, evaluator, metrics, plots, and templates
are implemented. Independent photos and human-reviewed annotations have not yet
been collected; that remaining work cannot be generated from the legacy data.
