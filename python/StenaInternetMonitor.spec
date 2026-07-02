# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# No more curl binaries needed with the requests library approach
binaries = []

# Add any data files
datas = [
    (os.path.abspath('icon.ico'), '.'),  # Include the icon file
    ('profiles.json', '.') if os.path.exists('profiles.json') else None,
    ('fonts/StenaSans-Medium.ttf', 'fonts'),  # Bundled UI font (regular)
    ('fonts/StenaSans-Bold.ttf', 'fonts'),    # Bundled UI font (bold)
]
# Remove None values that might be in the datas list
datas = [x for x in datas if x is not None]

# Make sure to include certificates for SSL verification
# This helps the requests library with HTTPS connections
cert_datas = collect_data_files('certifi')
datas.extend(cert_datas)

# Add hidden imports for requests and urllib3
hidden_imports = [
    'requests',
    'urllib3',
    'json',
    'certifi'
]
hidden_imports.extend(collect_submodules('urllib3'))
hidden_imports.extend(collect_submodules('requests'))

a = Analysis(
    ['stena_internet_gui.py'],  # Your main script
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='SLIM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True if you want to see error messages during development
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.abspath('icon.ico'),
)