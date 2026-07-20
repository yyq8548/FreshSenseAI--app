# Expanded 12-class model training

FreshSense expands the existing apple, banana, and orange model with fresh and
rotten mango, tomato, and pear classes. The new COCO exports are converted to
classification crops from their annotated bounding boxes.

## Data integrity rules

- All crops from one source image stay in one benchmark split.
- Roboflow suffixes are removed before source grouping.
- Exact output hashes and source group IDs must not cross splits.
- Unannotated images and invalid/tiny bounding boxes are excluded.
- Metrics from these source exports are development metrics, not an independent
  real-world store benchmark.

## Selected development artifact

The selected candidate uses an ImageNet-pretrained DenseNet201 frozen backbone
and a 12-class head. Its active local path is `models/densenet201.h5`; model
binaries remain excluded from Git and must be supplied through the reviewed
runtime or release bundle. The selected model SHA-256, gate SHA-256, class
order, evaluation report, and dataset-manifest hash are bound in
`artifacts/model_manifest.json`.

## Windows preparation

Run `scripts/enable_wsl_gpu.ps1` in an Administrator PowerShell and restart
Windows if requested. Ubuntu 24.04 runs under WSL2; the customer-facing Windows
application does not depend on WSL.

## GPU environment

From Ubuntu, run this command from the repository root:

```bash
bash scripts/setup_wsl_tensorflow_gpu.sh
```

## Prepare the dataset

The prepared dataset is generated outside the Git repository:

```powershell
py -3.11 scripts\prepare_expanded_dataset.py `
  --source "C:\path\to\fruit_scanner\dataset" `
  --output "C:\path\to\fruit_scanner\prepared_expanded_v2"
```

## Train the selected ImageNet head

Run from WSL2 and pass the prepared dataset as a Linux path under `/mnt/c`:

```bash
bash scripts/run_wsl_gpu_imagenet.sh /mnt/c/path/to/prepared_expanded_v2
```

The candidate model is written as `models/densenet201-imagenet-expanded.h5`.
Alternative legacy-backbone training and fine-tuning experiments remain
available through `run_wsl_gpu_training.sh` and `run_wsl_gpu_finetune.sh`, but
their evaluation results did not outperform the selected candidate.

## Calibrate, evaluate, and smoke-test

```bash
bash scripts/run_wsl_build_expanded_gate.sh /mnt/c/path/to/prepared_expanded_v2
bash scripts/run_wsl_evaluate_expanded.sh /mnt/c/path/to/prepared_expanded_v2
```

After the reviewed candidate model and gate are copied to their active runtime
paths, validate on Windows:

```powershell
py -3.11 scripts\create_artifact_manifest.py
py -3.11 scripts\verify_model_artifacts.py
py -3.11 scripts\smoke_expanded_model.py `
  --dataset "C:\path\to\prepared_expanded_v2"
py -3.11 -m pytest tests -q
```

Do not promote a candidate that fails startup validation, artifact association,
all-class smoke testing, or the main automated test suite.
