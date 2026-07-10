# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_dynamic_libs

tensorflow_binaries = collect_dynamic_libs("tensorflow")

a = Analysis(
    ["desktop_app.py"],
    pathex=[],
    binaries=tensorflow_binaries,
    datas=[
        ("models/densenet201.h5", "models"),
        ("data/food_knowledge_base.json", "data"),
    ],
    hiddenimports=["h5py", "keras", "tensorflow"],
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
