# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['run.py'],
    pathex=['.'],
    binaries=[], 
    datas=[
        ('field_manual_icon.png', '.')
    ],
    hiddenimports=['markdown', 'Pygments'],
    hookspath=[],
    runtime_hooks=['qt_runtime_hook.py'],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SecOps Field Manual', 
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
    icon='field_manual_icon.png'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SecOps Field Manual',
)

# For macOS, create the .app bundle
app = BUNDLE(
    coll,
    name='SecOps Field Manual.app',
    icon='field_manual_icon.png',
    bundle_identifier=None,
)
