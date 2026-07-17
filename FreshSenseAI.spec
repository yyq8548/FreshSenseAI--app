# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

tensorflow_binaries = collect_dynamic_libs("tensorflow")

a = Analysis(
    ["desktop_app.py"],
    pathex=[],
    binaries=tensorflow_binaries,
    datas=[
        ("VERSION", "."),
        ("models/densenet201.h5", "models"),
        ("models/open_set_gate.npz", "models"),
        ("models/embedding_cache", "models/embedding_cache"),
        ("artifacts/model_manifest.json", "artifacts"),
        ("evaluation/manifests/legacy_grouped_v1.json", "evaluation/manifests"),
        ("evaluation/reports/current_model/evaluation_report.json", "evaluation/reports/current_model"),
        ("evaluation/reports/gate_calibration_final.json", "evaluation/reports"),
        ("data/fruit_catalog.json", "data"),
        ("data/food_knowledge_base.json", "data"),
    ],
    hiddenimports=[
        "h5py",
        "keras",
        "tensorflow",
        "onnxruntime.capi._pybind_state",
        "tokenizers",
        *collect_submodules("fastembed"),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "pytest", "streamlit"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FreshSenseAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    version="work/windows_version_info.txt",
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FreshSenseAI",
)
