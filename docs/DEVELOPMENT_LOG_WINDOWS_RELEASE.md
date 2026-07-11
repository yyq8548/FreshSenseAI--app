# Development log: Windows-first release pipeline

Date: 2026-07-10

## Decision

FreshSense no longer requires or documents Docker. The native Windows desktop
application is the primary product, while the FastAPI interface remains an
optional developer integration that can run directly from Python.

## Implemented

- Removed the Dockerfile, Compose configuration, container CI workflow,
  container scripts, container tests, and Docker deployment documentation.
- Preserved reusable API authentication, request validation, rate limiting,
  security headers, request IDs, structured logs, health, and metrics.
- Added a central `VERSION` file and displayed it in the desktop window.
- Generated Windows executable version resources from the central version.
- Added fail-closed validation for the trained model, fruit catalog, food
  knowledge base, local ONNX embedding model, and tokenizer.
- Updated the Inno Setup definition with dynamic versioning, publisher/support
  metadata, stable upgrade identity, x64 installation mode, Start Menu and
  optional Desktop shortcuts, and uninstall metadata.
- Rebuilt the PowerShell release process to run tests, validate assets, package
  the application, verify executable metadata, create the installer, generate a
  SHA-256 checksum, create a JSON manifest, and verify the outputs.
- Added explicit reporting for unsigned installers so code signing can be added
  without hiding the current trust limitation.
- Added fail-closed certificate-store Authenticode signing for the packaged
  application and installer, mandatory timestamping, and signed-release mode.
- Added an isolated per-user installation, bundled-asset, version, and uninstall
  smoke test that refuses to overwrite an existing FreshSense registration.
- Added automated tests for versioning, release validation, packaging metadata,
  installer configuration, checksum verification, and Docker removal.

## Release boundary

The pipeline produces a technically verifiable Windows installer. A trusted
public release still needs an Authenticode code-signing certificate, timestamp
service, clean-machine acceptance test, and explicit GitHub Release approval.

## Verification evidence

- The packaged 0.2.0 application launched with bundled assets and completed
  real-model analysis with local semantic retrieval.
- The isolated test-only installer used a separate application ID, installed
  without production shortcuts, validated the executable version, trained
  model, and ONNX embedding model, then uninstalled successfully.
- The production installer checksum and manifest verification passed.
- The host runs Windows Home, where Windows Sandbox is not available, so a
  disposable clean-OS test still requires another Windows PC or VM.
- No trusted code-signing certificate exists in the Current User or Local
  Machine certificate stores. The signed-release path is implemented but cannot
  produce a public-trust signature until a certificate is provisioned.
