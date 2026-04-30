# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for GitHub App Manager v4.0
# Usage:  pyinstaller GitHubAppManager.spec
#         (or click "Build .exe" inside the app)

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ["github_app_manager.py"],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=[],
    hiddenimports=[
        "requests",
        "urllib3",
        "urllib3.util.retry",
        "certifi",
        "charset_normalizer",
        "charset_normalizer.md__mypyc",
        "idna",
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
        "win32com.client",
        "win32com",
        "pywintypes",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "pandas", "PIL", "scipy", "test"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Pull in all of requests' data (charset_normalizer codec files etc.)
from PyInstaller.utils.hooks import collect_all
datas_r, binaries_r, hiddenimports_r = collect_all("requests")
a.datas    += datas_r
a.binaries += binaries_r
a.hiddenimports += hiddenimports_r

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="GitHubAppManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # windowless on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
