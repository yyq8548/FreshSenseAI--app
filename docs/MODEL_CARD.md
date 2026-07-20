# FreshSense DenseNet201 Model Card

## Model details

- Status: FreshSense 0.6.0 public-beta release candidate
- Task: visible fresh/rotten classification for six supported produce types
- Supported identities: apple, banana, orange, mango, tomato, pear
- Architecture: ImageNet-pretrained DenseNet201 frozen visual backbone with a 12-class softmax head
- Input: one RGB image resized to 224 x 224 and scaled to `[0, 1]`
- Feature layer: `avg_pool` (1,920 values)
- Model SHA-256: `854a2451acf4df828092ab75bebff01cbc48361c862557415d589ca477d775cf`
- Model size: 74,817,136 bytes
- Gate SHA-256: `dc7b078fa523a23111598b1a29a5acdc27f04ff884d424ef19bdf0420503cc7c`

Output order:

```text
freshapples, freshbanana, freshoranges, freshmango, freshtomato, freshpear,
rottenapples, rottenbanana, rottenoranges, rottenmango, rottentomato, rottenpear
```

The ImageNet normalization is embedded in the saved model. The trained model is
the source of every visual label; FreshSense does not substitute a random,
placeholder, or GPT-generated prediction.

## Intended use

FreshSense provides visual decision support for a clear photograph containing
one supported fruit or tomato type. It can withhold a result when the image is
poor, unlike the calibrated supported inputs, conflicts with the predicted
fruit identity, or has insufficient confidence or class margin.

It is not a food-safety device. It cannot detect contamination, internal
spoilage, odor, texture, pathogens, chemical hazards, or whether food is safe to
eat. Store staff must inspect the produce and may override the model.

## Dataset and split controls

The expanded prepared dataset contains 26,667 classification images/crops from
8,049 source groups across 12 classes. Apple, banana, and orange come from the
legacy class folders. Mango, tomato, and pear are cropped from COCO bounding-box
exports. Unannotated images and invalid/tiny boxes are excluded.

| Split | Images | Source groups |
| --- | ---: | ---: |
| Train | 18,598 | 5,636 |
| Validation | 4,026 | 1,208 |
| Test | 4,043 | 1,205 |

Roboflow suffixes are removed before grouping, and every crop from one source
image stays in one split. Automated checks found zero source-group and zero
exact-output-hash overlap across the three splits.

These controls remove the identified split leakage from this evaluation
package. They do not make the dataset an independently collected store
benchmark: source provenance, physical-fruit identity, phone, lighting, and
background are incomplete.

## Development evaluation

Without the withholding policy, the 4,043-image grouped test result is:

| Metric | Result |
| --- | ---: |
| Accuracy | 98.54% |
| Macro F1 | 98.72% |
| Rotten-to-fresh errors | 27 / 2,158 (1.25%) |

Selected class F1 results:

| Class | F1 |
| --- | ---: |
| Fresh / rotten mango | 98.21% / 97.60% |
| Fresh / rotten tomato | 98.23% / 96.54% |
| Fresh / rotten pear | 99.67% / 100.00% |

With the model-bound open-set gate, 70% minimum confidence, and 15% minimum
top-two margin:

| Metric | Result |
| --- | ---: |
| Supported images | 4,043 |
| Accepted / withheld | 3,585 / 458 |
| Coverage | 88.67% |
| Selective accuracy when accepted | 99.16% |
| Overall accuracy including withheld | 87.93% |
| Rotten-to-fresh errors | 19 / 2,158 (0.88%) |
| Synthetic unsupported false acceptance | 0 / 192 |

These are grouped development results, not independent real-world accuracy.
Synthetic unsupported patterns are regression tests and are not substitutes for
photographs of other produce, objects, people, mixed scenes, and retail shelves.

## Calibration and artifact binding

The open-set artifact uses 12 class centroids from the DenseNet `avg_pool`
features. Thresholds target 95% own-class validation coverage, with a 90%
minimum coverage cap and separate deterministic synthetic calibration data.
Observed validation gate coverage is 96.97%; the synthetic calibration false
acceptance rate is 0%.

Startup verifies the gate model checksum, feature size, and exact prototype
order against the model and fruit catalog. Any mismatch fails closed.

## Known failure modes

- The accepted test set still contains rotten-to-fresh errors; human review is mandatory.
- Mixed-fruit scenes and images containing multiple produce types are outside the input contract.
- Other fruit varieties or retail objects can still resemble supported features.
- Real phone, lighting, background, cultivar, maturity, and damage conditions are not independently benchmarked.
- Freshness labels describe visible source-dataset categories and do not establish food safety.
- Softmax confidence covers only the 12 configured categories and is not general certainty.
- COCO crops can be easier than uncropped customer photos; store-photo performance may be lower.

## Required evidence before a production accuracy claim

1. Collect independently photographed supported and unsupported store images.
2. Keep every physical fruit or tomato specimen in only one split.
3. Freeze thresholds on validation data and evaluate the untouched test set once.
4. Review every false-fresh, false-rotten, uncertain, and unsupported outcome.
5. Measure performance by phone, lighting, background, store, and produce type.
6. Complete a controlled human-reviewed pilot and document corrections.

## Reproducibility artifacts

- Prepared manifest: `evaluation/manifests/expanded_12_class_v1.json`
- Training and conversion: `training/expanded_dataset.py`, `training/imagenet_densenet.py`
- Head evaluation: `evaluation/reports/expanded_12_class/imagenet_head_evaluation_report.json`
- Gate calibration: `evaluation/reports/expanded_12_class/open_set_calibration.json`
- Gated report and plots: `evaluation/reports/expanded_12_class/gated_test/`
- WSL2 GPU setup: `scripts/setup_wsl_tensorflow_gpu.sh`
- Runtime association: `artifacts/model_manifest.json`
