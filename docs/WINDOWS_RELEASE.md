# FreshSense AI Windows release guide

FreshSense is distributed as a self-contained, per-user Windows x64
application. End users do not install Python, a virtual environment, or Docker.

## Release outputs

The release pipeline creates three files in the workspace-level `outputs`
directory:

- `FreshSenseAI-Setup-<version>.exe` — the installer;
- `FreshSenseAI-Setup-<version>.exe.sha256` — its SHA-256 checksum; and
- `FreshSenseAI-Release-<version>.json` — version, architecture, hash,
  timestamp, and signature status.

The installer is per-user and does not normally require administrator access.
It installs under `%LOCALAPPDATA%\Programs\FreshSense AI`, creates a Start Menu
shortcut, offers an optional Desktop shortcut, supports upgrades using a stable
application ID, and registers an uninstaller.

For public-beta builds, the release manifest also records the release channel,
default photo-retention behavior, safety notice, signature status, and known
limitations. An unsigned beta may trigger a Windows unrecognized-publisher
warning even when its SHA-256 checksum is correct.

## Build prerequisites

1. Windows 10 or Windows 11 on x64 hardware.
2. Python 3.11 and the dependencies in `requirements-build.txt`.
3. Inno Setup 6. Install it with:

   ``` powershell
   winget install --id JRSoftware.InnoSetup
   ```

4. The trained model at `models\densenet201.h5`.
5. The prepared local embedding cache under `models\embedding_cache`.

The model and embedding cache are intentionally ignored by Git. They are
validated locally and bundled into the installed application.

## Build a release

From the repository root:

``` powershell
pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

The default build:

1. runs the full automated test suite;
2. validates the version, model, fruit catalog, knowledge base, ONNX embedding
   model, and tokenizer;
3. generates Windows executable metadata from the root `VERSION` file;
4. creates the self-contained application directory with PyInstaller;
5. verifies the executable's product version;
6. creates the versioned installer with Inno Setup; and
7. generates and verifies the checksum and release manifest.

Run an isolated install/uninstall smoke test on the current Windows account:

``` powershell
powershell -ExecutionPolicy Bypass -File scripts\smoke_windows_installer.ps1
```

This uses a dedicated directory under `%LOCALAPPDATA%`, disables shortcut
creation, validates the installed executable, vision model, ONNX embedding
model, and version metadata, then runs the real uninstaller and confirms the
directory is removed. It does not replace a pre-existing registered FreshSense
installation.

If Inno Setup is installed in a nonstandard directory, set `ISCC_PATH` to its
`ISCC.exe`. Use `-PrepareEmbeddingModel` only when the local embedding cache has
not already been prepared. `-SkipInstaller` creates a developer application
folder and deliberately does not create release artifacts.

## Change the version

`VERSION` is the single release-version source. It must contain three numeric
components, such as `0.2.0`. The build injects it into:

- the application window title;
- the Windows executable metadata;
- Add or Remove Programs;
- the installer filename; and
- the release manifest.

Do not edit the version directly in the Inno Setup file or PyInstaller spec.

## Clean-machine acceptance checklist

Before publishing, test the installer on a clean Windows user account or VM:

1. Verify the SHA-256 checksum.
2. Install without administrator privileges.
3. Launch from the Start Menu and optional Desktop shortcut.
4. Confirm the model finishes loading without a terminal window.
5. Analyze reviewed apple, banana, and orange images.
6. Confirm semantic retrieval is active in the analysis details.
7. Confirm safety warnings and uncertain-photo behavior.
8. Create, export, clear, and recreate local scan history.
9. Install the same version again and confirm repair/upgrade behavior.
10. Uninstall and confirm the program files and shortcuts are removed.

The automated current-account smoke above is not a substitute for a clean OS.
Windows Sandbox is a good disposable test environment on Windows Pro,
Enterprise, and Education, but Microsoft does not provide it on Windows Home.
Use a clean Windows Pro Sandbox, disposable VM, or separate test PC for the
final checklist.

Scan history is stored separately under `%LOCALAPPDATA%\FreshSense` and is not
uploaded. Decide explicitly whether an uninstall release should preserve or
remove that user-created history; the current installer preserves it.

## Publish to GitHub

Create a GitHub Release matching the `VERSION` value and upload all three
release outputs. Include the supported Windows architecture, safety limitation,
non-retention behavior, checksum-verification command, and known issues in the
release notes.

Users can verify the installer with:

``` powershell
Get-FileHash .\FreshSenseAI-Setup-0.5.0.exe -Algorithm SHA256
```

Compare the result with the `.sha256` file or release manifest.

## Code signing

The release pipeline can sign both the packaged application and installer with
a trusted Authenticode certificate installed in the Current User or Local
Machine certificate store. Configure the certificate thumbprint and an HTTP
timestamp service, then require a trusted signature:

``` powershell
$env:FRESHSENSE_SIGNING_CERTIFICATE_THUMBPRINT = "YOUR_CERTIFICATE_THUMBPRINT"
$env:FRESHSENSE_TIMESTAMP_SERVER = "http://YOUR_CA_TIMESTAMP_SERVER"
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 `
  -RequireSignedRelease
```

The signing script fails closed if the certificate is missing, expired, lacks
the code-signing enhanced-key usage, has no accessible private key, does not
produce a trusted signature, or cannot obtain a timestamp. The final verifier
also rejects an unsigned release when `-RequireSignedRelease` is used.

Never store a PFX file or password in the repository. Import the certificate
through the certificate provider's secure process or use a managed signing
service. Microsoft Artifact Signing is one managed option; it requires an Azure
account, identity validation, and a public-trust certificate profile.

Without a trusted certificate, the verifier records `NotSigned` and Windows may
display an unrecognized-publisher warning. A checksum detects changes but does
not establish publisher identity.
