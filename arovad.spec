# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = [
    'arova', 'arova.core', 'arova.core.voice', 'arova.core.cognition', 
    'arova.core.ambience', 'arova.core.automation', 'arova.core.platform', 
    'arova.daemon', 'arova.core.cognition.workspace_manager', 
    'arova.core.projection.projector', 'arova.core.providers',
    'arova.core.providers.implementations', 'arova.core.providers.network_utils',
    'arova.core.config.discovery', 'arova.core.config.manager',
    'arova.core.models', 'arova.core.models.adapters', 'arova.core.models.registry',
    'numpy', 'scipy', 'sklearn', 'websockets',
    'edge_tts', 'sounddevice', '_cffi_backend', 'psutil', 'PIL', 'yaml', 'pydantic',
    'requests', 'urllib3', 'certifi', 'aiohttp', 'ssl'
]

for pkg in ['arova', 'openwakeword', 'sounddevice', 'edge_tts', 'psutil', 'PIL', 'websockets', 'pydantic', 'requests', 'certifi', 'aiohttp', 'urllib3']:
    try:
        tmp_ret = collect_all(pkg)
        datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
    except Exception:
        pass


a = Analysis(
    ['arova/daemon/main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name='arovad',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='arovad',
)

