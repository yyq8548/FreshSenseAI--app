# Orange Reliability Plan

## Current evidence

The project owner reported more than 50 participants and three cases where an
orange result was not distinguished correctly. Case-level images, exact test
counts, reviewed outcomes, and repeat-test results are not yet available. The
project therefore cannot calculate an orange error-rate reduction yet.

## Reproduce the three cases

1. Ask each participant for an optional test photo and test conditions. Do not
   collect names, email addresses, local paths, or unrelated personal content.
2. Assign an anonymized sample ID and physical fruit ID.
3. Complete `evaluation/orange_failure_review/manifest_template.csv`.
4. Keep every photo of the same physical orange in one split.
5. Run:

```powershell
python scripts\analyze_orange_failures.py `
  --manifest evaluation\orange_failure_review\manifest.csv `
  --output evaluation\orange_failure_review\report.json `
  --overlay-dir evaluation\orange_failure_review\overlays
```

The report records the complete six-class distribution, gate result, image
quality, scene diagnostics, warnings, input checksum, and optional Grad-CAM
overlay without copying the source photo into the report.

## Improve the dataset

- Photograph multiple physical oranges across phones, daylight, warm indoor
  light, dark scenes, plain and cluttered backgrounds, compression levels,
  cultivars, ripeness stages, surface blemishes, and decay stages.
- Add difficult negatives including mandarins, tangerines, grapefruit, apples,
  orange-colored objects, mixed fruit, packaged food, and empty scenes.
- Group by physical specimen before splitting. Never let augmented or repeated
  views of one fruit cross train, validation, and test.
- Use validation only for model selection, gate calibration, and threshold
  freezing. Evaluate the final test split once.

## Acceptance evidence

Report per-class precision, recall, F1, rotten-to-fresh error rate, unsupported
false acceptance, calibration error, coverage, phone and lighting subgroups,
and CPU latency. Review every orange error and update `docs/MODEL_CARD.md` and
the evaluation report before making an accuracy-improvement claim.
