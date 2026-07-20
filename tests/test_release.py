from pathlib import Path

import pytest

from scripts.release_tools import (
    MIN_MODEL_BYTES,
    ReleaseValidationError,
    read_release_version,
    render_windows_version_info,
    validate_release_assets,
    windows_version_tuple,
)
from utils.version import APP_VERSION, read_app_version


ROOT = Path(__file__).resolve().parents[1]


def _complete_release_assets(tmp_path: Path) -> dict[str, Path]:
    model = tmp_path / "densenet201.h5"
    model.write_bytes(b"m" * MIN_MODEL_BYTES)
    embeddings = tmp_path / "embedding_cache"
    embeddings.mkdir()
    (embeddings / "model_optimized.onnx").write_bytes(b"onnx")
    (embeddings / "tokenizer.json").write_text("{}", encoding="utf-8")
    return {
        "version_path": ROOT / "VERSION",
        "model_path": model,
        "embedding_cache": embeddings,
        "catalog_path": ROOT / "data" / "fruit_catalog.json",
        "knowledge_base_path": ROOT / "data" / "food_knowledge_base.json",
    }


def test_version_is_centralized_and_valid():
    version = read_release_version(ROOT / "VERSION")

    assert version == "0.6.0"
    assert APP_VERSION == version
    assert read_app_version(ROOT / "VERSION") == version
    assert windows_version_tuple(version) == (0, 6, 0, 0)


def test_invalid_or_unavailable_runtime_version_uses_safe_label(tmp_path):
    invalid = tmp_path / "VERSION"
    invalid.write_text("version two", encoding="utf-8")

    assert read_app_version(invalid) == "development"
    assert read_app_version(tmp_path / "missing") == "development"


def test_windows_version_metadata_matches_release_version():
    metadata = render_windows_version_info("0.5.1")

    assert "filevers=(0, 5, 1, 0)" in metadata
    assert "StringStruct('FileVersion', '0.5.1')" in metadata
    assert "StringStruct('ProductVersion', '0.5.1')" in metadata
    assert "FreshSenseAI.exe" in metadata


def test_release_asset_validation_accepts_complete_local_bundle(tmp_path):
    assets = _complete_release_assets(tmp_path)

    assert validate_release_assets(**assets) == "0.6.0"


def test_release_asset_validation_fails_closed_without_embedding_model(tmp_path):
    assets = _complete_release_assets(tmp_path)
    (assets["embedding_cache"] / "model_optimized.onnx").unlink()

    with pytest.raises(ReleaseValidationError, match="ONNX"):
        validate_release_assets(**assets)


def test_release_asset_validation_rejects_placeholder_vision_model(tmp_path):
    assets = _complete_release_assets(tmp_path)
    assets["model_path"].write_bytes(b"placeholder")

    with pytest.raises(ReleaseValidationError, match="unexpectedly small"):
        validate_release_assets(**assets)


def test_pyinstaller_and_installer_use_versioned_release_inputs():
    spec = (ROOT / "FreshSenseAI.spec").read_text(encoding="utf-8")
    installer = (ROOT / "installer" / "FreshSenseAI.iss").read_text(encoding="utf-8")

    assert '("VERSION", ".")' in spec
    assert 'version="work/windows_version_info.txt"' in spec
    assert '("models/densenet201.h5", "models")' in spec
    assert '("models/open_set_gate.npz", "models")' in spec
    assert '("artifacts/model_manifest.json", "artifacts")' in spec
    assert "#ifndef MyAppVersion" in installer
    assert "#ifndef MyAppSourceDir" in installer
    assert '#define MyOutputBaseFilename "FreshSenseAI-Setup-" + MyAppVersion' in installer
    assert "OutputBaseFilename={#MyOutputBaseFilename}" in installer
    assert "PrivilegesRequired=lowest" in installer
    assert "ArchitecturesInstallIn64BitMode=x64compatible" in installer
    assert "UninstallDisplayName={#MyAppName} {#MyAppVersion}" in installer
    assert "desktopicon" in installer


def test_windows_build_pipeline_tests_packages_hashes_and_verifies():
    build_script = (ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")
    finalize_script = (ROOT / "scripts" / "finalize_windows_release.ps1").read_text(
        encoding="utf-8"
    )
    verify_script = (ROOT / "scripts" / "verify_windows_release.ps1").read_text(
        encoding="utf-8"
    )
    signing_script = (ROOT / "scripts" / "sign_windows_artifact.ps1").read_text(
        encoding="utf-8"
    )
    installer_smoke = (ROOT / "scripts" / "smoke_windows_installer.ps1").read_text(
        encoding="utf-8"
    )

    assert '"-m", "pytest"' in build_script
    assert '"-m", "PyInstaller"' in build_script
    assert "release_tools.py" in build_script
    assert "Resolve-InnoCompiler" in build_script
    assert '"/O$outputDir"' in build_script
    assert "FreshSenseAI-release-$version" in build_script
    assert "Refusing to use an unsafe release staging path" in build_script
    assert "finalize_windows_release.ps1" in build_script
    assert "verify_windows_release.ps1" in finalize_script
    assert "Get-FileHash" in finalize_script
    assert "Get-AuthenticodeSignature" in finalize_script
    assert "ConvertTo-Json" in finalize_script
    assert 'release_channel = "public-beta"' in finalize_script
    assert 'photo_retention = "none-by-default"' in finalize_script
    assert "known_limitations" in finalize_script
    assert "Get-FileHash" in verify_script
    assert "ConvertFrom-Json" in verify_script
    assert "RequireSignedRelease" in build_script
    assert "SigningCertificateThumbprint" in build_script
    assert "sign_windows_artifact.ps1" in build_script
    assert "Set-AuthenticodeSignature" in signing_script
    assert "1.3.6.1.5.5.7.3.3" in signing_script
    assert "TimestampServer" in signing_script
    assert "TimeStamperCertificate" in signing_script
    assert "FreshSenseAI-ReleaseSmoke-$Version" in installer_smoke
    assert "FreshSense AI Release Smoke" in installer_smoke
    assert "C73AA09C-D776-466D-9AE7-E3321F767D3F" in installer_smoke
    assert "MyCompression=zip/1" in installer_smoke
    assert "MySkipIcons=1" in installer_smoke
    assert "Start-Process" in installer_smoke
    assert "-Wait -PassThru -WindowStyle Hidden" in installer_smoke
    assert "/NOICONS" in installer_smoke
    assert "unins000.exe" in installer_smoke
    assert "embedding_cache" in installer_smoke

    build_requirements = (ROOT / "requirements-build.txt").read_text(encoding="utf-8")
    assert "pyinstaller==6.14.2" in build_requirements
    assert "pytest==8.4.1" in build_requirements
    assert "fastapi==0.139.0" in build_requirements


def test_docker_artifacts_are_not_part_of_the_windows_first_project():
    docker_paths = (
        "Dockerfile",
        ".dockerignore",
        "docker-compose.staging.yml",
        ".env.staging.example",
        ".github/workflows/container.yml",
        "scripts/smoke_staging_container.ps1",
    )

    assert all(not (ROOT / relative).exists() for relative in docker_paths)
