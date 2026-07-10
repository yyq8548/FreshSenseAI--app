# Development Log: Configuration-Driven Fruit Support

**Date:** July 10, 2026

## Goal

Make future fruit additions a data and model update instead of a repeated
application-code rewrite.

## Completed

- Added a versioned and validated `data/fruit_catalog.json` schema.
- Preserved the existing DenseNet model's six-class output order exactly.
- Moved fruit identity, freshness state, display names, shelf-life estimates,
  and storage advice into the catalog.
- Updated vision inference, local knowledge retrieval, rule-based reasoning,
  optional LLM payloads, recommendation generation, and desktop presentation
  to use catalog metadata.
- Added startup checks for catalog structure and knowledge coverage.
- Updated PyInstaller packaging so the catalog is included in desktop builds.
- Removed the fake prediction fallback from the legacy inference wrapper; all
  inference paths now fail closed.
- Added regression tests showing that a new fruit can flow through inference,
  retrieval, reasoning, recommendations, and presentation without fruit-specific
  code changes.

## Adding a Fruit

Adding a fruit now requires four coordinated assets:

1. A retrained model with two additional outputs.
2. Two ordered catalog class entries: fresh and rotten.
3. One fruit metadata entry with reviewed shelf-life and storage guidance.
4. At least one reviewed knowledge-base document for the fruit.

The model output order and the catalog `classes` order must match exactly.

## Safety Behavior

FreshSense rejects invalid or incomplete catalogs, mismatched model output
counts, and missing fruit knowledge. It never substitutes a fabricated model
result when the model cannot load.
