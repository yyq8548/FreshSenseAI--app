# Development Log — Versioned REST API

## Milestone

Added a fully functioning FastAPI layer around the existing FreshSense agent
without duplicating inference or changing the desktop workflow.

## Endpoints

- `GET /api/v1/health` reports the loaded model, active semantic or keyword
  retrieval mode, embedding model, supported fruits, and image-retention policy.
- `POST /api/v1/analyze` accepts one multipart image and returns a typed result
  containing prediction, confidence, image quality, scene analysis, retrieved
  knowledge and scores, warnings, reasoning, recommendation, and safety notice.
- `/openapi.json`, `/docs`, and `/redoc` expose the generated API contract and
  interactive documentation.

## Runtime architecture

`api.main:app` is the ASGI entry point. The application lifespan validates the
model, fruit catalog, and knowledge base before constructing one shared
`FruitScannerAgent`. Requests reuse that same vision model and semantic
retriever. An asynchronous lock serializes access to the stateful agent, while
the CPU-bound analysis runs outside the event loop in a worker thread.

The application factory accepts an agent factory and explicit upload limits.
This keeps unit tests lightweight and makes the production startup path fail
closed when required runtime assets are unavailable.

## Upload validation and privacy

The endpoint:

- accepts only JPEG, PNG, and WebP MIME types;
- verifies that the detected image format matches the declared MIME type;
- rejects empty and undecodable files;
- enforces encoded-byte and decoded-pixel limits;
- converts EXIF orientation and normalizes the image to RGB;
- never copies the photo or filename into application storage; and
- closes both the multipart upload and decoded image after each request.

The multipart parser can use short-lived operating-system temporary storage for
larger uploads. Closing the upload releases that temporary resource before
inference. No photo or filename is written to scan history, logs, the repository,
or permanent API storage.

## Safety behavior

The public serializer omits raw probability vectors and internal trace messages.
When the confidence gate returns `uncertain_input`, the API withholds the
tentative class and confidence just like the desktop interface. Unexpected
analysis exceptions return a generic structured error without exposing internal
paths, exception text, or model details.

## Configuration

- `FRESHSENSE_API_MAX_UPLOAD_BYTES` defaults to 10 MiB.
- `FRESHSENSE_API_MAX_IMAGE_PIXELS` defaults to 25 million pixels.

Run one worker per model instance:

``` powershell
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --workers 1
```

## Validation

The API tests cover shared lifespan initialization, both retrieval health modes,
successful typed analysis, uncertain-result redaction, invalid and empty files,
unsupported and mismatched media types, byte and pixel limits, safe internal
errors, upload disposal, privacy fields, and the generated OpenAPI schema.
