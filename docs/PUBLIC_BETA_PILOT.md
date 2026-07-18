# FreshSense 0.5 Public Beta Pilot

## Known baseline

The project owner reported more than 50 participants, mostly positive feedback,
and three orange errors. The earlier sessions did not capture enough
case-level metadata to calculate total-image accuracy, orange error rate,
warning comprehension, or task time. The preserved aggregate baseline is in
`pilot/data/public_beta_baseline_v1.json`.

## Collect the next round

1. Copy `pilot/templates/public_beta_observations.csv` outside the repository.
2. Use anonymized participant and sample IDs. Do not enter names, emails, photo
   paths, or filenames.
3. Record one row per independently reviewed analysis.
4. Use one physical fruit ID in the separate evaluation manifest and keep all
   photos of that specimen in one split.
5. Import and summarize:

```powershell
python scripts\pilot.py --store C:\FreshSensePilot\beta.sqlite3 import-csv `
  --source C:\FreshSensePilot\public_beta_observations.csv
python scripts\pilot.py --store C:\FreshSensePilot\beta.sqlite3 summary
python scripts\pilot.py --store C:\FreshSensePilot\beta.sqlite3 export `
  --output C:\FreshSensePilot\reviewed_results.csv
```

## Required report

Publish only aggregate, human-reviewed results:

- unique participants and total reviewed images;
- results by apple, banana, and orange;
- correct, false-fresh, false-rotten, uncertain, unsupported, and retake counts;
- the conditions and review outcome for each of the three orange failures;
- median analysis task time;
- result-comprehension and warning-helpfulness rates;
- the exact product or model change caused by feedback; and
- matched before-and-after orange results on an untouched test set.

Only after the matched retest may the project claim that orange
misclassification was reduced from a measured value to another measured value.
