# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — GitHub App Manager
# Usage: pyinstaller GitHubAppManager.spec   (from repo root)
# SPECPATH is injected by PyInstaller at eval-time — do not use __file__

from pathlib import Path

ROOT = Path(SPECPATH).resolve()
ICO  = ROOT / "icons" / "github_app_manager.ico"
ico_arg    = str(ICO) if ICO.is_file() else None
icon_datas = [(str(ICO), "icons")] if ICO.is_file() else []

block_cipher = None

a = Analysis(
    ["github_app_manager.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=icon_datas,
    hiddenimports=[
        "requests",
        "urllib3",
        "urllib3.util.retry",
        "certifi",
        "charset_normalizer",
        "idna",
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
        "win32com.client",
        "win32com",
        "pywintypes",
        "keyring",
        "keyring.backends",
        "keyring.backends.Windows",
        "gab",
        "gab.credentials",
        "gab.git_clone",
        "gab.zip_safe",
    ],
    hookspath=[],
    hooksconfig={"requests": {"collect-all": True}},
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "pandas", "PIL", "scipy", "test"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ico_arg,
)
