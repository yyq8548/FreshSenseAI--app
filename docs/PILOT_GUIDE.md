# Limited Pilot Guide

## Scope

Run one controlled use case, such as staff reviewing single-fruit photos under
known indoor lighting. Do not use the pilot to make food-safety decisions or
expand the supported fruit catalog.

## Privacy

Pilot tooling stores metadata only. Use an anonymized `sample_id`; never enter a
local photo path, name, email, or other personal identifier. Keep source photos
in a separately controlled collection if review requires them.

## Workflow

Initialize a local store:

```powershell
python scripts\pilot.py --store C:\FreshSensePilot\pilot.sqlite3 init
```

After a human review, record one outcome:

```powershell
python scripts\pilot.py --store C:\FreshSensePilot\pilot.sqlite3 record `
  --sample-id anon-0001 `
  --reviewer reviewer-a `
  --app-decision accept_prediction `
  --predicted-freshness fresh `
  --reviewed-outcome rotten `
  --confidence 0.98 `
  --device phone-a `
  --lighting indoor-warm `
  --background kitchen `
  --task-seconds 18.4 `
  --result-understood `
  --warning-helpful `
  --would-use-again `
  --usability-rating 4
```

Summarize and export:

```powershell
python scripts\pilot.py --store C:\FreshSensePilot\pilot.sqlite3 summary
python scripts\pilot.py --store C:\FreshSensePilot\pilot.sqlite3 export `
  --output C:\FreshSensePilot\pilot-summary.csv
```

The summary tracks correct, false-fresh, false-rotten, uncertain, unsupported,
retake, non-comparable outcomes, reviewers, task time, comprehension, warning
usefulness, willingness to reuse the tool, and usability ratings.

To migrate an older metadata-only JSONL pilot:

```powershell
python scripts\pilot.py --store C:\FreshSensePilot\pilot.sqlite3 migrate-jsonl `
  --source C:\FreshSensePilot\pilot.jsonl
```

To import the public-beta observation template:

```powershell
python scripts\pilot.py --store C:\FreshSensePilot\pilot.sqlite3 import-csv `
  --source C:\FreshSensePilot\public_beta_observations.csv
```

See `docs/PUBLIC_BETA_PILOT.md` for the known 50-plus participant aggregate
baseline, missing evidence, and the required 0.5 retest report.

## Exit criteria

Define thresholds before collection begins. At minimum, require zero unexplained
false-fresh cases, reviewed unsupported false acceptance below the agreed limit,
acceptable coverage, no severe subgroup failure, and documented review of every
error. A small pilot can reveal problems but cannot prove broad safety.

## Status

The SQLite metadata store, validation, summary, CSV export, migration, and tests are implemented.
No real pilot observations have been created by the development process; those
require an operator and human reviewers.
