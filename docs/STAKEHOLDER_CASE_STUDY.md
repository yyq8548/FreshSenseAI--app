# FreshSense stakeholder case study

## Executive summary

FreshSense is a Windows-first AI prototype that helps a person screen a clear
photo of one apple, banana, or orange for **visible patterns associated with
fresh or rotten produce**. It combines computer vision, an explicit
supported-input gate, confidence-based abstention, curated knowledge
retrieval, and plain-language guidance in a desktop application and REST API.

FreshSense is decision support, not a food-safety test. It cannot detect odor,
texture, contamination, internal spoilage, or every surface hazard. The user
retains responsibility for inspecting the fruit and deciding whether to
consume it.

## Business problem and user workflow

### Intended prototype users

- A household user making a quick visual screening decision.
- A produce-handling worker performing an initial triage before human review.
- A business stakeholder evaluating whether visual AI could reduce repetitive
  first-pass inspection work.

### Existing workflow

1. A person visually inspects fruit.
2. The person relies on experience to interpret color, spots, mold, and damage.
3. Unclear cases may be inconsistently categorized or discarded.
4. Guidance about storage and shelf life must be found separately.

### FreshSense-assisted workflow

1. The user supplies one clear photograph.
2. The application checks image quality and scene suitability.
3. A supported-input gate asks whether the image clearly resembles one
   supported fruit type.
4. The classifier proposes a fruit/freshness class only after that gate passes.
5. Confidence and margin checks can withhold the result as uncertain.
6. Accepted predictions receive curated storage and safety guidance.
7. The user reviews the explanation, warnings, and physical fruit before acting.

## Value hypothesis

FreshSense could create value by making first-pass visual screening more
consistent, returning an answer quickly, and presenting limitations alongside
the result. The prototype also demonstrates a reusable AI workflow: validate
the input, make a bounded prediction, abstain when evidence is weak, retrieve
reviewed knowledge, and preserve human oversight.

The prototype has not yet demonstrated financial savings or field accuracy.
Those claims require an independent benchmark and a controlled user pilot.

## Success criteria

The following measures are defined before the limited pilot:

| Area | Measure | Pilot target |
|---|---|---:|
| Safety | Rotten fruit incorrectly returned as fresh | <= 2% of reviewed supported cases |
| Scope control | Unsupported-image false acceptance | <= 5% |
| Coverage | Clear supported photos receiving a result | >= 80% |
| Usability | Median reviewer rating (1-5) | >= 4 |
| Comprehension | Users who understand that the output is visual guidance only | >= 90% |
| Performance | Median CPU analysis time | <= 3 seconds on the pilot machine |
| Privacy | Uploaded photographs retained by default | 0 |

These are prototype acceptance criteria, not guarantees of food safety.

## Stakeholder validation plan

1. Recruit at least five reviewers and collect at least 100 independently
   photographed cases across supported and unsupported inputs.
2. Keep all photographs from one physical fruit/capture session in one split.
3. Have a reviewer record the visible outcome independently of the model.
4. Record task duration, result comprehension, warning usefulness, willingness
   to use the tool again, and a 1-5 usability score.
5. Review every false-fresh result and every high-confidence disagreement.
6. Decide whether to revise the model, thresholds, interface, or use case before
   any wider rollout.

The SQLite pilot store records only anonymized identifiers and review metadata;
it does not retain photographs or original filenames.

## Evidence already available

- A packaged Windows desktop application and versioned FastAPI service.
- Six-class DenseNet201 inference for fresh/rotten apple, banana, and orange.
- A required feature-based supported-input gate.
- Semantic retrieval with a transparent keyword fallback.
- Structured evaluation for precision, recall, F1, calibration, abstention,
  unsupported false acceptance, subgroup metrics, and CPU latency.
- A model card, cryptographic artifact manifest, release validation, and more
  than 100 automated tests.

## Known evidence gap

The legacy dataset contains 13,600 files but only 1,512 reconstructed source
groups, with complete source-group overlap between the old train and test
collections. The grouped evaluation verifies software behavior, but the
current model had already seen those source groups during legacy training.
Therefore, the existing high accuracy is **not** an independent real-world
accuracy claim.

## Decision and next step

FreshSense is suitable as a controlled AI MVP and portfolio demonstration. It
is not ready for a public food-safety or automated-disposal workflow. The next
decision point occurs after the independent phone-photo benchmark, Grad-CAM
review, MobileNetV2 comparison, and stakeholder pilot meet the criteria above.
