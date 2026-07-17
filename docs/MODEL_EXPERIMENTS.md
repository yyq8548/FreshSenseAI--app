# Reproducible model experiments

FreshSense tracks MobileNetV2 comparison runs in a local MLflow SQLite database.
MLflow is a development tool and is not packaged with the desktop runtime.

## Setup

```powershell
python -m pip install -r requirements-training.txt
$env:FRESHSENSE_BENCHMARK_ROOT = "C:\path\to\canonical\dataset"
```

Validate the pipeline with a small, untrained smoke run:

```powershell
python scripts\train_mobilenet_mlflow.py --smoke
```

Run the grouped comparison with ImageNet initialization:

```powershell
python scripts\train_mobilenet_mlflow.py --epochs 12 --run-name grouped-imagenet-v1
```

Open the local experiment UI:

```powershell
mlflow server --backend-store-uri sqlite:///work/mlflow.db --port 5000
```

Each run records the manifest checksum, split counts, hyperparameters, epoch
metrics, final test metrics, model artifact, latency, and evaluation report.

The supplied `fruit-multiclass-problem-mobilenetv2-98.ipynb` targets ten fruit
identities and its dataset contains train/test duplicates. Its reported 98%
result is not a FreshSense freshness benchmark. FreshSense reuses the
MobileNetV2 architecture only and evaluates it against the grouped six-class
fresh/rotten manifest.

Even the grouped legacy comparison is not an independent field-accuracy claim.
The final model decision must use the untouched real-phone benchmark.

## Grouped ImageNet-initialized result

MLflow run `561724080029469c88e3ac73acb8a56e` completed five frozen-backbone
epochs over 9,514 training, 2,043 validation, and 2,043 test images:

| Measure | Result |
|---|---:|
| Classification accuracy | 98.97% |
| Macro F1 | 98.92% |
| Rotten-to-fresh errors | 8 / 1,161 |
| Rotten-to-fresh rate | 0.69% |
| Batch CPU inference | 3.44 ms/image |
| Saved model size | 9.72 MB |

This MobileNetV2 model is approximately 22.7 times smaller than the existing
220.97 MB DenseNet201 artifact. It is a promising candidate for a future
desktop model, but it has not been integrated into the release: it still needs
an independently calibrated supported-input gate and the real-phone benchmark.
