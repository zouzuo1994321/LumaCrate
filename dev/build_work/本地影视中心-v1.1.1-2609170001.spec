# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['Z:/【01】自研软件/【26-19】本地影视中心/src/main.py'],
    pathex=[],
    binaries=[],
    datas=[('Z:/【01】自研软件/【26-19】本地影视中心/src/style.qss', '.')],
    hiddenimports=['PySide6.QtXml'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='本地影视中心-v1.1.1-2609170001',
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
)
